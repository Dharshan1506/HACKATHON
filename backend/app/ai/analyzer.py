from typing import Dict, Any
from app.compliance.rules import LegalMetrologyRulesEngine

class ComplianceAIAnalyzer:
    """
    AI Compliance Analyzer combining Legal Metrology Act Rules with automated risk scoring,
    clause referencing, and executive summary generation.
    """

    @classmethod
    def analyze(cls, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes full Legal Metrology audit and produces structured compliance analysis.
        """
        # Execute Legal Metrology Rule checks
        rule_eval = LegalMetrologyRulesEngine.validate_extracted_data(extracted_data)

        score = rule_eval["score"]
        status = rule_eval["status"]
        risk_level = rule_eval["risk_level"]
        rule_checks = rule_eval["rule_checks"]

        # Synthesize executive summary & AI key insights
        summary = cls._generate_summary(extracted_data, score, status, risk_level, rule_checks)
        key_action_items = [
            rule["remediation"] for rule in rule_checks if rule["status"] in ["FAIL", "WARNING"]
        ]

        return {
            "score": score,
            "status": status,
            "risk_level": risk_level,
            "summary": summary,
            "passed_count": rule_eval["passed_count"],
            "warnings_count": rule_eval["warnings_count"],
            "violations_count": rule_eval["violations_count"],
            "rule_checks": rule_checks,
            "action_items": key_action_items if key_action_items else ["Packaging fully complies with Legal Metrology (Packaged Commodities) Rules, 2011."]
        }

    @classmethod
    def _generate_summary(cls, data: Dict[str, Any], score: float, status: str, risk: str, rules: list) -> str:
        commodity = data.get("commodity_name", "Packaged Product")
        brand = data.get("brand", "Generic Brand")
        
        failed = [r["title"] for r in rules if r["status"] == "FAIL"]
        warned = [r["title"] for r in rules if r["status"] == "WARNING"]

        if status == "PASS":
            return (
                f"The packaging label for '{brand} - {commodity}' scored {score}% compliance under the "
                f"Legal Metrology (Packaged Commodities) Rules, 2011. All 7 mandatory declarations are validly "
                f"presented with clear legible font and required standard metric units."
            )
        elif status == "WARNING":
            return (
                f"The label for '{brand} - {commodity}' achieved {score}% compliance. "
                f"Minor warnings detected in: {', '.join(warned)}. Address these warnings to prevent statutory notices "
                f"from state Legal Metrology inspectors."
            )
        else:
            issues = failed + warned
            return (
                f"CRITICAL COMPLIANCE FAILURE: '{brand} - {commodity}' scored only {score}% ({risk} Legal Risk). "
                f"Violations detected in mandatory requirements: {', '.join(issues)}. Continued distribution of non-compliant "
                f"packaged goods risks seizure under Section 36 of the Legal Metrology Act, 2009."
            )
