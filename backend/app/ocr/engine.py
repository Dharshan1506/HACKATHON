import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import re
import logging
from typing import Dict, Any, List, Tuple
from PIL import Image
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Global EasyOCR reader cache
_easyocr_reader = None

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
    Real Deep Learning OCR Engine for Packaged Commodities.
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

        # 1. Extract Real Text and Tokens via EasyOCR / PyTesseract / Image Analysis
        raw_text, detected_boxes = cls._extract_real_text_and_boxes(image_path, width, height)

        # 2. Parse Legal Metrology Declarations from Real Extracted Text
        fields, mapped_boxes = cls._parse_legal_metrology_fields(raw_text, detected_boxes, width, height)

        return {
            "image_dimensions": {"width": width, "height": height},
            "raw_text": raw_text,
            "fields": fields,
            "bounding_boxes": mapped_boxes
        }

    @classmethod
    def _extract_real_text_and_boxes(cls, image_path: str, width: int, height: int) -> Tuple[str, List[Dict[str, Any]]]:
        raw_lines = []
        detected_boxes = []

        # Try EasyOCR
        reader = get_easyocr_reader()
        if reader and os.path.exists(image_path):
            try:
                results = reader.readtext(image_path)
                for bbox, text, confidence in results:
                    text_clean = text.strip()
                    if text_clean:
                        raw_lines.append(text_clean)
                        # bbox format: [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
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

        # Try PyTesseract as fallback
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

            if os.path.exists(image_path):
                img = Image.open(image_path)
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

        # Fallback to OpenCV Contour / Layout Text Region Analysis
        if os.path.exists(image_path):
            try:
                cv_img = cv2.imread(image_path)
                if cv_img is not None:
                    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
                    blur = cv2.GaussianBlur(gray, (5, 5), 0)
                    thresh = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
                    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    
                    for c in contours:
                        x, y, w, h = cv2.boundingRect(c)
                        if w > 20 and h > 10 and w < width * 0.95:
                            detected_boxes.append({
                                "text": "Text Segment",
                                "box": [int(x), int(y), int(w), int(h)],
                                "confidence": 0.85
                            })
            except Exception as e:
                logger.warning(f"OpenCV layout error: {e}")

        return "\n".join(raw_lines) if raw_lines else "No text extracted.", detected_boxes

    @classmethod
    def _parse_legal_metrology_fields(cls, raw_text: str, detected_boxes: List[Dict[str, Any]], img_w: int, img_h: int) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
        full_text_lower = raw_text.lower()

        fields: Dict[str, str] = {
            "commodity_name": "",
            "brand": "",
            "net_quantity": "",
            "mrp": "",
            "unit_sale_price": "",
            "mfg_date": "",
            "expiry_date": "",
            "manufacturer_details": "",
            "customer_care": "",
            "country_of_origin": "",
            "barcode": ""
        }

        # 1. Net Quantity (e.g. 500 g, 1 kg, 250 ml, 1 L, 10 N, 5 pcs)
        qty_match = re.search(r'(\b\d+(\.\d+)?\s*(?:g|kg|ml|l|ltr|litre|litres|liter|liters|grams|kilograms|n|pcs|units|tablets|capsules)\b)', raw_text, re.IGNORECASE)
        if qty_match:
            fields["net_quantity"] = qty_match.group(1).strip()
        else:
            for line in lines:
                if any(q in line.lower() for q in ["net qty", "net weight", "net quantity", "net wt", "net vol"]):
                    fields["net_quantity"] = line
                    break

        # 2. Maximum Retail Price (MRP)
        mrp_match = re.search(r'((?:mrp|m\.r\.p|max(?:imum)?\s*retail\s*price|price|₹|rs\.?)\s*[:.-]?\s*(?:rs\.?|₹)?\s*\d+(?:\.\d{2})?(?:\s*(?:\(?[^)\n]*incl[^)\n]*\)?))?)', raw_text, re.IGNORECASE)
        if mrp_match and mrp_match.group(1).strip():
            fields["mrp"] = mrp_match.group(1).strip()
        else:
            for line in lines:
                if any(m in line.lower() for m in ["mrp", "m.r.p", "₹", "rs.", "price"]):
                    fields["mrp"] = line
                    break

        # 3. Unit Sale Price (USP)
        usp_match = re.search(r'((?:usp|unit\s*sale\s*price|unit\s*price|₹\s*\/?\s*g|₹\s*\/?\s*ml|₹\s*\/?\s*kg|rs\.?\s*\/?\s*g)\s*[:.-]?\s*(?:rs\.?|₹)?\s*\d+(?:\.\d{2})?\s*(?:per|\/)\s*(?:g|kg|ml|l|unit|piece|n))', raw_text, re.IGNORECASE)
        if usp_match:
            fields["unit_sale_price"] = usp_match.group(1).strip()
        else:
            for line in lines:
                if "usp" in line.lower() or ("per" in line.lower() and any(u in line.lower() for u in ["/g", "/kg", "/ml", "/l", "per g", "per ml"])):
                    fields["unit_sale_price"] = line
                    break

        # 4. Mfg / Packing Date (MM/YYYY or DD/MM/YYYY or Month Year)
        mfg_match = re.search(r'((?:mfg|mfd|packed|pkd|manufacture[d]?|date\s*of\s*mfg|date\s*of\s*packing)\s*[:.-]?\s*(?:[0-3]?[0-9][\/\-.])?[0-1]?[0-9][\/\-.][1-2][0-9]{3}|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,.-]+[1-2][0-9]{3})', raw_text, re.IGNORECASE)
        if mfg_match:
            fields["mfg_date"] = mfg_match.group(1).strip()
        else:
            for line in lines:
                if any(k in line.lower() for k in ["mfg", "mfd", "pkd", "packed", "date"]):
                    fields["mfg_date"] = line
                    break

        # 5. Expiry Date / Best Before
        exp_match = re.search(r'((?:exp|expiry|use\s*before|best\s*before)\s*[:.-]?\s*(?:[0-3]?[0-9][\/\-.])?[0-1]?[0-9][\/\-.][1-2][0-9]{3}|\d+\s*months?)', raw_text, re.IGNORECASE)
        if exp_match:
            fields["expiry_date"] = exp_match.group(1).strip()

        # 6. Manufacturer Details
        for i, line in enumerate(lines):
            if any(k in line.lower() for k in ["mfd by", "manufactured by", "packed by", "marketed by", "imported by", "mfg by", "manufactured & packed by"]):
                combined_mfg = line
                if i + 1 < len(lines) and len(lines[i + 1]) > 5:
                    combined_mfg += f", {lines[i + 1]}"
                fields["manufacturer_details"] = combined_mfg
                break
        if not fields["manufacturer_details"]:
            for line in lines:
                if any(w in line.lower() for w in ["pvt ltd", "private limited", "ltd.", "industries", "industrial area", "estate", "plot no"]):
                    fields["manufacturer_details"] = line
                    break

        # 7. Customer Care / Consumer Helpline
        for line in lines:
            if any(c in line.lower() for c in ["consumer care", "customer care", "helpline", "toll free", "complaints", "feedback", "email:", "care@"]):
                fields["customer_care"] = line
                break

        # 8. Country of Origin
        for line in lines:
            if any(o in line.lower() for o in ["country of origin", "made in", "origin:"]):
                fields["country_of_origin"] = line
                break
        if not fields["country_of_origin"] and "india" in full_text_lower:
            fields["country_of_origin"] = "India"

        # 9. Generic Commodity Name & Brand
        if lines:
            fields["brand"] = lines[0][:40]
            fields["commodity_name"] = lines[1][:60] if len(lines) > 1 else lines[0][:60]

        # 10. Map Bounding Boxes for Visual Inspection
        mapped_boxes = []
        for db in detected_boxes[:15]:
            mapped_boxes.append({
                "field": "detected_text",
                "box": db["box"],
                "label": db.get("text", "Text Area")[:30]
            })

        return fields, mapped_boxes
