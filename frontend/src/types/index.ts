export interface MandatoryRuleCheck {
  rule_id: string;
  rule_code: string;
  title: string;
  clause: string;
  description: string;
  field: string;
  value: string | null;
  status: 'PASS' | 'FAIL' | 'WARNING' | 'MANUAL REVIEW';
  priority?: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  severity?: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
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
  fields_confidence?: Record<string, number>;
  category?: string;
  detected_category?: string;
  raw_text: string;
  bounding_boxes: BoundingBox[];
  rule_checks: MandatoryRuleCheck[];
  summary: string;
  risk_percentage?: number;
  image_urls?: string[];
  image_filenames?: string[];
  action_items?: string[];
  manual_review_count?: number;
  critical_violations_count?: number;
  high_violations_count?: number;
  medium_violations_count?: number;
  low_violations_count?: number;
  prioritized_violations?: MandatoryRuleCheck[];
  formula?: string;
  passed_rule_weight?: number;
  total_applicable_rule_weight?: number;
}

export interface ComplianceReport {
  id: number;
  scan_id: number;
  report_code: string;
  product_name: string;
  category: string;
  detected_category?: string;
  brand?: string;
  compliance_score: number;
  compliance_status: string;
  compliance_tier?: string;
  tier?: string;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  risk_percentage?: number;
  violations_count: number;
  warnings_count: number;
  passed_count: number;
  manual_review_count?: number;
  fields_confidence?: Record<string, number>;
  critical_violations_count?: number;
  high_violations_count?: number;
  medium_violations_count?: number;
  low_violations_count?: number;
  prioritized_violations?: MandatoryRuleCheck[];
  formula?: string;
  passed_rule_weight?: number;
  total_applicable_rule_weight?: number;
  created_at: string;
  summary: string;
  details?: ExtractedPayload;
  image_url?: string;
  image_urls?: string[];
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
