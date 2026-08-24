import requests
import time

def test_flow():
    # 1. Start by scanning the test label image
    print("--- Scanning test image ---")
    files = {"file": ("test_label.png", open("test_label.png", "rb"), "image/png")}
    data = {"category": "Packaged Food"}
    
    res = requests.post("http://localhost:8000/api/scan", files=files, data=data)
    assert res.status_code == 200, f"Scan failed: {res.text}"
    
    scan_res = res.json()
    report_id = scan_res["id"]
    initial_score = scan_res["compliance_score"]
    print(f"Initial compliance score: {initial_score}%")
    
    details = scan_res.get("details", {})
    fields = details.get("fields", {})
    print(f"Extracted Brand: '{fields.get('brand')}'")
    print(f"Extracted Commodity: '{fields.get('commodity_name')}'")
    print(f"Extracted Net Quantity: '{fields.get('net_quantity')}'")
    print(f"Extracted MRP: '{fields.get('mrp')}'")
    print(f"Extracted Mfg Date: '{fields.get('mfg_date')}'")
    print(f"Extracted Expiry: '{fields.get('expiry_date')}'")
    print(f"Extracted Importer: '{fields.get('importer')}'")
    print(f"Extracted Address: '{fields.get('address')}'")
    print(f"Extracted Customer Care: '{fields.get('customer_care')}'")
    print(f"Extracted Origin: '{fields.get('country_of_origin')}'")
    
    # 2. Run update request to correct net quantity to invalid value and see score drop
    print("\n--- Correcting values to an invalid Net Quantity (no metric unit) ---")
    update_data = {
        "report_id": report_id,
        "net_quantity": "350"  # Invalid (no metric unit)
    }
    
    res2 = requests.post("http://localhost:8000/api/scan/update", data=update_data)
    assert res2.status_code == 200, f"Update failed: {res2.text}"
    
    updated_res = res2.json()
    new_score = updated_res["compliance_score"]
    print(f"Updated compliance score: {new_score}%")
    assert new_score < initial_score, "Score should have dropped due to invalid net quantity metric units!"
    
    # 3. Correct the values to a fully compliant net quantity and address details
    print("\n--- Correcting values to a fully compliant set ---")
    update_data2 = {
        "report_id": report_id,
        "commodity_name": "Premium Roasted Almond Butter",
        "brand": "NutriPure Organics",
        "net_quantity": "350 g",
        "mrp": "MRP Rs 385.00 (inclusive of all taxes)",
        "unit_sale_price": "Rs 1.10 per g",
        "mfg_date": "08/2026",
        "expiry_date": "12 Months from MFG",
        "manufacturer_details": "NutriPure Health Foods Pvt Ltd",
        "address": "Plot 14, Industrial Estate, Pune, Maharashtra - 411018",
        "importer": "None",
        "country_of_origin": "India",
        "customer_care": "Helpline: 1800-999-8888, Email: care@nutripure.com"
    }
    
    res3 = requests.post("http://localhost:8000/api/scan/update", data=update_data2)
    assert res3.status_code == 200, f"Final update failed: {res3.text}"
    
    final_res = res3.json()
    final_score = final_res["compliance_score"]
    print(f"Final compliance score: {final_score}%")
    assert final_score >= 85.0, f"Score should be low-risk compliant! Got {final_score}%"
    print("SUCCESS: AI/NLP Extraction & Interactive Correction Flow Fully Operational!")

if __name__ == "__main__":
    test_flow()
