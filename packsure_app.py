"""
PackSure AI – Legal Metrology Compliance Checker (Single-File All-in-One Application)
Can be executed directly in VS Code with: py packsure_app.py

Features:
- Full Python FastAPI backend
- Embedded SQLite / SQLAlchemy database with auto-migration
- Real EasyOCR / PyTesseract OCR text extraction engine
- India Legal Metrology (Packaged Commodities) Rules, 2011 Compliance Engine
- Complete Single-Page Web Application UI (Tailwind CSS, Lucide icons, Dark Glassmorphism)
- PDF Certificate export engine via ReportLab
- Automatic browser opening on startup
"""

import os
import sys
import re
import uuid
import datetime
import webbrowser
import logging
from typing import Optional, List, Dict, Any, Tuple
from contextlib import asynccontextmanager

# Configure OpenMP, MKLDNN, and stdout encoding for Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, JSON, ForeignKey, select, desc
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PackSureAI")

# -----------------------------------------------------------------------------
# Configuration & Directories
# -----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "backend", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

DATABASE_URL = "sqlite+aiosqlite:///" + os.path.join(BASE_DIR, "backend", "packsure.db").replace("\\", "/")

# -----------------------------------------------------------------------------
# Database Models & Engine
# -----------------------------------------------------------------------------
engine = create_async_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), default="Packaged Food")
    brand = Column(String(100), nullable=True)
    barcode = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    scans = relationship("ScanResult", back_populates="product", cascade="all, delete-orphan")

class ScanResult(Base):
    __tablename__ = "scan_results"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    image_url = Column(String(500), nullable=False)
    image_filename = Column(String(255), nullable=False)
    extracted_data = Column(JSON, nullable=False)
    compliance_score = Column(Float, nullable=False)
    compliance_status = Column(String(50), nullable=False)
    risk_level = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    product = relationship("Product", back_populates="scans")
    reports = relationship("Report", back_populates="scan", cascade="all, delete-orphan")

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scan_results.id"), nullable=False)
    report_code = Column(String(50), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)
    violations_count = Column(Integer, default=0)
    warnings_count = Column(Integer, default=0)
    passed_count = Column(Integer, default=0)
    details = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    scan = relationship("ScanResult", back_populates="reports")

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# -----------------------------------------------------------------------------
# Configurable Legal Metrology Rules Registry & Engine
# -----------------------------------------------------------------------------
class RulesRegistry:
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), "backend", "app", "compliance", "rules_config.json")
    _cached_rules: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def get_rules(cls, category: str = "ALL") -> List[Dict[str, Any]]:
        if cls._cached_rules is None:
            if os.path.exists(cls.CONFIG_PATH):
                try:
                    with open(cls.CONFIG_PATH, "r", encoding="utf-8") as f:
                        cls._cached_rules = json.load(f).get("rules", [])
                except Exception:
                    cls._cached_rules = None
            if cls._cached_rules is None:
                cls._cached_rules = cls._default_rules()

        cat = (category or "ALL").strip().lower()
        return [r for r in cls._cached_rules if "all" in [c.lower() for c in r.get("applicable_categories", ["ALL"])] or cat in [c.lower() for c in r.get("applicable_categories", [])]]

    @classmethod
    def _default_rules(cls) -> List[Dict[str, Any]]:
        return [
            {"id": "RULE_6_1_A", "code": "LM-RULE-6-1-A", "title": "Manufacturer / Packer / Importer Address", "clause": "Rule 6(1)(a) PCR 2011", "field": "manufacturer_details", "weight": 15, "applicable_categories": ["ALL"]},
            {"id": "RULE_6_1_B", "code": "LM-RULE-6-1-B", "title": "Generic / Common Name of Commodity", "clause": "Rule 6(1)(b) PCR 2011", "field": "commodity_name", "weight": 15, "applicable_categories": ["ALL"]},
            {"id": "RULE_6_1_C", "code": "LM-RULE-6-1-C", "title": "Net Quantity & Standard Units", "clause": "Rule 6(1)(c) & Rule 7", "field": "net_quantity", "weight": 20, "applicable_categories": ["ALL"]},
            {"id": "RULE_6_1_D", "code": "LM-RULE-6-1-D", "title": "Month & Year of Manufacture / Packing", "clause": "Rule 6(1)(d) PCR 2011", "field": "mfg_date", "weight": 15, "applicable_categories": ["ALL"]},
            {"id": "RULE_6_1_E", "code": "LM-RULE-6-1-E", "title": "Maximum Retail Price (MRP)", "clause": "Rule 6(1)(e) PCR 2011", "field": "mrp", "weight": 15, "applicable_categories": ["ALL"]},
            {"id": "RULE_6_1_E_USP", "code": "LM-RULE-6-1-E-USP", "title": "Unit Sale Price (USP)", "clause": "Rule 6(1)(e) 2021 Amend", "field": "unit_sale_price", "weight": 10, "applicable_categories": ["ALL"]},
            {"id": "RULE_6_1_F", "code": "LM-RULE-6-1-F", "title": "Consumer Care Details", "clause": "Rule 6(1)(f) PCR 2011", "field": "customer_care", "weight": 10, "applicable_categories": ["ALL"]},
            {"id": "RULE_6_1_G", "code": "LM-RULE-6-1-G", "title": "Country of Origin & Importer Declaration", "clause": "Rule 6(1)(g) PCR 2011", "field": "country_of_origin", "weight": 10, "applicable_categories": ["Imported Goods"]},
            {"id": "RULE_6_1_H", "code": "LM-RULE-6-1-H", "title": "Best Before / Expiry Period", "clause": "Rule 6(1)(d) & FSSAI Mandate", "field": "expiry_date", "weight": 10, "applicable_categories": ["Food", "Cosmetics"]}
        ]

class LegalMetrologyRulesEngine:
    """
    Deterministic Rule-Based Legal Metrology Compliance Engine.
    Executes statutory checks under the Packaged Commodities Rules 2011.
    Each rule returns strictly one of: PASS, FAIL, WARNING, MANUAL REVIEW.
    """

    @classmethod
    def validate(cls, data: Dict[str, Any], category: str = "ALL") -> Dict[str, Any]:
        rules = RulesRegistry.get_rules(category)
        results = []
        earned = 0.0
        total = sum(r.get("weight", 10) for r in rules)

        for rule in rules:
            val = str(data.get(rule["field"], "") or "").strip()
            res = cls._check_rule(rule, val, data, category)
            score_earned = rule.get("weight", 10) * res["fraction"]
            earned += score_earned

            results.append({
                "rule_id": rule["id"],
                "rule_code": rule["code"],
                "title": rule["title"],
                "clause": rule["clause"],
                "description": rule.get("description", ""),
                "field": rule["field"],
                "value": val if val else None,
                "status": res["status"],  # PASS, FAIL, WARNING, MANUAL REVIEW
                "weight": rule.get("weight", 10),
                "score_earned": round(score_earned, 2),
                "finding": res["finding"],
                "remediation": res["remediation"]
            })

        final_score = round((earned / total) * 100.0, 1) if total > 0 else 0.0
        
        passed_count = sum(1 for r in results if r["status"] == "PASS")
        warnings_count = sum(1 for r in results if r["status"] == "WARNING")
        violations_count = sum(1 for r in results if r["status"] == "FAIL")
        manual_review_count = sum(1 for r in results if r["status"] == "MANUAL REVIEW")

        # Deterministic status verdict
        if violations_count > 0:
            status = "FAIL"
            risk = "HIGH" if violations_count >= 2 else "MEDIUM"
        elif manual_review_count > 0:
            status = "MANUAL REVIEW"
            risk = "MEDIUM"
        elif warnings_count > 0 or final_score < 85.0:
            status = "WARNING"
            risk = "LOW"
        else:
            status = "PASS"
            risk = "LOW"

        summary = cls._generate_summary(final_score, status, passed_count, warnings_count, violations_count, manual_review_count)

        return {
            "score": final_score,
            "status": status,
            "risk_level": risk,
            "passed_count": passed_count,
            "warnings_count": warnings_count,
            "violations_count": violations_count,
            "manual_review_count": manual_review_count,
            "summary": summary,
            "rule_checks": results
        }

    @classmethod
    def _check_rule(cls, rule: Dict[str, Any], val: str, full_data: Dict[str, Any], category: str) -> Dict[str, Any]:
        rule_id = rule["id"]
        if not val or val.lower() in ["none", "null", "n/a", "not declared"]:
            if rule_id == "RULE_6_1_G" and category != "Imported Goods":
                return {"status": "PASS", "fraction": 1.0, "finding": "Domestic commodity; foreign importer declaration not required.", "remediation": "Compliant."}
            return {
                "status": "FAIL", 
                "fraction": 0.0, 
                "finding": f"Statutory declaration for '{rule['title']}' is missing from packaging.", 
                "remediation": rule.get("remediation", "Print mandatory declaration prominently on principal display panel.")
            }

        v = val.lower().strip()

        if rule_id == "RULE_6_1_A":
            has_structure = any(k in v for k in ["mfd", "manufactured", "packed", "imported", "marketed", "ltd", "pvt", "corp", "inc", "co.", "llp"])
            has_location = any(k in v for k in ["street", "road", "industrial", "estate", "area", "dist", "state", "india", "pin", "plot", "building", "floor", "sector", "lane"])
            has_pincode = bool(re.search(r'\b[1-9][0-9]{5}\b', val))
            is_ambiguous = any(w in v for w in ["under license", "co-packed", "job worker", "third party", "contract pack"])

            if is_ambiguous:
                return {"status": "MANUAL REVIEW", "fraction": 0.7, "finding": f"Complex multi-party manufacturing or licensing statement detected: '{val}'.", "remediation": "Verify that both marketing entity and manufacturing premise addresses are declared as per Rule 6(1)(a)."}
            elif has_structure and (has_location or has_pincode) and len(val) >= 20:
                return {"status": "PASS", "fraction": 1.0, "finding": f"Valid manufacturer/packer name and registered address present: '{val}'.", "remediation": "Compliant."}
            elif has_structure and len(val) >= 10:
                return {"status": "WARNING", "fraction": 0.6, "finding": "Manufacturer/Packer name detected but complete premises address or postal PIN code appears partial.", "remediation": "Include full registered address with 6-digit postal PIN code as mandated under Rule 6(1)(a)."}
            return {"status": "FAIL", "fraction": 0.2, "finding": "Manufacturer detail lacks legally recognized company structure or postal address format.", "remediation": "Declare 'Manufactured & Packed By: [Company Name, Full Registered Address, PIN Code]'."}

        elif rule_id == "RULE_6_1_B":
            if any(term == v for term in ["product", "sample", "item", "goods", "unknown", "generic"]):
                return {"status": "FAIL", "fraction": 0.0, "finding": f"Declaration '{val}' is too vague.", "remediation": "Declare specific common or generic commodity name."}
            elif len(val) >= 3:
                return {"status": "PASS", "fraction": 1.0, "finding": f"Generic commodity name '{val}' clearly declared.", "remediation": "Compliant."}
            return {"status": "MANUAL REVIEW", "fraction": 0.5, "finding": f"Extracted commodity string '{val}' is short or potentially truncated by OCR.", "remediation": "Inspect principal display panel to verify full commodity name."}

        elif rule_id == "RULE_6_1_C":
            if any(re.search(rf'\b{u}\b', v) for u in ["lbs", "lb", "oz", "ounce", "fl oz", "fluid oz", "gallon"]):
                return {"status": "FAIL", "fraction": 0.0, "finding": f"Non-metric unit detected in net quantity: '{val}'. Prohibited under Rule 7.", "remediation": "Replace non-metric measures (lbs, oz) exclusively with standard metric units (g, kg, ml, l, N)."}
            metric_match = re.search(r'(\d+(\.\d+)?)\s*(g|kg|ml|l|ltr|grams|kilograms|n|pcs|units)\b', v)
            if metric_match:
                has_space = bool(re.search(r'\d+\s+[a-zA-Z]', metric_match.group(0)))
                if has_space:
                    return {"status": "PASS", "fraction": 1.0, "finding": f"Net quantity '{val}' in standard metric units with numeral spacing.", "remediation": "Compliant."}
                return {"status": "WARNING", "fraction": 0.85, "finding": f"Net quantity '{val}' valid, but lacks mandated whitespace separation between numeral and unit symbol.", "remediation": "Insert a space between numeral and unit symbol (e.g. '350 g' instead of '350g')."}
            elif any(c.isdigit() for c in val):
                return {"status": "MANUAL REVIEW", "fraction": 0.4, "finding": f"Numeral detected in quantity field ('{val}') but metric unit symbol is ambiguous.", "remediation": "Confirm physical packaging specifies standard metric unit (g, kg, ml, l, N)."}
            return {"status": "FAIL", "fraction": 0.0, "finding": f"Invalid net quantity declaration '{val}'.", "remediation": "Specify net quantity in SI metric units prescribed under Rule 7 & 8."}

        elif rule_id == "RULE_6_1_D":
            date_match = re.search(r'(\b(0[1-9]|1[0-2])[\/\-.](20[1-3][0-9]|[1-3][0-9])\b|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,.-]+(20[1-3][0-9]|[1-3][0-9])\b)', v)
            if date_match:
                return {"status": "PASS", "fraction": 1.0, "finding": f"Manufacture/Packing date '{val}' in valid calendar format.", "remediation": "Compliant."}
            elif any(y in val for y in ["2023", "2024", "2025", "2026", "2027", "2028"]):
                return {"status": "WARNING", "fraction": 0.6, "finding": f"Year detected in date declaration '{val}', but month format is non-standard.", "remediation": "Format date strictly as 'Mfg Date: MM/YYYY' (e.g., 08/2026)."}
            elif any(w in v for w in ["best before", "expiry", "use by", "months"]):
                return {"status": "MANUAL REVIEW", "fraction": 0.5, "finding": f"Relative date or expiry string found ('{val}') instead of explicit manufacturing/packing date.", "remediation": "Ensure both manufacturing date (MM/YYYY) and expiry timeframe are declared."}
            return {"status": "FAIL", "fraction": 0.0, "finding": f"Date declaration '{val}' is invalid or missing month and year.", "remediation": "Print manufacturing month & year prominently as 'Mfg Date: MM/YYYY'."}

        elif rule_id == "RULE_6_1_E":
            has_tax = any(t in v for t in ["incl", "inclusive", "tax", "taxes", "all taxes"])
            has_mrp_prefix = any(m in v for m in ["mrp", "m.r.p", "max retail price", "maximum retail price", "rs", "₹", "inr"])
            has_digit = any(c.isdigit() for c in val)
            if has_mrp_prefix and has_digit and has_tax:
                return {"status": "PASS", "fraction": 1.0, "finding": f"MRP declaration '{val}' inclusive of all taxes.", "remediation": "Compliant."}
            elif has_mrp_prefix and has_digit:
                return {"status": "WARNING", "fraction": 0.75, "finding": f"MRP numeric price found in '{val}', but mandatory phrase '(inclusive of all taxes)' is missing.", "remediation": "Append '(inclusive of all taxes)' alongside MRP."}
            elif has_digit:
                return {"status": "MANUAL REVIEW", "fraction": 0.4, "finding": f"Numeric value '{val}' detected but lacking standardized 'MRP' or '₹' prefix.", "remediation": "Verify whether price declaration displays clear 'MRP Rs. XX' prefix."}
            return {"status": "FAIL", "fraction": 0.0, "finding": f"MRP declaration '{val}' lacks price numerals.", "remediation": "Declare 'MRP Rs. XX.XX (inclusive of all taxes)' prominently on the principal display panel."}

        elif rule_id == "RULE_6_1_E_USP":
            has_usp = any(p in v for p in ["per g", "per kg", "per ml", "per l", "per unit", "/g", "/kg", "/ml", "/l", "/unit", "usp"])
            has_digit = any(c.isdigit() for c in val)
            if has_usp and has_digit:
                return {"status": "PASS", "fraction": 1.0, "finding": f"Unit Sale Price '{val}' declared as per 2021 Amendments.", "remediation": "Compliant."}
            elif has_digit:
                return {"status": "WARNING", "fraction": 0.5, "finding": f"Unit price value '{val}' found but unit measure (per g/kg/ml) is unclear.", "remediation": "Declare USP clearly (e.g., '₹ 1.10 per g' or '₹ 50 per kg')."}
            return {"status": "MANUAL REVIEW", "fraction": 0.3, "finding": "Unit Sale Price (USP) was not detected. Exempt only for packages containing <= 10g or <= 10ml.", "remediation": "Check package net quantity; if > 10g/ml, declare Unit Sale Price adjacent to MRP."}

        elif rule_id == "RULE_6_1_F":
            has_email = "@" in val or "email" in v
            digits_count = len(re.findall(r'\d', val))
            has_phone = digits_count >= 8 or any(w in v for w in ["helpline", "toll free", "toll-free", "1800", "phone", "tel"])
            if has_email and has_phone:
                return {"status": "PASS", "fraction": 1.0, "finding": f"Complete consumer care email and helpline number declared: '{val}'.", "remediation": "Compliant."}
            elif has_email or has_phone:
                return {"status": "WARNING", "fraction": 0.7, "finding": f"Partial consumer care contact: '{val}'.", "remediation": "Provide both telephone helpline and active email address under 'Customer Care Cell'."}
            elif any(w in v for w in ["care", "customer", "complaint", "feedback", "contact"]):
                return {"status": "MANUAL REVIEW", "fraction": 0.4, "finding": f"Consumer care reference detected ('{val}') but requires visual verification.", "remediation": "Ensure executive contact address, email, and helpline number are fully legible."}
            return {"status": "FAIL", "fraction": 0.0, "finding": "Consumer care contact details are missing.", "remediation": "Include 'For Consumer Complaints: Contact Executive at [Address], Tel: [No], Email: [Mail]'."}

        elif rule_id == "RULE_6_1_G":
            has_origin = any(w in v for w in ["india", "origin", "made in", "product of", "imported from"]) or len(val) > 2
            importer_val = str(full_data.get("importer", "") or "").strip().lower()
            has_importer = len(importer_val) > 3 and importer_val != "none"
            if category == "Imported Goods":
                if has_origin and has_importer:
                    return {"status": "PASS", "fraction": 1.0, "finding": f"Country of origin ('{val}') and importer ('{importer_val}') declared.", "remediation": "Compliant."}
                elif has_origin:
                    return {"status": "WARNING", "fraction": 0.6, "finding": f"Country of origin '{val}' declared, but registered Indian importer name/address is missing.", "remediation": "Mandatory to declare registered Importer details for foreign goods."}
                return {"status": "FAIL", "fraction": 0.0, "finding": "Imported commodity missing mandatory Country of Origin declaration.", "remediation": "Declare 'Country of Origin: [Country]' on package."}
            else:
                return {"status": "PASS", "fraction": 1.0, "finding": f"Origin declared as '{val}'.", "remediation": "Compliant."}

        elif rule_id == "RULE_6_1_H":
            has_exp_pattern = bool(re.search(r'(\b(0[1-9]|1[0-2])[\/\-.](20[1-3][0-9]|[1-3][0-9])\b|\d+\s*months?)', v))
            has_exp_kw = any(w in v for w in ["best before", "expiry", "exp", "use by", "months from mfg", "months from packaging"])
            if has_exp_pattern and has_exp_kw:
                return {"status": "PASS", "fraction": 1.0, "finding": f"Best Before / Expiry declaration '{val}' complies with regulations.", "remediation": "Compliant."}
            elif has_exp_pattern or has_exp_kw:
                return {"status": "PASS", "fraction": 1.0, "finding": f"Expiry timeframe '{val}' present.", "remediation": "Compliant."}
            return {"status": "FAIL", "fraction": 0.0, "finding": "Mandatory Best Before / Expiry timeframe missing for perishable/cosmetic commodity.", "remediation": "Declare 'Best Before XX Months from Packaging' or 'Expiry Date: MM/YYYY'."}

        return {"status": "MANUAL REVIEW", "fraction": 0.5, "finding": f"Declaration '{val}' requires visual verification.", "remediation": "Inspect physical artwork for statutory alignment."}

    @classmethod
    def _generate_summary(cls, score: float, status: str, passed: int, warnings: int, violations: int, manual_review: int) -> str:
        if status == "PASS":
            return f"Product packaging demonstrates high statutory compliance ({score}%) under the Legal Metrology (Packaged Commodities) Rules, 2011. All {passed} evaluated declarations satisfy mandatory formatting and unit standards."
        elif status == "MANUAL REVIEW":
            return f"Statutory audit scored {score}%. {manual_review} declaration(s) flagged for MANUAL REVIEW due to complex licensing structures or ambiguous packaging phrases. Inspector verification recommended."
        elif status == "WARNING":
            return f"Statutory audit scored {score}% with {warnings} minor warning(s). Key declarations exist but contain minor discrepancies that require rectification."
        else:
            return f"Statutory audit FAILED with score {score}%. Found {violations} statutory violation(s) under the Legal Metrology Act 2009 & Packaged Commodities Rules 2011. Remediation required before market distribution."

# -----------------------------------------------------------------------------
# Real OCR Engine (EasyOCR + PyTesseract + Layout)
# -----------------------------------------------------------------------------
_paddleocr_reader = None
_easyocr_reader = None

def get_paddle_reader():
    global _paddleocr_reader
    if _paddleocr_reader is None:
        try:
            from paddleocr import PaddleOCR
            _paddleocr_reader = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False, show_log=False)
        except Exception:
            _paddleocr_reader = False
    return _paddleocr_reader if _paddleocr_reader is not False else None

def get_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr
            _easyocr_reader = easyocr.Reader(['en'], gpu=False)
        except Exception:
            _easyocr_reader = False
    return _easyocr_reader if _easyocr_reader is not False else None

class OCREngine:
    @classmethod
    async def process_image(cls, image_path: str) -> Dict[str, Any]:
        width, height = 800, 600
        try:
            with Image.open(image_path) as img:
                width, height = img.size
        except Exception:
            pass

        # OpenCV Preprocessing
        preprocessed_path = image_path
        try:
            cv_img = cv2.imread(image_path)
            if cv_img is not None:
                gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
                thresh = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                    cv2.THRESH_BINARY, 11, 2
                )
                preprocessed_path = image_path.replace(".", "_preprocessed.")
                cv2.imwrite(preprocessed_path, thresh)
        except Exception:
            pass

        raw_lines = []
        detected_boxes = []

        # Try PaddleOCR
        paddle_reader = get_paddle_reader()
        if paddle_reader and os.path.exists(preprocessed_path):
            try:
                results = paddle_reader.ocr(preprocessed_path, cls=True)
                if results and len(results) > 0:
                    page = results[0]
                    rec_texts = page.get("rec_texts", [])
                    rec_scores = page.get("rec_scores", [])
                    rec_boxes = page.get("rec_boxes", [])
                    
                    for text, score, box in zip(rec_texts, rec_scores, rec_boxes):
                        t = text.strip()
                        if t:
                            raw_lines.append(t)
                            min_x, min_y, max_x, max_y = box
                            w = max_x - min_x
                            h = max_y - min_y
                            detected_boxes.append({
                                "text": t,
                                "box": [int(min_x), int(min_y), int(w), int(h)],
                                "confidence": float(score)
                            })
            except Exception:
                pass

        # Try EasyOCR
        if not raw_lines:
            reader = get_reader()
            path_to_scan = image_path if os.path.exists(image_path) else preprocessed_path
            if reader and os.path.exists(path_to_scan):
                try:
                    results = reader.readtext(path_to_scan)
                    for bbox, text, conf in results:
                        t = text.strip()
                        if t:
                            raw_lines.append(t)
                            xs = [pt[0] for pt in bbox]
                            ys = [pt[1] for pt in bbox]
                            min_x, max_x = int(min(xs)), int(max(xs))
                            min_y, max_y = int(min(ys)), int(max(ys))
                            detected_boxes.append({
                                "text": t,
                                "box": [min_x, min_y, max_x - min_x, max_y - min_y],
                                "confidence": float(conf)
                            })
                except Exception:
                    pass

        # Fallback to pytesseract
        if not raw_lines:
            try:
                import pytesseract
                path_to_scan = image_path if os.path.exists(image_path) else preprocessed_path
                data = pytesseract.image_to_data(Image.open(path_to_scan), output_type=pytesseract.Output.DICT)
                n_boxes = len(data['text'])
                for i in range(n_boxes):
                    t = data['text'][i].strip()
                    if t:
                        raw_lines.append(t)
                        detected_boxes.append({
                            "text": t,
                            "box": [data['left'][i], data['top'][i], data['width'][i], data['height'][i]],
                            "confidence": float(data['conf'][i]) / 100.0
                        })
            except Exception:
                pass

        # Cleanup preprocessed image
        if preprocessed_path != image_path and os.path.exists(preprocessed_path):
            try:
                os.remove(preprocessed_path)
            except Exception:
                pass

        raw_text = "\n".join(raw_lines) if raw_lines else "No text detected."
        fields = cls._parse_fields(raw_text, raw_lines)
        detected_category = cls.detect_category(raw_text, fields)
        return {
            "raw_text": raw_text, 
            "fields": fields, 
            "detected_category": detected_category,
            "image_dimensions": {"width": width, "height": height}, 
            "bounding_boxes": detected_boxes
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
    def _parse_fields(cls, raw_text: str, lines: List[str]) -> Dict[str, str]:
        fields = {
            "commodity_name": "", "brand": "", "manufacturer_details": "", "address": "",
            "mrp": "", "net_quantity": "", "mfg_date": "", "expiry_date": "",
            "importer": "", "country_of_origin": "", "customer_care": "", "unit_sale_price": ""
        }
        
        raw_lower = raw_text.lower()

        def find_after_prefix(keywords: List[str], text_str: str) -> str:
            for line in text_str.split("\n"):
                for kw in keywords:
                    if kw.lower() in line.lower():
                        idx = line.lower().find(kw.lower())
                        extracted = line[idx + len(kw):].strip(" :.-=,")
                        if extracted and len(extracted) > 1:
                            return extracted
            return ""

        # Extract brand
        brand_keywords = ["brand name", "brand", "tm", "regd tm"]
        fields["brand"] = find_after_prefix(brand_keywords, raw_text)
        if not fields["brand"] and lines:
            for l in lines[:3]:
                if "brand" in l.lower():
                    fields["brand"] = l.split(":")[-1].strip()
                    break
            if not fields["brand"] and lines:
                fields["brand"] = lines[0][:40]

        # Extract product/commodity name
        commodity_keywords = ["commodity name", "commodity", "product name", "product"]
        fields["commodity_name"] = find_after_prefix(commodity_keywords, raw_text)
        if not fields["commodity_name"] and len(lines) > 1:
            for l in lines[1:4]:
                if not any(c.isdigit() for c in l) and len(l) > 5:
                    fields["commodity_name"] = l[:60]
                    break
            if not fields["commodity_name"]:
                fields["commodity_name"] = lines[1][:60] if len(lines) > 1 else lines[0][:60]

        # Extract manufacturer name
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

        # Extract address
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

        # Extract importer
        importer_keywords = ["imported by", "importer", "imported & marketed by", "import details"]
        fields["importer"] = find_after_prefix(importer_keywords, raw_text)
        if not fields["importer"]:
            for l in lines:
                if "imported" in l.lower() or "importer" in l.lower():
                    fields["importer"] = l.split(":")[-1].strip()
                    break

        # Country of origin
        origin_keywords = ["country of origin", "made in", "origin", "product of"]
        fields["country_of_origin"] = find_after_prefix(origin_keywords, raw_text)
        if not fields["country_of_origin"]:
            for l in lines:
                if "origin" in l.lower() or "made in" in l.lower():
                    fields["country_of_origin"] = l.split(":")[-1].strip()
                    break
        if not fields["country_of_origin"] and "india" in raw_lower:
            fields["country_of_origin"] = "India"

        # Customer care
        cc_keywords = ["customer care", "consumer care", "care cell", "complaints", "feedback", "helpline", "toll free", "toll-free"]
        fields["customer_care"] = find_after_prefix(cc_keywords, raw_text)
        if not fields["customer_care"]:
            for l in lines:
                if any(k in l.lower() for k in ["care", "customer", "helpline", "email", "@", "complaint"]):
                    fields["customer_care"] = l
                    break

        # MRP
        mrp_match = re.search(r'((?:mrp|m\.r\.p|price|₹|rs\.?)\s*[:.-]?\s*(?:rs\.?|₹)?\s*\d+(?:\.\d{2})?(?:\s*(?:\(?[^)\n]*incl[^)\n]*\)?))?)', raw_text, re.I)
        if mrp_match and mrp_match.group(1).strip():
            fields["mrp"] = mrp_match.group(1).strip()

        # Net Quantity
        qty_match = re.search(r'(\b\d+(\.\d+)?\s*(?:g|kg|ml|l|ltr|grams|n|pcs|units)\b)', raw_text, re.I)
        if qty_match:
            fields["net_quantity"] = qty_match.group(1).strip()

        # Mfg Date
        mfg_match = re.search(r'((?:mfg|mfd|packed|pkd)\s*[:.-]?\s*(?:[0-3]?[0-9][\/\-.])?[0-1]?[0-9][\/\-.][1-2][0-9]{3}|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,.-]+[1-2][0-9]{3})', raw_text, re.I)
        if mfg_match:
            fields["mfg_date"] = mfg_match.group(1).strip()

        # Best before / Expiry
        exp_keywords = ["best before", "expiry date", "exp date", "expiry", "exp", "use by"]
        fields["expiry_date"] = find_after_prefix(exp_keywords, raw_text)
        if not fields["expiry_date"]:
            exp_match = re.search(r'((?:exp|expiry|use\s*before|best\s*before)\s*[:.-]?\s*(?:[0-3]?[0-9][\/\-.])?[0-1]?[0-9][\/\-.][1-2][0-9]{3}|\d+\s*months?)', raw_text, re.I)
            if exp_match:
                fields["expiry_date"] = exp_match.group(1).strip()

        # Unit sale price
        usp_match = re.search(r'((?:usp|unit\s*price|₹\s*\/?\s*g|rs\.?\s*\/?\s*g)\s*[:.-]?\s*(?:rs\.?|₹)?\s*\d+(?:\.\d{2})?\s*(?:per|\/)\s*(?:g|kg|ml|l|unit|piece|n))', raw_text, re.I)
        if usp_match:
            fields["unit_sale_price"] = usp_match.group(1).strip()

        return fields

# -----------------------------------------------------------------------------
# PDF Report Generator
# -----------------------------------------------------------------------------
class ReportGenerator:
    @classmethod
    def generate_pdf(cls, report_code: str, product_name: str, score: float, status: str, risk: str, summary: str, rule_checks: list, output_path: str):
        doc = SimpleDocTemplate(output_path, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()
        
        t_style = ParagraphStyle('T', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, textColor=colors.HexColor("#0F172A"))
        b_style = ParagraphStyle('B', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, textColor=colors.HexColor("#334155"))
        
        story = [
            Paragraph("PackSure AI – Legal Metrology Compliance Certificate", t_style),
            Paragraph(f"Report Code: {report_code} | Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", b_style),
            Spacer(1, 10),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=12),
        ]
        
        st_col = "#10B981" if status == "PASS" else ("#F59E0B" if status == "WARNING" else "#EF4444")
        overview = [
            [Paragraph("<b>Product Name:</b>", b_style), Paragraph(product_name, b_style), Paragraph("<b>Score:</b>", b_style), Paragraph(f"<b>{score:.1f}%</b>", b_style)],
            [Paragraph("<b>Status:</b>", b_style), Paragraph(f"<font color='{st_col}'><b>{status}</b></font>", b_style), Paragraph("<b>Risk:</b>", b_style), Paragraph(risk, b_style)]
        ]
        t = Table(overview, colWidths=[110, 180, 110, 140])
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")), ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")), ('PADDING', (0,0), (-1,-1), 6)]))
        story.append(t)
        story.append(Spacer(1, 12))
        
        story.append(Paragraph("<b>Executive Summary:</b> " + summary, b_style))
        story.append(Spacer(1, 12))
        
        table_data = [["Rule Clause", "Mandatory Declaration", "Status", "Finding & Remediation"]]
        for r in rule_checks:
            sc = "#10B981" if r.get("status") == "PASS" else ("#F59E0B" if r.get("status") == "WARNING" else "#EF4444")
            table_data.append([
                Paragraph(f"<b>{r.get('rule_code')}</b>", b_style),
                Paragraph(f"<b>{r.get('title')}</b><br/>{r.get('value') or 'Missing'}", b_style),
                Paragraph(f"<font color='{sc}'><b>{r.get('status')}</b></font>", b_style),
                Paragraph(f"{r.get('finding')}<br/><b>Action:</b> {r.get('remediation')}", b_style)
            ])
        rt = Table(table_data, colWidths=[110, 140, 60, 230])
        rt.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F172A")), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ('PADDING', (0,0), (-1,-1), 5)]))
        story.append(rt)
        
        doc.build(story)
        return output_path

# -----------------------------------------------------------------------------
# FastAPI Application & Lifespan
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="PackSure AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# -----------------------------------------------------------------------------
# REST API Endpoints
# -----------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    return {"status": "online", "engine": "PaddleOCR + Legal Metrology Rules 2011", "version": "1.0.0"}

@app.get("/api/compliance/rules")
async def get_rules(category: Optional[str] = None):
    rules = RulesRegistry.get_rules(category or "ALL")
    return {
        "rules": rules,
        "total_rules": len(rules),
        "reference": "Legal Metrology (Packaged Commodities) Rules, 2011",
        "statute": "Legal Metrology Act 2009 & Packaged Commodities Rules 2011"
    }

@app.post("/api/ocr")
async def run_dedicated_ocr(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    unique_fn = f"ocr_{uuid.uuid4().hex[:8]}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, unique_fn)
    
    with open(saved_path, "wb") as f:
        f.write(await file.read())

    try:
        ocr_result = await OCREngine.process_image(saved_path)
    finally:
        if os.path.exists(saved_path):
            try:
                os.remove(saved_path)
            except Exception:
                pass

    return ocr_result

@app.post("/api/scan")
async def scan(
    file: UploadFile = File(...),
    product_name: Optional[str] = Form(None),
    category: Optional[str] = Form("Auto-Detect"),
    db: AsyncSession = Depends(get_db)
):
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    unique_fn = f"scan_{uuid.uuid4().hex[:8]}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, unique_fn)
    
    with open(saved_path, "wb") as f:
        f.write(await file.read())

    # OCR + Rules Evaluation
    ocr_res = await OCREngine.process_image(saved_path)
    fields = ocr_res["fields"]
    if product_name and product_name.strip():
        fields["commodity_name"] = product_name.strip()

    # Category Detection
    detected_cat = ocr_res.get("detected_category", "Food")
    clean_cat = category.strip() if category and category.strip() else ""
    if not clean_cat or clean_cat.lower() in ["auto-detect", "auto", "packaged food", "general"]:
        final_category = detected_cat
    else:
        final_category = clean_cat

    # Combine manufacturer details, address and importer for rule evaluation
    eval_fields = fields.copy()
    mfg_parts = []
    if fields.get("manufacturer_details"): mfg_parts.append(fields["manufacturer_details"])
    if fields.get("address"): mfg_parts.append(fields["address"])
    if fields.get("importer"): mfg_parts.append(f"Importer: {fields['importer']}")
    eval_fields["manufacturer_details"] = ", ".join(mfg_parts)

    eval_res = LegalMetrologyRulesEngine.validate(eval_fields, category=final_category)
    
    p_name = fields.get("commodity_name") or product_name or "Packaged Product"
    p_brand = fields.get("brand") or "Brand"
    
    summary = eval_res["summary"]
    
    product = Product(name=f"{p_brand} - {p_name}", category=final_category, brand=p_brand)
    db.add(product)
    await db.flush()

    extracted_payload = {
        "fields": fields,
        "category": final_category,
        "detected_category": detected_cat,
        "raw_text": ocr_res["raw_text"],
        "bounding_boxes": ocr_res["bounding_boxes"],
        "rule_checks": eval_res["rule_checks"],
        "summary": summary,
        "manual_review_count": eval_res.get("manual_review_count", 0)
    }

    scan_res = ScanResult(
        product_id=product.id,
        image_url=f"/uploads/{unique_fn}",
        image_filename=unique_fn,
        extracted_data=extracted_payload,
        compliance_score=eval_res["score"],
        compliance_status=eval_res["status"],
        risk_level=eval_res["risk_level"]
    )
    db.add(scan_res)
    await db.flush()

    report_code = f"PSR-{uuid.uuid4().hex[:6].upper()}"
    report = Report(
        scan_id=scan_res.id,
        report_code=report_code,
        title=f"Legal Metrology Audit - {p_name}",
        summary=summary,
        violations_count=eval_res["violations_count"],
        warnings_count=eval_res["warnings_count"],
        passed_count=eval_res["passed_count"],
        details=scan_res.extracted_data
    )
    db.add(report)
    await db.commit()

    return {
        "id": report.id,
        "scan_id": scan_res.id,
        "report_code": report_code,
        "product_name": product.name,
        "category": product.category,
        "detected_category": detected_cat,
        "compliance_score": scan_res.compliance_score,
        "compliance_status": scan_res.compliance_status,
        "risk_level": scan_res.risk_level,
        "passed_count": report.passed_count,
        "warnings_count": report.warnings_count,
        "violations_count": report.violations_count,
        "manual_review_count": eval_res.get("manual_review_count", 0),
        "summary": summary,
        "details": scan_res.extracted_data
    }

@app.post("/api/scan/update")
async def update_scan(
    report_id: int = Form(...),
    commodity_name: Optional[str] = Form(None),
    brand: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    manufacturer_details: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    mrp: Optional[str] = Form(None),
    net_quantity: Optional[str] = Form(None),
    mfg_date: Optional[str] = Form(None),
    expiry_date: Optional[str] = Form(None),
    importer: Optional[str] = Form(None),
    country_of_origin: Optional[str] = Form(None),
    customer_care: Optional[str] = Form(None),
    unit_sale_price: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Report).where(Report.id == report_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    stmt = select(ScanResult).where(ScanResult.id == report.scan_id)
    result = await db.execute(stmt)
    scan_result = result.scalar_one_or_none()
    if not scan_result:
        raise HTTPException(status_code=404, detail="Scan result not found")

    fields = scan_result.extracted_data.get("fields", {})

    if commodity_name is not None: fields["commodity_name"] = commodity_name
    if brand is not None: fields["brand"] = brand
    if manufacturer_details is not None: fields["manufacturer_details"] = manufacturer_details
    if address is not None: fields["address"] = address
    if mrp is not None: fields["mrp"] = mrp
    if net_quantity is not None: fields["net_quantity"] = net_quantity
    if mfg_date is not None: fields["mfg_date"] = mfg_date
    if expiry_date is not None: fields["expiry_date"] = expiry_date
    if importer is not None: fields["importer"] = importer
    if country_of_origin is not None: fields["country_of_origin"] = country_of_origin
    if customer_care is not None: fields["customer_care"] = customer_care
    if unit_sale_price is not None: fields["unit_sale_price"] = unit_sale_price

    existing_cat = scan_result.extracted_data.get("category", "Food")
    updated_cat = category.strip() if category and category.strip() else existing_cat

    # Combine manufacturer info for legal rules validation
    eval_fields = fields.copy()
    mfg_parts = []
    if fields.get("manufacturer_details"): mfg_parts.append(fields["manufacturer_details"])
    if fields.get("address"): mfg_parts.append(fields["address"])
    if fields.get("importer"): mfg_parts.append(f"Importer: {fields['importer']}")
    eval_fields["manufacturer_details"] = ", ".join(mfg_parts)

    eval_res = LegalMetrologyRulesEngine.validate(eval_fields, category=updated_cat)

    summary = eval_res["summary"]

    extracted_payload = {
        "fields": fields,
        "category": updated_cat,
        "detected_category": scan_result.extracted_data.get("detected_category", updated_cat),
        "raw_text": scan_result.extracted_data.get("raw_text", ""),
        "bounding_boxes": scan_result.extracted_data.get("bounding_boxes", []),
        "rule_checks": eval_res["rule_checks"],
        "summary": summary,
        "manual_review_count": eval_res.get("manual_review_count", 0)
    }

    scan_result.extracted_data = extracted_payload
    scan_result.compliance_score = eval_res["score"]
    scan_result.compliance_status = eval_res["status"]
    scan_result.risk_level = eval_res["risk_level"]

    report.summary = summary
    report.violations_count = eval_res["violations_count"]
    report.warnings_count = eval_res["warnings_count"]
    report.passed_count = eval_res["passed_count"]
    report.details = extracted_payload

    stmt = select(Product).where(Product.id == scan_result.product_id)
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()
    if product:
        p_name = fields.get("commodity_name") or "Product"
        p_brand = fields.get("brand") or "Generic Brand"
        product.name = f"{p_brand} - {p_name}"
        product.brand = p_brand
        product.category = updated_cat

    await db.commit()

    # Re-generate PDF
    pdf_filename = f"Report_{report.report_code}.pdf"
    pdf_path = os.path.join(UPLOAD_DIR, pdf_filename)
    if os.path.exists(pdf_path):
        try:
            os.remove(pdf_path)
        except Exception:
            pass

    ReportGenerator.generate_pdf(
        report_code=report.report_code,
        product_name=product.name if product else report.title,
        score=scan_result.compliance_score,
        status=scan_result.compliance_status,
        risk=scan_result.risk_level,
        summary=summary,
        rule_checks=eval_res["rule_checks"],
        output_path=pdf_path
    )

    return {
        "id": report.id,
        "scan_id": scan_result.id,
        "report_code": report.report_code,
        "product_name": product.name if product else report.title,
        "category": product.category if product else updated_cat,
        "detected_category": scan_result.extracted_data.get("detected_category", updated_cat),
        "compliance_score": scan_result.compliance_score,
        "compliance_status": scan_result.compliance_status,
        "risk_level": scan_result.risk_level,
        "passed_count": report.passed_count,
        "warnings_count": report.warnings_count,
        "violations_count": report.violations_count,
        "manual_review_count": eval_res.get("manual_review_count", 0),
        "summary": summary,
        "details": scan_result.extracted_data
    }

@app.get("/api/reports")
async def list_reports(db: AsyncSession = Depends(get_db)):
    stmt = select(Report, ScanResult, Product).join(ScanResult, Report.scan_id == ScanResult.id).outerjoin(Product, ScanResult.product_id == Product.id).order_by(desc(Report.created_at))
    rows = (await db.execute(stmt)).all()
    reports = []
    for rep, scan, prod in rows:
        reports.append({
            "id": rep.id,
            "report_code": rep.report_code,
            "product_name": prod.name if prod else rep.title,
            "category": prod.category if prod else "General",
            "compliance_score": scan.compliance_score,
            "compliance_status": scan.compliance_status,
            "risk_level": scan.risk_level,
            "passed_count": rep.passed_count,
            "warnings_count": rep.warnings_count,
            "violations_count": rep.violations_count,
            "summary": rep.summary,
            "created_at": rep.created_at.isoformat()
        })
    return {"reports": reports, "total": len(reports)}

@app.get("/api/reports/{report_id}/pdf")
async def download_pdf(report_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Report, ScanResult, Product).join(ScanResult, Report.scan_id == ScanResult.id).outerjoin(Product, ScanResult.product_id == Product.id).where(Report.id == report_id)
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    rep, scan, prod = row
    pdf_path = os.path.join(UPLOAD_DIR, f"Report_{rep.report_code}.pdf")
    ReportGenerator.generate_pdf(
        report_code=rep.report_code,
        product_name=prod.name if prod else rep.title,
        score=scan.compliance_score,
        status=scan.compliance_status,
        risk=scan.risk_level,
        summary=rep.summary,
        rule_checks=rep.details.get("rule_checks", []),
        output_path=pdf_path
    )
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"Report_{rep.report_code}.pdf")

# -----------------------------------------------------------------------------
# Embedded Web Application Interface (HTML + Tailwind + JavaScript)
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index_ui():
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PackSure AI – Legal Metrology Compliance Checker</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/lucide@latest"></script>
  <style>
    body { font-family: 'Inter', sans-serif; }
    .glass-card { background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.08); }
    .badge-pass { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); font-weight: 600; padding: 2px 8px; border-radius: 9999px; font-size: 11px; }
    .badge-warning { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); font-weight: 600; padding: 2px 8px; border-radius: 9999px; font-size: 11px; }
    .badge-fail { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); font-weight: 600; padding: 2px 8px; border-radius: 9999px; font-size: 11px; }
    .badge-manual-review, .badge-manual_review, .badge-needs_review, .badge-needs-review { background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); font-weight: 600; padding: 2px 8px; border-radius: 9999px; font-size: 11px; }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col selection:bg-cyan-500 selection:text-white">

  <!-- Navbar -->
  <header class="sticky top-0 z-50 glass-card border-b border-slate-800">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center gap-3 cursor-pointer" onclick="switchTab('home')">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
          <i data-lucide="shield-check" class="w-6 h-6 text-white"></i>
        </div>
        <div>
          <span class="font-black text-xl text-white tracking-tight">PackSure <span class="text-cyan-400">AI</span></span>
          <span class="text-[10px] font-bold uppercase ml-2 px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">PCR 2011</span>
        </div>
      </div>

      <nav class="flex items-center gap-2">
        <button onclick="switchTab('home')" id="btn-home" class="px-3.5 py-2 rounded-lg text-sm font-medium bg-slate-800 text-cyan-400 border border-cyan-500/30">PackSure AI</button>
        <button onclick="switchTab('scan')" id="btn-scan" class="px-3.5 py-2 rounded-lg text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-850">Scan Product</button>
        <button onclick="switchTab('reports')" id="btn-reports" class="px-3.5 py-2 rounded-lg text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-850">View Reports</button>
      </nav>
    </div>
  </header>

  <!-- Main Content Area -->
  <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 pt-8 pb-16">
    
    <!-- Tab 1: Home View -->
    <div id="view-home" class="space-y-12">
      <section class="glass-card p-8 sm:p-12 rounded-3xl border border-slate-800 relative overflow-hidden">
        <div class="max-w-2xl space-y-6">
          <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 text-xs font-semibold">
            <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>
            <span>Real Deep Learning OCR & Legal Metrology Act Rules</span>
          </div>
          <h1 class="text-4xl sm:text-5xl font-black text-white leading-tight">
            Legal Metrology <span class="text-cyan-400">Compliance Checker</span>
          </h1>
          <p class="text-slate-300 text-base leading-relaxed">
            Automated compliance engine enforcing the 7 mandatory declarations of India's Packaged Commodities Rules 2011. Scan or upload product packaging photos to verify MRP, Net Quantity, Dates, Manufacturer details, and Consumer Care helpline in seconds.
          </p>
          <div class="flex flex-wrap gap-4 pt-2">
            <button onclick="switchTab('scan')" class="px-6 py-3.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold text-sm shadow-xl shadow-cyan-500/20 hover:scale-105 transition-all">
              <i data-lucide="camera" class="w-4 h-4 inline-block mr-2"></i> Scan Product
            </button>
            <button onclick="switchTab('reports')" class="px-6 py-3.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-200 font-semibold text-sm hover:text-white hover:bg-slate-850 transition-all">
              <i data-lucide="file-text" class="w-4 h-4 inline-block mr-2"></i> View Reports
            </button>
          </div>
        </div>
      </section>

      <!-- 3 Feature Hubs -->
      <section class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div onclick="switchTab('scan')" class="glass-card p-6 rounded-2xl border border-slate-800 hover:border-cyan-500/50 cursor-pointer transition-all hover:-translate-y-1">
          <div class="w-12 h-12 rounded-xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center mb-4">
            <i data-lucide="camera" class="w-6 h-6"></i>
          </div>
          <h3 class="text-lg font-bold text-white mb-1">Scan Product</h3>
          <p class="text-xs text-slate-400">Upload packaging photo, preview image, remove, and run deep learning OCR compliance checking.</p>
        </div>
        <div onclick="switchTab('scan')" class="glass-card p-6 rounded-2xl border border-slate-800 hover:border-indigo-500/50 cursor-pointer transition-all hover:-translate-y-1">
          <div class="w-12 h-12 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center mb-4">
            <i data-lucide="upload-cloud" class="w-6 h-6"></i>
          </div>
          <h3 class="text-lg font-bold text-white mb-1">Upload Packaging</h3>
          <p class="text-xs text-slate-400">Directly upload high-resolution label artwork files (JPG, PNG, WEBP) for statutory audit logs.</p>
        </div>
        <div onclick="switchTab('reports')" class="glass-card p-6 rounded-2xl border border-slate-800 hover:border-emerald-500/50 cursor-pointer transition-all hover:-translate-y-1">
          <div class="w-12 h-12 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center mb-4">
            <i data-lucide="file-text" class="w-6 h-6"></i>
          </div>
          <h3 class="text-lg font-bold text-white mb-1">View Reports</h3>
          <p class="text-xs text-slate-400">Access saved audit histories, inspect clause-by-clause findings, and download PDF certificates.</p>
        </div>
      </section>
    </div>

    <!-- Tab 2: Product Scan View -->
    <div id="view-scan" class="space-y-8 hidden">
      <div class="glass-card p-6 rounded-3xl border border-slate-800">
        <h2 class="text-2xl font-black text-white">Product Packaging Scanner</h2>
        <p class="text-xs text-slate-400 mt-1">Upload your product packaging image to run genuine OCR extraction and Legal Metrology rule checks.</p>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        <!-- Left: Upload & Preview -->
        <div class="lg:col-span-5 glass-card p-6 rounded-3xl border border-slate-800 space-y-5">
          <h3 class="font-bold text-white text-base">Select Packaging Photo</h3>

          <div id="dropzone" onclick="document.getElementById('file-input').click()" class="border-2 border-dashed border-slate-700 hover:border-cyan-500 rounded-2xl p-6 text-center cursor-pointer bg-slate-900/40 hover:bg-slate-900/70 transition-all min-h-[220px] flex flex-col items-center justify-center">
            <input type="file" id="file-input" accept="image/*" onchange="handleFile(event)" class="hidden">
            <div id="upload-prompt" class="space-y-2">
              <i data-lucide="upload-cloud" class="w-10 h-10 text-cyan-400 mx-auto"></i>
              <p class="text-sm font-bold text-white">Click or drag packaging image here</p>
              <p class="text-[11px] text-slate-400">Supports JPG, JPEG, PNG, WEBP</p>
            </div>
            <div id="preview-container" class="hidden relative w-full">
              <img id="preview-img" class="max-h-64 mx-auto rounded-lg object-contain">
            </div>
          </div>

          <div id="preview-actions" class="hidden flex items-center justify-between">
            <span id="file-info" class="text-xs font-mono text-slate-400 truncate max-w-[200px]"></span>
            <button onclick="removeImage()" class="px-3 py-1.5 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/30 text-xs font-bold hover:bg-rose-500/20">
              <i data-lucide="trash-2" class="w-3.5 h-3.5 inline-block mr-1"></i> Remove Image
            </button>
          </div>

          <div class="space-y-3 pt-2 border-t border-slate-800">
            <div>
              <label class="block text-xs font-semibold text-slate-300 mb-1">Commodity / Product Name (Optional)</label>
              <input type="text" id="p-name" placeholder="e.g. Refined Sunflower Cooking Oil" class="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-sm focus:outline-none focus:border-cyan-500">
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-300 mb-1">Product Category</label>
              <select id="p-category" class="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-sm focus:outline-none focus:border-cyan-500">
                <option value="Auto-Detect">Auto-Detect (AI Classification)</option>
                <option value="Food">Food</option>
                <option value="Cosmetics">Cosmetics</option>
                <option value="Household">Household</option>
                <option value="Consumer Goods">Consumer Goods</option>
                <option value="Imported Goods">Imported Goods</option>
                <option value="Other">Other</option>
              </select>
            </div>
            <button id="scan-btn" onclick="startScan()" class="w-full py-3.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 font-bold text-sm text-white shadow-lg shadow-cyan-500/20 hover:scale-[1.02] transition-all">
              <i data-lucide="shield-check" class="w-4 h-4 inline-block mr-1.5"></i> Start Compliance Check
            </button>
          </div>
        </div>

        <!-- Right: Results -->
        <div class="lg:col-span-7 space-y-6">
          <div id="scan-placeholder" class="glass-card p-12 rounded-3xl border border-slate-800 text-center space-y-3 min-h-[380px] flex flex-col items-center justify-center">
            <i data-lucide="sparkles" class="w-12 h-12 text-cyan-400/60 mb-2"></i>
            <h4 class="text-lg font-bold text-white">Ready to Verify Packaging</h4>
            <p class="text-xs text-slate-400 max-w-sm">Upload a product label photo and click Start Compliance Check to extract declarations and evaluate Legal Metrology Act compliance.</p>
          </div>

          <div id="scan-results" class="hidden space-y-5">
            <div class="glass-card p-6 rounded-3xl border border-slate-800 space-y-4">
              <div class="flex items-start justify-between border-b border-slate-800 pb-4">
                <div>
                  <div class="flex items-center gap-2">
                    <span id="res-code" class="text-xs font-mono text-cyan-400 font-bold"></span>
                    <span id="res-category" class="text-[11px] px-2.5 py-0.5 rounded-md bg-indigo-500/10 text-indigo-400 font-semibold border border-indigo-500/20"></span>
                  </div>
                  <h3 id="res-name" class="text-xl font-bold text-white mt-0.5"></h3>
                </div>
                <div class="text-right">
                  <div id="res-score" class="text-3xl font-black text-white"></div>
                  <span id="res-status" class="inline-block mt-1"></span>
                </div>
              </div>
              <p id="res-summary" class="text-xs text-slate-300 bg-slate-900/80 p-3 rounded-xl border border-slate-850 leading-relaxed"></p>
              <div class="flex justify-between items-center pt-2 border-b border-slate-800 pb-3 mb-2">
                <span id="res-counts" class="text-xs font-semibold text-slate-400"></span>
                <a id="res-pdf-link" target="_blank" class="px-4 py-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs font-bold hover:bg-emerald-500/20">
                  <i data-lucide="download" class="w-3.5 h-3.5 inline-block mr-1"></i> Download PDF
                </a>
              </div>
              <div class="space-y-2">
                <button onclick="toggleRawOcr()" class="text-xs text-cyan-400 hover:underline font-bold flex items-center gap-1">
                  <i data-lucide="eye" class="w-3.5 h-3.5"></i> <span id="ocr-toggle-text">Show Detected Bounding Boxes & Confidence</span>
                </button>
                <div id="ocr-details-box" class="hidden p-3 rounded-xl bg-slate-950 border border-slate-850 text-xs space-y-3">
                  <div class="font-mono text-slate-400 text-[10px]">Raw OCR Stream:</div>
                  <pre id="raw-ocr-stream" class="whitespace-pre-wrap max-h-32 overflow-y-auto text-cyan-400 font-mono text-[10px] bg-slate-900 p-2 rounded-lg"></pre>
                  <div class="font-mono text-slate-400 text-[10px]">OCR Text Segments & Confidence:</div>
                  <div id="ocr-segments-list" class="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-48 overflow-y-auto"></div>
                </div>
              </div>
            </div>

            <!-- Review & Correct Extracted Declarations Form -->
            <div class="glass-card p-6 rounded-3xl border border-slate-800 space-y-4">
              <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <h4 class="text-sm font-bold text-white flex items-center gap-1.5">
                  <i data-lucide="edit-3" class="w-4 h-4 text-cyan-400"></i>
                  <span>Review & Correct Extracted Declarations</span>
                </h4>
                <span class="text-[9px] font-semibold text-slate-500 uppercase tracking-wider">AI/NLP Structured Data</span>
              </div>
              
              <input type="hidden" id="edit-report-id">
              
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                <div>
                  <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Product Category</label>
                  <select id="edit-category" class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-850 text-xs text-white focus:outline-none focus:border-cyan-500">
                    <option value="Food">Food</option>
                    <option value="Cosmetics">Cosmetics</option>
                    <option value="Household">Household</option>
                    <option value="Consumer Goods">Consumer Goods</option>
                    <option value="Imported Goods">Imported Goods</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
                <div>
                  <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Brand Name</label>
                  <input type="text" id="edit-brand" class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-850 text-xs text-white focus:outline-none focus:border-cyan-500">
                </div>
                <div>
                  <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Product / Commodity Name</label>
                  <input type="text" id="edit-commodity_name" class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-850 text-xs text-white focus:outline-none focus:border-cyan-500">
                </div>
                <div>
                  <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Manufacturer Name</label>
                  <input type="text" id="edit-manufacturer_details" class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-850 text-xs text-white focus:outline-none focus:border-cyan-500">
                </div>
                <div>
                  <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Manufacturer Address</label>
                  <input type="text" id="edit-address" class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-850 text-xs text-white focus:outline-none focus:border-cyan-500">
                </div>
                <div>
                  <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Importer Name</label>
                  <input type="text" id="edit-importer" class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-850 text-xs text-white focus:outline-none focus:border-cyan-500">
                </div>
                <div>
                  <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Country of Origin</label>
                  <input type="text" id="edit-country_of_origin" class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-850 text-xs text-white focus:outline-none focus:border-cyan-500">
                </div>
                <div>
                  <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Customer Care Details</label>
                  <input type="text" id="edit-customer_care" class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-850 text-xs text-white focus:outline-none focus:border-cyan-500">
                </div>
                <div>
                  <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Maximum Retail Price (MRP)</label>
                  <input type="text" id="edit-mrp" class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-850 text-xs text-white focus:outline-none focus:border-cyan-500">
                </div>
                <div>
                  <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Net Quantity</label>
                  <input type="text" id="edit-net_quantity" class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-850 text-xs text-white focus:outline-none focus:border-cyan-500">
                </div>
                <div>
                  <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Manufacturing Date</label>
                  <input type="text" id="edit-mfg_date" class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-850 text-xs text-white focus:outline-none focus:border-cyan-500">
                </div>
                <div>
                  <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Best Before / Expiry</label>
                  <input type="text" id="edit-expiry_date" class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-850 text-xs text-white focus:outline-none focus:border-cyan-500">
                </div>
                <div>
                  <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Unit Sale Price</label>
                  <input type="text" id="edit-unit_sale_price" class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-850 text-xs text-white focus:outline-none focus:border-cyan-500">
                </div>
              </div>
              
              <button onclick="updateScanResults()" id="update-evaluate-btn" class="w-full py-3 mt-1.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 font-bold text-xs text-white shadow-lg shadow-emerald-500/20 hover:scale-[1.01] transition-all">
                <i data-lucide="refresh-cw" class="w-3.5 h-3.5 inline-block mr-1"></i> Save Corrections & Recalculate Compliance
              </button>
            </div>

            <div class="glass-card p-6 rounded-3xl border border-slate-800 space-y-4">
              <h4 class="text-sm font-bold text-white">7 Mandatory Declarations Audit Breakdown</h4>
              <div id="rules-list" class="space-y-3"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab 3: Reports View -->
    <div id="view-reports" class="space-y-6 hidden">
      <div class="glass-card p-6 rounded-3xl border border-slate-800 flex justify-between items-center">
        <div>
          <h2 class="text-2xl font-black text-white">Compliance Audit Reports</h2>
          <p class="text-xs text-slate-400 mt-1">Search and view past Legal Metrology compliance audit certificates.</p>
        </div>
        <button onclick="loadReports()" class="px-4 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-cyan-400 font-semibold hover:bg-slate-850">
          <i data-lucide="refresh-cw" class="w-3.5 h-3.5 inline-block mr-1"></i> Refresh
        </button>
      </div>

      <div id="reports-grid" class="grid grid-cols-1 md:grid-cols-2 gap-4"></div>
    </div>
  </main>

  <!-- Footer -->
  <footer class="border-t border-slate-800 py-6 text-center text-xs text-slate-500">
    © 2026 PackSure AI – Legal Metrology Compliance Checker. India Legal Metrology (Packaged Commodities) Rules, 2011.
  </footer>

  <script>
    let currentFile = null;

    function switchTab(tab) {
      ['home', 'scan', 'reports'].forEach(t => {
        document.getElementById('view-' + t).classList.toggle('hidden', t !== tab);
        const btn = document.getElementById('btn-' + t);
        if (btn) {
          if (t === tab) {
            btn.className = 'px-3.5 py-2 rounded-lg text-sm font-medium bg-slate-800 text-cyan-400 border border-cyan-500/30';
          } else {
            btn.className = 'px-3.5 py-2 rounded-lg text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-850';
          }
        }
      });
      if (tab === 'reports') loadReports();
      lucide.createIcons();
    }

    function handleFile(e) {
      if (e.target.files && e.target.files[0]) {
        currentFile = e.target.files[0];
        document.getElementById('upload-prompt').classList.add('hidden');
        const container = document.getElementById('preview-container');
        container.classList.remove('hidden');
        document.getElementById('preview-img').src = URL.createObjectURL(currentFile);
        document.getElementById('preview-actions').classList.remove('hidden');
        document.getElementById('file-info').innerText = currentFile.name + ' (' + (currentFile.size/1024).toFixed(1) + ' KB)';
        lucide.createIcons();
      }
    }

    function removeImage() {
      currentFile = null;
      document.getElementById('file-input').value = '';
      document.getElementById('preview-container').classList.add('hidden');
      document.getElementById('upload-prompt').classList.remove('hidden');
      document.getElementById('preview-actions').classList.add('hidden');
      document.getElementById('scan-results').classList.add('hidden');
      document.getElementById('scan-placeholder').classList.remove('hidden');
    }

    async function startScan() {
      if (!currentFile) {
        alert('Please select a packaging image first.');
        return;
      }
      const btn = document.getElementById('scan-btn');
      btn.innerText = 'Extracting OCR & Checking Compliance...';
      btn.disabled = true;

      try {
        const formData = new FormData();
        formData.append('file', currentFile);
        const name = document.getElementById('p-name').value;
        if (name) formData.append('product_name', name);
        formData.append('category', document.getElementById('p-category').value);

        const res = await fetch('/api/scan', { method: 'POST', body: formData });
        const data = await res.json();
        
        document.getElementById('scan-placeholder').classList.add('hidden');
        const resultsEl = document.getElementById('scan-results');
        resultsEl.classList.remove('hidden');

        document.getElementById('res-code').innerText = data.report_code;
        document.getElementById('res-name').innerText = data.product_name;
        document.getElementById('res-category').innerText = 'Category: ' + (data.category || data.detected_category || 'Other');
        document.getElementById('res-score').innerText = data.compliance_score + '%';
        
        const stEl = document.getElementById('res-status');
        const statusSlug = (data.compliance_status || 'pass').toLowerCase().replace(/\s+/g, '-');
        stEl.className = 'badge-' + statusSlug;
        stEl.innerText = data.compliance_status;
        
        document.getElementById('res-summary').innerText = data.summary;
        document.getElementById('res-counts').innerText = 'Passed: ' + (data.passed_count || 0) + ' | Warnings: ' + (data.warnings_count || 0) + ' | Violations: ' + (data.violations_count || 0) + ' | Review: ' + (data.manual_review_count || 0);
        document.getElementById('res-pdf-link').href = '/api/reports/' + data.id + '/pdf';

        // Populate Review & Corrections Form
        const fields = data.details?.fields || {};
        document.getElementById('edit-report-id').value = data.id;
        document.getElementById('edit-category').value = data.category || data.detected_category || 'Food';
        document.getElementById('edit-commodity_name').value = fields.commodity_name || '';
        document.getElementById('edit-brand').value = fields.brand || '';
        document.getElementById('edit-manufacturer_details').value = fields.manufacturer_details || '';
        document.getElementById('edit-address').value = fields.address || '';
        document.getElementById('edit-importer').value = fields.importer || '';
        document.getElementById('edit-country_of_origin').value = fields.country_of_origin || '';
        document.getElementById('edit-customer_care').value = fields.customer_care || '';
        document.getElementById('edit-mrp').value = fields.mrp || '';
        document.getElementById('edit-net_quantity').value = fields.net_quantity || '';
        document.getElementById('edit-mfg_date').value = fields.mfg_date || '';
        document.getElementById('edit-expiry_date').value = fields.expiry_date || '';
        document.getElementById('edit-unit_sale_price').value = fields.unit_sale_price || '';

        // Populate OCR details
        document.getElementById('raw-ocr-stream').innerText = data.details?.raw_text || 'No text detected.';
        const segmentsList = document.getElementById('ocr-segments-list');
        segmentsList.innerHTML = '';
        const boxes = data.details?.bounding_boxes || [];
        if (boxes.length === 0) {
          segmentsList.innerHTML = '<p class="col-span-2 text-slate-500 italic text-[11px]">No bounding boxes recorded.</p>';
        } else {
          boxes.forEach(boxItem => {
            const confidencePercent = Math.round((boxItem.confidence || 0.85) * 100);
            const badgeClass = boxItem.confidence >= 0.85 
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
              : boxItem.confidence >= 0.7 
                ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' 
                : 'bg-rose-500/10 text-rose-400 border border-rose-500/20';

            const seg = document.createElement('div');
            seg.className = 'p-2 rounded-lg bg-slate-900 border border-slate-850 flex items-center justify-between text-[11px]';
            seg.innerHTML = `
              <div class="truncate pr-2">
                <div class="text-slate-200 font-semibold truncate">${boxItem.text}</div>
                <div class="text-[9px] text-slate-500 font-mono">Box: [${boxItem.box ? boxItem.box.join(', ') : '0,0,0,0'}]</div>
              </div>
              <span class="px-1.5 py-0.5 rounded text-[9px] font-bold shrink-0 ${badgeClass}">${confidencePercent}%</span>
            `;
            segmentsList.appendChild(seg);
          });
        }

        const list = document.getElementById('rules-list');
        list.innerHTML = '';
        (data.details?.rule_checks || []).forEach(r => {
          const item = document.createElement('div');
          const ruleStatusSlug = (r.status || 'pass').toLowerCase().replace(/\s+/g, '-');
          item.className = 'p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1.5 text-xs';
          item.innerHTML = `
            <div class="flex justify-between items-center">
              <span class="font-mono text-cyan-400 font-bold">${r.rule_code}</span>
              <span class="badge-${ruleStatusSlug}">${r.status}</span>
            </div>
            <div class="font-bold text-white">${r.title}</div>
            <div class="text-[11px] font-mono text-slate-300 bg-slate-950 p-2 rounded truncate"><span class="text-slate-500">Extracted:</span> ${r.value || 'Not Declared / Missing'}</div>
            <div class="text-slate-400"><span class="text-slate-500 font-medium">Finding:</span> ${r.finding}</div>
            <div class="text-cyan-300 pt-0.5"><span class="text-cyan-500 font-semibold">Action:</span> ${r.remediation}</div>
          `;
          list.appendChild(item);
        });
      } catch (err) {
        alert('Scan failed: ' + err);
      } finally {
        btn.innerHTML = '<i data-lucide="shield-check" class="w-4 h-4 inline-block mr-1.5"></i> Start Compliance Check';
        btn.disabled = false;
        lucide.createIcons();
      }
    }

    async function updateScanResults() {
      const reportId = document.getElementById('edit-report-id').value;
      if (!reportId) return;
      
      const btn = document.getElementById('update-evaluate-btn');
      btn.innerText = 'Recalculating...';
      btn.disabled = true;
      
      try {
        const formData = new FormData();
        formData.append('report_id', reportId);
        formData.append('category', document.getElementById('edit-category').value);
        
        const fieldNames = [
          'commodity_name', 'brand', 'manufacturer_details', 'address',
          'importer', 'country_of_origin', 'customer_care', 'mrp',
          'net_quantity', 'mfg_date', 'expiry_date', 'unit_sale_price'
        ];
        
        fieldNames.forEach(name => {
          const val = document.getElementById('edit-' + name).value;
          formData.append(name, val);
        });
        
        const res = await fetch('/api/scan/update', { method: 'POST', body: formData });
        const data = await res.json();
        
        document.getElementById('res-name').innerText = data.product_name;
        document.getElementById('res-category').innerText = 'Category: ' + (data.category || data.detected_category || 'Other');
        document.getElementById('res-score').innerText = data.compliance_score + '%';
        
        const stEl = document.getElementById('res-status');
        const statusSlug = (data.compliance_status || 'pass').toLowerCase().replace(/\s+/g, '-');
        stEl.className = 'badge-' + statusSlug;
        stEl.innerText = data.compliance_status;
        
        document.getElementById('res-summary').innerText = data.summary;
        document.getElementById('res-counts').innerText = 'Passed: ' + (data.passed_count || 0) + ' | Warnings: ' + (data.warnings_count || 0) + ' | Violations: ' + (data.violations_count || 0) + ' | Review: ' + (data.manual_review_count || 0);
        
        const list = document.getElementById('rules-list');
        list.innerHTML = '';
        (data.details?.rule_checks || []).forEach(r => {
          const item = document.createElement('div');
          const ruleStatusSlug = (r.status || 'pass').toLowerCase().replace(/\s+/g, '-');
          item.className = 'p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1.5 text-xs';
          item.innerHTML = `
            <div class="flex justify-between items-center">
              <span class="font-mono text-cyan-400 font-bold">${r.rule_code}</span>
              <span class="badge-${ruleStatusSlug}">${r.status}</span>
            </div>
            <div class="font-bold text-white">${r.title}</div>
            <div class="text-[11px] font-mono text-slate-300 bg-slate-950 p-2 rounded truncate"><span class="text-slate-500">Extracted:</span> ${r.value || 'Not Declared / Missing'}</div>
            <div class="text-slate-400"><span class="text-slate-500 font-medium">Finding:</span> ${r.finding}</div>
            <div class="text-cyan-300 pt-0.5"><span class="text-cyan-500 font-semibold">Action:</span> ${r.remediation}</div>
          `;
          list.appendChild(item);
        });
        
        alert('Compliance re-evaluated successfully!');
      } catch (err) {
        alert('Update failed: ' + err);
      } finally {
        btn.innerHTML = '<i data-lucide="refresh-cw" class="w-3.5 h-3.5 inline-block mr-1"></i> Save Corrections & Recalculate Compliance';
        btn.disabled = false;
        lucide.createIcons();
      }
    }

    let showOcrDetails = false;
    function toggleRawOcr() {
      showOcrDetails = !showOcrDetails;
      const box = document.getElementById('ocr-details-box');
      const text = document.getElementById('ocr-toggle-text');
      box.classList.toggle('hidden', !showOcrDetails);
      text.innerText = showOcrDetails ? 'Hide Detected Bounding Boxes & Confidence' : 'Show Detected Bounding Boxes & Confidence';
    }

    async function loadReports() {
      const grid = document.getElementById('reports-grid');
      grid.innerHTML = '<p class="text-xs text-slate-400">Loading audit reports...</p>';
      try {
        const res = await fetch('/api/reports');
        const data = await res.json();
        grid.innerHTML = '';
        if (data.reports.length === 0) {
          grid.innerHTML = '<p class="text-xs text-slate-400">No reports found.</p>';
          return;
        }
        data.reports.forEach(r => {
          const el = document.createElement('div');
          el.className = 'glass-card p-5 rounded-2xl border border-slate-800 space-y-3';
          el.innerHTML = `
            <div class="flex justify-between items-start">
              <div>
                <span class="text-xs font-mono text-cyan-400 font-bold">${r.report_code}</span>
                <h4 class="font-bold text-white text-base mt-0.5">${r.product_name}</h4>
              </div>
              <span class="badge-${r.compliance_status.toLowerCase()}">${r.compliance_status} (${r.compliance_score}%)</span>
            </div>
            <p class="text-xs text-slate-400 line-clamp-2">${r.summary}</p>
            <div class="flex justify-between items-center pt-2 border-t border-slate-800 text-xs">
              <span class="text-slate-500">${new Date(r.created_at).toLocaleDateString()}</span>
              <a href="/api/reports/${r.id}/pdf" target="_blank" class="text-emerald-400 hover:underline font-bold">Download PDF →</a>
            </div>
          `;
          grid.appendChild(el);
        });
      } catch (e) {
        grid.innerHTML = '<p class="text-xs text-rose-400">Error loading reports.</p>';
      }
      lucide.createIcons();
    }

    lucide.createIcons();
  </script>
</body>
</html>"""

# -----------------------------------------------------------------------------
# Main Runner
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 65)
    print("  PackSure AI – Legal Metrology Compliance Checker")
    print("  Single-File All-in-One Application")
    print("=" * 65)
    print("\nStarting server on http://localhost:8000 ...")
    
    # Open browser automatically after a short delay
    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open("http://localhost:8000")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(app, host="0.0.0.0", port=8000)
