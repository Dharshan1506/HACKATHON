import os
import sys
import pypdfium2 as pdfium

# Ensure project paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

from app.reports.generator import ReportGenerator

def test_pdf_generation():
    print("=================================================================")
    print("   LEGAL METROLOGY PDF AUDIT REPORT GENERATION TEST")
    print("=================================================================")

    output_pdf_path = os.path.join(BASE_DIR, "backend", "uploads", "test_report_sample.pdf")
    if os.path.exists(output_pdf_path):
        os.remove(output_pdf_path)

    test_image_path = os.path.join(BASE_DIR, "test_label.jpg")

    mock_scan_data = {
        "compliance_score": 86.6,
        "compliance_status": "MOSTLY COMPLIANT",
        "risk_level": "LOW RISK",
        "extracted_data": {
            "category": "Food",
            "formula": "Score = 95.2 / 110.0 × 100 = 86.6%",
            "summary": "Packaging label satisfies 5 core statutory requirements. Unit Sale Price (USP) declaration is missing and requires remedial printing beside MRP.",
            "raw_text": "NutriPure Creamy Peanut Butter Net Qty: 350g MRP Rs 350.00 incl of all taxes Mfg Date: 01/2026 Exp: 12 Months NutriFoods Pvt Ltd Mumbai Consumer Care: 1800-222-3333 care@nutripure.com",
            "bounding_boxes": [
                {"box": [10, 10, 100, 30], "text": "NutriPure", "confidence": 0.98},
                {"box": [10, 35, 120, 55], "text": "Creamy Peanut Butter", "confidence": 0.95},
                {"box": [10, 60, 80, 80], "text": "Net Qty: 350g", "confidence": 0.92},
                {"box": [10, 85, 140, 105], "text": "MRP Rs 350.00", "confidence": 0.97},
            ],
            "critical_violations_count": 0,
            "high_violations_count": 1,
            "medium_violations_count": 0,
            "low_violations_count": 1,
            "fields": {
                "commodity_name": "Creamy Peanut Butter",
                "brand": "NutriPure",
                "net_quantity": "350g",
                "mrp": "Rs 350.00",
                "unit_sale_price": "",
                "mfg_date": "01/2026",
                "expiry_date": "12 Months",
                "manufacturer_details": "NutriFoods Pvt Ltd, Sector 5, Andheri East, Mumbai 400069",
                "country_of_origin": "India",
                "customer_care": "Tel: 1800-222-3333, Email: care@nutripure.com"
            },
            "rule_checks": [
                {
                    "rule_id": 6,
                    "rule_code": "LM-RULE-6-1-E-USP",
                    "title": "Unit Sale Price (USP)",
                    "clause": "Rule 6(1)(e) Amendment 2021",
                    "status": "FAIL",
                    "priority": "HIGH",
                    "value": "",
                    "finding": "Mandatory declaration for 'Unit Sale Price (USP)' is missing from packaging.",
                    "remediation": "Print Unit Sale Price as '₹ 1.00 per g' or '₹ 100 per 100g' alongside MRP."
                },
                {
                    "rule_id": 3,
                    "rule_code": "LM-RULE-6-1-C",
                    "title": "Net Quantity & Standard Units",
                    "clause": "Rule 6(1)(c) & Rule 7",
                    "status": "WARNING",
                    "priority": "LOW",
                    "value": "350g",
                    "finding": "Net quantity '350g' lacks mandated whitespace separation between numeral and unit.",
                    "remediation": "Separate numeral and unit symbol with a single space: '350 g'."
                },
                {
                    "rule_id": 1,
                    "rule_code": "LM-RULE-6-1-A",
                    "title": "Manufacturer / Packer / Importer Address",
                    "clause": "Rule 6(1)(a) PCR 2011",
                    "status": "PASS",
                    "priority": "LOW",
                    "value": "NutriFoods Pvt Ltd, Sector 5, Mumbai 400069",
                    "finding": "Valid manufacturer/packer name and complete registered address present.",
                    "remediation": "Declaration is compliant."
                },
                {
                    "rule_id": 2,
                    "rule_code": "LM-RULE-6-1-B",
                    "title": "Generic / Common Name of Commodity",
                    "clause": "Rule 6(1)(b) PCR 2011",
                    "status": "PASS",
                    "priority": "LOW",
                    "value": "Creamy Peanut Butter",
                    "finding": "Generic commodity name clearly declared.",
                    "remediation": "Declaration is compliant."
                },
                {
                    "rule_id": 4,
                    "rule_code": "LM-RULE-6-1-D",
                    "title": "Month & Year of Manufacture / Packing",
                    "clause": "Rule 6(1)(d) PCR 2011",
                    "status": "PASS",
                    "priority": "LOW",
                    "value": "01/2026",
                    "finding": "Valid manufacturing date '01/2026' declared.",
                    "remediation": "Declaration is compliant."
                },
                {
                    "rule_id": 5,
                    "rule_code": "LM-RULE-6-1-E",
                    "title": "Maximum Retail Price (MRP)",
                    "clause": "Rule 6(1)(e) PCR 2011",
                    "status": "PASS",
                    "priority": "LOW",
                    "value": "Rs 350.00",
                    "finding": "MRP inclusive of all taxes declared.",
                    "remediation": "Declaration is compliant."
                },
                {
                    "rule_id": 7,
                    "rule_code": "LM-RULE-6-1-F",
                    "title": "Consumer Care Details",
                    "clause": "Rule 6(1)(f) PCR 2011",
                    "status": "PASS",
                    "priority": "LOW",
                    "value": "Tel: 1800-222-3333, Email: care@nutripure.com",
                    "finding": "Complete consumer care phone and email declared.",
                    "remediation": "Declaration is compliant."
                }
            ]
        }
    }

    # Generate PDF Report
    gen_path = ReportGenerator.generate_pdf_report(
        report_code="PSR-TEST-88",
        product_name="NutriPure - Creamy Peanut Butter",
        scan_data=mock_scan_data,
        output_path=output_pdf_path,
        image_path=test_image_path if os.path.exists(test_image_path) else None
    )

    print(f" PDF Report Generated Successfully at: {gen_path}")
    assert os.path.exists(gen_path), "PDF file was not created!"
    file_size = os.path.getsize(gen_path)
    print(f" PDF File Size: {file_size:,} bytes")
    assert file_size > 1000, "PDF file is suspiciously small!"

    # Read PDF and verify required sections
    pdf_doc = pdfium.PdfDocument(gen_path)
    num_pages = len(pdf_doc)
    print(f" Total Pages: {num_pages}")
    assert num_pages >= 1, "PDF must have at least 1 page"

    full_text = ""
    for page in pdf_doc:
        textpage = page.get_textpage()
        full_text += textpage.get_text_range() + "\n"

    print("\n--- Verifying Required Content in PDF ---")
    required_keywords = [
        ("Product Details", ["NutriPure", "Creamy Peanut Butter", "350g", "Rs 350.00"]),
        ("OCR Information", ["PaddleOCR", "bounding boxes", "Raw Stream"]),
        ("Compliance Score", ["86.6%", "COMPLIANCE SCORE", "MOSTLY COMPLIANT"]),
        ("Passed/Failed Rules", ["PASSED: 5", "FAILED: 1", "WARNINGS: 1"]),
        ("Violations", ["PRIORITY ISSUES", "High"]),
        ("Recommendations", ["Actionable Statutory Packaging Recommendations", "Print Unit Sale Price"]),
        ("Rule References", ["LM-RULE-6-1-E-USP", "LM-RULE-6-1-C", "Rule 6(1)(e)", "Rule 6(1)(c)"]),
        ("Legal Disclaimer", ["STATUTORY REGULATORY DISCLAIMER", "Legal Metrology Act, 2009"])
    ]

    for section_name, terms in required_keywords:
        for term in terms:
            if term.lower() not in full_text.lower():
                print(f"❌ Missing expected term '{term}' for section '{section_name}' in PDF!")
                sys.exit(1)
        print(f" Verified: {section_name} present and complete")

    print("\n ALL PDF REPORT CONTENT TESTS PASSED WITH 100% COMPLIANCE!")
    print("=================================================================")

if __name__ == "__main__":
    test_pdf_generation()
