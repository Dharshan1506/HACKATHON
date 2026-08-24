import requests
from backend.app.ocr.engine import OCREngine

def test_category_detection_unit():
    print("--- 1. Testing Category Classifier Unit Rules ---")
    
    # Food
    food_cat = OCREngine.detect_category("Organic Peanut Butter with Roasted Flax Seeds FSSAI Lic 1002345", {"commodity_name": "Peanut Butter"})
    print(f"Peanut Butter detected as: {food_cat}")
    assert food_cat == "Food", f"Expected Food, got {food_cat}"
    
    # Cosmetics
    cosmetics_cat = OCREngine.detect_category("Moisturizing Face Cream SPF 30 with Hyaluronic Acid & Vitamin E Paraben Free", {"commodity_name": "Face Cream"})
    print(f"Face Cream detected as: {cosmetics_cat}")
    assert cosmetics_cat == "Cosmetics", f"Expected Cosmetics, got {cosmetics_cat}"
    
    # Household
    household_cat = OCREngine.detect_category("Powerful Floor Cleaner and Disinfectant Surface Cleaner 500ml", {"commodity_name": "Floor Cleaner"})
    print(f"Floor Cleaner detected as: {household_cat}")
    assert household_cat == "Household", f"Expected Household, got {household_cat}"
    
    # Consumer Goods
    goods_cat = OCREngine.detect_category("High Speed USB-C 65W Fast Charging Braided Cable 2M with Warranty", {"commodity_name": "USB-C Cable"})
    print(f"USB-C Cable detected as: {goods_cat}")
    assert goods_cat == "Consumer Goods", f"Expected Consumer Goods, got {goods_cat}"
    
    # Imported Goods
    imported_cat = OCREngine.detect_category("Premium Swiss Chocolates. Imported by Swiss Gourmet India Ltd. Made in Switzerland", {"importer": "Swiss Gourmet India Ltd", "country_of_origin": "Switzerland"})
    print(f"Imported Swiss Chocolates detected as: {imported_cat}")
    assert imported_cat == "Imported Goods", f"Expected Imported Goods, got {imported_cat}"
    
    # Other
    other_cat = OCREngine.detect_category("Generic Prototype Unit X-900 Alpha Specimen", {"commodity_name": "Specimen X"})
    print(f"Generic Prototype detected as: {other_cat}")
    assert other_cat == "Other", f"Expected Other, got {other_cat}"
    
    print("Unit tests for all 6 categories PASSED!\n")

def test_api_scan_and_manual_category_override():
    print("--- 2. Testing API Category Auto-Detection & Manual Override ---")
    
    # Scan with Auto-Detect
    files = {"file": ("test_label.png", open("test_label.png", "rb"), "image/png")}
    data = {"category": "Auto-Detect"}
    
    res = requests.post("http://localhost:8000/api/scan", files=files, data=data)
    assert res.status_code == 200, f"Scan failed: {res.text}"
    scan_json = res.json()
    
    report_id = scan_json["id"]
    detected_category = scan_json.get("detected_category") or scan_json.get("category")
    print(f"Image auto-detected category: {detected_category}")
    assert detected_category == "Food", f"Expected Food category for Almond Butter label, got {detected_category}"
    
    # Manually change category to 'Imported Goods'
    print("\n--- 3. Testing User Manual Override to 'Imported Goods' ---")
    update_data = {
        "report_id": report_id,
        "category": "Imported Goods",
        "importer": "Global Gourmet Imports Pvt Ltd",
        "country_of_origin": "USA"
    }
    
    res2 = requests.post("http://localhost:8000/api/scan/update", data=update_data)
    assert res2.status_code == 200, f"Update failed: {res2.text}"
    update_json = res2.json()
    
    updated_category = update_json.get("category")
    print(f"Updated category in response: {updated_category}")
    assert updated_category == "Imported Goods", f"Expected Imported Goods, got {updated_category}"
    
    print("API Category Auto-Detection and Manual Override flow PASSED!")

if __name__ == "__main__":
    test_category_detection_unit()
    test_api_scan_and_manual_category_override()
