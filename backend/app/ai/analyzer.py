from typing import Dict, Any
from app.compliance.rules import LegalMetrologyRulesEngine

class ComplianceAIAnalyzer:
    """
    AI Compliance Analyzer combining Legal Metrology Act Rules with automated risk scoring,
    clause referencing, and executive summary generation.
    """

    @classmethod
    def analyze(cls, extracted_data: Dict[str, Any], category: str = "ALL") -> Dict[str, Any]:
        """
        Executes full Legal Metrology audit and produces structured compliance analysis.
        """
        # Execute deterministic Legal Metrology Rule checks
        rule_eval = LegalMetrologyRulesEngine.validate_extracted_data(extracted_data, category=category)

        score = rule_eval["score"]
        status = rule_eval["status"]
        risk_level = rule_eval["risk_level"]
        rule_checks = rule_eval["rule_checks"]

        # Synthesize executive summary & deterministic insights
        summary = cls._generate_summary(extracted_data, score, status, risk_level, rule_checks)
        key_action_items = [
            rule["remediation"] for rule in rule_checks if rule["status"] in ["FAIL", "WARNING", "MANUAL REVIEW"]
        ]

        return {
            "score": score,
            "status": status,
            "compliance_tier": status,
            "tier": status,
            "risk_level": risk_level,
            "summary": summary,
            "passed_rule_weight": rule_eval.get("passed_rule_weight", 0),
            "total_applicable_rule_weight": rule_eval.get("total_applicable_rule_weight", 0),
            "formula": rule_eval.get("formula", f"Score = {score}%"),
            "passed_count": rule_eval["passed_count"],
            "warnings_count": rule_eval["warnings_count"],
            "violations_count": rule_eval["violations_count"],
            "manual_review_count": rule_eval.get("manual_review_count", 0),
            "rule_checks": rule_checks,
            "action_items": key_action_items if key_action_items else ["Packaging fully complies with Legal Metrology (Packaged Commodities) Rules, 2011."]
        }

    @classmethod
    def _generate_summary(cls, data: Dict[str, Any], score: float, status: str, risk: str, rules: list) -> str:
        commodity = data.get("commodity_name", "Packaged Product")
        brand = data.get("brand", "Generic Brand")
        
        failed = [r["title"] for r in rules if r["status"] == "FAIL"]
        warned = [r["title"] for r in rules if r["status"] == "WARNING"]
        review = [r["title"] for r in rules if r["status"] == "MANUAL REVIEW"]

        if score >= 90.0:
            return (
                f"The packaging label for '{brand} - {commodity}' is COMPLIANT ({score}% score) under the "
                f"Legal Metrology (Packaged Commodities) Rules, 2011. Mandatory declarations satisfy all unit and placement standards."
            )
        elif score >= 70.0:
            return (
                f"The label for '{brand} - {commodity}' is MOSTLY COMPLIANT ({score}% score). "
                f"Minor warnings noted in: {', '.join(warned) if warned else 'formatting details'}. Rectify to prevent regulatory inspection queries."
            )
        elif score >= 40.0:
            return (
                f"The label for '{brand} - {commodity}' is flagged as NEEDS REVIEW ({score}% score). "
                f"Items requiring inspector review: {', '.join(review + warned + failed)}. Verify declarations against physical label packaging."
            )
        else:
            issues = failed + warned
            return (
                f"HIGH RISK DETECTED: '{brand} - {commodity}' scored only {score}% ({risk} Legal Risk). "
                f"Violations detected in mandatory requirements: {', '.join(issues)}. Continued distribution risks regulatory seizure under the Legal Metrology Act, 2009."
            )
