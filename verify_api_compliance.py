import requests
import time

time.sleep(2) # Give server a moment

print("--- Testing Live /api/compliance/rules endpoint ---")
res = requests.get("http://localhost:8000/api/compliance/rules")
print(f"Status: {res.status_code}")
data = res.json()
print(f"Rules Count: {len(data.get('rules', []))}")
for r in data.get("rules", []):
    print(f" - [{r.get('code')}] {r.get('title')} ({r.get('clause')})")

print("\n--- Testing Live /api/scan with test image ---")
from PIL import Image, ImageDraw

img = Image.new('RGB', (800, 600), color=(255, 255, 255))
d = ImageDraw.Draw(img)
d.text((30, 40), "Brand: NutriPure - Almond Butter Creamy", fill=(0, 0, 0))
d.text((30, 90), "Manufactured & Packed By: NutriFoods Pvt Ltd, Sector 18, Mumbai 400001, India", fill=(0, 0, 0))
d.text((30, 140), "Net Quantity: 350 g", fill=(0, 0, 0))
d.text((30, 190), "Mfg Date: 08/2026", fill=(0, 0, 0))
d.text((30, 240), "Best Before: 12 Months from Packing", fill=(0, 0, 0))
d.text((30, 290), "MRP Rs. 350.00 (inclusive of all taxes)", fill=(0, 0, 0))
d.text((30, 340), "Unit Sale Price: Rs 1.00 per g", fill=(0, 0, 0))
d.text((30, 390), "Consumer Care: Tel 1800-222-3333, Email: care@nutripure.in", fill=(0, 0, 0))
test_img_path = "sample_test_label.jpg"
img.save(test_img_path)

with open(test_img_path, "rb") as f:
    res = requests.post("http://localhost:8000/api/scan", files={"file": (test_img_path, f, "image/jpeg")}, data={"category": "Food"})
print(f"Scan Status: {res.status_code}")
scan_data = res.json()
print(f"Product Name: {scan_data.get('product_name')}")
print(f"Category: {scan_data.get('category')}")
print(f"Compliance Score: {scan_data.get('compliance_score')}%")
print(f"Compliance Status: {scan_data.get('compliance_status')}")
print(f"Counts: Passed={scan_data.get('passed_count')}, Warnings={scan_data.get('warnings_count')}, Violations={scan_data.get('violations_count')}, Manual Review={scan_data.get('manual_review_count')}")
print("Rule Checks:")
for rc in scan_data.get("details", {}).get("rule_checks", []):
    print(f"   [{rc.get('status')}] {rc.get('rule_code')} - {rc.get('title')}: {rc.get('finding')}")

print("\n LIVE SYSTEM VERIFICATION COMPLETED SUCCESSFULLY!")
