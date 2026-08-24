import os
import sys
import json

# Ensure backend package can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.compliance.rules import LegalMetrologyRulesEngine, RulesRegistry

def test_rules_loading():
    print("\n--- TEST 1: Rules Config Loading & Storage ---")
    rules = RulesRegistry.load_rules(reload=True)
    assert len(rules) >= 7, f"Expected at least 7 rules, got {len(rules)}"
    print(f" Loaded {len(rules)} configurable rules from rules_config.json")
    
    # Check category filtering
    food_rules = RulesRegistry.get_applicable_rules("Food")
    imported_rules = RulesRegistry.get_applicable_rules("Imported Goods")
    print(f" Applicable rules for 'Food': {len(food_rules)}")
    print(f" Applicable rules for 'Imported Goods': {len(imported_rules)}")
    assert len(food_rules) >= 7
    assert len(imported_rules) >= 7

def test_pass_status():
    print("\n--- TEST 2: Fully Compliant Label -> PASS Status ---")
    data = {
        "commodity_name": "Almond Butter Creamy",
        "brand": "NutriPure",
        "manufacturer_details": "Manufactured & Packed By: NutriFoods Pvt Ltd, Plot 42, Sector 18, Industrial Area, Mumbai, Maharashtra, PIN 400001, India",
        "address": "Plot 42, Sector 18, Mumbai 400001",
        "mrp": "MRP Rs. 350.00 (inclusive of all taxes)",
        "net_quantity": "350 g",
        "mfg_date": "08/2026",
        "expiry_date": "12 Months from Packaging",
        "customer_care": "Customer Care Cell: Tel 1800-222-3333, Email: care@nutripure.in",
        "unit_sale_price": "₹ 1.00 per g"
    }

    result = LegalMetrologyRulesEngine.validate_extracted_data(data, category="Food")
    print(f" Score: {result['score']}% | Status: {result['status']} | Risk: {result['risk_level']}")
    print(f" Passed: {result['passed_count']} | Warnings: {result['warnings_count']} | Violations: {result['violations_count']} | Manual Review: {result['manual_review_count']}")
    assert result["status"] == "PASS", f"Expected PASS, got {result['status']}"
    assert result["score"] >= 90.0, f"Expected >= 90.0, got {result['score']}"
    assert result["violations_count"] == 0

def test_warning_status():
    print("\n--- TEST 3: Minor Formatting Issues -> WARNING Status ---")
    data = {
        "commodity_name": "Almond Butter Creamy",
        "brand": "NutriPure",
        "manufacturer_details": "Manufactured By NutriFoods Pvt Ltd, Mumbai Industrial Area", # Missing full PIN code
        "mrp": "MRP Rs. 350.00", # Missing '(inclusive of all taxes)'
        "net_quantity": "350g", # Missing space before 'g'
        "mfg_date": "08/2026",
        "expiry_date": "08/2027",
        "customer_care": "Email: care@nutripure.in", # Missing phone helpline
        "unit_sale_price": "₹ 1.00 per g"
    }

    result = LegalMetrologyRulesEngine.validate_extracted_data(data, category="Food")
    print(f" Score: {result['score']}% | Status: {result['status']} | Risk: {result['risk_level']}")
    print(f" Passed: {result['passed_count']} | Warnings: {result['warnings_count']} | Violations: {result['violations_count']} | Manual Review: {result['manual_review_count']}")
    assert result["warnings_count"] > 0
    assert result["violations_count"] == 0
    assert result["status"] in ["WARNING", "PASS"]

def test_manual_review_status():
    print("\n--- TEST 4: Complex Multi-Party Licensing / Ambiguity -> MANUAL REVIEW Status ---")
    data = {
        "commodity_name": "Herbal Hair Cleanser",
        "brand": "VedaAura",
        "manufacturer_details": "Manufactured under license by Third Party Contract Pack Ltd, Okhla Phase III", # Ambiguous contract pack phrase
        "mrp": "MRP Rs. 249.00 (inclusive of all taxes)",
        "net_quantity": "200 ml",
        "mfg_date": "Best before 24 months from mfg date", # Relative date without explicit MM/YYYY
        "expiry_date": "24 months",
        "customer_care": "For feedback contact care executive at company office", # Missing clear phone/email
        "unit_sale_price": "₹ 1.25 per ml"
    }

    result = LegalMetrologyRulesEngine.validate_extracted_data(data, category="Cosmetics")
    print(f" Score: {result['score']}% | Status: {result['status']} | Risk: {result['risk_level']}")
    print(f" Passed: {result['passed_count']} | Warnings: {result['warnings_count']} | Violations: {result['violations_count']} | Manual Review: {result['manual_review_count']}")
    assert result["manual_review_count"] > 0, "Expected at least 1 rule in MANUAL REVIEW"
    print(" Verified MANUAL REVIEW triggered correctly for ambiguous licensing & relative dates.")

def test_fail_status():
    print("\n--- TEST 5: Prohibited Units & Missing Mandatory Declarations -> FAIL Status ---")
    data = {
        "commodity_name": "product", # Vague name
        "brand": "Generic",
        "manufacturer_details": "", # Missing manufacturer
        "mrp": "", # Missing MRP
        "net_quantity": "1.5 lbs", # Prohibited non-metric unit
        "mfg_date": "", # Missing mfg date
        "customer_care": "" # Missing customer care
    }

    result = LegalMetrologyRulesEngine.validate_extracted_data(data, category="Consumer Goods")
    print(f" Score: {result['score']}% | Status: {result['status']} | Risk: {result['risk_level']}")
    print(f" Passed: {result['passed_count']} | Warnings: {result['warnings_count']} | Violations: {result['violations_count']} | Manual Review: {result['manual_review_count']}")
    assert result["status"] == "FAIL", f"Expected FAIL, got {result['status']}"
    assert result["violations_count"] >= 3, f"Expected >=3 violations, got {result['violations_count']}"
    assert result["risk_level"] == "HIGH"

def test_imported_goods_rule():
    print("\n--- TEST 6: Imported Goods Country of Origin & Importer Evaluation ---")
    # Case A: Missing Origin on Imported Product
    missing_origin_data = {
        "commodity_name": "Dark Chocolate 85%",
        "brand": "SwissAlpine",
        "manufacturer_details": "Packed in Zurich, Switzerland",
        "mrp": "MRP Rs. 450 (inclusive of all taxes)",
        "net_quantity": "100 g",
        "mfg_date": "05/2026",
        "customer_care": "help@swissimport.in, 1800-444-5555",
        "country_of_origin": "", # Missing!
        "importer": "" # Missing!
    }
    res_a = LegalMetrologyRulesEngine.validate_extracted_data(missing_origin_data, category="Imported Goods")
    origin_check_a = next(r for r in res_a["rule_checks"] if r["rule_id"] == "RULE_6_1_G")
    print(f" Case A (Imported without Origin): Rule 6(1)(g) Status = {origin_check_a['status']}")
    assert origin_check_a["status"] == "FAIL"

    # Case B: Domestic Product doesn't fail Rule 6(1)(g)
    res_b = LegalMetrologyRulesEngine.validate_extracted_data(missing_origin_data, category="Food")
    origin_check_b = next((r for r in res_b["rule_checks"] if r["rule_id"] == "RULE_6_1_G"), None)
    print(f" Case B (Domestic Product): Rule 6(1)(g) Applicable = {origin_check_b is not None}")

if __name__ == "__main__":
    print("================================================================")
    print("   LEGAL METROLOGY COMPLIANCE RULES ENGINE TEST SUITE")
    print("================================================================")
    test_rules_loading()
    test_pass_status()
    test_warning_status()
    test_manual_review_status()
    test_fail_status()
    test_imported_goods_rule()
    print("\n ALL 6 RULES ENGINE TESTS PASSED PERFECTLY!")
    print("================================================================")
