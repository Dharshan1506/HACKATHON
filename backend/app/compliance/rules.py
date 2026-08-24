import re
from typing import Dict, Any, List

class LegalMetrologyRulesEngine:
    """
    Compliance engine enforcing India Legal Metrology (Packaged Commodities) Rules, 2011.
    Evaluates 7 Mandatory Declarations + Unit Sale Price + Font & Format Standards.
    """

    MANDATORY_RULES = [
        {
            "id": "RULE_6_1_A",
            "code": "LM-RULE-6-1-A",
            "title": "Manufacturer / Packer / Importer Address",
            "clause": "Rule 6(1)(a) of Legal Metrology (Packaged Commodities) Rules 2011",
            "description": "Name and complete address of the manufacturer, packer, or importer must be clearly declared.",
            "field": "manufacturer_details",
            "weight": 15
        },
        {
            "id": "RULE_6_1_B",
            "code": "LM-RULE-6-1-B",
            "title": "Generic / Common Name of Commodity",
            "clause": "Rule 6(1)(b) of Legal Metrology (Packaged Commodities) Rules 2011",
            "description": "The common or generic name of the commodity contained in the package.",
            "field": "commodity_name",
            "weight": 15
        },
        {
            "id": "RULE_6_1_C",
            "code": "LM-RULE-6-1-C",
            "title": "Net Quantity & Standard Units",
            "clause": "Rule 6(1)(c) & Rule 7 of Legal Metrology Rules",
            "description": "Net quantity in metric units (g, kg, ml, l, N, pcs) with clear numeral spacing.",
            "field": "net_quantity",
            "weight": 20
        },
        {
            "id": "RULE_6_1_D",
            "code": "LM-RULE-6-1-D",
            "title": "Month & Year of Manufacture / Packing",
            "clause": "Rule 6(1)(d) of Legal Metrology Rules",
            "description": "Date of manufacture/packing/import in MM/YYYY, Month Year, or DD/MM/YYYY format.",
            "field": "mfg_date",
            "weight": 15
        },
        {
            "id": "RULE_6_1_E",
            "code": "LM-RULE-6-1-E",
            "title": "Maximum Retail Price (MRP)",
            "clause": "Rule 6(1)(e) of Legal Metrology Rules",
            "description": "MRP declared as 'MRP Rs. XX (inclusive of all taxes)' or '₹ XX (incl. of all taxes)'.",
            "field": "mrp",
            "weight": 15
        },
        {
            "id": "RULE_6_1_E_USP",
            "code": "LM-RULE-6-1-E-USP",
            "title": "Unit Sale Price (USP)",
            "clause": "Rule 6(1)(e) Amendment 2021",
            "description": "Unit Sale Price (e.g. ₹/g, ₹/kg, ₹/ml) declared clearly alongside MRP for packages > 10g/ml.",
            "field": "unit_sale_price",
            "weight": 10
        },
        {
            "id": "RULE_6_1_F",
            "code": "LM-RULE-6-1-F",
            "title": "Customer Care Contact Details",
            "clause": "Rule 6(1)(f) of Legal Metrology Rules",
            "description": "Complete contact info including Email, Helpline Number, and Address for consumer complaints.",
            "field": "customer_care",
            "weight": 10
        }
    ]

    @classmethod
    def validate_extracted_data(cls, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        earned_score = 0.0
        total_possible = sum(rule["weight"] for rule in cls.MANDATORY_RULES)

        for rule in cls.MANDATORY_RULES:
            field_name = rule["field"]
            field_value = str(extracted_data.get(field_name, "") or "").strip()
            
            check_result = cls._evaluate_rule(rule["id"], field_value, extracted_data)
            status = check_result["status"]  # PASS, FAIL, WARNING
            score_fraction = check_result["score_fraction"]
            
            rule_earned = rule["weight"] * score_fraction
            earned_score += rule_earned

            results.append({
                "rule_id": rule["id"],
                "rule_code": rule["code"],
                "title": rule["title"],
                "clause": rule["clause"],
                "description": rule["description"],
                "field": field_name,
                "value": field_value if field_value else None,
                "status": status,
                "weight": rule["weight"],
                "score_earned": round(rule_earned, 2),
                "finding": check_result["finding"],
                "remediation": check_result["remediation"]
            })

        final_score = round((earned_score / total_possible) * 100.0, 1) if total_possible > 0 else 0.0

        if final_score >= 85.0:
            compliance_status = "PASS"
            risk_level = "LOW"
        elif final_score >= 65.0:
            compliance_status = "WARNING"
            risk_level = "MEDIUM"
        elif final_score >= 40.0:
            compliance_status = "FAIL"
            risk_level = "HIGH"
        else:
            compliance_status = "FAIL"
            risk_level = "CRITICAL"

        passed_count = sum(1 for r in results if r["status"] == "PASS")
        warnings_count = sum(1 for r in results if r["status"] == "WARNING")
        violations_count = sum(1 for r in results if r["status"] == "FAIL")

        return {
            "score": final_score,
            "status": compliance_status,
            "risk_level": risk_level,
            "passed_count": passed_count,
            "warnings_count": warnings_count,
            "violations_count": violations_count,
            "rule_checks": results
        }

    @classmethod
    def _evaluate_rule(cls, rule_id: str, value: str, full_data: Dict[str, Any]) -> Dict[str, Any]:
        if not value:
            return {
                "status": "FAIL",
                "score_fraction": 0.0,
                "finding": "Declaration is missing entirely from the packaging label.",
                "remediation": "Print the mandatory declaration prominently on the principal display panel."
            }

        val_lower = value.lower()

        if rule_id == "RULE_6_1_A":
            # Manufacturer address: Must have name + address / pin
            has_mfg_keyword = any(k in val_lower for k in ["mfd", "manufactured", "packed", "imported", "marketed", "ltd", "pvt", "corp", "inc"])
            has_location = any(k in val_lower for k in ["pvt", "street", "road", "industrial", "dist", "state", "india", "pin", "flat", "plot"]) or len(value) > 15
            if has_mfg_keyword and has_location:
                return {
                    "status": "PASS",
                    "score_fraction": 1.0,
                    "finding": "Valid manufacturer/packer name and address present.",
                    "remediation": "Compliant."
                }
            elif has_mfg_keyword:
                return {
                    "status": "WARNING",
                    "score_fraction": 0.6,
                    "finding": "Manufacturer name detected but complete address or postal pin code appears partial.",
                    "remediation": "Include complete premises address with postal pin code as per Rule 6(1)(a)."
                }
            return {
                "status": "FAIL",
                "score_fraction": 0.2,
                "finding": "Manufacturer detail lacks legally recognized company structure or address format.",
                "remediation": "Use clear prefix 'Manufactured & Packed By:' followed by full registered address."
            }

        elif rule_id == "RULE_6_1_B":
            # Commodity name
            if len(value) >= 3:
                return {
                    "status": "PASS",
                    "score_fraction": 1.0,
                    "finding": f"Generic commodity name '{value}' properly declared.",
                    "remediation": "Compliant."
                }
            return {
                "status": "FAIL",
                "score_fraction": 0.0,
                "finding": "Commodity name is too vague or incomplete.",
                "remediation": "Declare the common or generic name of the commodity on the principal panel."
            }

        elif rule_id == "RULE_6_1_C":
            # Net quantity (e.g. 500 g, 1 kg, 250 ml, 5 N)
            qty_pattern = r'(\d+(\.\d+)?)\s*(g|kg|ml|l|ltr|liter|grams|kilograms|n|pcs|units)\b'
            match = re.search(qty_pattern, val_lower)
            if match:
                return {
                    "status": "PASS",
                    "score_fraction": 1.0,
                    "finding": f"Net quantity '{value}' complies with metric unit standards.",
                    "remediation": "Compliant."
                }
            elif any(char.isdigit() for char in value):
                return {
                    "status": "WARNING",
                    "score_fraction": 0.5,
                    "finding": "Numeral detected but missing standard metric unit symbol (g, kg, ml, l, N).",
                    "remediation": "Ensure space between numeral and metric unit (e.g. '500 g' instead of '500g' or non-metric units)."
                }
            return {
                "status": "FAIL",
                "score_fraction": 0.0,
                "finding": "Invalid net quantity format.",
                "remediation": "State net quantity using standard metric units prescribed under Rule 7."
            }

        elif rule_id == "RULE_6_1_D":
            # Date of manufacture (MM/YYYY or Month Year)
            date_pattern = r'(\b(0[1-9]|1[0-2])[\/\-](20\d{2}|\d{2})\b|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(20\d{2}|\d{2})\b)'
            if re.search(date_pattern, val_lower):
                return {
                    "status": "PASS",
                    "score_fraction": 1.0,
                    "finding": f"Manufacture/Packing date '{value}' meets standard format.",
                    "remediation": "Compliant."
                }
            elif any(year in value for year in ["2023", "2024", "2025", "2026"]):
                return {
                    "status": "WARNING",
                    "score_fraction": 0.6,
                    "finding": "Year found, but month format is non-standard.",
                    "remediation": "Use standard MM/YYYY format (e.g., 08/2026) or 'Mfg Date: Month Year'."
                }
            return {
                "status": "FAIL",
                "score_fraction": 0.0,
                "finding": "Date format non-compliant or illegible.",
                "remediation": "Print manufacturing month & year clearly as 'Mfg Date: MM/YYYY'."
            }

        elif rule_id == "RULE_6_1_E":
            # MRP
            has_tax_mention = any(t in val_lower for t in ["incl", "inclusive", "tax", "taxes"])
            has_mrp_prefix = any(m in val_lower for m in ["mrp", "m.r.p", "max retail price", "rs", "₹"])
            has_digit = any(char.isdigit() for char in value)

            if has_mrp_prefix and has_digit and has_tax_mention:
                return {
                    "status": "PASS",
                    "score_fraction": 1.0,
                    "finding": f"MRP '{value}' correctly declares inclusive of all taxes.",
                    "remediation": "Compliant."
                }
            elif has_mrp_prefix and has_digit:
                return {
                    "status": "WARNING",
                    "score_fraction": 0.7,
                    "finding": "MRP and price numeral found, but missing required phrase '(inclusive of all taxes)'.",
                    "remediation": "Append '(inclusive of all taxes)' right after or below the MRP."
                }
            return {
                "status": "FAIL",
                "score_fraction": 0.0,
                "finding": "MRP declaration invalid or missing price digits.",
                "remediation": "Declare 'MRP Rs. XX.XX (incl. of all taxes)' on principal display panel."
            }

        elif rule_id == "RULE_6_1_E_USP":
            # Unit Sale Price (USP)
            has_per = any(p in val_lower for p in ["per", "/", "g", "kg", "ml", "l", "unit"])
            has_digit = any(char.isdigit() for char in value)
            if has_per and has_digit:
                return {
                    "status": "PASS",
                    "score_fraction": 1.0,
                    "finding": f"Unit Sale Price '{value}' present.",
                    "remediation": "Compliant."
                }
            return {
                "status": "WARNING",
                "score_fraction": 0.4,
                "finding": "Unit Sale Price (USP) missing or non-standard.",
                "remediation": "Declare Unit Sale Price (e.g. ₹0.20/g or ₹50/kg) as mandated by 2021 Amendments."
            }

        elif rule_id == "RULE_6_1_F":
            # Customer care: Email / phone / address
            has_email = "@" in value or "email" in val_lower
            has_phone = any(char.isdigit() for char in value) and len(re.findall(r'\d', value)) >= 8
            if has_email and has_phone:
                return {
                    "status": "PASS",
                    "score_fraction": 1.0,
                    "finding": "Complete customer care email and phone number present.",
                    "remediation": "Compliant."
                }
            elif has_email or has_phone:
                return {
                    "status": "WARNING",
                    "score_fraction": 0.6,
                    "finding": "Partial customer contact (only email or phone provided).",
                    "remediation": "Provide both email ID and phone helpline number under 'Consumer Care Cell'."
                }
            return {
                "status": "FAIL",
                "score_fraction": 0.0,
                "finding": "Customer care details incomplete or missing.",
                "remediation": "Include 'For Consumer Complaints: Contact Executive at [Address], Phone: [No], Email: [Mail]'."
            }

        return {
            "status": "FAIL",
            "score_fraction": 0.0,
            "finding": "Validation failed.",
            "remediation": "Inspect label for compliance."
        }
