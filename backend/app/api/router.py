import os
import uuid
import datetime
from typing import Optional, List, Any
from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.config import settings
from app.database.connection import get_db
from app.database.models import Product, ScanResult, Report
from app.ocr.engine import OCREngine
from app.ai.analyzer import ComplianceAIAnalyzer
from app.compliance.rules import LegalMetrologyRulesEngine
from app.reports.generator import ReportGenerator

router = APIRouter(prefix=settings.API_PREFIX)

def _clean_form_str(val: Any) -> Optional[str]:
    if val is None or not isinstance(val, str):
        return None
    cleaned = val.strip()
    return cleaned if cleaned else None

@router.get("/health")
async def health_check():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }

@router.get("/compliance/rules")
async def get_compliance_rules():
    return {
        "rules": LegalMetrologyRulesEngine.MANDATORY_RULES,
        "reference": "Legal Metrology (Packaged Commodities) Rules, 2011"
    }

@router.post("/scan")
async def scan_product(
    file: UploadFile = File(...),
    product_name: Optional[str] = Form(None),
    category: Optional[str] = Form("Packaged Commodity"),
    brand: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Accepts packaging label image, runs genuine OCR extraction and AI Legal Metrology compliance evaluation.
    """
    clean_p_name = _clean_form_str(product_name)
    clean_category = _clean_form_str(category) or "Packaged Commodity"
    clean_brand = _clean_form_str(brand)

    ext = os.path.splitext(file.filename)[1] or ".jpg"
    unique_filename = f"scan_{uuid.uuid4().hex[:10]}{ext}"
    saved_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    with open(saved_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 1. Run Authentic OCR
    ocr_result = await OCREngine.process_image(saved_path, file.filename)
    fields = ocr_result["fields"]

    if clean_p_name:
        fields["commodity_name"] = clean_p_name
    if clean_brand:
        fields["brand"] = clean_brand

    # 2. Run AI Compliance Evaluation
    compliance_analysis = ComplianceAIAnalyzer.analyze(fields)

    extracted_payload = {
        "fields": fields,
        "raw_text": ocr_result["raw_text"],
        "bounding_boxes": ocr_result["bounding_boxes"],
        "rule_checks": compliance_analysis["rule_checks"],
        "summary": compliance_analysis["summary"],
        "action_items": compliance_analysis["action_items"]
    }

    # 3. Save Product
    p_name = fields.get("commodity_name") or clean_p_name or "Packaged Product"
    p_brand = fields.get("brand") or clean_brand or "Generic Brand"
    
    product = Product(
        name=f"{p_brand} - {p_name}" if p_brand and p_name else (p_name or "Product"),
        category=clean_category,
        brand=p_brand
    )
    db.add(product)
    await db.flush()

    # 4. Save ScanResult
    scan_result = ScanResult(
        product_id=product.id,
        image_url=f"/uploads/{unique_filename}",
        image_filename=unique_filename,
        extracted_data=extracted_payload,
        compliance_score=compliance_analysis["score"],
        compliance_status=compliance_analysis["status"],
        risk_level=compliance_analysis["risk_level"]
    )
    db.add(scan_result)
    await db.flush()

    # 5. Save Report
    report_code = f"PSR-{uuid.uuid4().hex[:6].upper()}"
    report = Report(
        scan_id=scan_result.id,
        report_code=report_code,
        title=f"Legal Metrology Audit Report - {p_name}",
        summary=compliance_analysis["summary"],
        violations_count=compliance_analysis["violations_count"],
        warnings_count=compliance_analysis["warnings_count"],
        passed_count=compliance_analysis["passed_count"],
        details=extracted_payload
    )
    db.add(report)
    await db.commit()

    return {
        "id": report.id,
        "scan_id": scan_result.id,
        "report_id": report.id,
        "report_code": report.report_code,
        "product_name": product.name,
        "category": product.category,
        "brand": product.brand,
        "compliance_score": scan_result.compliance_score,
        "compliance_status": scan_result.compliance_status,
        "risk_level": scan_result.risk_level,
        "passed_count": report.passed_count,
        "warnings_count": report.warnings_count,
        "violations_count": report.violations_count,
        "summary": compliance_analysis["summary"],
        "extracted_data": extracted_payload,
        "details": extracted_payload,
        "created_at": scan_result.created_at.isoformat()
    }

@router.post("/ocr")
async def run_dedicated_ocr(file: UploadFile = File(...)):
    """
    Accepts image file, runs OpenCV preprocessing and PaddleOCR to return raw text + bounding boxes + confidence
    """
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    unique_filename = f"ocr_{uuid.uuid4().hex[:10]}{ext}"
    saved_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    with open(saved_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        ocr_result = await OCREngine.process_image(saved_path, file.filename)
    finally:
        if os.path.exists(saved_path):
            try:
                os.remove(saved_path)
            except Exception:
                pass

    return ocr_result

@router.post("/upload")
async def upload_product_package(
    file: UploadFile = File(...),
    category: Optional[str] = Form("Packaged Food"),
    db: AsyncSession = Depends(get_db)
):
    return await scan_product(file=file, product_name=None, category=category, brand=None, db=db)

@router.get("/reports")
async def list_reports(
    status: Optional[str] = None,
    query: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Report, ScanResult, Product).join(
        ScanResult, Report.scan_id == ScanResult.id
    ).outerjoin(
        Product, ScanResult.product_id == Product.id
    ).order_by(desc(Report.created_at))

    result = await db.execute(stmt)
    rows = result.all()

    reports_list = []
    for rep, scan, prod in rows:
        if status and status.upper() != "ALL" and scan.compliance_status != status.upper():
            continue
        
        prod_name = prod.name if prod else rep.title
        if query and query.lower() not in prod_name.lower() and query.lower() not in rep.report_code.lower():
            continue

        reports_list.append({
            "id": rep.id,
            "scan_id": scan.id,
            "report_code": rep.report_code,
            "product_name": prod_name,
            "category": prod.category if prod else "General",
            "compliance_score": scan.compliance_score,
            "compliance_status": scan.compliance_status,
            "risk_level": scan.risk_level,
            "violations_count": rep.violations_count,
            "warnings_count": rep.warnings_count,
            "passed_count": rep.passed_count,
            "created_at": rep.created_at.isoformat(),
            "summary": rep.summary
        })

    return {"reports": reports_list, "total": len(reports_list)}

@router.get("/reports/{report_id}")
async def get_report_detail(report_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Report, ScanResult, Product).join(
        ScanResult, Report.scan_id == ScanResult.id
    ).outerjoin(
        Product, ScanResult.product_id == Product.id
    ).where(Report.id == report_id)

    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    rep, scan, prod = row
    return {
        "id": rep.id,
        "scan_id": scan.id,
        "report_code": rep.report_code,
        "product_name": prod.name if prod else rep.title,
        "category": prod.category if prod else "General",
        "brand": prod.brand if prod else "",
        "compliance_score": scan.compliance_score,
        "compliance_status": scan.compliance_status,
        "risk_level": scan.risk_level,
        "violations_count": rep.violations_count,
        "warnings_count": rep.warnings_count,
        "passed_count": rep.passed_count,
        "created_at": rep.created_at.isoformat(),
        "summary": rep.summary,
        "details": rep.details,
        "image_url": scan.image_url
    }

@router.get("/reports/{report_id}/pdf")
async def download_report_pdf(report_id: int, db: AsyncSession = Depends(get_db)):
    rep_data = await get_report_detail(report_id, db)
    
    pdf_filename = f"Report_{rep_data['report_code']}.pdf"
    pdf_path = os.path.join(settings.UPLOAD_DIR, pdf_filename)
    
    ReportGenerator.generate_pdf_report(
        report_code=rep_data['report_code'],
        product_name=rep_data['product_name'],
        scan_data={
            "compliance_score": rep_data['compliance_score'],
            "compliance_status": rep_data['compliance_status'],
            "risk_level": rep_data['risk_level'],
            "extracted_data": rep_data['details']
        },
        output_path=pdf_path
    )

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_filename
    )
