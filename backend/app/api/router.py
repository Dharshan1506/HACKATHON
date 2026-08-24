import os
import uuid
import datetime
from typing import Optional, List
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
    Accepts packaging label image, runs OCR extraction and AI Legal Metrology compliance evaluation.
    """
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    unique_filename = f"scan_{uuid.uuid4().hex[:10]}{ext}"
    saved_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    with open(saved_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 1. Run OCR
    ocr_result = await OCREngine.process_image(saved_path, file.filename)
    fields = ocr_result["fields"]

    if product_name:
        fields["commodity_name"] = product_name
    if brand:
        fields["brand"] = brand

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
    p_name = fields.get("commodity_name", product_name or "Packaged Product")
    p_brand = fields.get("brand", brand or "Generic Brand")
    
    product = Product(name=f"{p_brand} - {p_name}", category=category, brand=p_brand)
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
        "scan_id": scan_result.id,
        "report_id": report.id,
        "report_code": report.report_code,
        "product_name": product.name,
        "compliance_score": scan_result.compliance_score,
        "compliance_status": scan_result.compliance_status,
        "risk_level": scan_result.risk_level,
        "summary": compliance_analysis["summary"],
        "extracted_data": extracted_payload,
        "created_at": scan_result.created_at.isoformat()
    }

@router.post("/upload")
async def upload_product_package(
    file: UploadFile = File(...),
    category: str = Form("Packaged Food"),
    db: AsyncSession = Depends(get_db)
):
    return await scan_product(file=file, category=category, db=db)

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

@router.post("/demo/seed")
async def seed_demo_data(db: AsyncSession = Depends(get_db)):
    """
    Populates database with sample packaged commodity scan reports.
    """
    sample_files = [
        ("cooking_oil.jpg", "SunPure - Refined Sunflower Cooking Oil", "Packaged Food"),
        ("choco_biscuit.jpg", "NutriBite - Choco Crunch Biscuits", "Packaged Food"),
        ("herbal_shampoo.jpg", "Botanica - Herbal Hair Shampoo", "Cosmetics"),
        ("organic_milk.jpg", "PureNature - Organic Almond Milk", "Dairy & Beverages")
    ]

    created = 0
    for filename, p_name, category in sample_files:
        mock_path = os.path.join(settings.UPLOAD_DIR, filename)

        ocr_res = await OCREngine.process_image(mock_path, filename)
        comp_res = ComplianceAIAnalyzer.analyze(ocr_res["fields"])

        extracted_payload = {
            "fields": ocr_res["fields"],
            "raw_text": ocr_res["raw_text"],
            "bounding_boxes": ocr_res["bounding_boxes"],
            "rule_checks": comp_res["rule_checks"],
            "summary": comp_res["summary"],
            "action_items": comp_res["action_items"]
        }

        prod = Product(name=p_name, category=category, brand=ocr_res["fields"].get("brand", "Brand"))
        db.add(prod)
        await db.flush()

        scan = ScanResult(
            product_id=prod.id,
            image_url=f"/uploads/{filename}",
            image_filename=filename,
            extracted_data=extracted_payload,
            compliance_score=comp_res["score"],
            compliance_status=comp_res["status"],
            risk_level=comp_res["risk_level"]
        )
        db.add(scan)
        await db.flush()

        rep = Report(
            scan_id=scan.id,
            report_code=f"PSR-{uuid.uuid4().hex[:6].upper()}",
            title=f"Legal Metrology Audit - {p_name}",
            summary=comp_res["summary"],
            violations_count=comp_res["violations_count"],
            warnings_count=comp_res["warnings_count"],
            passed_count=comp_res["passed_count"],
            details=extracted_payload
        )
        db.add(rep)
        created += 1

    await db.commit()
    return {"message": f"Successfully seeded {created} demo compliance audit reports."}
