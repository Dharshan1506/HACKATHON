import sys
import os
from PIL import Image, ImageDraw
import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def create_sample_packaging_image(filename="test_label.png"):
    img = Image.new("RGB", (800, 700), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Draw packaging border
    draw.rectangle([10, 10, 790, 690], outline=(15, 23, 42), width=3)
    
    # Header
    draw.text((30, 40), "PREMIUM ROASTED ALMOND BUTTER", fill=(15, 23, 42))
    draw.text((30, 90), "BRAND: NutriPure Organics", fill=(51, 65, 85))
    
    # Declarations
    draw.text((30, 150), "NET QUANTITY: 350 g", fill=(15, 23, 42))
    draw.text((30, 200), "MRP Rs. 385.00 (inclusive of all taxes)", fill=(15, 23, 42))
    draw.text((30, 250), "UNIT SALE PRICE: Rs. 1.10 per g", fill=(15, 23, 42))
    draw.text((30, 300), "MFG DATE: 08/2026 | BEST BEFORE: 12 MONTHS FROM MFG", fill=(15, 23, 42))
    draw.text((30, 360), "MANUFACTURED & PACKED BY:", fill=(15, 23, 42))
    draw.text((30, 390), "NutriPure Health Foods Pvt Ltd, Plot 14, Industrial Estate, Pune, Maharashtra - 411018", fill=(51, 65, 85))
    draw.text((30, 460), "FOR CONSUMER COMPLAINTS:", fill=(15, 23, 42))
    draw.text((30, 490), "Contact Care Officer, Helpline: 1800-999-8888, Email: care@nutripure.com", fill=(51, 65, 85))
    draw.text((30, 560), "COUNTRY OF ORIGIN: INDIA", fill=(15, 23, 42))

    img.save(filename)
    print(f"Created test label image: {filename}")
    return filename

def test_api_upload(filename):
    url = "http://localhost:8000/api/scan"
    with open(filename, "rb") as f:
        files = {"file": (filename, f, "image/png")}
        data = {"category": "Packaged Food"}
        response = httpx.post(url, files=files, data=data, timeout=30.0)
        
    print("\nAPI Response Status Code:", response.status_code)
    result = response.json()
    print("Report Code:", result.get("report_code"))
    print("Product Name:", result.get("product_name"))
    print("Compliance Score:", result.get("compliance_score"), "%")
    print("Compliance Status:", result.get("compliance_status"))
    print("Rule Checks Count:", len(result.get("extracted_data", {}).get("rule_checks", [])))
    print("\nRule Breakdown:")
    for r in result.get("extracted_data", {}).get("rule_checks", []):
        print(f"  [{r['status']}] {r['rule_code']} ({r['title']}) -> Value: {r.get('value')} | Score: {r.get('score_earned')}")

if __name__ == "__main__":
    img_path = create_sample_packaging_image()
    test_api_upload(img_path)
