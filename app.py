"""
Vitamin Checker - Analyze supermarket receipts for vitamin gaps.
Flask backend with receipt parsing, French text normalization, and nutrition analysis.
"""

import os
import re
import json
import unicodedata
import secrets
import tempfile
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

# ─── EasyOCR Reader (lazy-loaded singleton) ──────────────────────────
_ocr_reader = None

def _get_ocr_reader():
    """Return a shared EasyOCR reader instance (lazy-loaded, French + English)."""
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(['fr', 'en'], gpu=False)
    return _ocr_reader

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# ─── Rate Limiting ─────────────────────────────────────────────────
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# ─── Security Configuration ─────────────────────────────────────────
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'tif', 'webp', 'pdf'}
ALLOWED_MIMETYPES = {
    'image/png', 'image/jpeg', 'image/gif', 'image/bmp',
    'image/tiff', 'image/webp', 'application/pdf'
}
MAX_IMAGE_PIXELS = 50_000_000  # 50 megapixels max (prevent decompression bomb)


def allowed_file(filename, file_obj=None):
    """Check file extension and optionally MIME type."""
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        return False
    # Also validate MIME type if file object is available
    if file_obj and hasattr(file_obj, 'content_type') and file_obj.content_type:
        if file_obj.content_type not in ALLOWED_MIMETYPES:
            return False
    return True


def validate_image_safety(filepath):
    """Validate image is safe to process (not a decompression bomb, not too large)."""
    try:
        from PIL import Image
        img = Image.open(filepath)
        # Check pixel count (decompression bomb protection)
        width, height = img.size
        if width * height > MAX_IMAGE_PIXELS:
            img.close()
            return False, "Image dimensions too large. Please use a smaller image."
        # Check actual format matches extension
        img_format = img.format
        img.close()
        return True, None
    except Exception as e:
        return False, f"Invalid image file: {str(e)}"


def cleanup_file(filepath):
    """Safely delete an uploaded file."""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except OSError:
        pass


# ─── Nutrition Database ─────────────────────────────────────────────
VITAMINS = {
    "A":   {"name": "Vitamin A",          "unit": "\u00b5g", "rda": 900,  "color": "#e74c3c"},
    "B1":  {"name": "Thiamine (B1)",      "unit": "mg",  "rda": 1.2,  "color": "#e67e22"},
    "B2":  {"name": "Riboflavin (B2)",    "unit": "mg",  "rda": 1.3,  "color": "#f1c40f"},
    "B3":  {"name": "Niacin (B3)",        "unit": "mg",  "rda": 16,   "color": "#2ecc71"},
    "B5":  {"name": "Pantothenic (B5)",   "unit": "mg",  "rda": 5,    "color": "#1abc9c"},
    "B6":  {"name": "Pyridoxine (B6)",    "unit": "mg",  "rda": 1.7,  "color": "#3498db"},
    "B9":  {"name": "Folate (B9)",        "unit": "\u00b5g", "rda": 400,  "color": "#9b59b6"},
    "B12": {"name": "Cobalamin (B12)",    "unit": "\u00b5g", "rda": 2.4,  "color": "#8e44ad"},
    "C":   {"name": "Vitamin C",          "unit": "mg",  "rda": 90,   "color": "#e91e63"},
    "D":   {"name": "Vitamin D",          "unit": "\u00b5g", "rda": 20,   "color": "#ff9800"},
    "E":   {"name": "Vitamin E",          "unit": "mg",  "rda": 15,   "color": "#4caf50"},
    "K":   {"name": "Vitamin K",          "unit": "\u00b5g", "rda": 120,  "color": "#009688"},
}

# ─── Load Food Database from JSON ───────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'food_database.json')

def load_food_database():
    """Load the food vitamin database from JSON."""
    with open(DB_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

FOOD_VITAMINS = load_food_database()

# ─── French Text Normalization ──────────────────────────────────────
def normalize_french(text):
    """Normalize French text for matching: strip accents, lowercase, remove spaces/apostrophes."""
    text = text.lower().strip()
    # Remove accents: é→e, è→e, ê→e, ë→e, à→a, â→a, ù→u, û→u, ü→u, î→i, ï→i, ô→o, ç→c, œ→oe, æ→ae
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = text.replace('\u0153', 'oe').replace('\u00e6', 'ae')
    # Remove apostrophes and hyphens and spaces for key matching
    text = text.replace("'", "").replace("-", "").replace(" ", "")
    return text

# Build a normalized lookup: normalized_key -> original_key
_NORMALIZED_LOOKUP = {}
for _key in FOOD_VITAMINS:
    _norm = normalize_french(_key)
    if _norm not in _NORMALIZED_LOOKUP:
        _NORMALIZED_LOOKUP[_norm] = _key

# ─── Receipt Parsing ────────────────────────────────────────────────

NOISE_WORDS = re.compile(
    r'\b(total|sous.total|tva|tax|cb|carte|esp[e\u00e8]ces|rendu|monnaie|'
    r'merci|bonjour|code|n\u00b0|ticket|caisse|hypermarch[e\u00e9]|supermarch[e\u00e9]|'
    r'carrefour|leclerc|auchan|intermarch[e\u00e9]|casino|super.u|lid[l]|aldi|'
    r'franprix|monoprix|cora|geant|promos?|promo|remise|r[e\u00e9]duction|'
    r'unit[a-z]*|prix|kg|pi[e\u00e8]ce|euro|\u20ac|chr|f|^|\d+[,.]\d{2}\b|'
    r'additif|produit|marque|ref|ean|article|nb|qt[e\u00e8]|quantit[e\u00e9]|'
    r'montant|somme|net|brut|tl|tlca|tva|taux|taux\s*\d+%|'
    r'cb|visa|mastercard|terminal|autorisation|contrat|n\u00b0|date|heure|'
    r'caisse|magasin|adresse|tel|siret|ape|rcs|capital|social|'
    r'www|http|borne|scann[e\u00e9]|self|scan|'
    r'montant|du|el[e\u00e9]gible|articles|vendus|nombre|recapitulatif|'
    r'solde|ancien|nouveau|fidelit[e\u00e9]|carte|points|'
    r'payer|regler|reglement|spec[e\u00e8]ces|emer|pin|nb|\b[a-z]\b)\b',
    re.IGNORECASE
)

NOISE_LINE_PATTERNS = re.compile(
    r'^(total|sous.total|tva|cb|carte|esp[e\u00e8]ces|rendu|monnaie|'
    r'merci|ticket|caisse|code|n\u00b0|montant|somme|net|brut|'
    r'nombre|qt[e\u00e8]|el[e\u00e9]gible|articles|vendus|recapitulatif|'
    r'solde|ancien|nouveau|fidelit[e\u00e9]|points|'
    r'payer|regler|reglement|spec[e\u00e8]ces|emer|pin|'
    r'cb|visa|mastercard|terminal|autorisation|contrat|'
    r'date|heure|magasin|adresse|tel|siret|ape|rcs|capital|social|'
    r'www|http|borne|scann[e\u00e9]|self|scan|'
    r'.*\d+[,.]\d{2}\s*$|'
    r'^\s*\d+\s*$|'
    r'^\s*[a-z]\s*$|'
    r'^\s*[\W\d]+\s*$)',
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

        if NOISE_LINE_PATTERNS.match(line):
            continue

        # Remove special characters often misread by OCR
        line = re.sub(r'[\\\"\'\u2018\u2019\u201c\u201d|\u005c*_~`^]', '', line)

        # Remove price patterns
        line = re.sub(r'\s*\d+[,]\d{2}\s*\u20ac?\s*$', '', line)
        line = re.sub(r'\d+[,.]\d{2}\s*EUR\b', '', line, flags=re.IGNORECASE)
        # Remove quantity/weight patterns
        line = re.sub(r'\d+[,.]?\d*\s*(kg|g|ml|cl|l|KG|G|ML|CL|L)\b', '', line)
        line = re.sub(r'x\s*\d+[,.]?\d*\s*(euro?|\u20ac)/?\s*(kg|l|piece)?\b', '', line, flags=re.IGNORECASE)
        line = re.sub(r'^\d+\s*x\s*', '', line)
        line = re.sub(r'\d+\s*[xX]\s*\d+[,.]?\d*', '', line)
        line = re.sub(r'\bEUR\b|\u20ac', '', line, flags=re.IGNORECASE)
        line = re.sub(r'\b\d{8,}\b', '', line)

        cleaned = re.sub(NOISE_WORDS, '', line).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned).strip(' -,.:;')
        cleaned = re.sub(r'\b\d+([,.]\d+)?\b', '', cleaned).strip(' -,.:;')
        cleaned = re.sub(r'\b[a-zA-Z]\b', '', cleaned).strip()
        cleaned = re.sub(r'[^\w\s\u00e0\u00e2\u00e4\u00e9\u00e8\u00ea\u00eb\u00ef\u00ee\u00f4\u00f9\u00fb\u00fc\u00ff\u00e7\u0153\u00e6]', '', cleaned).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        if len(cleaned) < 3:
            continue

        alpha_count = sum(1 for c in cleaned if c.isalpha())
        if alpha_count < 3:
            continue

        items.append(cleaned.lower())

    return items


def match_food(item, food_db):
    """Fuzzy match a receipt item to a food in the database with French normalization."""
    raw = item.lower().strip()
    norm = normalize_french(raw)

    # 1. Direct match on raw key
    if raw in food_db:
        return raw, food_db[raw]

    # 2. Direct match on normalized key
    if norm in _NORMALIZED_LOOKUP:
        orig_key = _NORMALIZED_LOOKUP[norm]
        return orig_key, food_db[orig_key]

    # 3. Partial match: food name contained in item (longest match wins)
    best_match = None
    best_score = 0

    for norm_key, orig_key in _NORMALIZED_LOOKUP.items():
        if len(norm_key) < 3:
            continue
        if norm_key in norm:
            score = len(norm_key)
            if score > best_score:
                best_score = score
                best_match = (orig_key, food_db[orig_key])

    # 4. Item contained in food name
    if not best_match:
        for norm_key, orig_key in _NORMALIZED_LOOKUP.items():
            if len(norm) >= 3 and norm in norm_key:
                score = len(norm)
                if score > best_score:
                    best_score = score
                    best_match = (orig_key, food_db[orig_key])

    # 5. Levenshtein distance for close matches (typo/OCR corrections)
    if not best_match and len(norm) >= 4:
        best_dist = float('inf')
        for norm_key, orig_key in _NORMALIZED_LOOKUP.items():
            if abs(len(norm_key) - len(norm)) > 3:
                continue
            # Only compute Levenshtein for reasonably similar lengths
            dist = _levenshtein(norm, norm_key)
            if dist < best_dist and dist <= max(1, len(norm) // 4):
                best_dist = dist
                best_match = (orig_key, food_db[orig_key])

    return best_match


def _levenshtein(s1, s2):
    """Compute Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


def analyze_vitamins(items):
    """Analyze a list of food items and return vitamin coverage."""
    vitamin_totals = {k: 0.0 for k in VITAMINS}
    matched_items = []
    unmatched_items = []
    seen_keys = set()

    for item in items:
        result = match_food(item, FOOD_VITAMINS)
        if result:
            food_key, vitamins = result
            # Merge if same food matched multiple times (dedup the vitamin contribution)
            if food_key not in seen_keys:
                seen_keys.add(food_key)
                matched_items.append({"item": item, "matched_as": food_key, "vitamins": vitamins})
                for vit_key, pct in vitamins.items():
                    if vit_key in vitamin_totals:
                        vitamin_totals[vit_key] += min(pct, 100)
        else:
            if item:
                unmatched_items.append(item)

    vitamin_coverage = {}
    for vit_key, total_pct in vitamin_totals.items():
        vitamin_coverage[vit_key] = round(min(total_pct, 500), 1)

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
@limiter.limit("10 per minute")
def analyze():
    if 'receipt_image' not in request.files:
        return jsonify({"error": "Please upload a photo of your grocery receipt."}), 400

    file = request.files['receipt_image']
    if not file or not file.filename:
        return jsonify({"error": "No file received. Please upload an image."}), 400

    # Validate file extension and MIME type
    if not allowed_file(file.filename, file):
        return jsonify({"error": "Invalid file type. Please upload an image (JPG, PNG, GIF, BMP, TIFF, WebP) or PDF."}), 400

    filename = secure_filename(file.filename)
    if not filename:
        filename = 'receipt_upload'

    # Save to a temporary file that will be cleaned up
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    try:
        file.save(filepath)

        # Validate image safety (prevent decompression bombs)
        img_safe, img_error = validate_image_safety(filepath)
        if not img_safe:
            cleanup_file(filepath)
            return jsonify({"error": img_error}), 400

        text = ''
        try:
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
            reader = _get_ocr_reader()
            results = reader.readtext(filepath, detail=0, paragraph=True)
            text = '\n'.join(results).strip()

            if not text.strip():
                return jsonify({"error": "Could not read any text from the image. Is the photo clear and legible?"}), 400

        except ImportError:
            return jsonify({"error": "OCR not available. Please install easyocr."}), 500
        except RuntimeError as e:
            return jsonify({"error": f"OCR engine error: {str(e)}"}), 500

        items = parse_receipt_text(text)
        result = analyze_vitamins(items)
        result['ocr_text'] = text
        return jsonify(result)

    finally:
        # Always clean up uploaded file
        cleanup_file(filepath)


@app.route('/sample')
def sample():
    """Return a sample analysis result for demo purposes."""
    sample_receipt = """Banane x2 2,40\u20ac
Poulet filet 4,95\u20ac
Brocoli 1,80\u20ac
Riz basmati 1kg 2,15\u20ac
Yaourt nature x4 2,60\u20ac
Jus dorange 1L 2,30\u20ac
Saumon 200g 5,90\u20ac
Epinard 300g 2,10\u20ac
Pain complet 1,50\u20ac
Tomate x3 1,95\u20ac
Huile olive 4,20\u20ac
Fromage gruyere 3,40\u20ac
Chocolat noir 2,10\u20ac
Ail x2 0,80\u20ac"""
    items = parse_receipt_text(sample_receipt)
    result = analyze_vitamins(items)
    result["ocr_text"] = sample_receipt
    return jsonify(result)


if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=False, host='0.0.0.0', port=5000)