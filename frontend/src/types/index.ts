export interface MandatoryRuleCheck {
  rule_id: string;
  rule_code: string;
  title: string;
  clause: string;
  description: string;
  field: string;
  value: string | null;
  status: 'PASS' | 'FAIL' | 'WARNING';
  weight: number;
  score_earned: number;
  finding: string;
  remediation: string;
}

export interface BoundingBox {
  field: string;
  box: [number, number, number, number]; // [x, y, width, height]
  label: string;
}

export interface ExtractedPayload {
  fields: Record<string, string>;
  raw_text: string;
  bounding_boxes: BoundingBox[];
  rule_checks: MandatoryRuleCheck[];
  summary: string;
  action_items: string[];
}

export interface ComplianceReport {
  id: number;
  scan_id: number;
  report_code: string;
  product_name: string;
  category: string;
  brand?: string;
  compliance_score: number;
  compliance_status: 'PASS' | 'FAIL' | 'WARNING';
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  violations_count: number;
  warnings_count: number;
  passed_count: number;
  created_at: string;
  summary: string;
  details?: ExtractedPayload;
  image_url?: string;
}

export interface RuleReference {
  id: string;
  code: string;
  title: string;
  clause: string;
  description: string;
  field: string;
  weight: number;
}
