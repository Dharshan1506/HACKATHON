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

def test_compliant_tier():
    print("\n--- TEST 2: Score 90-100 -> COMPLIANT Tier ---")
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
    print(f" Score: {result['score']}% | Tier/Status: {result['status']} | Formula: {result['formula']}")
    print(f" Passed Weight: {result['passed_rule_weight']} / {result['total_applicable_rule_weight']}")
    assert result["score"] >= 90.0, f"Expected >= 90.0, got {result['score']}"
    assert result["status"] == "COMPLIANT", f"Expected COMPLIANT, got {result['status']}"
    assert result["risk_level"] == "LOW"

def test_mostly_compliant_tier():
    print("\n--- TEST 3: Score 70-89 -> MOSTLY COMPLIANT Tier ---")
    data = {
        "commodity_name": "Almond Butter Creamy",
        "brand": "NutriPure",
        "manufacturer_details": "Manufactured By NutriFoods Pvt Ltd, Mumbai Industrial Area", # Minor warning
        "mrp": "MRP Rs. 350.00", # Minor warning (missing incl taxes phrase)
        "net_quantity": "350g", # Minor warning (missing space)
        "mfg_date": "08/2026",
        "expiry_date": "08/2027",
        "customer_care": "Email: care@nutripure.in", # Minor warning (missing phone)
        "unit_sale_price": "1.00" # Missing unit measurement
    }

    result = LegalMetrologyRulesEngine.validate_extracted_data(data, category="Food")
    print(f" Score: {result['score']}% | Tier/Status: {result['status']} | Formula: {result['formula']}")
    assert 70.0 <= result["score"] <= 89.9, f"Expected 70-89, got {result['score']}"
    assert result["status"] == "MOSTLY COMPLIANT", f"Expected MOSTLY COMPLIANT, got {result['status']}"

def test_needs_review_tier():
    print("\n--- TEST 4: Score 40-69 -> NEEDS REVIEW Tier ---")
    data = {
        "commodity_name": "Herbal Hair Cleanser",
        "brand": "VedaAura",
        "manufacturer_details": "Manufactured under license by Third Party Contract Pack Ltd, Okhla Phase III", # Manual review
        "mrp": "MRP Rs. 249.00 (inclusive of all taxes)",
        "net_quantity": "200 ml",
        "mfg_date": "", # Missing mfg date -> 0 weight
        "expiry_date": "24 months",
        "customer_care": "", # Missing customer care -> 0 weight
        "unit_sale_price": "" # Missing USP -> 0 weight
    }

    result = LegalMetrologyRulesEngine.validate_extracted_data(data, category="Cosmetics")
    print(f" Score: {result['score']}% | Tier/Status: {result['status']} | Formula: {result['formula']}")
    assert 40.0 <= result["score"] <= 69.9, f"Expected 40-69, got {result['score']}"
    assert result["status"] == "NEEDS REVIEW", f"Expected NEEDS REVIEW, got {result['status']}"

def test_high_risk_tier():
    print("\n--- TEST 5: Score 0-39 -> HIGH RISK Tier ---")
    data = {
        "commodity_name": "product", # Vague name -> 0
        "brand": "Generic",
        "manufacturer_details": "", # Missing manufacturer -> 0
        "mrp": "", # Missing MRP -> 0
        "net_quantity": "1.5 lbs", # Prohibited non-metric unit -> 0
        "mfg_date": "", # Missing mfg date -> 0
        "customer_care": "" # Missing customer care -> 0
    }

    result = LegalMetrologyRulesEngine.validate_extracted_data(data, category="Consumer Goods")
    print(f" Score: {result['score']}% | Tier/Status: {result['status']} | Formula: {result['formula']}")
    assert result["score"] <= 39.9, f"Expected <=39.9, got {result['score']}"
    assert result["status"] == "HIGH RISK", f"Expected HIGH RISK, got {result['status']}"
    assert result["risk_level"] == "HIGH"

def test_formula_correctness():
    print("\n--- TEST 6: Formula Verification (Score = Passed Weight / Total Weight × 100) ---")
    data = {
        "commodity_name": "Refined Sunflower Oil",
        "brand": "SunGold",
        "manufacturer_details": "Manufactured By SunGold Ltd, Sector 4, Hyderabad 500001, India",
        "mrp": "MRP Rs. 180.00 (inclusive of all taxes)",
        "net_quantity": "1 l",
        "mfg_date": "08/2026",
        "expiry_date": "08/2027",
        "customer_care": "Helpline: 1800-111-2222, Email: help@sungold.in",
        "unit_sale_price": "₹ 180.00 per l"
    }
    result = LegalMetrologyRulesEngine.validate_extracted_data(data, category="Food")
    expected_score = round((result["passed_rule_weight"] / result["total_applicable_rule_weight"]) * 100.0, 1)
    assert result["score"] == expected_score, f"Formula mismatch: {result['score']} != {expected_score}"
    print(f" Formula Verified: {result['passed_rule_weight']} / {result['total_applicable_rule_weight']} × 100 = {result['score']}% ({result['status']})")

if __name__ == "__main__":
    print("================================================================")
    print("   LEGAL METROLOGY COMPLIANCE SCORE & 4-TIER TEST SUITE")
    print("================================================================")
    test_rules_loading()
    test_compliant_tier()
    test_mostly_compliant_tier()
    test_needs_review_tier()
    test_high_risk_tier()
    test_formula_correctness()
    print("\n ALL 6 SCORE & TIER TESTS PASSED PERFECTLY!")
    print("================================================================")
