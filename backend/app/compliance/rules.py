import re
import json
import os
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("packsure.compliance")

CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), "rules_config.json")

class RulesRegistry:
    """
    Manages loading, updating, and querying configurable Legal Metrology compliance rules.
    Rules are stored in rules_config.json so they can be modified or extended without code changes.
    """
    _rules_cache: Optional[List[Dict[str, Any]]] = None
    _config_version: str = "2.4.0"

    @classmethod
    def load_rules(cls, reload: bool = False) -> List[Dict[str, Any]]:
        if cls._rules_cache is not None and not reload:
            return cls._rules_cache

        if os.path.exists(CONFIG_FILE_PATH):
            try:
                with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cls._rules_cache = data.get("rules", [])
                    cls._config_version = data.get("version", "2.4.0")
                    return cls._rules_cache
            except Exception as e:
                logger.error(f"Error loading rules_config.json: {e}")

        # Fallback in-memory rules if config file cannot be read
        cls._rules_cache = cls._default_rules()
        return cls._rules_cache

    @classmethod
    def get_applicable_rules(cls, category: str = "ALL") -> List[Dict[str, Any]]:
        all_rules = cls.load_rules()
        category_clean = (category or "ALL").strip().lower()

        applicable = []
        for r in all_rules:
            app_cats = [c.lower() for c in r.get("applicable_categories", ["ALL"])]
            if "all" in app_cats or category_clean in app_cats:
                applicable.append(r)
        return applicable

    @classmethod
    def _default_rules(cls) -> List[Dict[str, Any]]:
        return [
            {
                "id": "RULE_6_1_A",
                "code": "LM-RULE-6-1-A",
                "title": "Manufacturer / Packer / Importer Address",
                "clause": "Rule 6(1)(a) of Legal Metrology Rules 2011",
                "description": "Name and complete address of the manufacturer, packer, or importer.",
                "field": "manufacturer_details",
                "weight": 15,
                "applicable_categories": ["ALL"],
                "severity": "CRITICAL"
            },
            {
                "id": "RULE_6_1_B",
                "code": "LM-RULE-6-1-B",
                "title": "Generic / Common Name of Commodity",
                "clause": "Rule 6(1)(b) of Legal Metrology Rules 2011",
                "description": "The common or generic name of the commodity.",
                "field": "commodity_name",
                "weight": 15,
                "applicable_categories": ["ALL"],
                "severity": "CRITICAL"
            },
            {
                "id": "RULE_6_1_C",
                "code": "LM-RULE-6-1-C",
                "title": "Net Quantity & Standard Units",
                "clause": "Rule 6(1)(c) & Rule 7 of Legal Metrology Rules",
                "description": "Net quantity in standard metric units (g, kg, ml, l, N, pcs).",
                "field": "net_quantity",
                "weight": 20,
                "applicable_categories": ["ALL"],
                "severity": "CRITICAL"
            },
            {
                "id": "RULE_6_1_D",
                "code": "LM-RULE-6-1-D",
                "title": "Month & Year of Manufacture / Packing",
                "clause": "Rule 6(1)(d) of Legal Metrology Rules 2011",
                "description": "Date of manufacture/packing/import in MM/YYYY format.",
                "field": "mfg_date",
                "weight": 15,
                "applicable_categories": ["ALL"],
                "severity": "MAJOR"
            },
            {
                "id": "RULE_6_1_E",
                "code": "LM-RULE-6-1-E",
                "title": "Maximum Retail Price (MRP)",
                "clause": "Rule 6(1)(e) of Legal Metrology Rules 2011",
                "description": "MRP declared as 'MRP Rs. XX (inclusive of all taxes)'.",
                "field": "mrp",
                "weight": 15,
                "applicable_categories": ["ALL"],
                "severity": "CRITICAL"
            },
            {
                "id": "RULE_6_1_E_USP",
                "code": "LM-RULE-6-1-E-USP",
                "title": "Unit Sale Price (USP)",
                "clause": "Rule 6(1)(e) Amendment 2021",
                "description": "Unit Sale Price declared in Rs per g/kg/ml/l/unit.",
                "field": "unit_sale_price",
                "weight": 10,
                "applicable_categories": ["ALL"],
                "severity": "MAJOR"
            },
            {
                "id": "RULE_6_1_F",
                "code": "LM-RULE-6-1-F",
                "title": "Consumer Care Details",
                "clause": "Rule 6(1)(f) of Legal Metrology Rules 2011",
                "description": "Telephone helpline, email ID, and postal address for consumer complaints.",
                "field": "customer_care",
                "weight": 10,
                "applicable_categories": ["ALL"],
                "severity": "MAJOR"
            }
        ]


class LegalMetrologyRulesEngine:
    """
    Deterministic Rule-Based Legal Metrology Compliance Engine.
    Executes statutory checks under the Packaged Commodities Rules 2011.
    Each rule returns strictly one of: PASS, FAIL, WARNING, MANUAL REVIEW.
    """

    @classmethod
    def classify_tier(cls, score: float) -> Dict[str, Any]:
        """
        Classifies deterministic compliance score into mandated tiers:
        90 - 100 = COMPLIANT
        70 - 89  = MOSTLY COMPLIANT
        40 - 69  = NEEDS REVIEW
        0  - 39  = HIGH RISK
        """
        if score >= 90.0:
            return {
                "tier": "COMPLIANT",
                "risk_level": "LOW",
                "badge_class": "badge-compliant",
                "color": "#10B981",
                "description": "Packaging is fully compliant with statutory declarations under Legal Metrology Rules."
            }
        elif score >= 70.0:
            return {
                "tier": "MOSTLY COMPLIANT",
                "risk_level": "LOW",
                "badge_class": "badge-mostly-compliant",
                "color": "#06B6D4",
                "description": "Packaging meets primary mandatory declarations with minor notices."
            }
        elif score >= 40.0:
            return {
                "tier": "NEEDS REVIEW",
                "risk_level": "MEDIUM",
                "badge_class": "badge-needs-review",
                "color": "#F59E0B",
                "description": "Packaging requires manual review due to missing details or ambiguous declarations."
            }
        else:
            return {
                "tier": "HIGH RISK",
                "risk_level": "HIGH",
                "badge_class": "badge-high-risk",
                "color": "#EF4444",
                "description": "Critical statutory violations detected. Package is non-compliant and at high regulatory risk."
            }

    @classmethod
    def validate_extracted_data(cls, extracted_data: Dict[str, Any], category: str = "ALL") -> Dict[str, Any]:
        applicable_rules = RulesRegistry.get_applicable_rules(category)
        results: List[Dict[str, Any]] = []
        earned_score = 0.0
        total_possible = sum(rule.get("weight", 10) for rule in applicable_rules)

        for rule in applicable_rules:
            field_name = rule["field"]
            field_value = str(extracted_data.get(field_name, "") or "").strip()
            
            check_result = cls._evaluate_single_rule(rule, field_value, extracted_data, category)
            status = check_result["status"]  # PASS, FAIL, WARNING, MANUAL REVIEW
            score_fraction = check_result["score_fraction"]
            
            weight = rule.get("weight", 10)
            rule_earned = weight * score_fraction
            earned_score += rule_earned

            results.append({
                "rule_id": rule["id"],
                "rule_code": rule["code"],
                "title": rule["title"],
                "clause": rule["clause"],
                "description": rule.get("description", ""),
                "field": field_name,
                "value": field_value if field_value else None,
                "status": status,
                "severity": rule.get("severity", "MAJOR"),
                "weight": weight,
                "score_earned": round(rule_earned, 2),
                "finding": check_result["finding"],
                "remediation": check_result["remediation"]
            })

        # Formula: Score = Passed Rule Weight / Total Applicable Rule Weight * 100
        final_score = round((earned_score / total_possible) * 100.0, 1) if total_possible > 0 else 0.0
        tier_info = cls.classify_tier(final_score)
        compliance_status = tier_info["tier"]
        risk_level = tier_info["risk_level"]

        # Counts
        passed_count = sum(1 for r in results if r["status"] == "PASS")
        warnings_count = sum(1 for r in results if r["status"] == "WARNING")
        violations_count = sum(1 for r in results if r["status"] == "FAIL")
        manual_review_count = sum(1 for r in results if r["status"] == "MANUAL REVIEW")

        # Generate deterministic summary based on tier and counts
        summary = cls._generate_deterministic_summary(final_score, compliance_status, passed_count, warnings_count, violations_count, manual_review_count)

        return {
            "score": final_score,
            "status": compliance_status,
            "tier": compliance_status,
            "compliance_tier": compliance_status,
            "risk_level": risk_level,
            "passed_rule_weight": round(earned_score, 1),
            "total_applicable_rule_weight": total_possible,
            "formula": f"Score = {round(earned_score, 1)} / {total_possible} × 100 = {final_score}%",
            "passed_count": passed_count,
            "warnings_count": warnings_count,
            "violations_count": violations_count,
            "manual_review_count": manual_review_count,
            "summary": summary,
            "rule_checks": results
        }

    @classmethod
    def _evaluate_single_rule(cls, rule: Dict[str, Any], value: str, full_data: Dict[str, Any], category: str) -> Dict[str, Any]:
        rule_id = rule["id"]
        params = rule.get("params", {})

        # If value is completely missing
        if not value or value.lower() in ["none", "null", "n/a", "not declared"]:
            # Special case: If country of origin is missing but category is Imported Goods -> Critical FAIL
            if rule_id == "RULE_6_1_G" and category == "Imported Goods":
                return {
                    "status": "FAIL",
                    "score_fraction": 0.0,
                    "finding": "Mandatory Country of Origin & Importer declaration is completely missing for imported commodity.",
                    "remediation": "Declare 'Country of Origin: [Country]' and 'Imported By: [Name & Registered Address]'."
                }
            
            # Non-imported goods don't strictly require foreign importer declaration unless imported
            if rule_id == "RULE_6_1_G" and category != "Imported Goods":
                return {
                    "status": "PASS",
                    "score_fraction": 1.0,
                    "finding": "Domestic commodity; foreign importer declaration not required.",
                    "remediation": "Compliant."
                }

            return {
                "status": "FAIL",
                "score_fraction": 0.0,
                "finding": f"Statutory declaration for '{rule['title']}' is completely missing from the packaging label.",
                "remediation": rule.get("remediation", "Print the mandatory declaration prominently on the principal display panel.")
            }

        val_lower = value.lower().strip()

        # -------------------------------------------------------------
        # RULE 6(1)(a): Manufacturer / Packer / Importer Address
        # -------------------------------------------------------------
        if rule_id == "RULE_6_1_A":
            has_structure = any(k in val_lower for k in ["mfd", "manufactured", "packed", "imported", "marketed", "ltd", "pvt", "corp", "inc", "co.", "llp"])
            has_location = any(k in val_lower for k in ["street", "road", "industrial", "estate", "area", "dist", "state", "india", "pin", "plot", "building", "floor", "sector", "lane"])
            has_pincode = bool(re.search(r'\b[1-9][0-9]{5}\b', value))
            
            # Check if ambiguous or co-packing multi-party phrasing exists
            is_ambiguous_entity = any(w in val_lower for w in ["under license", "co-packed", "job worker", "third party", "contract pack"])

            if is_ambiguous_entity:
                return {
                    "status": "MANUAL REVIEW",
                    "score_fraction": 0.7,
                    "finding": f"Complex multi-party manufacturing or contract licensing statement detected: '{value}'.",
                    "remediation": "Verify that both marketing entity and actual manufacturing premise addresses are fully declared as per Rule 6(1)(a)."
                }
            elif has_structure and (has_location or has_pincode) and len(value) >= 20:
                return {
                    "status": "PASS",
                    "score_fraction": 1.0,
                    "finding": f"Valid manufacturer/packer name and address present: '{value}'.",
                    "remediation": "Compliant."
                }
            elif has_structure and len(value) >= 10:
                return {
                    "status": "WARNING",
                    "score_fraction": 0.6,
                    "finding": "Manufacturer/Packer name detected but complete premises address or postal PIN code appears partial.",
                    "remediation": "Include full registered address with 6-digit postal PIN code as mandated under Rule 6(1)(a)."
                }
            else:
                return {
                    "status": "FAIL",
                    "score_fraction": 0.2,
                    "finding": "Manufacturer detail lacks legally recognized company structure or postal address format.",
                    "remediation": "Declare 'Manufactured & Packed By: [Company Name, Full Registered Address, PIN Code]'."
                }

        # -------------------------------------------------------------
        # RULE 6(1)(b): Generic / Common Commodity Name
        # -------------------------------------------------------------
        elif rule_id == "RULE_6_1_B":
            vague_terms = ["product", "sample", "item", "goods", "unknown", "generic"]
            if any(term == val_lower for term in vague_terms):
                return {
                    "status": "FAIL",
                    "score_fraction": 0.0,
                    "finding": f"Declaration '{value}' is too vague and does not state the true commodity nature.",
                    "remediation": "Declare the specific common or generic name (e.g., 'Roasted Almond Butter' or 'Refined Sunflower Oil')."
                }
            elif len(value) >= 3:
                return {
                    "status": "PASS",
                    "score_fraction": 1.0,
                    "finding": f"Generic commodity name '{value}' clearly declared on package.",
                    "remediation": "Compliant."
                }
            else:
                return {
                    "status": "MANUAL REVIEW",
                    "score_fraction": 0.5,
                    "finding": f"Extracted commodity string '{value}' is short or potentially truncated by OCR.",
                    "remediation": "Inspect principal display panel to ensure full commodity name is legible."
                }

        # -------------------------------------------------------------
        # RULE 6(1)(c): Net Quantity & Standard Metric Units
        # -------------------------------------------------------------
        elif rule_id == "RULE_6_1_C":
            # Check for illegal non-metric units
            has_non_metric = any(re.search(rf'\b{u}\b', val_lower) for u in ["lbs", "lb", "oz", "ounce", "fl oz", "fluid oz", "gallon", "pint"])
            if has_non_metric:
                return {
                    "status": "FAIL",
                    "score_fraction": 0.0,
                    "finding": f"Non-metric unit detected in net quantity declaration: '{value}'. Non-metric units are prohibited under Rule 7.",
                    "remediation": "Replace non-metric measures (lbs, oz) exclusively with standard metric units (g, kg, ml, l, N)."
                }

            # Valid metric unit regex
            metric_match = re.search(r'(\d+(\.\d+)?)\s*(g|kg|ml|l|ltr|grams|kilograms|n|pcs|units)\b', val_lower)
            if metric_match:
                # Check for proper spacing between numeral and unit (e.g., '500 g' vs '500g')
                raw_token = metric_match.group(0)
                has_space = bool(re.search(r'\d+\s+[a-zA-Z]', raw_token))
                
                if has_space:
                    return {
                        "status": "PASS",
                        "score_fraction": 1.0,
                        "finding": f"Net quantity '{value}' complies with metric units and spacing standards.",
                        "remediation": "Compliant."
                    }
                else:
                    return {
                        "status": "WARNING",
                        "score_fraction": 0.85,
                        "finding": f"Net quantity '{value}' contains valid metric unit, but lacks mandated whitespace separation between numeral and unit symbol.",
                        "remediation": "Insert a space between numeral and unit symbol (e.g. '350 g' instead of '350g')."
                    }
            elif any(char.isdigit() for char in value):
                return {
                    "status": "MANUAL REVIEW",
                    "score_fraction": 0.4,
                    "finding": f"Numeral detected in quantity field ('{value}') but metric unit symbol is ambiguous.",
                    "remediation": "Confirm physical packaging specifies valid metric unit (g, kg, ml, l, N)."
                }
            else:
                return {
                    "status": "FAIL",
                    "score_fraction": 0.0,
                    "finding": f"Invalid net quantity declaration '{value}'. No metric units identified.",
                    "remediation": "State net quantity using standard metric units prescribed under Rule 7 & 8."
                }

        # -------------------------------------------------------------
        # RULE 6(1)(d): Month & Year of Manufacture / Packing
        # -------------------------------------------------------------
        elif rule_id == "RULE_6_1_D":
            date_regex = r'(\b(0[1-9]|1[0-2])[\/\-.](20[1-3][0-9]|[1-3][0-9])\b|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,.-]+(20[1-3][0-9]|[1-3][0-9])\b)'
            date_match = re.search(date_regex, val_lower)
            
            if date_match:
                return {
                    "status": "PASS",
                    "score_fraction": 1.0,
                    "finding": f"Manufacture/Packing date '{value}' meets statutory MM/YYYY calendar format.",
                    "remediation": "Compliant."
                }
            elif any(y in value for y in ["2023", "2024", "2025", "2026", "2027", "2028"]):
                return {
                    "status": "WARNING",
                    "score_fraction": 0.6,
                    "finding": f"Year detected in date declaration '{value}', but month format is non-standard.",
                    "remediation": "Format date strictly as 'Mfg Date: MM/YYYY' (e.g., 08/2026)."
                }
            elif any(w in val_lower for w in ["best before", "expiry", "use by", "months"]):
                return {
                    "status": "MANUAL REVIEW",
                    "score_fraction": 0.5,
                    "finding": f"Relative date or expiry string found ('{value}') instead of explicit manufacturing/packing date.",
                    "remediation": "Ensure both manufacturing date (MM/YYYY) and expiry timeframe are declared."
                }
            else:
                return {
                    "status": "FAIL",
                    "score_fraction": 0.0,
                    "finding": f"Date declaration '{value}' is invalid or missing month and year.",
                    "remediation": "Print manufacturing month & year prominently as 'Mfg Date: MM/YYYY'."
                }

        # -------------------------------------------------------------
        # RULE 6(1)(e): Maximum Retail Price (MRP)
        # -------------------------------------------------------------
        elif rule_id == "RULE_6_1_E":
            has_tax = any(t in val_lower for t in ["incl", "inclusive", "tax", "taxes", "all taxes"])
            has_mrp_prefix = any(m in val_lower for m in ["mrp", "m.r.p", "max retail price", "rs", "₹", "inr"])
            has_digit = any(char.isdigit() for char in value)

            if has_mrp_prefix and has_digit and has_tax:
                return {
                    "status": "PASS",
                    "score_fraction": 1.0,
                    "finding": f"MRP declaration '{value}' properly includes all applicable taxes.",
                    "remediation": "Compliant."
                }
            elif has_mrp_prefix and has_digit:
                return {
                    "status": "WARNING",
                    "score_fraction": 0.75,
                    "finding": f"MRP numeric price found in '{value}', but mandatory statutory phrase '(inclusive of all taxes)' is missing.",
                    "remediation": "Append '(inclusive of all taxes)' or '(incl. of all taxes)' alongside the MRP."
                }
            elif has_digit:
                return {
                    "status": "MANUAL REVIEW",
                    "score_fraction": 0.4,
                    "finding": f"Numeric value '{value}' detected but lacking standardized 'MRP' or '₹' prefix.",
                    "remediation": "Verify whether price declaration displays clear 'MRP Rs. XX' prefix."
                }
            else:
                return {
                    "status": "FAIL",
                    "score_fraction": 0.0,
                    "finding": f"MRP declaration '{value}' lacks price numerals.",
                    "remediation": "Declare 'MRP Rs. XX.XX (inclusive of all taxes)' prominently on the principal display panel."
                }

        # -------------------------------------------------------------
        # RULE 6(1)(e) USP: Unit Sale Price
        # -------------------------------------------------------------
        elif rule_id == "RULE_6_1_E_USP":
            has_usp = any(p in val_lower for p in ["per g", "per kg", "per ml", "per l", "per unit", "/g", "/kg", "/ml", "/l", "/unit", "usp"])
            has_digit = any(char.isdigit() for char in value)

            if has_usp and has_digit:
                return {
                    "status": "PASS",
                    "score_fraction": 1.0,
                    "finding": f"Unit Sale Price '{value}' declared as per 2021 Amendments.",
                    "remediation": "Compliant."
                }
            elif has_digit:
                return {
                    "status": "WARNING",
                    "score_fraction": 0.5,
                    "finding": f"Unit price value '{value}' found but unit measure (per g/kg/ml) is unclear.",
                    "remediation": "Declare USP clearly (e.g., '₹ 1.10 per g' or '₹ 50 per kg')."
                }
            else:
                return {
                    "status": "MANUAL REVIEW",
                    "score_fraction": 0.3,
                    "finding": "Unit Sale Price (USP) was not detected. Exempt only for packages containing <= 10g or <= 10ml.",
                    "remediation": "Check package net quantity; if > 10g/ml, declare Unit Sale Price adjacent to MRP."
                }

        # -------------------------------------------------------------
        # RULE 6(1)(f): Consumer Care Details
        # -------------------------------------------------------------
        elif rule_id == "RULE_6_1_F":
            has_email = "@" in value or "email" in val_lower
            digits_count = len(re.findall(r'\d', value))
            has_phone = digits_count >= 8 or any(w in val_lower for w in ["helpline", "toll free", "toll-free", "1800", "phone", "tel"])

            if has_email and has_phone:
                return {
                    "status": "PASS",
                    "score_fraction": 1.0,
                    "finding": f"Complete consumer care email and helpline number declared: '{value}'.",
                    "remediation": "Compliant."
                }
            elif has_email or has_phone:
                return {
                    "status": "WARNING",
                    "score_fraction": 0.7,
                    "finding": f"Partial consumer care contact: '{value}'. Providing both telephone and email is standard best practice.",
                    "remediation": "Provide both telephone helpline and active email address under 'Customer Care Cell'."
                }
            elif any(w in val_lower for w in ["care", "customer", "complaint", "feedback", "contact"]):
                return {
                    "status": "MANUAL REVIEW",
                    "score_fraction": 0.4,
                    "finding": f"Consumer care reference detected ('{value}') but contact numbers/emails require visual verification.",
                    "remediation": "Ensure executive contact address, email, and helpline number are fully legible."
                }
            else:
                return {
                    "status": "FAIL",
                    "score_fraction": 0.0,
                    "finding": "Consumer care contact details are missing.",
                    "remediation": "Include 'For Consumer Complaints: Contact Executive at [Address], Tel: [No], Email: [Mail]'."
                }

        # -------------------------------------------------------------
        # RULE 6(1)(g): Country of Origin & Importer
        # -------------------------------------------------------------
        elif rule_id == "RULE_6_1_G":
            has_origin = any(w in val_lower for w in ["india", "origin", "made in", "product of", "imported from"]) or len(value) > 2
            importer_val = str(full_data.get("importer", "") or "").strip().lower()
            has_importer = len(importer_val) > 3 and importer_val != "none"

            if category == "Imported Goods":
                if has_origin and has_importer:
                    return {
                        "status": "PASS",
                        "score_fraction": 1.0,
                        "finding": f"Country of origin ('{value}') and registered importer ('{importer_val}') declared for imported commodity.",
                        "remediation": "Compliant."
                    }
                elif has_origin:
                    return {
                        "status": "WARNING",
                        "score_fraction": 0.6,
                        "finding": f"Country of origin '{value}' declared, but registered Indian importer name/address is missing.",
                        "remediation": "Mandatory under Rule 6(1)(a) & (g) to declare registered Importer details for foreign goods."
                    }
                else:
                    return {
                        "status": "FAIL",
                        "score_fraction": 0.0,
                        "finding": "Imported commodity missing mandatory Country of Origin declaration.",
                        "remediation": "Declare 'Country of Origin: [Country]' on package."
                    }
            else:
                if "india" in val_lower or "origin" in val_lower or has_origin:
                    return {
                        "status": "PASS",
                        "score_fraction": 1.0,
                        "finding": f"Origin declared as '{value}'.",
                        "remediation": "Compliant."
                    }
                return {
                    "status": "PASS",
                    "score_fraction": 1.0,
                    "finding": "Domestic commodity origin inferred from local manufacturer registration.",
                    "remediation": "Compliant."
                }

        # -------------------------------------------------------------
        # RULE 6(1)(h): Best Before / Expiry Period (Food & Cosmetics)
        # -------------------------------------------------------------
        elif rule_id == "RULE_6_1_H":
            has_exp_pattern = bool(re.search(r'(\b(0[1-9]|1[0-2])[\/\-.](20[1-3][0-9]|[1-3][0-9])\b|\d+\s*months?)', val_lower))
            has_exp_kw = any(w in val_lower for w in ["best before", "expiry", "exp", "use by", "months from mfg", "months from packaging"])

            if has_exp_pattern and has_exp_kw:
                return {
                    "status": "PASS",
                    "score_fraction": 1.0,
                    "finding": f"Best Before / Expiry declaration '{value}' complies with regulations.",
                    "remediation": "Compliant."
                }
            elif has_exp_pattern or has_exp_kw:
                return {
                    "status": "PASS",
                    "score_fraction": 1.0,
                    "finding": f"Expiry timeframe '{value}' present.",
                    "remediation": "Compliant."
                }
            else:
                return {
                    "status": "FAIL",
                    "score_fraction": 0.0,
                    "finding": "Mandatory Best Before / Expiry timeframe missing for perishable/cosmetic commodity.",
                    "remediation": "Declare 'Best Before XX Months from Packaging' or 'Expiry Date: MM/YYYY'."
                }

        # Default fallback
        return {
            "status": "MANUAL REVIEW",
            "score_fraction": 0.5,
            "finding": f"Declaration '{value}' requires visual verification.",
            "remediation": "Inspect physical artwork for statutory alignment."
        }

    @classmethod
    def _generate_deterministic_summary(cls, score: float, status: str, passed: int, warnings: int, violations: int, manual_review: int) -> str:
        if score >= 90.0:
            return f"Product packaging is COMPLIANT ({score}% compliance score) under the Legal Metrology (Packaged Commodities) Rules, 2011. All {passed} mandatory statutory declarations meet required formatting, placement, and metric standards."
        elif score >= 70.0:
            return f"Product packaging is MOSTLY COMPLIANT ({score}% compliance score). Found {warnings} minor warning(s) or formatting adjustments. Rectify minor discrepancies before full-scale commercial distribution."
        elif score >= 40.0:
            return f"Product packaging NEEDS REVIEW ({score}% compliance score). Found {manual_review} item(s) flagged for manual verification or non-standard declarations under Legal Metrology standards."
        else:
            return f"Product packaging is HIGH RISK ({score}% compliance score). Detected {violations} critical statutory violation(s) under the Legal Metrology Act 2009. Packaging does not meet mandatory consumer packaging regulations."


# Alias for backward compatibility
ComplianceAIAnalyzer = LegalMetrologyRulesEngine
