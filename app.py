"""
Vitamin Checker - Analyze supermarket receipts for vitamin gaps.
Flask backend with receipt parsing and nutrition analysis.
"""

import os
import re
import json
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# ─── Nutrition Database ─────────────────────────────────────────────
# Vitamins with daily recommended values (adult)
VITAMINS = {
    "A":   {"name": "Vitamin A",   "unit": "µg",  "rda": 900,   "color": "#e74c3c"},
    "B1":  {"name": "Thiamine (B1)",  "unit": "mg",  "rda": 1.2,   "color": "#e67e22"},
    "B2":  {"name": "Riboflavin (B2)",  "unit": "mg",  "rda": 1.3,   "color": "#f1c40f"},
    "B3":  {"name": "Niacin (B3)",  "unit": "mg",  "rda": 16,    "color": "#2ecc71"},
    "B5":  {"name": "Pantothenic (B5)", "unit": "mg",  "rda": 5,     "color": "#1abc9c"},
    "B6":  {"name": "Pyridoxine (B6)",  "unit": "mg",  "rda": 1.7,   "color": "#3498db"},
    "B9":  {"name": "Folate (B9)",  "unit": "µg",  "rda": 400,   "color": "#9b59b6"},
    "B12": {"name": "Cobalamin (B12)", "unit": "µg",  "rda": 2.4,   "color": "#8e44ad"},
    "C":   {"name": "Vitamin C",   "unit": "mg",  "rda": 90,    "color": "#e91e63"},
    "D":   {"name": "Vitamin D",   "unit": "µg",  "rda": 20,    "color": "#ff9800"},
    "E":   {"name": "Vitamin E",   "unit": "mg",  "rda": 15,    "color": "#4caf50"},
    "K":   {"name": "Vitamin K",   "unit": "µg",  "rda": 120,   "color": "#009688"},
}

# Food items mapped to vitamins (per ~100g typical serving)
# Values: percentage of RDA per 100g
FOOD_VITAMINS = {
    # 🍎 Fruits
    "orange":        {"C": 88, "B1": 8, "B9": 10, "A": 5},
    "pomodeorange":  {"C": 88, "B1": 8, "B9": 10, "A": 5},
    "pomme":         {"C": 7, "B6": 4, "K": 3, "A": 1},
    "banane":        {"C": 15, "B6": 22, "B9": 5, "B1": 3},
    "banana":        {"C": 15, "B6": 22, "B9": 5, "B1": 3},
    "fraise":        {"C": 98, "B9": 6, "K": 3},
    "kiwi":          {"C": 155, "K": 30, "E": 7, "B9": 5},
    "ananas":        {"C": 80, "B1": 7, "B6": 8},
    "citron":        {"C": 92, "B6": 5, "B1": 4},
    "mangue":        {"C": 60, "A": 22, "B6": 7, "B9": 7},
    "raisin":        {"C": 11, "K": 12, "B6": 5, "B1": 5},
    "peche":         {"C": 10, "A": 6, "E": 5, "K": 2},
    "abricot":       {"A": 20, "C": 13, "E": 5, "B3": 5},
    "pasteque":      {"C": 10, "A": 7},
    "melon":         {"C": 30, "A": 70},

    # 🥬 Vegetables
    "carotte":       {"A": 334, "K": 12, "C": 10, "B6": 6},
    "carotte":       {"A": 334, "K": 12, "C": 10, "B6": 6},
    "brocoli":       {"C": 149, "K": 127, "B9": 16, "A": 12},
    "brocoli":       {"C": 149, "K": 127, "B9": 16, "A": 12},
    "epinard":       {"K": 460, "A": 188, "B9": 49, "C": 47},
    "epinard":       {"K": 460, "A": 188, "B9": 49, "C": 47},
    "tomate":        {"C": 21, "A": 20, "K": 7, "B6": 5},
    "tomate":        {"C": 21, "A": 20, "K": 7, "B6": 5},
    "poivron":       {"C": 200, "A": 18, "B6": 17},
    "salade":        {"A": 148, "K": 100, "C": 16, "B9": 9},
    "laitue":        {"A": 148, "K": 100, "C": 16, "B9": 9},
    "pomme de terre":{"C": 33, "B6": 17, "B1": 6, "B3": 6},
    "patate":        {"C": 33, "B6": 17, "B1": 6, "B3": 6},
    "oignon":        {"C": 12, "B6": 6, "B1": 3},
    "ail":           {"C": 18, "B6": 13, "B1": 5},
    "champignon":    {"B2": 17, "B3": 14, "B5": 8, "D": 4},
    "courgette":     {"C": 18, "A": 6, "B6": 5},
    "aubergine":     {"B6": 4, "K": 3, "C": 3},
    "concombre":     {"C": 4, "K": 16, "A": 1},
    "celeri":        {"K": 12, "C": 4, "A": 4},
    "chou":          {"C": 43, "K": 55, "B6": 7},
    "haricot vert":  {"C": 18, "K": 15, "A": 3, "B9": 4},
    "petit pois":    {"C": 20, "K": 21, "B1": 20, "B9": 11},
    "poireau":       {"K": 38, "C": 13, "A": 17, "B9": 9},
    "navet":         {"C": 28, "K": 1, "A": 1},
    "radis":         {"C": 18, "K": 2, "B6": 3},

    # 🥩 Meat & Fish
    "poulet":        {"B3": 56, "B6": 28, "B12": 6, "B5": 8},
    "chicken":       {"B3": 56, "B6": 28, "B12": 6, "B5": 8},
    "boeuf":         {"B12": 100, "B6": 22, "B3": 31, "B2": 13, "B5": 7},
    "steak":         {"B12": 100, "B6": 22, "B3": 31, "B2": 13, "B5": 7},
    "viande":        {"B12": 70, "B6": 20, "B3": 25, "B2": 12},
    "porc":          {"B1": 56, "B6": 22, "B3": 22, "B12": 7, "B2": 11},
    "agneau":        {"B12": 50, "B3": 29, "B2": 18, "B6": 13},
    "saumon":        {"D": 70, "B12": 52, "B3": 50, "B6": 22, "A": 1},
    "salmon":        {"D": 70, "B12": 52, "B3": 50, "B6": 22, "A": 1},
    "thon":          {"B3": 60, "B12": 45, "D": 39, "B6": 24, "B1": 8},
    "tuna":          {"B3": 60, "B12": 45, "D": 39, "B6": 24, "B1": 8},
    "sardine":       {"D": 60, "B12": 138, "B3": 18, "B2": 14, "E": 8},
    "cabillaud":     {"B12": 30, "B3": 17, "B6": 14, "D": 7},
    "crevette":      {"B12": 18, "D": 4, "B3": 11, "E": 4},
    "cedar":         {"B12": 30, "B3": 17, "D": 10},

    # 🥛 Dairy
    "lait":          {"D": 10, "B12": 18, "A": 5, "B2": 17, "C": 1},
    "milk":          {"D": 10, "B12": 18, "A": 5, "B2": 17, "C": 1},
    "yaourt":        {"B2": 16, "B12": 16, "C": 1, "A": 1, "D": 3},
    "yogurt":        {"B2": 16, "B12": 16, "C": 1, "A": 1, "D": 3},
    "fromage":       {"B12": 25, "A": 20, "C": 0, "D": 3, "K": 4},
    "cheese":        {"B12": 25, "A": 20, "C": 0, "D": 3, "K": 4},
    "gruyere":       {"B12": 40, "A": 22, "D": 3, "B2": 18},
    "parmesan":      {"B12": 33, "A": 16, "C": 0, "D": 2},
    "beurre":        {"A": 30, "D": 7, "E": 7},
    "butter":        {"A": 30, "D": 7, "E": 7},
    "creme":         {"A": 13, "D": 3, "B2": 7, "B12": 5},

    # 🥚 Eggs
    "oeuf":          {"B12": 19, "D": 11, "A": 10, "B2": 15, "E": 3},
    "egg":           {"B12": 19, "D": 11, "A": 10, "B2": 15, "E": 3},

    # 🍞 Grains & Bread
    "pain":          {"B1": 22, "B3": 14, "B9": 10, "B2": 7, "E": 1},
    "bread":         {"B1": 22, "B3": 14, "B9": 10, "B2": 7, "E": 1},
    "riz":           {"B1": 12, "B3": 12, "B6": 6, "B9": 3},
    "rice":          {"B1": 12, "B3": 12, "B6": 6, "B9": 3},
    "pates":         {"B1": 13, "B3": 14, "B9": 10, "B6": 4, "E": 1},
    "pasta":         {"B1": 13, "B3": 14, "B9": 10, "B6": 4, "E": 1},
    "cereales":      {"B1": 50, "B9": 50, "B12": 50, "B6": 50, "D": 30, "E": 25},
    "cereale":       {"B1": 50, "B9": 50, "B12": 50, "B6": 50, "D": 30, "E": 25},
    "avoine":        {"B1": 18, "B6": 6, "B5": 7, "B9": 3, "E": 1},
    "flocons":       {"B1": 18, "B6": 6, "B5": 7, "B9": 3, "E": 1},
    "quinoa":        {"B1": 8, "B2": 11, "B6": 12, "B9": 12, "E": 6},

    # 🥜 Nuts & Seeds
    "amande":        {"E": 170, "B2": 17, "B9": 8, "B3": 5},
    "amandes":       {"E": 170, "B2": 17, "B9": 8, "B3": 5},
    "noix":          {"E": 9, "B1": 13, "B6": 20, "B9": 7, "K": 1},
    "noisette":      {"E": 50, "B1": 20, "B6": 15, "B9": 9},
    "noisettes":     {"E": 50, "B1": 20, "B6": 15, "B9": 9},
    "cacahuete":     {"B3": 48, "E": 30, "B9": 18, "B1": 15},
    "pistache":      {"B6": 20, "B1": 12, "E": 10, "A": 3},
    "graine":        {"E": 25, "B1": 18, "B6": 12, "B9": 8},
    "tournesol":     {"E": 260, "B1": 39, "B6": 24, "B9": 16},

    # 🫘 Legumes
    "lentille":      {"B9": 90, "B1": 22, "B6": 14, "B5": 12, "K": 4},
    "lentilles":     {"B9": 90, "B1": 22, "B6": 14, "B5": 12, "K": 4},
    "haricot":       {"B9": 30, "B1": 12, "B6": 8, "K": 2},
    "pois chiche":   {"B9": 55, "B6": 13, "B1": 11, "B5": 7},
    "pois":          {"C": 20, "K": 21, "B1": 20, "B9": 11},

    # 🧊 Frozen / Prepared
    "pizza":         {"B12": 15, "C": 5, "A": 8, "C": 8, "B1": 8, "B2": 8},
    "plat":          {"B1": 8, "B2": 8, "B3": 8, "B12": 5},
    "soupe":         {"A": 15, "C": 10, "K": 5, "B9": 5},

    # 🍫 Treats
    "chocolat":      {"E": 10, "B1": 7, "B6": 4, "K": 3},
    "chocolate":     {"E": 10, "B1": 7, "B6": 4, "K": 3},
    "confiture":     {"C": 2, "E": 1},
    "sucre":         {},
    "soda":          {},
    "coca":          {},
    "bonbon":        {},

    # 🧂 Oils & Condiments
    "huile":          {"E": 60, "K": 50},
    "huile dolive":   {"E": 72, "K": 50},
    "olive oil":      {"E": 72, "K": 50},
    "vinaigre":       {},
    "moutarde":       {"K": 5, "E": 2, "C": 1},
    "ketchup":        {"C": 4, "A": 3},

    # 🍷 Drinks
    "vin":           {"K": 1, "B6": 3},
    "biere":         {"B6": 5, "B3": 4, "B2": 3, "B12": 1},
    "jus":           {"C": 100, "B9": 7, "A": 3},
    "jus dorange":   {"C": 120, "B9": 10, "A": 2, "B1": 6},
    "cafe":          {"B2": 6, "B3": 3, "B5": 3, "B1": 2},
    "the":           {"B2": 3, "B9": 3},

    # 🫐 More Fruits
    "cerise":        {"A": 3, "C": 12, "K": 2},
    "myrtille":      {"C": 16, "K": 19, "E": 4, "B6": 3},
    "framboise":     {"C": 44, "K": 8, "B9": 4, "E": 6},
    "clementine":     {"C": 60, "A": 3, "B1": 3},
    "mandarine":      {"C": 50, "A": 4, "B1": 4},
    "prune":         {"C": 10, "A": 6, "K": 5, "B2": 2},
    "figue":         {"K": 9, "B6": 5, "C": 3},
    "grenade":        {"C": 17, "K": 13, "B9": 6, "E": 3},

    # 🥬 More Vegetables
    "haricot":       {"B9": 30, "B1": 12, "B6": 8, "K": 2},
    "poivron rouge":  {"C": 300, "A": 55, "B6": 20},
    "poivron vert":   {"C": 180, "A": 2, "B6": 14},
    "avocat":        {"K": 20, "B5": 14, "B6": 13, "B9": 20, "E": 10, "C": 15},
    "avocados":      {"K": 20, "B5": 14, "B6": 13, "B9": 20, "E": 10, "C": 15},
    "artichaut":     {"C": 17, "K": 12, "B9": 18, "B1": 6},
    "asperge":       {"K": 42, "B9": 30, "C": 10, "A": 2},
    "bettrave":      {"C": 7, "B9": 22, "K": 1},
    "endive":        {"K": 50, "C": 5, "A": 4, "B9": 7},
    "bette":         {"K": 600, "A": 120, "C": 20},

    # 🧀 More Dairy
    "fromage blanc":  {"B12": 15, "A": 8, "B2": 10, "C": 1},
    "faisselle":      {"B12": 12, "B2": 12, "A": 5},
    "caille":         {"A": 15, "B12": 12, "B2": 10, "D": 2},
    "roquefort":      {"B12": 30, "A": 20, "B2": 18},
    "comte":          {"B12": 40, "A": 22, "C": 0, "D": 3, "K": 4},
    "camembert":      {"B12": 22, "A": 15, "B2": 12, "D": 2},

    # 🐟 More Fish & Seafood
    "cabillaud":     {"B12": 30, "B3": 17, "B6": 14, "D": 7},
    "sole":          {"B12": 20, "B3": 14, "B6": 8},
    "truite":        {"D": 50, "B12": 40, "B3": 28, "B6": 15},
    "maquereau":     {"D": 80, "B12": 125, "B3": 30, "B6": 22},

    # 🥖 More Bread & Grains
    "baguette":      {"B1": 20, "B3": 12, "B9": 8, "B2": 6, "E": 1},
    "pain complet":  {"B1": 24, "B3": 16, "B9": 12, "B2": 8, "E": 2, "B6": 10},
    "biscotte":      {"B1": 15, "B3": 10, "B9": 6, "E": 3},
    "mouna":         {"B1": 10, "B3": 6, "C": 2, "E": 1},
    "brioche":       {"A": 10, "B1": 12, "B2": 10, "B12": 5, "D": 3},

    # 🍝 More Prepared Foods
    "linguine":      {"B1": 13, "B3": 14, "B9": 10, "B6": 4, "E": 1},
    "penne":         {"B1": 12, "B3": 12, "B9": 8, "B6": 4},
    "spaghetti":     {"B1": 11, "B3": 11, "B9": 8, "B6": 3},
    "ravioli":       {"B12": 10, "B1": 8, "A": 5, "C": 5},
    "quiche":        {"A": 15, "B12": 12, "B2": 10, "C": 5, "D": 5},
    "lasagne":       {"B12": 12, "A": 8, "B1": 10, "B3": 8, "C": 8},
    "lasagnes":      {"B12": 12, "A": 8, "B1": 10, "B3": 8, "C": 8},
    "gratin":        {"A": 12, "B12": 10, "B2": 8, "C": 5, "D": 3},
    "rissole":       {"B12": 10, "B3": 12, "B6": 8, "A": 3},
    "salade riss":   {"A": 10, "C": 5, "K": 8, "B9": 3},

    # 🫒 More Oils & Condiments
    "huile dolive":   {"E": 72, "K": 50},
    "huile de tournesol": {"E": 260, "K": 5, "B6": 40},
    "huile de noix":  {"E": 35, "K": 15, "B1": 8},
    "mayonnaise":     {"E": 50, "K": 20, "A": 5, "D": 3},
    "vinaigrette":    {"E": 30, "K": 15, "C": 2},

    # ☕ Drinks refined
    "jus dorange":   {"C": 120, "B9": 10, "A": 2, "B1": 6},
    "jus de pomme":   {"C": 30, "B9": 2, "B1": 2},
    "jus de raisin":  {"C": 25, "K": 6, "B6": 3},
    "jus multifruit": {"C": 80, "A": 2, "B9": 5, "B1": 3},

    # 🌿 Herbs & Spices
    "persil":        {"K": 570, "C": 133, "A": 84, "B9": 9},
    "basilic":       {"K": 170, "A": 44, "C": 18},

    # 🧂 Other
    "chicore":       {"K": 5, "B1": 3, "C": 3, "B6": 2},
    "chicoree":      {"K": 5, "B1": 3, "C": 3, "B6": 2},
    "cerise":        {"C": 12, "A": 3, "K": 2},
    "steak hache":   {"B12": 80, "B6": 22, "B3": 25, "B2": 12, "B5": 6},
    "viande hache":  {"B12": 70, "B6": 20, "B3": 25, "B2": 12},
    "saucisse":      {"B12": 20, "B3": 15, "B1": 12, "B6": 8},
    "merguez":       {"B12": 18, "B3": 14, "B1": 10, "B6": 7, "C": 3},
    "tiramisu":      {"B12": 10, "A": 8, "B2": 8, "C": 1},
    "mousse":         {"B12": 8, "A": 6, "B2": 6, "C": 1},
    "compote":        {"C": 5, "K": 2, "B9": 1},
    "confiture":      {"C": 2, "E": 1},
    "sauce":         {"C": 3, "A": 3, "E": 2},
    "moutarde":      {"K": 5, "E": 2},
}

# ─── Receipt Parsing ─────────────────────────────────────────────────

# Common French receipt noise words to strip
NOISE_WORDS = re.compile(
    r'\b(total|sous.total|tva|tax|cb|carte|esp[eè]ces|rendu|monnaie|'
    r'merci|bonjour|code|n°|ticket|caisse|hypermarch[eé]|supermarch[eé]|'
    r'carrefour|leclerc|auchan|intermarch[eé]|casino|super.u|lid[l]|aldi|'
    r'franprix|monoprix|cora|geant|promos?|promo|remise|r[eé]duction|'
    r'unit[a-z]*|prix|kg|pi[eè]ce|euro|€|chr|f|^|\d+[,.]\d{2}\b|'
    r'additif|produit|marque|ref|ean|article|nb|qt[eé]|quantit[eé]|'
    r'montant|somme|net|brut|tl|tlca|tva|taux|taux\s*\d+%|'
    r'cb|visa|mastercard|terminal|autorisation|contrat|n°|date|heure|'
    r'caisse|magasin|adresse|tel|siret|ape|rcs|capital|social|'
    r'www|http|borne|scann[eé]|self|scan|'
    r'montant|du|el[eé]gible|articles|vendus|nombre|recapitulatif|'
    r'solde|ancien|nouveau|fidelit[eé]|carte|points|'
    r'payer|regler|reglement|spec[eè]ces|emer|pin|nb|\b[a-z]\b)\b',
    re.IGNORECASE
)

# Patterns for lines that are clearly not product names
NOISE_LINE_PATTERNS = re.compile(
    r'^(total|sous.total|tva|cb|carte|esp[eè]ces|rendu|monnaie|'
    r'merci|ticket|caisse|code|n°|montant|somme|net|brut|'
    r'nombre|qt[eé]|el[eé]gible|articles|vendus|recapitulatif|'
    r'solde|ancien|nouveau|fidelit[eé]|points|'
    r'payer|regler|reglement|spec[eè]ces|emer|pin|'
    r'cb|visa|mastercard|terminal|autorisation|contrat|'
    r'date|heure|magasin|adresse|tel|siret|ape|rcs|capital|social|'
    r'www|http|borne|scann[eé]|self|scan|'
    r'.*\d+[,.]\d{2}\s*$|'   # line is just a number price
    r'^\s*\d+\s*$|'           # line is just a number
    r'^\s*[a-z]\s*$|'         # single char
    r'^\s*[\W\d]+\s*$)',      # only non-word chars and digits
    re.IGNORECASE
)


def parse_receipt_text(text):
    """Extract food items from raw receipt text."""
    lines = text.strip().split('\n')
    items = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Skip lines that are clearly noise (totals, metadata, etc.)
        if NOISE_LINE_PATTERNS.match(line):
            continue

        # Remove special characters often misread by OCR
        line = re.sub(r'[\"\'""''|\\*_~`^]', '', line)

        # Remove price patterns (e.g. "3,45" or "3.45" at end of line)
        line = re.sub(r'\s*\d+[,]\d{2}\s*€?\s*$', '', line)
        # Remove inline price patterns like "4,85 EUR" or "5,99 EUR"
        line = re.sub(r'\d+[,.]\d{2}\s*EUR\b', '', line, flags=re.IGNORECASE)
        # Remove quantity/weight patterns like "0,972 kg" or "500G" or "1KG"
        line = re.sub(r'\d+[,.]?\d*\s*(kg|g|ml|cl|l|KG|G|ML|CL|L)\b', '', line)
        # Remove unit price patterns like "x 4,99EURO/kg" or "x 5,99EUR/kg"
        line = re.sub(r'x\s*\d+[,.]?\d*\s*(euro?|€)/?\s*(kg|l|piece)?\b', '', line, flags=re.IGNORECASE)
        # Remove quantity prefixes like "2x " or "3 x " or "x5"
        line = re.sub(r'^\d+\s*x\s*', '', line)
        # Remove "X skipped" like "5 X 0,90"
        line = re.sub(r'\d+\s*[xX]\s*\d+[,.]?\d*', '', line)
        # Remove standalone "EUR" or "€"
        line = re.sub(r'\bEUR\b|€', '', line, flags=re.IGNORECASE)
        # Remove UPC/barcode-looking number blocks
        line = re.sub(r'\b\d{8,}\b', '', line)

        # Skip lines that are mostly noise after cleaning
        cleaned = re.sub(NOISE_WORDS, '', line).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned).strip(' -,.:;')

        # Remove isolated numbers
        cleaned = re.sub(r'\b\d+([,.]\d+)?\b', '', cleaned).strip(' -,.:;')

        # Remove single-char leftovers and special chars
        cleaned = re.sub(r'\b[a-zA-Z]\b', '', cleaned).strip()
        cleaned = re.sub(r'[^\w\sàâäéèêëïîôùûüÿçœæ]', '', cleaned).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # Skip very short fragments (less than 3 chars)
        if len(cleaned) < 3:
            continue

        # Skip if the line has too many numbers vs letters (likely metadata)
        alpha_count = sum(1 for c in cleaned if c.isalpha())
        if alpha_count < 3:
            continue

        items.append(cleaned.lower())

    return items


def match_food(item, food_db):
    """Fuzzy match a receipt item to a food in the database."""
    item = item.lower().strip()

    # Direct match
    if item in food_db:
        return item, food_db[item]

    # Partial match: food name is in the item
    best_match = None
    best_score = 0

    for food_key, vitamins in food_db.items():
        # Check if food_key is contained in item or vice versa
        if food_key in item:
            score = len(food_key)
            if score > best_score:
                best_score = score
                best_match = (food_key, vitamins)

    # Also check if item is contained in any food_key
    if not best_match:
        for food_key, vitamins in food_db.items():
            if item in food_key:
                score = len(item)
                if score > best_score:
                    best_score = score
                    best_match = (food_key, vitamins)

    if best_match:
        return best_match

    # If no vitamins at all, return None
    return None


def analyze_vitamins(items):
    """Analyze a list of food items and return vitamin coverage."""
    vitamin_totals = {k: 0.0 for k in VITAMINS}
    matched_items = []
    unmatched_items = []

    for item in items:
        result = match_food(item, FOOD_VITAMINS)
        if result:
            food_key, vitamins = result
            matched_items.append({"item": item, "matched_as": food_key, "vitamins": vitamins})
            for vit_key, pct in vitamins.items():
                if vit_key in vitamin_totals:
                    # Cap each food contribution at 100% to avoid one superfood dominating
                    vitamin_totals[vit_key] += min(pct, 100)
        else:
            if item:  # only add non-empty items
                unmatched_items.append(item)

    # Convert totals to percentages of RDA (capped at some reasonable max for display)
    vitamin_coverage = {}
    for vit_key, total_pct in vitamin_totals.items():
        # Normalize: if you bought e.g. 3 items contributing, cap contribution
        # but show raw total so user sees surplus too
        vitamin_coverage[vit_key] = round(min(total_pct, 500), 1)  # cap display at 500%

    # Compute gap = 100% - coverage (can be negative = surplus)
    gaps = {}
    for vit_key, coverage in vitamin_coverage.items():
        gap_pct = max(0, round(100 - coverage, 1))
        gaps[vit_key] = {
            "coverage": coverage,
            "gap": gap_pct,
            "status": "surplus" if coverage >= 100 else "deficit",
            "rda": VITAMINS[vit_key]["rda"],
            "unit": VITAMINS[vit_key]["unit"],
            "name": VITAMINS[vit_key]["name"],
            "color": VITAMINS[vit_key]["color"],
        }

    # Sort: biggest gaps first
    sorted_gaps = dict(sorted(gaps.items(), key=lambda x: x[1]["gap"], reverse=True))

    return {
        "gaps": sorted_gaps,
        "matched_items": matched_items,
        "unmatched_items": unmatched_items,
        "total_items": len(items),
        "matched_count": len(matched_items),
    }


# ─── Routes ──────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    # Image upload is required
    if 'receipt_image' not in request.files:
        return jsonify({"error": "Please upload a photo of your grocery receipt."}), 400

    file = request.files['receipt_image']
    if not file or not file.filename:
        return jsonify({"error": "No file received. Please upload an image."}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    file.save(filepath)

    # OCR the image
    text = ''
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(filepath)
        # Use PSM 6 (assume uniform block of text) - best for receipts
        # Also try with French language + English fallback
        try:
            ocr_text = pytesseract.image_to_string(img, lang='fra+eng', config='--psm 6')
            text = ocr_text.strip()
        except Exception:
            try:
                ocr_text = pytesseract.image_to_string(img, lang='fra', config='--psm 6')
                text = ocr_text.strip()
            except Exception:
                ocr_text = pytesseract.image_to_string(img, lang='eng', config='--psm 6')
                text = ocr_text.strip()

        if not text.strip():
            return jsonify({"error": "Could not read any text from the image. Is the photo clear and legible?"}), 400

    except ImportError:
        return jsonify({"error": "OCR not available. Please install pytesseract and Tesseract OCR."}), 500

    items = parse_receipt_text(text)
    result = analyze_vitamins(items)
    result['ocr_text'] = text  # include OCR text for debugging
    return jsonify(result)


@app.route('/sample')
def sample():
    """Return a sample analysis result for demo purposes."""
    sample_receipt = """Banane x2 2,40€
Poulet filet 4,95€
Brocoli 1,80€
Riz basmati 1kg 2,15€
Yaourt nature x4 2,60€
Jus dorange 1L 2,30€
Saumon 200g 5,90€
Epinard 300g 2,10€
Pain complet 1,50€
Tomate x3 1,95€
Huile olive 4,20€
Fromage gruyere 3,40€
Chocolat noir 2,10€
Ail x2 0,80€"""
    items = parse_receipt_text(sample_receipt)
    result = analyze_vitamins(items)
    result["ocr_text"] = sample_receipt
    return jsonify(result)


if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)