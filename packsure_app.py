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

# Configure OpenMP and stdout encoding for Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
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
# Legal Metrology Compliance Rules Engine (Packaged Commodities Rules 2011)
# -----------------------------------------------------------------------------
class LegalMetrologyRulesEngine:
    MANDATORY_RULES = [
        {
            "id": "RULE_6_1_A",
            "code": "LM-RULE-6-1-A",
            "title": "Manufacturer / Packer / Importer Address",
            "clause": "Rule 6(1)(a) of Legal Metrology (Packaged Commodities) Rules 2011",
            "description": "Name and complete address of the manufacturer, packer, or importer must be clearly declared.",
            "field": "manufacturer_details",
            "weight": 15
        },
        {
            "id": "RULE_6_1_B",
            "code": "LM-RULE-6-1-B",
            "title": "Generic / Common Name of Commodity",
            "clause": "Rule 6(1)(b) of Legal Metrology (Packaged Commodities) Rules 2011",
            "description": "The common or generic name of the commodity contained in the package.",
            "field": "commodity_name",
            "weight": 15
        },
        {
            "id": "RULE_6_1_C",
            "code": "LM-RULE-6-1-C",
            "title": "Net Quantity & Standard Units",
            "clause": "Rule 6(1)(c) & Rule 7 of Legal Metrology Rules",
            "description": "Net quantity in metric units (g, kg, ml, l, N, pcs) with clear numeral spacing.",
            "field": "net_quantity",
            "weight": 20
        },
        {
            "id": "RULE_6_1_D",
            "code": "LM-RULE-6-1-D",
            "title": "Month & Year of Manufacture / Packing",
            "clause": "Rule 6(1)(d) of Legal Metrology Rules",
            "description": "Date of manufacture/packing/import in MM/YYYY, Month Year, or DD/MM/YYYY format.",
            "field": "mfg_date",
            "weight": 15
        },
        {
            "id": "RULE_6_1_E",
            "code": "LM-RULE-6-1-E",
            "title": "Maximum Retail Price (MRP)",
            "clause": "Rule 6(1)(e) of Legal Metrology Rules",
            "description": "MRP declared as 'MRP Rs. XX (inclusive of all taxes)' or '₹ XX (incl. of all taxes)'.",
            "field": "mrp",
            "weight": 15
        },
        {
            "id": "RULE_6_1_E_USP",
            "code": "LM-RULE-6-1-E-USP",
            "title": "Unit Sale Price (USP)",
            "clause": "Rule 6(1)(e) Amendment 2021",
            "description": "Unit Sale Price (e.g. ₹/g, ₹/kg, ₹/ml) declared clearly alongside MRP for packages > 10g/ml.",
            "field": "unit_sale_price",
            "weight": 10
        },
        {
            "id": "RULE_6_1_F",
            "code": "LM-RULE-6-1-F",
            "title": "Customer Care Contact Details",
            "clause": "Rule 6(1)(f) of Legal Metrology Rules",
            "description": "Complete contact info including Email, Helpline Number, and Address for consumer complaints.",
            "field": "customer_care",
            "weight": 10
        }
    ]

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        results = []
        earned = 0.0
        total = sum(r["weight"] for r in cls.MANDATORY_RULES)

        for rule in cls.MANDATORY_RULES:
            val = str(data.get(rule["field"], "") or "").strip()
            res = cls._check_rule(rule["id"], val, data)
            score_earned = rule["weight"] * res["fraction"]
            earned += score_earned

            results.append({
                "rule_id": rule["id"],
                "rule_code": rule["code"],
                "title": rule["title"],
                "clause": rule["clause"],
                "description": rule["description"],
                "field": rule["field"],
                "value": val if val else None,
                "status": res["status"],
                "weight": rule["weight"],
                "score_earned": round(score_earned, 2),
                "finding": res["finding"],
                "remediation": res["remediation"]
            })

        final_score = round((earned / total) * 100.0, 1) if total > 0 else 0.0
        status = "PASS" if final_score >= 85.0 else ("WARNING" if final_score >= 60.0 else "FAIL")
        risk = "LOW" if final_score >= 85.0 else ("MEDIUM" if final_score >= 60.0 else "HIGH")

        return {
            "score": final_score,
            "status": status,
            "risk_level": risk,
            "passed_count": sum(1 for r in results if r["status"] == "PASS"),
            "warnings_count": sum(1 for r in results if r["status"] == "WARNING"),
            "violations_count": sum(1 for r in results if r["status"] == "FAIL"),
            "rule_checks": results
        }

    @classmethod
    def _check_rule(cls, rule_id: str, val: str, full_data: Dict[str, Any]) -> Dict[str, Any]:
        if not val:
            return {"status": "FAIL", "fraction": 0.0, "finding": "Declaration missing from packaging.", "remediation": "Print mandatory declaration on display panel."}
        v = val.lower()

        if rule_id == "RULE_6_1_A":
            if any(k in v for k in ["mfd", "manufactured", "packed", "ltd", "pvt", "corp", "inc", "road", "industrial", "estate", "india", "pin"]) or len(val) > 15:
                return {"status": "PASS", "fraction": 1.0, "finding": "Valid manufacturer/packer details declared.", "remediation": "Compliant."}
            return {"status": "WARNING", "fraction": 0.5, "finding": "Partial manufacturer details.", "remediation": "Include full registered address & PIN code."}

        elif rule_id == "RULE_6_1_B":
            if len(val) >= 3:
                return {"status": "PASS", "fraction": 1.0, "finding": f"Commodity '{val}' declared.", "remediation": "Compliant."}
            return {"status": "FAIL", "fraction": 0.0, "finding": "Commodity name too short.", "remediation": "Declare full generic commodity name."}

        elif rule_id == "RULE_6_1_C":
            if re.search(r'(\d+(\.\d+)?)\s*(g|kg|ml|l|ltr|grams|n|pcs|units)\b', v):
                return {"status": "PASS", "fraction": 1.0, "finding": f"Net quantity '{val}' in metric units.", "remediation": "Compliant."}
            elif any(c.isdigit() for c in val):
                return {"status": "WARNING", "fraction": 0.6, "finding": "Number found but missing metric unit.", "remediation": "Use standard metric units (e.g. '500 g')."}
            return {"status": "FAIL", "fraction": 0.0, "finding": "Invalid quantity format.", "remediation": "Specify net quantity in SI metric units."}

        elif rule_id == "RULE_6_1_D":
            if re.search(r'(\b(0[1-9]|1[0-2])[\/\-](20\d{2}|\d{2})\b|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(20\d{2}|\d{2})\b|\b\d{4}\b)', v):
                return {"status": "PASS", "fraction": 1.0, "finding": f"Mfg date '{val}' present.", "remediation": "Compliant."}
            return {"status": "FAIL", "fraction": 0.0, "finding": "Non-standard date.", "remediation": "Use MM/YYYY format (e.g. 08/2026)."}

        elif rule_id == "RULE_6_1_E":
            has_tax = any(t in v for t in ["incl", "tax", "taxes"])
            has_mrp = any(m in v for m in ["mrp", "m.r.p", "rs", "₹", "price"])
            has_digit = any(c.isdigit() for c in val)
            if has_mrp and has_digit and has_tax:
                return {"status": "PASS", "fraction": 1.0, "finding": f"MRP '{val}' inclusive of taxes.", "remediation": "Compliant."}
            elif has_mrp and has_digit:
                return {"status": "WARNING", "fraction": 0.7, "finding": "MRP present but missing '(inclusive of all taxes)'.", "remediation": "Add '(inclusive of all taxes)'."}
            return {"status": "FAIL", "fraction": 0.0, "finding": "MRP missing or illegible.", "remediation": "Declare 'MRP Rs. XX.XX (incl. of all taxes)'."}

        elif rule_id == "RULE_6_1_E_USP":
            if any(u in v for u in ["per", "/", "g", "kg", "ml", "l"]) and any(c.isdigit() for c in val):
                return {"status": "PASS", "fraction": 1.0, "finding": f"USP '{val}' present.", "remediation": "Compliant."}
            return {"status": "WARNING", "fraction": 0.4, "finding": "USP not clearly stated.", "remediation": "State Unit Sale Price (e.g. ₹0.50/g)."}

        elif rule_id == "RULE_6_1_F":
            if "@" in val or "email" in v or any(c.isdigit() for c in val):
                return {"status": "PASS", "fraction": 1.0, "finding": "Customer care contact present.", "remediation": "Compliant."}
            return {"status": "FAIL", "fraction": 0.0, "finding": "No consumer care helpline.", "remediation": "Provide consumer helpline number and email."}

        return {"status": "FAIL", "fraction": 0.0, "finding": "Check failed.", "remediation": "Review label."}

# -----------------------------------------------------------------------------
# Real OCR Engine (EasyOCR + PyTesseract + Layout)
# -----------------------------------------------------------------------------
_easyocr_reader = None

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

        raw_lines = []
        reader = get_reader()
        if reader and os.path.exists(image_path):
            try:
                results = reader.readtext(image_path)
                for bbox, text, conf in results:
                    t = text.strip()
                    if t:
                        raw_lines.append(t)
            except Exception as e:
                logger.warning(f"EasyOCR read error: {e}")

        # Fallback to pytesseract
        if not raw_lines:
            try:
                import pytesseract
                full = pytesseract.image_to_string(Image.open(image_path)).strip()
                if full:
                    raw_lines = [l.strip() for l in full.split("\n") if l.strip()]
            except Exception:
                pass

        raw_text = "\n".join(raw_lines) if raw_lines else "No text detected."
        fields = cls._parse_fields(raw_text, raw_lines)
        return {"raw_text": raw_text, "fields": fields, "image_dimensions": {"width": width, "height": height}}

    @classmethod
    def _parse_fields(cls, raw_text: str, lines: List[str]) -> Dict[str, str]:
        fields = {"commodity_name": "", "brand": "", "net_quantity": "", "mrp": "", "unit_sale_price": "", "mfg_date": "", "expiry_date": "", "manufacturer_details": "", "customer_care": "", "country_of_origin": ""}
        
        # Net Qty
        m = re.search(r'(\b\d+(\.\d+)?\s*(?:g|kg|ml|l|ltr|grams|n|pcs|units)\b)', raw_text, re.I)
        if m: fields["net_quantity"] = m.group(1).strip()
        
        # MRP
        m = re.search(r'((?:mrp|m\.r\.p|price|₹|rs\.?)\s*[:.-]?\s*(?:rs\.?|₹)?\s*\d+(?:\.\d{2})?(?:\s*(?:\(?[^)\n]*incl[^)\n]*\)?))?)', raw_text, re.I)
        if m and m.group(1).strip(): fields["mrp"] = m.group(1).strip()
        
        # USP
        m = re.search(r'((?:usp|unit\s*price|₹\s*\/?\s*g|rs\.?\s*\/?\s*g)\s*[:.-]?\s*(?:rs\.?|₹)?\s*\d+(?:\.\d{2})?\s*(?:per|\/)\s*(?:g|kg|ml|l|unit|piece|n))', raw_text, re.I)
        if m: fields["unit_sale_price"] = m.group(1).strip()
        
        # Mfg Date
        m = re.search(r'((?:mfg|mfd|packed|pkd)\s*[:.-]?\s*(?:[0-3]?[0-9][\/\-.])?[0-1]?[0-9][\/\-.][1-2][0-9]{3}|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,.-]+[1-2][0-9]{3})', raw_text, re.I)
        if m: fields["mfg_date"] = m.group(1).strip()

        # Manufacturer
        for l in lines:
            if any(k in l.lower() for k in ["mfd by", "manufactured by", "packed by", "pvt ltd", "limited", "industries", "estate"]):
                fields["manufacturer_details"] = l
                break

        # Customer Care
        for l in lines:
            if any(k in l.lower() for k in ["care", "customer", "helpline", "email", "@", "complaint"]):
                fields["customer_care"] = l
                break

        # Commodity / Brand
        if lines:
            fields["brand"] = lines[0][:40]
            fields["commodity_name"] = lines[1][:60] if len(lines) > 1 else lines[0][:60]

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
    return {"status": "online", "engine": "EasyOCR + Legal Metrology Rules 2011", "version": "1.0.0"}

@app.get("/api/compliance/rules")
async def get_rules():
    return {"rules": LegalMetrologyRulesEngine.MANDATORY_RULES}

@app.post("/api/scan")
async def scan(
    file: UploadFile = File(...),
    product_name: Optional[str] = Form(None),
    category: Optional[str] = Form("Packaged Food"),
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

    eval_res = LegalMetrologyRulesEngine.validate(fields)
    
    p_name = fields.get("commodity_name") or product_name or "Packaged Product"
    p_brand = fields.get("brand") or "Brand"
    
    summary = f"Audit evaluated with score {eval_res['score']}% ({eval_res['status']}). Enforces Legal Metrology Rules 2011."
    
    product = Product(name=f"{p_brand} - {p_name}", category=category or "Packaged Food", brand=p_brand)
    db.add(product)
    await db.flush()

    scan_res = ScanResult(
        product_id=product.id,
        image_url=f"/uploads/{unique_fn}",
        image_filename=unique_fn,
        extracted_data={"fields": fields, "raw_text": ocr_res["raw_text"], "rule_checks": eval_res["rule_checks"], "summary": summary},
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
        "compliance_score": scan_res.compliance_score,
        "compliance_status": scan_res.compliance_status,
        "risk_level": scan_res.risk_level,
        "passed_count": report.passed_count,
        "warnings_count": report.warnings_count,
        "violations_count": report.violations_count,
        "summary": summary,
        "details": scan_res.extracted_data
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
    return """<!DOCTYPE html>
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
              <label class="block text-xs font-semibold text-slate-300 mb-1">Category</label>
              <select id="p-category" class="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-sm focus:outline-none focus:border-cyan-500">
                <option>Packaged Food</option>
                <option>Dairy & Beverages</option>
                <option>Cosmetics & Personal Care</option>
                <option>General Goods</option>
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
                  <span id="res-code" class="text-xs font-mono text-cyan-400 font-bold"></span>
                  <h3 id="res-name" class="text-xl font-bold text-white mt-0.5"></h3>
                </div>
                <div class="text-right">
                  <div id="res-score" class="text-3xl font-black text-white"></div>
                  <span id="res-status" class="inline-block mt-1"></span>
                </div>
              </div>
              <p id="res-summary" class="text-xs text-slate-300 bg-slate-900/80 p-3 rounded-xl border border-slate-850 leading-relaxed"></p>
              <div class="flex justify-between items-center pt-2">
                <span id="res-counts" class="text-xs font-semibold text-slate-400"></span>
                <a id="res-pdf-link" target="_blank" class="px-4 py-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs font-bold hover:bg-emerald-500/20">
                  <i data-lucide="download" class="w-3.5 h-3.5 inline-block mr-1"></i> Download PDF
                </a>
              </div>
            </div>

            <div class="glass-card p-6 rounded-3xl border border-slate-800 space-y-4">
              <h4 class="text-sm font-bold text-white">7 Mandatory Declarations Audit Breakdown</h4>
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
        document.getElementById('res-score').innerText = data.compliance_score + '%';
        
        const stEl = document.getElementById('res-status');
        stEl.className = 'badge-' + data.compliance_status.toLowerCase();
        stEl.innerText = data.compliance_status;
        
        document.getElementById('res-summary').innerText = data.summary;
        document.getElementById('res-counts').innerText = 'Passed: ' + data.passed_count + ' | Warnings: ' + data.warnings_count + ' | Failures: ' + data.violations_count;
        document.getElementById('res-pdf-link').href = '/api/reports/' + data.id + '/pdf';

        const list = document.getElementById('rules-list');
        list.innerHTML = '';
        (data.details?.rule_checks || []).forEach(r => {
          const item = document.createElement('div');
          item.className = 'p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1.5 text-xs';
          item.innerHTML = `
            <div class="flex justify-between items-center">
              <span class="font-mono text-cyan-400 font-bold">${r.rule_code}</span>
              <span class="badge-${r.status.toLowerCase()}">${r.status}</span>
            </div>
            <div class="font-bold text-white">${r.title}</div>
            <div class="text-[11px] font-mono text-slate-300 bg-slate-950 p-2 rounded">${r.value || 'Not Declared / Missing'}</div>
            <div class="text-slate-400">${r.finding}</div>
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
