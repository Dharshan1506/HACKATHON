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
    def classify_tier(cls, score: float) -> Dict[str, Any]:
        """
        Deterministic Compliance Score Tiers:
        90-100 = COMPLIANT
        70-89  = MOSTLY COMPLIANT
        40-69  = NEEDS REVIEW
        0-39   = HIGH RISK
        """
        if score >= 90.0:
            return {
                "tier": "COMPLIANT",
                "risk_level": "LOW",
                "badge_class": "badge-compliant",
                "color": "#10B981"
            }
        elif score >= 70.0:
            return {
                "tier": "MOSTLY COMPLIANT",
                "risk_level": "LOW",
                "badge_class": "badge-mostly-compliant",
                "color": "#06B6D4"
            }
        elif score >= 40.0:
            return {
                "tier": "NEEDS REVIEW",
                "risk_level": "MEDIUM",
                "badge_class": "badge-needs-review",
                "color": "#F59E0B"
            }
        else:
            return {
                "tier": "HIGH RISK",
                "risk_level": "HIGH",
                "badge_class": "badge-high-risk",
                "color": "#EF4444"
            }

    @classmethod
    def classify_priority(cls, rule_id: str, status: str, is_missing: bool = False, finding: str = "", category: str = "ALL") -> str:
        """
        Classifies compliance issues into 4 prioritized severity levels:
        - CRITICAL: Missing core mandatory declarations (Manufacturer, MRP, Net Qty, Commodity Name, Origin on Imports, Mfg Date) or prohibited units (lbs/oz).
        - HIGH: Serious violations, missing USP, missing Consumer Care, missing Expiry on perishable/cosmetics, or major formatting errors.
        - MEDIUM: Manual review items, ambiguous licensing/contract statements, missing tax statements on MRP, partial address.
        - LOW: Minor formatting warnings (missing whitespace in '350g', partial consumer contact), or compliant (PASS) checks.
        """
        if status == "PASS":
            return "LOW"

        critical_core_rules = ["RULE_6_1_A", "RULE_6_1_B", "RULE_6_1_C", "RULE_6_1_D", "RULE_6_1_E", "RULE_6_1_G"]
        
        # Missing core mandatory declarations or prohibited non-metric units -> CRITICAL
        if (is_missing and rule_id in critical_core_rules) or "prohibited" in finding.lower() or "non-metric" in finding.lower():
            return "CRITICAL"

        # Serious violations on core declarations -> CRITICAL
        if status == "FAIL":
            if rule_id in critical_core_rules:
                return "CRITICAL"
            # Missing USP, Customer Care, Expiry Date -> HIGH
            return "HIGH"

        # Manual review items -> MEDIUM
        if status == "MANUAL REVIEW":
            return "MEDIUM"

        # Warnings
        if status == "WARNING":
            # Missing tax inclusivity phrase or partial address / non-standard month format -> MEDIUM
            if rule_id in ["RULE_6_1_A", "RULE_6_1_E", "RULE_6_1_D"]:
                return "MEDIUM"
            # Minor whitespace formatting (e.g. '350g') or partial consumer care -> LOW
            return "LOW"

        return "LOW"

    @classmethod
    def validate(cls, data: Dict[str, Any], category: str = "ALL") -> Dict[str, Any]:
        rules = RulesRegistry.get_rules(category)
        results = []
        earned = 0.0
        total = sum(r.get("weight", 10) for r in rules)

        for rule in rules:
            val = str(data.get(rule["field"], "") or "").strip()
            is_missing = not val or val.lower() in ["none", "null", "n/a", "not declared"]
            
            res = cls._check_rule(rule, val, data, category)
            status_val = res["status"]
            finding_val = res["finding"]
            
            priority = cls.classify_priority(rule["id"], status_val, is_missing=is_missing, finding=finding_val, category=category)
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
                "status": status_val,  # PASS, FAIL, WARNING, MANUAL REVIEW
                "priority": priority,   # CRITICAL, HIGH, MEDIUM, LOW
                "severity": priority,
                "weight": rule.get("weight", 10),
                "score_earned": round(score_earned, 2),
                "finding": finding_val,
                "remediation": res["remediation"]
            })

        # Priority map and Status map for sorting (Highest priority to lowest)
        priority_order = {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4}
        status_order = {"FAIL": 1, "WARNING": 2, "MANUAL REVIEW": 3, "PASS": 4}

        # Sort violations and rule checks from highest priority to lowest priority
        results.sort(
            key=lambda r: (
                priority_order.get(r.get("priority", "LOW"), 5),
                status_order.get(r.get("status", "PASS"), 5),
                -r.get("weight", 0)
            )
        )

        # Formula: Score = Passed Rule Weight / Total Applicable Rule Weight * 100
        final_score = round((earned / total) * 100.0, 1) if total > 0 else 0.0
        tier_info = cls.classify_tier(final_score)
        status = tier_info["tier"]
        risk = tier_info["risk_level"]

        passed_count = sum(1 for r in results if r["status"] == "PASS")
        warnings_count = sum(1 for r in results if r["status"] == "WARNING")
        violations_count = sum(1 for r in results if r["status"] == "FAIL")
        manual_review_count = sum(1 for r in results if r["status"] == "MANUAL REVIEW")

        # Priority Counts
        critical_violations_count = sum(1 for r in results if r["priority"] == "CRITICAL" and r["status"] != "PASS")
        high_violations_count = sum(1 for r in results if r["priority"] == "HIGH" and r["status"] != "PASS")
        medium_violations_count = sum(1 for r in results if r["priority"] == "MEDIUM" and r["status"] != "PASS")
        low_violations_count = sum(1 for r in results if r["priority"] == "LOW" and r["status"] != "PASS")

        # Filter prioritized violations
        prioritized_violations = [r for r in results if r["status"] in ["FAIL", "WARNING", "MANUAL REVIEW"]]

        summary = cls._generate_summary(final_score, status, passed_count, warnings_count, violations_count, manual_review_count)

        return {
            "score": final_score,
            "status": status,
            "tier": status,
            "compliance_tier": status,
            "risk_level": risk,
            "passed_rule_weight": round(earned, 1),
            "total_applicable_rule_weight": total,
            "formula": f"Score = {round(earned, 1)} / {total} × 100 = {final_score}%",
            "passed_count": passed_count,
            "warnings_count": warnings_count,
            "violations_count": violations_count,
            "manual_review_count": manual_review_count,
            "critical_violations_count": critical_violations_count,
            "high_violations_count": high_violations_count,
            "medium_violations_count": medium_violations_count,
            "low_violations_count": low_violations_count,
            "prioritized_violations": prioritized_violations,
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
        if score >= 90.0:
            return f"Product packaging is COMPLIANT ({score}% compliance score) under the Legal Metrology (Packaged Commodities) Rules, 2011. All {passed} mandatory statutory declarations meet required formatting, placement, and metric standards."
        elif score >= 70.0:
            return f"Product packaging is MOSTLY COMPLIANT ({score}% compliance score). Found {warnings} minor warning(s) or formatting adjustments. Rectify minor discrepancies before full-scale commercial packaging."
        elif score >= 40.0:
            return f"Product packaging NEEDS REVIEW ({score}% compliance score). Found {manual_review} item(s) flagged for manual verification or non-standard declarations under Legal Metrology standards."
        else:
            return f"Product packaging is HIGH RISK ({score}% compliance score). Detected {violations} critical statutory violation(s) under the Legal Metrology Act 2009. Packaging does not meet mandatory consumer packaging regulations."

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
    def _create_image_flowable(cls, image_path: Optional[str], max_w: float = 140, max_h: float = 130):
        if not image_path or not os.path.exists(image_path):
            return None
        try:
            with Image.open(image_path) as pimg:
                w, h = pimg.size
                aspect = h / float(w)
                target_w = max_w
                target_h = target_w * aspect
                if target_h > max_h:
                    target_h = max_h
                    target_w = target_h / aspect
            from reportlab.platypus import Image as RLImage
            return RLImage(image_path, width=target_w, height=target_h)
        except Exception:
            return None

    @classmethod
    def generate_pdf(
        cls,
        report_code: str,
        product_name: str,
        score: float,
        status: str,
        risk: str,
        summary: str,
        rule_checks: list,
        output_path: str,
        image_path: Optional[str] = None,
        extracted_data: Optional[dict] = None
    ) -> str:
        """
        Generates an official, comprehensive PDF Legal Metrology Audit Certificate and Regulatory Report.
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0F172A")
        )
        meta_style = ParagraphStyle(
            'DocMeta',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#64748B")
        )
        section_heading = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=10,
            spaceAfter=4
        )
        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#334155")
        )
        body_bold = ParagraphStyle(
            'BodyBold',
            parent=body_style,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor("#0F172A")
        )
        finding_style = ParagraphStyle(
            'Finding',
            parent=body_style,
            fontName='Helvetica',
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#475569")
        )
        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=7,
            leading=9.5,
            textColor=colors.HexColor("#64748B")
        )

        story = []

        # 1. Header Banner
        header_table_data = [
            [
                Paragraph("<b>PACKSURE AI</b><br/><font size=7 color='#06B6D4'>LEGAL METROLOGY REGULATORY COMPLIANCE SYSTEM</font>", title_style),
                Paragraph(f"<b>AUDIT CERTIFICATE</b><br/><font size=7 color='#64748B'>Report Code: {report_code}<br/>Generated: {datetime.datetime.now().strftime('%d %b %Y, %H:%M')}</font>", ParagraphStyle('RightMeta', parent=meta_style, alignment=2))
            ]
        ]
        t_header = Table(header_table_data, colWidths=[320, 220])
        t_header.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(t_header)
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0F172A"), spaceAfter=8))

        # 2. Executive Summary & Compliance Score Card
        ext_dict = extracted_data or {}
        fields = ext_dict.get("fields", {})
        category = ext_dict.get("category", "Food")
        formula_text = ext_dict.get("formula", f"Score = {score:.1f}%")

        status_color = "#10B981" if score >= 90 else ("#06B6D4" if score >= 70 else ("#F59E0B" if score >= 40 else "#EF4444"))
        status_bg = "#ECFDF5" if score >= 90 else ("#ECFEFF" if score >= 70 else ("#FFFBEB" if score >= 40 else "#FEF2F2"))

        score_card_data = [
            [
                Paragraph(f"<font size=18 color='{status_color}'><b>{score:.1f}%</b></font><br/><font size=7 color='#64748B'><b>COMPLIANCE SCORE</b></font>", ParagraphStyle('Score', parent=body_style, alignment=1)),
                Paragraph(f"<font size=11 color='{status_color}'><b>{status}</b></font><br/><font size=7 color='#64748B'>STATUTORY VERDICT</font>", ParagraphStyle('Verdict', parent=body_style, alignment=1)),
                Paragraph(f"<font size=10 color='#0F172A'><b>{risk} RISK</b></font><br/><font size=7 color='#64748B'>ENFORCEMENT EXPOSURE</font>", ParagraphStyle('Risk', parent=body_style, alignment=1)),
                Paragraph(f"<font size=8 color='#0F172A'><b>{category}</b></font><br/><font size=7 color='#64748B'>PRODUCT CATEGORY</font>", ParagraphStyle('Cat', parent=body_style, alignment=1))
            ]
        ]
        t_score = Table(score_card_data, colWidths=[135, 135, 135, 135])
        t_score.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(status_bg)),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor(status_color)),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(t_score)
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<font size=7 color='#475569'><b>Deterministic Formula:</b> {formula_text} &nbsp;|&nbsp; <b>Standards:</b> 90-100% Compliant, 70-89% Mostly Compliant, 40-69% Needs Review, 0-39% High Risk</font>", meta_style))
        story.append(Spacer(1, 8))

        # 3. Product Details & Embedded Packaging Photo
        story.append(Paragraph("Product Declarations & Physical Label Image", section_heading))

        img_flowable = cls._create_image_flowable(image_path, max_w=140, max_h=130)
        if not img_flowable:
            img_flowable = Paragraph("<font size=8 color='#94A3B8'><i>Packaging Photo<br/>Not Attached</i></font>", ParagraphStyle('NoImg', parent=body_style, alignment=1))

        details_table_data = [
            [
                Paragraph("<b>Product / Commodity:</b>", body_style),
                Paragraph(fields.get("commodity_name") or product_name, body_bold),
                Paragraph("<b>Maximum Retail Price (MRP):</b>", body_style),
                Paragraph(fields.get("mrp") or "<font color='#EF4444'>Missing</font>", body_bold)
            ],
            [
                Paragraph("<b>Brand Name:</b>", body_style),
                Paragraph(fields.get("brand") or "Not Declared", body_style),
                Paragraph("<b>Net Quantity:</b>", body_style),
                Paragraph(fields.get("net_quantity") or "<font color='#EF4444'>Missing</font>", body_bold)
            ],
            [
                Paragraph("<b>Mfg / Packing Date:</b>", body_style),
                Paragraph(fields.get("mfg_date") or "<font color='#EF4444'>Missing</font>", body_style),
                Paragraph("<b>Unit Sale Price (USP):</b>", body_style),
                Paragraph(fields.get("unit_sale_price") or "<font color='#F59E0B'>Missing</font>", body_style)
            ],
            [
                Paragraph("<b>Expiry / Best Before:</b>", body_style),
                Paragraph(fields.get("expiry_date") or "Not Declared", body_style),
                Paragraph("<b>Country of Origin:</b>", body_style),
                Paragraph(fields.get("country_of_origin") or "India", body_style)
            ],
            [
                Paragraph("<b>Manufacturer Details:</b>", body_style),
                Paragraph(fields.get("manufacturer_details") or fields.get("address") or "<font color='#EF4444'>Missing</font>", body_style),
                Paragraph("<b>Consumer Care Helpline:</b>", body_style),
                Paragraph(fields.get("customer_care") or "<font color='#F59E0B'>Missing</font>", body_style)
            ]
        ]
        t_details = Table(details_table_data, colWidths=[90, 100, 95, 95])
        t_details.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        split_container = [
            [img_flowable, t_details]
        ]
        t_split = Table(split_container, colWidths=[150, 390])
        t_split.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('PADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(t_split)
        story.append(Spacer(1, 8))

        # 4. OCR Extraction Diagnostics Summary
        raw_text_snippet = ext_dict.get("raw_text", "").replace("\n", " ")[:200]
        boxes_count = len(ext_dict.get("bounding_boxes", []))
        story.append(Paragraph(
            f"<b>OCR Extraction Diagnostic:</b> Engine: <i>PaddleOCR v2.7 (DBNet + CRNN)</i> &nbsp;|&nbsp; "
            f"Detected Segments: <b>{boxes_count} bounding boxes</b> &nbsp;|&nbsp; "
            f"Raw Stream: <font size=7 color='#64748B'>\"{raw_text_snippet}...\"</font>",
            body_style
        ))
        story.append(Spacer(1, 8))

        # 5. Prioritized Violations & Status Counts Bar
        checks = rule_checks or []
        passed_cnt = sum(1 for c in checks if c.get("status") == "PASS")
        failed_cnt = sum(1 for c in checks if c.get("status") == "FAIL")
        warn_cnt = sum(1 for c in checks if c.get("status") == "WARNING")
        review_cnt = sum(1 for c in checks if c.get("status") == "MANUAL REVIEW")

        crit_cnt = ext_dict.get("critical_violations_count", sum(1 for c in checks if c.get("priority") == "CRITICAL" and c.get("status") != "PASS"))
        hi_cnt = ext_dict.get("high_violations_count", sum(1 for c in checks if c.get("priority") == "HIGH" and c.get("status") != "PASS"))
        med_cnt = ext_dict.get("medium_violations_count", sum(1 for c in checks if c.get("priority") == "MEDIUM" and c.get("status") != "PASS"))

        metrics_data = [
            [
                Paragraph(f"<b>PASSED:</b> {passed_cnt}", ParagraphStyle('P', parent=body_style, textColor=colors.HexColor("#10B981"))),
                Paragraph(f"<b>FAILED:</b> {failed_cnt}", ParagraphStyle('F', parent=body_style, textColor=colors.HexColor("#EF4444"))),
                Paragraph(f"<b>WARNINGS:</b> {warn_cnt}", ParagraphStyle('W', parent=body_style, textColor=colors.HexColor("#F59E0B"))),
                Paragraph(f"<b>MANUAL REVIEW:</b> {review_cnt}", ParagraphStyle('R', parent=body_style, textColor=colors.HexColor("#8B5CF6"))),
                Paragraph(f"<b>PRIORITY ISSUES:</b> <font color='#EF4444'>{crit_cnt} Critical</font>, <font color='#F97316'>{hi_cnt} High</font>, <font color='#8B5CF6'>{med_cnt} Med</font>", body_style),
            ]
        ]
        t_metrics = Table(metrics_data, colWidths=[70, 70, 80, 100, 220])
        t_metrics.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('PADDING', (0, 0), (-1, -1), 3.5),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(t_metrics)
        story.append(Spacer(1, 8))

        # 6. Detailed Statutory Declarations Audit Table (Sorted)
        story.append(Paragraph("Statutory Declarations Audit Breakdown (PCR 2011)", section_heading))

        rule_table_data = [[
            Paragraph("<b>Rule Reference & Code</b>", ParagraphStyle('TH1', parent=body_style, fontName='Helvetica-Bold', textColor=colors.white)),
            Paragraph("<b>Mandatory Declaration & Extracted Value</b>", ParagraphStyle('TH2', parent=body_style, fontName='Helvetica-Bold', textColor=colors.white)),
            Paragraph("<b>Verdict / Priority</b>", ParagraphStyle('TH3', parent=body_style, fontName='Helvetica-Bold', textColor=colors.white)),
            Paragraph("<b>Statutory Finding & Actionable Remediation</b>", ParagraphStyle('TH4', parent=body_style, fontName='Helvetica-Bold', textColor=colors.white)),
        ]]

        for r in checks:
            st = r.get("status", "FAIL")
            pri = r.get("priority", "LOW")
            st_color = "#10B981" if st == "PASS" else ("#F59E0B" if st == "WARNING" else ("#8B5CF6" if st == "MANUAL REVIEW" else "#EF4444"))
            pri_color = "#EF4444" if pri == "CRITICAL" else ("#F97316" if pri == "HIGH" else ("#8B5CF6" if pri == "MEDIUM" else "#3B82F6"))

            val_display = r.get("value") or "<font color='#EF4444'>Missing / Undetected</font>"

            rule_table_data.append([
                Paragraph(f"<b>{r.get('rule_code', '')}</b><br/><font size=6.5 color='#64748B'>{r.get('clause', '')}</font>", body_style),
                Paragraph(f"<b>{r.get('title', '')}</b><br/><font size=7 color='#334155'>{val_display}</font>", body_style),
                Paragraph(f"<font color='{st_color}'><b>{st}</b></font><br/><font size=6.5 color='{pri_color}'><b>{pri}</b></font>", body_style),
                Paragraph(f"{r.get('finding', '')}<br/><font color='#0284C7'><b>Fix:</b> {r.get('remediation', '')}</font>", finding_style)
            ])

        t_rules = Table(rule_table_data, colWidths=[105, 135, 75, 225])
        t_rules.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ]))
        story.append(t_rules)
        story.append(Spacer(1, 10))

        # 7. Actionable Regulatory Recommendations Checklist
        story.append(Paragraph("Actionable Statutory Packaging Recommendations", section_heading))
        non_pass = [c for c in checks if c.get("status") != "PASS"]
        if non_pass:
            rec_items = []
            for idx, item in enumerate(non_pass, start=1):
                rec_items.append([
                    Paragraph(f"<b>{idx}.</b>", body_bold),
                    Paragraph(f"<b>{item.get('title', '')} ({item.get('rule_code', '')}):</b> {item.get('remediation', '')} <font color='#64748B'><i>[Ref: {item.get('clause', '')}]</i></font>", body_style)
                ])
            t_rec = Table(rec_items, colWidths=[20, 520])
            t_rec.setStyle(TableStyle([
                ('PADDING', (0, 0), (-1, -1), 2.5),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(t_rec)
        else:
            story.append(Paragraph("<font color='#10B981'><b>✓ All mandatory declarations comply with Legal Metrology (Packaged Commodities) Rules, 2011. Packaging is legally cleared for commercial distribution.</b></font>", body_style))

        story.append(Spacer(1, 10))

        # 8. Statutory Legal Disclaimer
        story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#CBD5E1"), spaceAfter=6))
        story.append(Paragraph(
            "<b>STATUTORY REGULATORY DISCLAIMER:</b> This Legal Metrology Compliance Audit Certificate is generated deterministically "
            "by the PackSure AI Compliance Engine in strict conformance with the Legal Metrology Act, 2009 (Act No. 1 of 2010) and the "
            "Legal Metrology (Packaged Commodities) Rules, 2011 (as amended). This certificate provides a pre-market technical audit of "
            "mandatory statutory declarations. Final legal responsibility remains with the manufacturer, packer, or importer to maintain physical artwork compliance.",
            disclaimer_style
        ))

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

    img_path = None
    if scan_result.image_filename:
        cand = os.path.join(UPLOAD_DIR, scan_result.image_filename)
        if os.path.exists(cand):
            img_path = cand

    ReportGenerator.generate_pdf(
        report_code=report.report_code,
        product_name=product.name if product else report.title,
        score=scan_result.compliance_score,
        status=scan_result.compliance_status,
        risk=scan_result.risk_level,
        summary=summary,
        rule_checks=eval_res["rule_checks"],
        output_path=pdf_path,
        image_path=img_path,
        extracted_data=scan_result.extracted_data
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

    img_path = None
    if scan.image_filename:
        cand = os.path.join(UPLOAD_DIR, scan.image_filename)
        if os.path.exists(cand):
            img_path = cand

    ReportGenerator.generate_pdf(
        report_code=rep.report_code,
        product_name=prod.name if prod else rep.title,
        score=scan.compliance_score,
        status=scan.compliance_status,
        risk=scan.risk_level,
        summary=rep.summary,
        rule_checks=rep.details.get("rule_checks", []) if rep.details else [],
        output_path=pdf_path,
        image_path=img_path,
        extracted_data=rep.details
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
    .badge-compliant { background: rgba(16, 185, 129, 0.18); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35); font-weight: 700; padding: 4px 12px; border-radius: 9999px; font-size: 11px; letter-spacing: 0.05em; text-transform: uppercase; }
    .badge-mostly-compliant { background: rgba(6, 182, 212, 0.18); color: #22d3ee; border: 1px solid rgba(6, 182, 212, 0.35); font-weight: 700; padding: 4px 12px; border-radius: 9999px; font-size: 11px; letter-spacing: 0.05em; text-transform: uppercase; }
    .badge-needs-review { background: rgba(245, 158, 11, 0.18); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.35); font-weight: 700; padding: 4px 12px; border-radius: 9999px; font-size: 11px; letter-spacing: 0.05em; text-transform: uppercase; }
    .badge-high-risk { background: rgba(239, 68, 68, 0.18); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.35); font-weight: 700; padding: 4px 12px; border-radius: 9999px; font-size: 11px; letter-spacing: 0.05em; text-transform: uppercase; }
    
    .badge-pass { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); font-weight: 600; padding: 2px 8px; border-radius: 9999px; font-size: 11px; }
    .badge-warning { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); font-weight: 600; padding: 2px 8px; border-radius: 9999px; font-size: 11px; }
    .badge-fail { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); font-weight: 600; padding: 2px 8px; border-radius: 9999px; font-size: 11px; }
    .badge-manual-review, .badge-manual_review { background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); font-weight: 600; padding: 2px 8px; border-radius: 9999px; font-size: 11px; }

    .priority-critical { background: rgba(225, 29, 72, 0.2); color: #fb7185; border: 1px solid rgba(225, 29, 72, 0.4); font-weight: 800; padding: 2px 7px; border-radius: 6px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; }
    .priority-high { background: rgba(234, 88, 12, 0.2); color: #fb923c; border: 1px solid rgba(234, 88, 12, 0.4); font-weight: 800; padding: 2px 7px; border-radius: 6px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; }
    .priority-medium { background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.4); font-weight: 800; padding: 2px 7px; border-radius: 6px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; }
    .priority-low { background: rgba(59, 130, 246, 0.18); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.35); font-weight: 800; padding: 2px 7px; border-radius: 6px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; }
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

          <div id="scan-results" class="hidden space-y-6">
            <!-- Executive Compliance Verdict Card -->
            <div class="glass-card p-6 rounded-3xl border border-slate-800 space-y-5 shadow-xl">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
                <div class="flex items-center gap-3.5">
                  <div id="res-img-container" onclick="openImageModal()" class="relative group w-14 h-14 rounded-2xl overflow-hidden border border-slate-700 bg-slate-950 flex-shrink-0 cursor-pointer shadow-md" title="Click to view full image">
                    <img id="res-img-thumb" class="w-full h-full object-cover group-hover:scale-110 transition-transform">
                    <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                      <i data-lucide="maximize-2" class="w-3.5 h-3.5 text-cyan-300"></i>
                    </div>
                  </div>
                  <div>
                    <div class="flex items-center gap-2">
                      <span id="res-code" class="text-xs font-mono text-cyan-400 font-bold px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/20"></span>
                      <span id="res-category" class="text-[11px] px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 font-semibold border border-indigo-500/20"></span>
                    </div>
                    <h3 id="res-name" class="text-xl font-bold text-white mt-1"></h3>
                  </div>
                </div>

                <div class="flex flex-wrap items-center gap-3">
                  <div class="text-right">
                    <div id="res-score" class="text-3xl font-black text-white"></div>
                    <div class="text-[10px] text-slate-400 font-semibold">Deterministic Score</div>
                  </div>
                  <span id="res-status" class="inline-block"></span>
                  <a id="res-header-pdf-link" target="_blank" class="px-3.5 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-bold text-xs shadow-lg shadow-emerald-500/20 hover:scale-105 transition-all flex items-center gap-1.5" title="Download Official Legal Metrology PDF Report">
                    <i data-lucide="download" class="w-3.5 h-3.5"></i>
                    <span>Download Report</span>
                  </a>
                </div>
              </div>

              <!-- Deterministic Score Formula & 4-Tier Scale -->
              <div class="p-3.5 rounded-2xl bg-slate-950 border border-slate-800 space-y-2.5 text-xs">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-slate-400 font-bold text-[11px] uppercase tracking-wider">
                  <span class="flex items-center gap-1.5 text-cyan-400">
                    <i data-lucide="calculator" class="w-3.5 h-3.5"></i>
                    <span>Formula: Score = Passed Weight / Total Applicable Weight × 100</span>
                  </span>
                  <span id="res-formula-text" class="font-mono text-cyan-300 font-bold"></span>
                </div>
                
                <!-- 4 Tier Range Scale -->
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-0.5">
                  <div class="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-center">
                    <div class="font-extrabold text-emerald-400 text-xs">90 – 100%</div>
                    <div class="text-[10px] text-emerald-300 font-bold uppercase">COMPLIANT</div>
                  </div>
                  <div class="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-center">
                    <div class="font-extrabold text-cyan-400 text-xs">70 – 89%</div>
                    <div class="text-[10px] text-cyan-300 font-bold uppercase">MOSTLY COMPLIANT</div>
                  </div>
                  <div class="p-2 rounded-xl bg-amber-500/10 border border-amber-500/20 text-center">
                    <div class="font-extrabold text-amber-400 text-xs">40 – 69%</div>
                    <div class="text-[10px] text-amber-300 font-bold uppercase">NEEDS REVIEW</div>
                  </div>
                  <div class="p-2 rounded-xl bg-rose-500/10 border border-rose-500/20 text-center">
                    <div class="font-extrabold text-rose-400 text-xs">0 – 39%</div>
                    <div class="text-[10px] text-rose-300 font-bold uppercase">HIGH RISK</div>
                  </div>
                </div>
              </div>

              <!-- Summary Box -->
              <div class="p-3.5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1">
                <div class="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <i data-lucide="sparkles" class="w-3.5 h-3.5 text-cyan-400"></i>
                  <span>AI Statutory Assessment</span>
                </div>
                <p id="res-summary" class="text-xs text-slate-200 leading-relaxed"></p>
              </div>

              <!-- Status Checks Breakdown Grid -->
              <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-center">
                <div onclick="filterChecks('PASS')" class="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 cursor-pointer transition-all">
                  <div id="res-count-passed" class="text-lg font-bold text-emerald-400">0</div>
                  <div class="text-[10px] text-emerald-300 font-semibold uppercase">Passed Checks</div>
                </div>
                <div onclick="filterChecks('FAIL')" class="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 hover:bg-rose-500/20 cursor-pointer transition-all">
                  <div id="res-count-violations" class="text-lg font-bold text-rose-400">0</div>
                  <div class="text-[10px] text-rose-300 font-semibold uppercase">Failed Checks</div>
                </div>
                <div onclick="filterChecks('WARNING')" class="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 hover:bg-amber-500/20 cursor-pointer transition-all">
                  <div id="res-count-warnings" class="text-lg font-bold text-amber-400">0</div>
                  <div class="text-[10px] text-amber-300 font-semibold uppercase">Warnings</div>
                </div>
                <div onclick="filterChecks('MANUAL REVIEW')" class="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/20 hover:bg-purple-500/20 cursor-pointer transition-all">
                  <div id="res-count-review" class="text-lg font-bold text-purple-400">0</div>
                  <div class="text-[10px] text-purple-300 font-semibold uppercase">Manual Review</div>
                </div>
              </div>

              <!-- Priority Violations Breakdown Bar -->
              <div class="flex flex-wrap items-center justify-between gap-2 p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs">
                <span class="text-slate-400 font-bold uppercase tracking-wider text-[10px] flex items-center gap-1">
                  <i data-lucide="alert-triangle" class="w-3.5 h-3.5 text-rose-400"></i>
                  <span>Priority Violations:</span>
                </span>
                <div class="flex flex-wrap items-center gap-1.5">
                  <button onclick="filterPriority('CRITICAL')" id="res-pri-critical" class="priority-critical cursor-pointer hover:opacity-90">0 CRITICAL</button>
                  <button onclick="filterPriority('HIGH')" id="res-pri-high" class="priority-high cursor-pointer hover:opacity-90">0 HIGH</button>
                  <button onclick="filterPriority('MEDIUM')" id="res-pri-medium" class="priority-medium cursor-pointer hover:opacity-90">0 MEDIUM</button>
                  <button onclick="filterPriority('LOW')" id="res-pri-low" class="priority-low cursor-pointer hover:opacity-90">0 LOW</button>
                </div>
              </div>

              <!-- Quick Action Buttons -->
              <div class="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-800">
                <button onclick="toggleRawOcr()" class="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-850 text-slate-300 text-xs font-semibold border border-slate-800 flex items-center gap-1.5">
                  <i data-lucide="code-2" class="w-3.5 h-3.5 text-cyan-400"></i>
                  <span id="ocr-toggle-text">Show Detected OCR Segments</span>
                </button>
                <a id="res-pdf-link" target="_blank" class="px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-bold text-xs shadow-lg shadow-emerald-500/20 hover:scale-105 transition-all flex items-center gap-1.5">
                  <i data-lucide="download" class="w-3.5 h-3.5"></i>
                  <span>Download Report (PDF)</span>
                </a>
              </div>

              <div id="ocr-details-box" class="hidden p-3.5 rounded-xl bg-slate-950 border border-slate-850 text-xs space-y-3">
                <div class="font-mono text-slate-400 text-[10px]">Raw OCR Stream:</div>
                <pre id="raw-ocr-stream" class="whitespace-pre-wrap max-h-32 overflow-y-auto text-cyan-400 font-mono text-[10px] bg-slate-900 p-2 rounded-lg"></pre>
                <div class="font-mono text-slate-400 text-[10px]">OCR Text Segments & Confidence:</div>
                <div id="ocr-segments-list" class="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-48 overflow-y-auto"></div>
              </div>
            </div>

            <!-- Actionable Recommendations & Remediation Checklist -->
            <div class="glass-card p-6 rounded-3xl border border-slate-800 space-y-3.5 shadow-xl">
              <div class="flex items-center justify-between pb-2 border-b border-slate-800">
                <h4 class="text-sm font-bold text-white flex items-center gap-2">
                  <i data-lucide="list-checks" class="w-4 h-4 text-cyan-400"></i>
                  <span>Statutory Packaging Recommendations</span>
                </h4>
                <span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">Remediation Checklist</span>
              </div>
              <div id="recommendations-list" class="space-y-2.5"></div>
            </div>

            <!-- Review & Correct Extracted Declarations Form -->
            <div class="glass-card p-6 rounded-3xl border border-slate-800 space-y-4 shadow-xl">
              <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <h4 class="text-sm font-bold text-white flex items-center gap-1.5">
                  <i data-lucide="edit-3" class="w-4 h-4 text-cyan-400"></i>
                  <span>Review & Correct Extracted Declarations</span>
                </h4>
                <span class="text-[9px] font-semibold text-slate-500 uppercase tracking-wider">Editable Fields</span>
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
                  <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Manufacturer Details</label>
                  <input type="text" id="edit-manufacturer_details" class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-850 text-xs text-white focus:outline-none focus:border-cyan-500">
                </div>
                <div>
                  <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Address</label>
                  <input type="text" id="edit-address" class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-850 text-xs text-white focus:outline-none focus:border-cyan-500">
                </div>
                <div>
                  <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Importer Name (If Imported)</label>
                  <input type="text" id="edit-importer" class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-850 text-xs text-white focus:outline-none focus:border-cyan-500">
                </div>
                <div>
                  <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Country of Origin</label>
                  <input type="text" id="edit-country_of_origin" class="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-850 text-xs text-white focus:outline-none focus:border-cyan-500">
                </div>
                <div>
                  <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Customer Care Contacts</label>
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

            <!-- Mandatory Legal Declarations Detailed Audit Explorer -->
            <div class="glass-card p-6 rounded-3xl border border-slate-800 space-y-4 shadow-xl">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
                <h4 class="text-sm font-bold text-white flex items-center gap-2">
                  <i data-lucide="scale" class="w-4 h-4 text-cyan-400"></i>
                  <span>Legal Metrology Statutory Declarations Audit</span>
                </h4>
                <div class="flex flex-wrap items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800 text-[11px]">
                  <button onclick="filterChecks('ALL')" id="tab-all" class="px-2.5 py-1 rounded-lg font-bold text-cyan-400 bg-slate-800">All</button>
                  <button onclick="filterChecks('FAIL')" id="tab-fail" class="px-2.5 py-1 rounded-lg font-bold text-slate-400 hover:text-white">Failed</button>
                  <button onclick="filterChecks('WARNING')" id="tab-warning" class="px-2.5 py-1 rounded-lg font-bold text-slate-400 hover:text-white">Warnings</button>
                  <button onclick="filterChecks('PASS')" id="tab-pass" class="px-2.5 py-1 rounded-lg font-bold text-slate-400 hover:text-white">Passed</button>
                </div>
              </div>
              <div id="rules-list" class="space-y-3"></div>
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

  <!-- Lightbox Image Modal -->
  <div id="image-modal" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-md hidden flex items-center justify-center p-4" onclick="closeImageModal()">
    <div class="relative max-w-4xl max-h-[90vh] bg-slate-900 border border-slate-700 rounded-3xl p-4 shadow-2xl overflow-hidden" onclick="event.stopPropagation()">
      <button type="button" onclick="closeImageModal()" class="absolute top-4 right-4 p-2 rounded-full bg-slate-800 hover:bg-slate-700 text-white z-10 transition-colors">
        <i data-lucide="x" class="w-5 h-5"></i>
      </button>
      <img id="modal-img" class="max-h-[80vh] w-auto mx-auto rounded-xl object-contain">
    </div>
  </div>

  <!-- Footer -->
  <footer class="border-t border-slate-800 py-6 text-center text-xs text-slate-500">
    © 2026 PackSure AI – Legal Metrology Compliance Checker. India Legal Metrology (Packaged Commodities) Rules, 2011.
  </footer>

  <script>
    let currentFile = null;
    let currentReportData = null;
    let activeFilter = 'ALL';

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
        const url = URL.createObjectURL(currentFile);
        document.getElementById('preview-img').src = url;
        document.getElementById('res-img-thumb').src = url;
        document.getElementById('modal-img').src = url;
        document.getElementById('preview-actions').classList.remove('hidden');
        document.getElementById('file-info').innerText = currentFile.name + ' (' + (currentFile.size/1024).toFixed(1) + ' KB)';
        lucide.createIcons();
      }
    }

    function removeImage() {
      currentFile = null;
      currentReportData = null;
      document.getElementById('file-input').value = '';
      document.getElementById('preview-container').classList.add('hidden');
      document.getElementById('upload-prompt').classList.remove('hidden');
      document.getElementById('preview-actions').classList.add('hidden');
      document.getElementById('scan-results').classList.add('hidden');
      document.getElementById('scan-placeholder').classList.remove('hidden');
    }

    function openImageModal() {
      document.getElementById('image-modal').classList.remove('hidden');
    }

    function closeImageModal() {
      document.getElementById('image-modal').classList.add('hidden');
    }

    function renderRuleChecksList() {
      if (!currentReportData) return;
      const list = document.getElementById('rules-list');
      list.innerHTML = '';
      const allChecks = currentReportData.details?.rule_checks || [];
      
      const filtered = allChecks.filter(r => {
        if (activeFilter === 'ALL') return true;
        if (activeFilter === 'FAIL') return r.status === 'FAIL';
        if (activeFilter === 'WARNING') return r.status === 'WARNING';
        if (activeFilter === 'PASS') return r.status === 'PASS';
        if (['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].includes(activeFilter)) {
          return (r.priority || 'LOW') === activeFilter;
        }
        return true;
      });

      if (filtered.length === 0) {
        list.innerHTML = '<div class="p-6 text-center text-slate-500 text-xs rounded-2xl bg-slate-900/40 border border-slate-800">No declarations match the active filter.</div>';
        return;
      }

      filtered.forEach(r => {
        const item = document.createElement('div');
        const ruleStatusSlug = (r.status || 'pass').toLowerCase().replace(/\s+/g, '-');
        const priSlug = (r.priority || 'low').toLowerCase();
        item.className = 'p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1.5 text-xs';
        item.innerHTML = `
          <div class="flex justify-between items-center">
            <div class="flex flex-wrap items-center gap-2">
              <span class="font-mono text-cyan-400 font-bold">${r.rule_code}</span>
              <span class="priority-${priSlug}">${r.priority || 'LOW'} PRIORITY</span>
            </div>
            <span class="badge-${ruleStatusSlug}">${r.status}</span>
          </div>
          <div class="font-bold text-white">${r.title}</div>
          <div class="text-[10px] text-slate-400 italic">${r.clause || ''}</div>
          <div class="text-[11px] font-mono text-slate-300 bg-slate-950 p-2 rounded truncate"><span class="text-slate-500">Extracted:</span> ${r.value || 'Not Declared / Missing'}</div>
          <div class="text-slate-300"><span class="text-slate-500 font-semibold">Finding:</span> ${r.finding}</div>
          <div class="text-cyan-300 pt-0.5"><span class="text-cyan-500 font-semibold">Action:</span> ${r.remediation}</div>
        `;
        list.appendChild(item);
      });
    }

    function filterChecks(filterType) {
      activeFilter = filterType;
      ['all', 'fail', 'warning', 'pass'].forEach(t => {
        const el = document.getElementById('tab-' + t);
        if (el) {
          if (t.toUpperCase() === filterType) {
            el.className = 'px-2.5 py-1 rounded-lg font-bold text-cyan-400 bg-slate-800';
          } else {
            el.className = 'px-2.5 py-1 rounded-lg font-bold text-slate-400 hover:text-white';
          }
        }
      });
      renderRuleChecksList();
    }

    function filterPriority(priType) {
      activeFilter = priType;
      renderRuleChecksList();
    }

    function renderRecommendations(checks) {
      const recList = document.getElementById('recommendations-list');
      recList.innerHTML = '';
      const issues = checks.filter(r => r.status !== 'PASS');
      if (issues.length === 0) {
        recList.innerHTML = `
          <div class="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center gap-2">
            <i data-lucide="check-circle" class="w-4 h-4 text-emerald-400 flex-shrink-0"></i>
            <span>Packaging label is fully compliant with Legal Metrology requirements. Ready for commercial market distribution.</span>
          </div>
        `;
        return;
      }
      issues.forEach((r, idx) => {
        const item = document.createElement('div');
        const priClass = r.priority === 'CRITICAL' ? 'bg-rose-500/20 text-rose-300 border-rose-500/40' :
                         r.priority === 'HIGH' ? 'bg-orange-500/20 text-orange-300 border-orange-500/40' :
                         'bg-purple-500/20 text-purple-300 border-purple-500/40';
        item.className = 'p-3 rounded-xl bg-slate-900/80 border border-slate-800 flex items-start gap-2.5 text-xs';
        item.innerHTML = `
          <span class="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold border flex-shrink-0 mt-0.5 ${priClass}">${idx + 1}</span>
          <div class="space-y-0.5 flex-1">
            <div class="flex items-center justify-between">
              <span class="font-bold text-white">${r.title}</span>
              <span class="text-[10px] font-mono text-slate-400">${r.clause || ''}</span>
            </div>
            <p class="text-cyan-300 leading-relaxed">${r.remediation}</p>
          </div>
        `;
        recList.appendChild(item);
      });
    }

    function populateReportData(data) {
      currentReportData = data;
      document.getElementById('res-code').innerText = data.report_code;
      document.getElementById('res-name').innerText = data.product_name;
      document.getElementById('res-category').innerText = data.category || data.detected_category || 'Food';
      document.getElementById('res-score').innerText = data.compliance_score + '%';
      
      const stEl = document.getElementById('res-status');
      const statusSlug = (data.compliance_status || 'compliant').toLowerCase().replace(/\s+/g, '-');
      stEl.className = 'badge-' + statusSlug;
      stEl.innerText = data.compliance_status;
      
      const formulaStr = data.details?.formula || `Score = Passed Weight / Total Weight × 100 = ${data.compliance_score}%`;
      document.getElementById('res-formula-text').innerText = formulaStr;
      document.getElementById('res-summary').innerText = data.summary;
      
      document.getElementById('res-count-passed').innerText = data.passed_count || 0;
      document.getElementById('res-count-violations').innerText = data.violations_count || 0;
      document.getElementById('res-count-warnings').innerText = data.warnings_count || 0;
      document.getElementById('res-count-review').innerText = data.manual_review_count || 0;
      document.getElementById('res-pdf-link').href = '/api/reports/' + data.id + '/pdf';
      const headerPdf = document.getElementById('res-header-pdf-link');
      if (headerPdf) headerPdf.href = '/api/reports/' + data.id + '/pdf';

      // Update Priority Counts
      const checks = data.details?.rule_checks || [];
      const priCrit = data.details?.critical_violations_count !== undefined 
        ? data.details.critical_violations_count 
        : checks.filter(r => r.priority === 'CRITICAL' && r.status !== 'PASS').length;
      const priHi = data.details?.high_violations_count !== undefined 
        ? data.details.high_violations_count 
        : checks.filter(r => r.priority === 'HIGH' && r.status !== 'PASS').length;
      const priMed = data.details?.medium_violations_count !== undefined 
        ? data.details.medium_violations_count 
        : checks.filter(r => r.priority === 'MEDIUM' && r.status !== 'PASS').length;
      const priLo = data.details?.low_violations_count !== undefined 
        ? data.details.low_violations_count 
        : checks.filter(r => r.priority === 'LOW' && r.status !== 'PASS').length;

      document.getElementById('res-pri-critical').innerText = `${priCrit} CRITICAL`;
      document.getElementById('res-pri-high').innerText = `${priHi} HIGH`;
      document.getElementById('res-pri-medium').innerText = `${priMed} MEDIUM`;
      document.getElementById('res-pri-low').innerText = `${priLo} LOW`;

      // Render Recommendations Checklist
      renderRecommendations(checks);

      // Render Filtered Rule Checks
      renderRuleChecksList();

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
      lucide.createIcons();
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
        document.getElementById('scan-results').classList.remove('hidden');

        populateReportData(data);
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
        populateReportData(data);
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
      text.innerText = showOcrDetails ? 'Hide Detected OCR Segments' : 'Show Detected OCR Segments';
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
