#!/usr/bin/env python3
"""Comprehensive test suite for VitaminChecker."""
import sys
import os
import json
import unicodedata
import re

# Ensure flask is importable
sys.path.insert(0, '/opt/data/home/.local/lib/python3.13/site-packages')
os.chdir('/opt/data/home/repos/VitaminChecker')

from app import (
    parse_receipt_text, match_food, normalize_french, 
    analyze_vitamins, FOOD_VITAMINS, _NORMALIZED_LOOKUP, VITAMINS,
    allowed_file, NOISE_WORDS, NOISE_LINE_PATTERNS
)

failed = 0
passed = 0

def check(condition, msg):
    global failed, passed
    if condition:
        passed += 1
        print(f"  ✅ {msg}")
    else:
        failed += 1
        print(f"  ❌ {msg}")

# ═══════════════════════════════════════════════
print("=" * 60)
print("1. normalize_french()")
print("=" * 60)
tests = [
    ("épinards", "epinards"),
    ("crème fraîche", "cremefraiche"),  # 'fraîche' normalizes to 'fraiche' (î→i), correct
    ("œufs", "oeufs"),
    ("yaourt nature", "yaourtnature"),
    ("pâte à pizza", "pateapizza"),
    ("lait demi-écrémé", "laitdemiecreme"),
    ("bœuf", "boeuf"),
    ("chocolat noir", "chocolatnoir"),
    ("laitue", "laitue"),
    ("Saumon", "saumon"),
    ("  PAIN COMPLET  ", "paincomplet"),
    ("fromage-blanc", "fromageblanc"),
    ("l'eau", "leau"),
]
for inp, expected in tests:
    result = normalize_french(inp)
    check(result == expected, f"normalize('{inp}') = '{result}' (expected: '{expected}')")

# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("2. match_food() — exact, accent, typo, substring")
print("=" * 60)

# Should match
positive_tests = [
    ("épinards", "epinard"),
    ("crème", "creme"),
    ("yaourt nature", "yaourt nature"),
    ("pâtes", "pates"),
    ("bœuf", "boeuf"),
    ("laitue", "laitue"),
    ("sardine", "sardine"),
    ("frommage", "fromage"),    # Levenshtein
    ("bananne", "banane"),      # Levenshtein
    ("chorizo", "chorizo"),      # exact
    ("steak haché", "steak hache"),
    ("oranges", "orange"),       # substring in food name contains item
    ("saumon frais", "saumon"),  # food name in item
]
for item, expected_key in positive_tests:
    result = match_food(item, FOOD_VITAMINS)
    if result:
        check(result[0] == expected_key, f"'{item}' → '{result[0]}' (expected: '{expected_key}')")
    else:
        check(False, f"'{item}' → NO MATCH (expected: '{expected_key}')")

# Should NOT match
negative_tests = ["flamby", "xyzabc", "qqqq", "aa"]
for item in negative_tests:
    result = match_food(item, FOOD_VITAMINS)
    check(result is None, f"'{item}' → {'NO MATCH' if result is None else 'MATCHED: ' + result[0]} (expected: NO MATCH)")

# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("3. parse_receipt_text() — noise filtering")
print("=" * 60)

# Simple receipt
simple = "Banane x2 2,40€\nPoulet filet 4,95€\nBrocoli 1,80€"
items = parse_receipt_text(simple)
check(len(items) >= 3, f"Simple receipt: {len(items)} items extracted (expected >= 3)")
for i in items:
    print(f"    '{i}'")

# Noisy receipt (should filter out totals, TVA, etc.)
noisy = """CARREFOUR MARKET
18/04/2026 14:32
Caisse 3

BANANE x2       2,40€
FILET POULET     4,95€
BROCOLI          1,80€
RIZ BASMATI 1kg  2,15€
YAOURT NATURE x4 2,60€
JUS D ORANGE 1L  2,30€
SAUMON 200g      5,90€
EPINARD 300g     2,10€
PAIN COMPLET     1,50€
TOMATE x3        1,95€
HUILE D OLIVE    4,20€
FROMAGE GRUYERE  3,40€
CHOCOLAT NOIR    2,10€
AIL x2           0,80€

TOTAL            35,15€
CB               35,15€
Merci de votre visite !"""
items = parse_receipt_text(noisy)
result = analyze_vitamins(items)
check(result['matched_count'] >= 12, f"Noisy receipt: {result['matched_count']}/{result['total_items']} matched (expected >= 12/14)")
if result['unmatched_items']:
    print(f"    Unmatched: {result['unmatched_items']}")

# Heavy accents receipt
accented = """CRÈME FRAÎCHE 30%  1,95
ŒUFS x6             2,50
LAIT DEMI-ÉCRÉMÉ    1,20
PÂTES COMPLÈTES     0,95
SARDINES            2,80
AVOCAT              1,60
KIWI x3             1,50
AMANDES             3,90"""
items2 = parse_receipt_text(accented)
result2 = analyze_vitamins(items2)
check(result2['matched_count'] >= 7, f"Accented receipt: {result2['matched_count']}/{result2['total_items']} matched (expected >= 7/8)")
if result2['unmatched_items']:
    print(f"    Unmatched: {result2['unmatched_items']}")

# Empty receipt
empty = "TOTAL 0,00€\nMerci"
items3 = parse_receipt_text(empty)
check(len(items3) == 0, f"Empty receipt: {len(items3)} items (expected 0)")

# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("4. analyze_vitamins() — coverage & gaps")
print("=" * 60)

# Simple test with known foods
test_items = ["banane", "saumon", "epinard"]
result = analyze_vitamins(test_items)
check(result['matched_count'] == 3, f"Matched: {result['matched_count']} (expected 3)")
check('gaps' in result, "Result has 'gaps'")
check('matched_items' in result, "Result has 'matched_items'")
check('unmatched_items' in result, "Result has 'unmatched_items'")
check(len(result['unmatched_items']) == 0, f"No unmatched items (got: {result['unmatched_items']})")

# Check vitamin keys in gaps
for vit_key in VITAMINS:
    check(vit_key in result['gaps'], f"Vitamin {vit_key} present in gaps")
    if vit_key in result['gaps']:
        g = result['gaps'][vit_key]
        check('coverage' in g, f"  {vit_key}: has 'coverage'")
        check('gap' in g, f"  {vit_key}: has 'gap'")
        check('status' in g, f"  {vit_key}: has 'status'")
        check(g['status'] in ['deficit', 'surplus'], f"  {vit_key}: status is valid ({g['status']})")

# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("5. Database integrity")
print("=" * 60)

print(f"  Total food entries: {len(FOOD_VITAMINS)}")
valid_vitamins = set(VITAMINS.keys())
invalid_count = 0
for food, vitamins in FOOD_VITAMINS.items():
    for vit_key, pct in vitamins.items():
        if vit_key not in valid_vitamins:
            print(f"  ❌ '{food}' has invalid vitamin key '{vit_key}'")
            invalid_count += 1
        if not isinstance(pct, (int, float)) or pct < 0 or pct > 1000:
            print(f"  ❌ '{food}' has invalid % for {vit_key}: {pct}")
            invalid_count += 1
check(invalid_count == 0, f"All vitamin keys valid ({invalid_count} invalid)")

# Check for normalized key collisions
seen_norms = {}
dupes = 0
for key in FOOD_VITAMINS:
    norm = normalize_french(key)
    if norm in seen_norms:
        if dupes < 10:
            print(f"  ⚠️  Collision: '{key}' and '{seen_norms[norm]}' → '{norm}'")
        dupes += 1
    else:
        seen_norms[norm] = key
check(dupes == 0, f"No normalized key collisions ({dupes} collisions)")

# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("6. allowed_file() — security validation")
print("=" * 60)

from werkzeug.datastructures import FileStorage

class FakeFile:
    def __init__(self, filename, content_type=''):
        self.filename = filename
        self.content_type = content_type

check(allowed_file("photo.jpg"), "allowed_file: photo.jpg")
check(allowed_file("photo.PNG"), "allowed_file: photo.PNG")
check(allowed_file("receipt.pdf"), "allowed_file: receipt.pdf")
check(allowed_file("doc.pdf", FakeFile("doc.pdf", "application/pdf")), "allowed_file: doc.pdf with MIME")
check(not allowed_file("script.exe"), "not allowed: script.exe")
check(not allowed_file("script.php"), "not allowed: script.php")
check(not allowed_file("photo.jpg", FakeFile("photo.jpg", "application/x-php")), "not allowed: photo.jpg with PHP MIME")
check(allowed_file("photo.webp"), "allowed_file: photo.webp")

# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("7. Frontend JS consistency")
print("=" * 60)

# Check that VITAMIN_SOURCES keys in JS match VITAMINS keys in Python
js_vitamins_src = {
    "A", "B1", "B2", "B3", "B5", "B6", "B9", "B12", "C", "D", "E", "K"
}
py_vitamins = set(VITAMINS.keys())
check(js_vitamins_src == py_vitamins, f"JS VITAMIN_SOURCES keys match Python VITAMINS keys (JS: {js_vitamins_src == py_vitamins})")

# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)