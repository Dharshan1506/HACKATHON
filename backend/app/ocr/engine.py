import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import re
import logging
from typing import Dict, Any, List, Tuple
from PIL import Image
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Global PaddleOCR reader cache
_paddleocr_reader = None
# Global EasyOCR reader cache
_easyocr_reader = None

def get_paddleocr_reader():
    global _paddleocr_reader
    if _paddleocr_reader is None:
        try:
            from paddleocr import PaddleOCR
            _paddleocr_reader = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False, show_log=False)
        except Exception as e:
            logger.warning(f"PaddleOCR not available: {e}")
            _paddleocr_reader = False
    return _paddleocr_reader if _paddleocr_reader is not False else None

def get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr
            _easyocr_reader = easyocr.Reader(['en'], gpu=False)
        except Exception as e:
            logger.warning(f"EasyOCR not available: {e}")
            _easyocr_reader = False
    return _easyocr_reader if _easyocr_reader is not False else None


class OCREngine:
    """
    Real Deep Learning OCR Engine for Packaged Commodities using PaddleOCR as primary.
    Extracts authentic text, computes bounding boxes, and parses Legal Metrology declarations.
    """

    @classmethod
    async def process_image(cls, image_path: str, filename: str) -> Dict[str, Any]:
        width, height = 800, 600
        if os.path.exists(image_path):
            try:
                with Image.open(image_path) as img:
                    width, height = img.size
            except Exception:
                pass

        # 1. OpenCV Preprocessing
        preprocessed_path = image_path
        if os.path.exists(image_path):
            try:
                cv_img = cv2.imread(image_path)
                if cv_img is not None:
                    # Grayscale conversion
                    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
                    # Adaptive thresholding to handle uneven packaging lighting and shadows
                    thresh = cv2.adaptiveThreshold(
                        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                        cv2.THRESH_BINARY, 11, 2
                    )
                    preprocessed_path = image_path.replace(".", "_preprocessed.")
                    cv2.imwrite(preprocessed_path, thresh)
            except Exception as e:
                logger.warning(f"OpenCV preprocessing error: {e}")

        # 2. Extract Real Text and Tokens via PaddleOCR / EasyOCR / PyTesseract
        raw_text, detected_boxes = cls._extract_real_text_and_boxes(preprocessed_path, image_path, width, height)

        # 3. Parse Legal Metrology Declarations from Real Extracted Text
        fields, mapped_boxes = cls._parse_legal_metrology_fields(raw_text, detected_boxes, width, height)

        # 4. Detect Product Category
        detected_category = cls.detect_category(raw_text, fields)

        # Clean up temp preprocessed image
        if preprocessed_path != image_path and os.path.exists(preprocessed_path):
            try:
                os.remove(preprocessed_path)
            except Exception:
                pass

        return {
            "image_dimensions": {"width": width, "height": height},
            "raw_text": raw_text,
            "fields": fields,
            "detected_category": detected_category,
            "bounding_boxes": mapped_boxes
        }

    @classmethod
    def detect_category(cls, raw_text: str, fields: Dict[str, str]) -> str:
        """
        Detects product category among:
        'Food', 'Cosmetics', 'Household', 'Consumer Goods', 'Imported Goods', 'Other'
        """
        combined_text = f"{raw_text} {fields.get('commodity_name', '')} {fields.get('brand', '')} {fields.get('importer', '')} {fields.get('country_of_origin', '')}".lower()
        
        # 1. Imported Goods
        importer = fields.get('importer', '').strip()
        country = fields.get('country_of_origin', '').strip().lower()
        non_india_countries = [
            'usa', 'united states', 'uk', 'united kingdom', 'china', 'germany', 
            'japan', 'france', 'italy', 'thailand', 'vietnam', 'korea', 'taiwan', 
            'spain', 'mexico', 'brazil', 'canada', 'australia', 'switzerland', 
            'belgium', 'netherlands', 'indonesia', 'malaysia', 'dubai', 'uae'
        ]
        has_imported_mention = any(k in combined_text for k in ['imported by', 'importer', 'country of origin: imported', 'imported & marketed', 'customs duty', 'import details'])
        is_foreign_country = any(c in country for c in non_india_countries) or ('india' not in country and len(country) > 2 and ('made in' in combined_text or 'origin' in combined_text))
        
        if (importer and len(importer) > 2 and importer.lower() != 'none') or has_imported_mention or is_foreign_country:
            return "Imported Goods"

        # 2. Food
        food_keywords = [
            'fssai', 'butter', 'almond', 'peanut', 'cashew', 'biscuit', 'cookie', 'flour', 'atta', 'maida', 
            'rice', 'wheat', 'oil', 'edible', 'cooking oil', 'ghee', 'milk', 'dairy', 'paneer', 'cheese',
            'snack', 'chips', 'chocolate', 'candy', 'confectionery', 'sugar', 'salt', 'spice', 'masala',
            'tea', 'coffee', 'juice', 'beverage', 'drink', 'sauce', 'ketchup', 'pickle', 'jam', 'honey',
            'noodle', 'pasta', 'cereal', 'oats', 'corn flakes', 'syrup', 'wafer', 'namkeen', 'bakery',
            'bread', 'cake', 'nutritional info', 'nutrition facts', 'ingredients:', 'energy (kcal)', 
            'protein (g)', 'carbohydrate', 'fat (g)', 'serving size', 'dietary', 'veg logo', 'non-veg',
            'food', 'organic', 'granola', 'pulses', 'dal', 'seed', 'dry fruits', 'per 100g', 'per serving'
        ]
        if any(k in combined_text for k in food_keywords):
            return "Food"

        # 3. Cosmetics
        cosmetics_keywords = [
            'shampoo', 'conditioner', 'soap', 'body wash', 'face wash', 'face cream', 'lotion', 'moisturizer',
            'serum', 'perfume', 'fragrance', 'deodorant', 'body spray', 'lipstick', 'lip balm', 'makeup',
            'sunscreen', 'spf', 'foundation', 'concealer', 'eyeliner', 'mascara', 'nail polish', 'hair oil',
            'hair dye', 'hair color', 'face mask', 'scrub', 'cleanser', 'toner', 'cosmetic', 'beauty',
            'skincare', 'haircare', 'dermatologically', 'paraben free', 'sulphate free', 'skin whitening',
            'anti-aging', 'aloe vera gel', 'essential oil', 'hyaluronic', 'salicylic', 'retinol'
        ]
        if any(k in combined_text for k in cosmetics_keywords):
            return "Cosmetics"

        # 4. Household
        household_keywords = [
            'detergent', 'washing powder', 'dishwash', 'dish wash', 'liquid detergent', 'floor cleaner',
            'toilet cleaner', 'glass cleaner', 'disinfectant', 'surface cleaner', 'bleach', 'fabric conditioner',
            'fabric softener', 'stain remover', 'mosquito repellent', 'insecticide', 'pest control', 'air freshener',
            'room spray', 'scrubber', 'sponge', 'mop', 'broom', 'trash bag', 'garbage bag', 'tissue paper',
            'kitchen roll', 'aluminum foil', 'cling wrap', 'drain cleaner', 'odor eliminator', 'candle',
            'matches', 'cleaning wipe', 'cleaner'
        ]
        if any(k in combined_text for k in household_keywords):
            return "Household"

        # 5. Consumer Goods
        consumer_goods_keywords = [
            'charger', 'cable', 'earphone', 'headphone', 'speaker', 'bluetooth', 'usb', 'power bank',
            'battery', 'led bulb', 'lamp', 'torch', 'electronic', 'appliance', 'kettle', 'iron', 'trimmer',
            'dryer', 'fan', 'clock', 'watch', 'calculator', 'pen', 'pencil', 'notebook', 'diary', 'stationery',
            'bottle', 'flask', 'lunch box', 'container', 'plasticware', 'cookware', 'pan', 'pot', 'utensil',
            'knife', 'scissors', 'hanger', 't-shirt', 'shirt', 'clothing', 'apparel', 'garment', 'socks',
            'towel', 'bedsheet', 'blanket', 'shoe', 'footwear', 'sandal', 'slipper', 'tool', 'screwdriver',
            'wrench', 'tape', 'glue', 'adhesive', 'toy', 'board game', 'sports', 'fitness', 'dumbbell',
            'yoga mat', 'backpack', 'bag', 'wallet', 'umbrella'
        ]
        if any(k in combined_text for k in consumer_goods_keywords):
            return "Consumer Goods"

        return "Other"

    @classmethod
    def _extract_real_text_and_boxes(cls, preprocessed_path: str, original_path: str, width: int, height: int) -> Tuple[str, List[Dict[str, Any]]]:
        raw_lines = []
        detected_boxes = []

        # Try PaddleOCR
        paddle_reader = get_paddleocr_reader()
        if paddle_reader and os.path.exists(preprocessed_path):
            try:
                results = paddle_reader.ocr(preprocessed_path, cls=True)
                if results and len(results) > 0:
                    page = results[0]
                    # PaddleOCR 3.7.0 returns a dictionary with 'rec_texts', 'rec_scores', 'rec_boxes'
                    rec_texts = page.get("rec_texts", [])
                    rec_scores = page.get("rec_scores", [])
                    rec_boxes = page.get("rec_boxes", [])
                    
                    for text, score, box in zip(rec_texts, rec_scores, rec_boxes):
                        text_clean = text.strip()
                        if text_clean:
                            raw_lines.append(text_clean)
                            # box is [xmin, ymin, xmax, ymax]
                            min_x, min_y, max_x, max_y = box
                            w = max_x - min_x
                            h = max_y - min_y
                            detected_boxes.append({
                                "text": text_clean,
                                "box": [int(min_x), int(min_y), int(w), int(h)],
                                "confidence": float(score)
                            })
                    if raw_lines:
                        return "\n".join(raw_lines), detected_boxes
            except Exception as e:
                logger.warning(f"PaddleOCR extraction error: {e}")

        # Fallback to EasyOCR
        reader = get_easyocr_reader()
        path_to_scan = original_path if os.path.exists(original_path) else preprocessed_path
        if reader and os.path.exists(path_to_scan):
            try:
                results = reader.readtext(path_to_scan)
                for bbox, text, confidence in results:
                    text_clean = text.strip()
                    if text_clean:
                        raw_lines.append(text_clean)
                        xs = [pt[0] for pt in bbox]
                        ys = [pt[1] for pt in bbox]
                        min_x, max_x = int(min(xs)), int(max(xs))
                        min_y, max_y = int(min(ys)), int(max(ys))
                        detected_boxes.append({
                            "text": text_clean,
                            "box": [min_x, min_y, max_x - min_x, max_y - min_y],
                            "confidence": float(confidence)
                        })
                if raw_lines:
                    return "\n".join(raw_lines), detected_boxes
            except Exception as e:
                logger.warning(f"EasyOCR extraction error: {e}")

        # Fallback to PyTesseract as final fallback
        try:
            import pytesseract
            tess_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe")
            ]
            for p in tess_paths:
                if os.path.exists(p):
                    pytesseract.pytesseract.tesseract_cmd = p
                    break

            if os.path.exists(path_to_scan):
                img = Image.open(path_to_scan)
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                n_boxes = len(data['text'])
                for i in range(n_boxes):
                    t = data['text'][i].strip()
                    if t:
                        raw_lines.append(t)
                        detected_boxes.append({
                            "text": t,
                            "box": [data['left'][i], data['top'][i], data['width'][i], data['height'][i]],
                            "confidence": float(data['conf'][i])
                        })
                full_text = pytesseract.image_to_string(img).strip()
                if full_text:
                    return full_text, detected_boxes
        except Exception as e:
            logger.warning(f"PyTesseract extraction error: {e}")

        return "\n".join(raw_lines) if raw_lines else "No text extracted.", detected_boxes

    @classmethod
    def _parse_legal_metrology_fields(cls, raw_text: str, detected_boxes: List[Dict[str, Any]], img_w: int, img_h: int) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
        full_text_lower = raw_text.lower()

        fields: Dict[str, str] = {
            "commodity_name": "",
            "brand": "",
            "manufacturer_details": "",
            "address": "",
            "mrp": "",
            "net_quantity": "",
            "mfg_date": "",
            "expiry_date": "",
            "importer": "",
            "country_of_origin": "",
            "customer_care": "",
            "unit_sale_price": ""
        }

        # Helper to find lines starting with or containing key prefixes
        def find_after_prefix(keywords: List[str], text_str: str) -> str:
            for line in text_str.split("\n"):
                for kw in keywords:
                    if kw.lower() in line.lower():
                        idx = line.lower().find(kw.lower())
                        extracted = line[idx + len(kw):].strip(" :.-=,")
                        if extracted and len(extracted) > 1:
                            return extracted
            return ""

        # Extract Brand
        brand_keywords = ["brand name", "brand", "tm", "regd tm"]
        fields["brand"] = find_after_prefix(brand_keywords, raw_text)
        if not fields["brand"] and lines:
            for l in lines[:3]:
                if "brand" in l.lower():
                    fields["brand"] = l.split(":")[-1].strip()
                    break
            if not fields["brand"] and lines:
                fields["brand"] = lines[0][:40]

        # Extract Commodity Name
        commodity_keywords = ["commodity name", "commodity", "product name", "product"]
        fields["commodity_name"] = find_after_prefix(commodity_keywords, raw_text)
        if not fields["commodity_name"] and len(lines) > 1:
            for l in lines[1:4]:
                if not any(c.isdigit() for c in l) and len(l) > 5:
                    fields["commodity_name"] = l[:60]
                    break
            if not fields["commodity_name"]:
                fields["commodity_name"] = lines[1][:60] if len(lines) > 1 else lines[0][:60]

        # Extract Manufacturer
        mfg_keywords = ["manufactured by", "mfd by", "packed by", "mfd & packed by", "manufactured & packed by", "packed and manufactured by"]
        fields["manufacturer_details"] = find_after_prefix(mfg_keywords, raw_text)
        if not fields["manufacturer_details"]:
            for l in lines:
                if any(k in l.lower() for k in ["mfd by", "manufactured by", "packed by", "mfg by"]):
                    fields["manufacturer_details"] = l.split(":")[-1].strip()
                    break
            if not fields["manufacturer_details"]:
                for l in lines:
                    if any(k in l.lower() for k in ["pvt ltd", "private limited", "ltd", "corp", "inc"]):
                        fields["manufacturer_details"] = l
                        break

        # Extract Address
        address_parts = []
        for l in lines:
            l_lower = l.lower()
            if any(k in l_lower for k in ["plot no", "industrial estate", "industrial area", "road", "street", "lane", "phase", "sector", "building", "floor", "nagar", "ward", "pin code", "pincode"]):
                address_parts.append(l)
            elif re.search(r'\b\d{6}\b', l):
                address_parts.append(l)
        if address_parts:
            seen = set()
            unique_parts = []
            for part in address_parts:
                part_clean = part.strip(" ,.-")
                if part_clean not in seen:
                    seen.add(part_clean)
                    unique_parts.append(part_clean)
            fields["address"] = ", ".join(unique_parts)

        # Extract Importer
        importer_keywords = ["imported by", "importer", "imported & marketed by", "import details"]
        fields["importer"] = find_after_prefix(importer_keywords, raw_text)
        if not fields["importer"]:
            for l in lines:
                if "imported" in l.lower() or "importer" in l.lower():
                    fields["importer"] = l.split(":")[-1].strip()
                    break

        # Extract Country of Origin
        origin_keywords = ["country of origin", "made in", "origin", "product of"]
        fields["country_of_origin"] = find_after_prefix(origin_keywords, raw_text)
        if not fields["country_of_origin"]:
            for l in lines:
                if "origin" in l.lower() or "made in" in l.lower():
                    fields["country_of_origin"] = l.split(":")[-1].strip()
                    break
        if not fields["country_of_origin"] and "india" in full_text_lower:
            fields["country_of_origin"] = "India"

        # Extract Customer Care
        cc_keywords = ["customer care", "consumer care", "care cell", "complaints", "feedback", "helpline", "toll free", "toll-free"]
        fields["customer_care"] = find_after_prefix(cc_keywords, raw_text)
        if not fields["customer_care"]:
            for l in lines:
                if any(k in l.lower() for k in ["care", "customer", "helpline", "email", "@", "complaint"]):
                    fields["customer_care"] = l
                    break

        # Extract MRP
        mrp_match = re.search(r'((?:mrp|m\.r\.p|price|₹|rs\.?)\s*[:.-]?\s*(?:rs\.?|₹)?\s*\d+(?:\.\d{2})?(?:\s*(?:\(?[^)\n]*incl[^)\n]*\)?))?)', raw_text, re.I)
        if mrp_match and mrp_match.group(1).strip():
            fields["mrp"] = mrp_match.group(1).strip()

        # Extract Net Quantity
        qty_match = re.search(r'(\b\d+(\.\d+)?\s*(?:g|kg|ml|l|ltr|grams|n|pcs|units)\b)', raw_text, re.I)
        if qty_match:
            fields["net_quantity"] = qty_match.group(1).strip()

        # Extract Mfg Date
        mfg_match = re.search(r'((?:mfg|mfd|packed|pkd)\s*[:.-]?\s*(?:[0-3]?[0-9][\/\-.])?[0-1]?[0-9][\/\-.][1-2][0-9]{3}|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,.-]+[1-2][0-9]{3})', raw_text, re.I)
        if mfg_match:
            fields["mfg_date"] = mfg_match.group(1).strip()

        # Extract Expiry Date
        exp_keywords = ["best before", "expiry date", "exp date", "expiry", "exp", "use by"]
        fields["expiry_date"] = find_after_prefix(exp_keywords, raw_text)
        if not fields["expiry_date"]:
            exp_match = re.search(r'((?:exp|expiry|use\s*before|best\s*before)\s*[:.-]?\s*(?:[0-3]?[0-9][\/\-.])?[0-1]?[0-9][\/\-.][1-2][0-9]{3}|\d+\s*months?)', raw_text, re.I)
            if exp_match:
                fields["expiry_date"] = exp_match.group(1).strip()

        # Extract Unit Sale Price
        usp_match = re.search(r'((?:usp|unit\s*price|₹\s*\/?\s*g|rs\.?\s*\/?\s*g)\s*[:.-]?\s*(?:rs\.?|₹)?\s*\d+(?:\.\d{2})?\s*(?:per|\/)\s*(?:g|kg|ml|l|unit|piece|n))', raw_text, re.I)
        if usp_match:
            fields["unit_sale_price"] = usp_match.group(1).strip()

        # Map Bounding Boxes for Visual Inspection
        mapped_boxes = []
        for db in detected_boxes[:15]:
            mapped_boxes.append({
                "field": "detected_text",
                "box": db["box"],
                "label": db.get("text", "Text Area")[:30]
            })

        return fields, mapped_boxes
