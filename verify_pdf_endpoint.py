import requests
import os
import pypdfium2 as pdfium

def test_live_pdf_download():
    print("=================================================================")
    print("   TESTING LIVE API SCAN & PDF REPORT DOWNLOAD ENDPOINT")
    print("=================================================================")

    base_url = "http://localhost:8000"
    
    # 1. Scan image
    img_path = "test_label.png" if os.path.exists("test_label.png") else "sample_test_label.jpg"
    with open(img_path, "rb") as f:
        files = {"file": ("test_label.png", f, "image/png")}
        data = {"product_name": "NutriPure Almond Butter", "category": "Food"}
        res = requests.post(f"{base_url}/api/scan", files=files, data=data)

    print(f"Scan Status: {res.status_code}")
    assert res.status_code == 200, f"Scan failed: {res.text}"
    scan_json = res.json()
    report_id = scan_json["id"]
    report_code = scan_json["report_code"]
    print(f"Report ID: {report_id}, Code: {report_code}, Score: {scan_json['compliance_score']}%")

    # 2. Download PDF
    pdf_res = requests.get(f"{base_url}/api/reports/{report_id}/pdf")
    print(f"PDF Download Status: {pdf_res.status_code}")
    print(f"Content-Type: {pdf_res.headers.get('content-type')}")
    assert pdf_res.status_code == 200, f"Download failed: {pdf_res.text}"
    assert "application/pdf" in pdf_res.headers.get("content-type", "")

    # Save to disk
    downloaded_pdf = f"downloaded_report_{report_code}.pdf"
    with open(downloaded_pdf, "wb") as f:
        f.write(pdf_res.content)
    
    pdf_size = os.path.getsize(downloaded_pdf)
    print(f"Downloaded PDF Size: {pdf_size:,} bytes")
    assert pdf_size > 1000, "Downloaded PDF is too small!"

    # Inspect PDF contents
    pdf_doc = pdfium.PdfDocument(downloaded_pdf)
    print(f"Total Pages in Downloaded PDF: {len(pdf_doc)}")
    
    full_text = ""
    for page in pdf_doc:
        textpage = page.get_textpage()
        full_text += textpage.get_text_range() + "\n"

    print("\n--- Downloaded PDF Content Verification ---")
    checklist = [
        "PACKSURE AI",
        report_code,
        "COMPLIANCE SCORE",
        "STATUTORY VERDICT",
        "Product Declarations",
        "OCR Extraction Diagnostic",
        "PASSED:",
        "FAILED:",
        "Statutory Declarations Audit Breakdown",
        "LM-RULE-6-1",
        "Actionable Statutory Packaging Recommendations",
        "STATUTORY REGULATORY DISCLAIMER"
    ]
    for item in checklist:
        assert item.lower() in full_text.lower(), f"Missing '{item}' in live generated PDF!"
        print(f" [PASS] '{item}' found in live PDF.")

    print("\n LIVE ENDPOINT PDF GENERATION & DOWNLOAD TEST PASSED 100%!")
    print("=================================================================")

if __name__ == "__main__":
    test_live_pdf_download()
