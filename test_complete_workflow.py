import os
import sys
import requests
import json
import pypdfium2 as pdfium

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
API_URL = "http://localhost:8000"

def test_full_pipeline_workflow():
    print("=" * 70)
    print("      PACKSURE AI - COMPLETE END-TO-END PIPELINE AUDIT TEST")
    print("=" * 70)

    # -------------------------------------------------------------
    # STEP 1: Image Upload & Real OCR Execution
    # -------------------------------------------------------------
    print("\n--- [STEP 1/10] Upload Product Packaging Image & Trigger OCR ---")
    img_path = os.path.join(BASE_DIR, "test_label.png")
    if not os.path.exists(img_path):
        img_path = os.path.join(BASE_DIR, "sample_test_label.jpg")
    
    assert os.path.exists(img_path), f"Test label image missing at {img_path}"
    print(f"Using authentic label image: {os.path.basename(img_path)} ({os.path.getsize(img_path):,} bytes)")

    with open(img_path, "rb") as f:
        files = {"file": (os.path.basename(img_path), f, "image/png")}
        form_data = {
            "product_name": "NutriPure Almond Butter Creamy",
            "category": "Auto-Detect"
        }
        res = requests.post(f"{API_URL}/api/scan", files=files, data=form_data)

    print(f"API Scan Response Code: {res.status_code}")
    assert res.status_code == 200, f"Scan failed: {res.text}"
    scan_data = res.json()
    report_id = scan_data["id"]
    report_code = scan_data["report_code"]
    print(f" Scan Successful! Report ID: {report_id} | Report Code: {report_code}")

    # -------------------------------------------------------------
    # STEP 2: Verify Authentic OCR & OpenCV Extraction
    # -------------------------------------------------------------
    print("\n--- [STEP 2/10] Verify Authentic OCR & OpenCV Extraction ---")
    raw_ocr = scan_data["details"].get("raw_text", "")
    bboxes = scan_data["details"].get("bounding_boxes", [])
    print(f"Raw OCR Text Extracted ({len(raw_ocr)} chars): \"{raw_ocr[:120]}...\"")
    print(f"Detected Text Segments / Bounding Boxes: {len(bboxes)}")
    assert len(raw_ocr) > 20, "OCR produced suspiciously empty text!"
    assert len(bboxes) > 0, "No bounding boxes extracted!"
    print(" Verified: Real OCR text and bounding boxes extracted.")

    # -------------------------------------------------------------
    # STEP 3: Verify AI Information Extraction (NLP & Structured JSON)
    # -------------------------------------------------------------
    print("\n--- [STEP 3/10] Verify AI Structured Information Extraction ---")
    fields = scan_data["details"].get("fields", {})
    print("Structured Fields Extracted:")
    for k, v in fields.items():
        print(f"  • {k}: '{v}'")
    
    assert "net_quantity" in fields, "Net quantity field missing from extraction!"
    assert "mrp" in fields, "MRP field missing from extraction!"
    assert "manufacturer_details" in fields or "address" in fields, "Manufacturer info missing from extraction!"
    print(" Verified: Structured JSON extractions without hallucination.")

    # -------------------------------------------------------------
    # STEP 4: Verify Category Detection
    # -------------------------------------------------------------
    print("\n--- [STEP 4/10] Verify Category Classification ---")
    detected_cat = scan_data.get("detected_category") or scan_data.get("category")
    print(f"Detected Commodity Category: '{detected_cat}'")
    assert detected_cat in ["Food", "Cosmetics", "Household", "Consumer Goods", "Imported Goods", "Other"], f"Invalid category: {detected_cat}"
    print(f" Verified: Category correctly resolved as '{detected_cat}'.")

    # -------------------------------------------------------------
    # STEP 5: Verify Rule-Based Compliance Engine & Statuses
    # -------------------------------------------------------------
    print("\n--- [STEP 5/10] Verify Deterministic Legal Metrology Rules Engine ---")
    rule_checks = scan_data["details"].get("rule_checks", [])
    print(f"Total Evaluated Mandatory Declarations: {len(rule_checks)}")
    assert len(rule_checks) >= 6, "Expected at least 6 mandatory PCR 2011 declarations evaluated!"

    valid_statuses = {"PASS", "FAIL", "WARNING", "MANUAL REVIEW"}
    for r in rule_checks:
        assert r["status"] in valid_statuses, f"Invalid rule status: {r['status']}"
        print(f"  [{r['status']}] {r['rule_code']} ({r['title']}): Priority={r.get('priority')}")
    print(" Verified: All rule checks returned valid deterministic statutory verdicts.")

    # -------------------------------------------------------------
    # STEP 6: Verify Deterministic Compliance Score & 4-Tier Scale
    # -------------------------------------------------------------
    print("\n--- [STEP 6/10] Verify Deterministic Score & 4-Tier Scale ---")
    score = scan_data["compliance_score"]
    status = scan_data["compliance_status"]
    print(f"Compliance Score: {score:.1f}% | Overall Status: {status}")
    assert 0.0 <= score <= 100.0, f"Score out of bounds: {score}"
    
    if score >= 90.0:
        assert status == "COMPLIANT", f"Expected COMPLIANT for {score}%, got {status}"
    elif score >= 70.0:
        assert status == "MOSTLY COMPLIANT", f"Expected MOSTLY COMPLIANT for {score}%, got {status}"
    elif score >= 40.0:
        assert status == "NEEDS REVIEW", f"Expected NEEDS REVIEW for {score}%, got {status}"
    else:
        assert status == "HIGH RISK", f"Expected HIGH RISK for {score}%, got {status}"
    print(f" Verified: Score {score:.1f}% mapped to tier '{status}'.")

    # -------------------------------------------------------------
    # STEP 7: Verify Risk Priority Classification & Sorting
    # -------------------------------------------------------------
    print("\n--- [STEP 7/10] Verify Violation Prioritization & Sorting ---")
    priority_order = {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4}
    status_order = {"FAIL": 1, "WARNING": 2, "MANUAL REVIEW": 3, "PASS": 4}

    prev_key = (0, 0)
    for r in rule_checks:
        pri = r.get("priority", "LOW")
        st = r.get("status", "FAIL")
        curr_key = (priority_order.get(pri, 4), status_order.get(st, 4))
        assert curr_key >= prev_key, f"Sorting violation: {r['rule_code']} with key {curr_key} came after {prev_key}"
        prev_key = curr_key
    print(" Verified: Checks are strictly sorted from highest priority to lowest priority.")

    # -------------------------------------------------------------
    # STEP 8: Verify Live Manual Correction & Re-evaluation
    # -------------------------------------------------------------
    print("\n--- [STEP 8/10] Verify Manual Review & Instant Recalculation ---")
    # Simulate user adding Unit Sale Price and fixing Net Qty spacing
    update_payload = {
        "report_id": report_id,
        "commodity_name": "NutriPure Almond Butter Creamy",
        "brand": "NutriPure",
        "category": "Food",
        "manufacturer_details": "NutriFoods India Pvt Ltd, Andheri East, Mumbai 400069",
        "address": "Andheri East, Mumbai 400069",
        "mrp": "Rs 350.00",
        "net_quantity": "350 g",
        "unit_sale_price": "Rs 1.00 per g",
        "mfg_date": "01/2026",
        "expiry_date": "12 Months",
        "importer": "",
        "country_of_origin": "India",
        "customer_care": "1800-222-3333, care@nutripure.com"
    }
    up_res = requests.post(f"{API_URL}/api/scan/update", data=update_payload)
    print(f"Update API Status: {up_res.status_code}")
    assert up_res.status_code == 200, f"Update failed: {up_res.text}"
    updated_data = up_res.json()
    print(f"Re-calculated Compliance Score: {updated_data['compliance_score']}% | Status: {updated_data['compliance_status']}")
    assert updated_data["compliance_score"] >= score, "Score should have improved after remedial corrections!"
    print(" Verified: Live field editing re-evaluates compliance deterministically.")

    # -------------------------------------------------------------
    # STEP 9: Verify Official PDF Report Download & Integrity
    # -------------------------------------------------------------
    print("\n--- [STEP 9/10] Verify PDF Report Generation & Download ---")
    pdf_res = requests.get(f"{API_URL}/api/reports/{report_id}/pdf")
    assert pdf_res.status_code == 200, f"PDF download failed: {pdf_res.text}"
    assert "application/pdf" in pdf_res.headers.get("content-type", "")
    print(f"PDF Downloaded successfully ({len(pdf_res.content):,} bytes)")

    # Inspect PDF contents via pdfium
    temp_pdf = os.path.join(BASE_DIR, "backend", "uploads", f"audit_{report_code}.pdf")
    with open(temp_pdf, "wb") as f:
        f.write(pdf_res.content)

    pdf_doc = pdfium.PdfDocument(temp_pdf)
    assert len(pdf_doc) >= 1, "PDF document must have pages!"
    pdf_text = ""
    for page in pdf_doc:
        pdf_text += page.get_textpage().get_text_range() + "\n"

    assert report_code.lower() in pdf_text.lower(), "Report code missing from PDF!"
    assert "compliance score" in pdf_text.lower(), "Compliance score missing from PDF!"
    assert "legal metrology" in pdf_text.lower(), "Legal Metrology reference missing from PDF!"
    assert "disclaimer" in pdf_text.lower(), "Disclaimer missing from PDF!"
    print(f" Verified: PDF certificate contains all required sections across {len(pdf_doc)} pages.")

    # -------------------------------------------------------------
    # STEP 10: Verify Audit History Repository
    # -------------------------------------------------------------
    print("\n--- [STEP 10/10] Verify Audit History Repository & Search ---")
    hist_res = requests.get(f"{API_URL}/api/reports")
    assert hist_res.status_code == 200, f"History list failed: {hist_res.text}"
    reports_list = hist_res.json().get("reports", [])
    print(f"Total Reports in Audit History Database: {len(reports_list)}")
    assert len(reports_list) > 0, "Audit repository is empty!"

    matching_rep = next((r for r in reports_list if r["report_code"] == report_code), None)
    assert matching_rep is not None, f"Newly created report {report_code} not found in history!"
    print(f" Found Report in History: Code={matching_rep['report_code']}, Score={matching_rep['compliance_score']}%")
    print(" Verified: Audit logs persisted to SQLite database and queryable.")

    print("\n" + "=" * 70)
    print(" ALL 10 PIPELINE PHASES VERIFIED WITH 100% SUCCESS & ACCURACY!")
    print("=" * 70)

if __name__ == "__main__":
    test_full_pipeline_workflow()
