import os
import datetime
from typing import Dict, Any, Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image as RLImage, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from PIL import Image as PILImage

class ReportGenerator:
    """
    Compliance Report Generator producing audit JSON reports and downloadable PDF files
    under the Legal Metrology (Packaged Commodities) Rules, 2011.
    """

    @classmethod
    def _create_image_flowable(cls, image_path: Optional[str], max_w: float = 140, max_h: float = 140):
        if not image_path or not os.path.exists(image_path):
            return None
        try:
            with PILImage.open(image_path) as pimg:
                w, h = pimg.size
                aspect = h / float(w)
                target_w = max_w
                target_h = target_w * aspect
                if target_h > max_h:
                    target_h = max_h
                    target_w = target_h / aspect
            return RLImage(image_path, width=target_w, height=target_h)
        except Exception:
            return None

    @classmethod
    def generate_pdf_report(cls, report_code: str, product_name: str, scan_data: Dict[str, Any], output_path: str, image_path: Optional[str] = None) -> str:
        """
        Generates an official, comprehensive PDF Legal Metrology Audit Certificate and Regulatory Report.
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()

        # Premium Custom Typography & Palette
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0F172A")
        )
        subtitle_style = ParagraphStyle(
            'DocSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#06B6D4")
        )
        meta_style = ParagraphStyle(
            'DocMeta',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#64748B")
        )
        section_heading = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=10,
            spaceAfter=4
        )
        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#334155")
        )
        body_bold = ParagraphStyle(
            'BodyBold',
            parent=body_style,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor("#0F172A")
        )
        finding_style = ParagraphStyle(
            'Finding',
            parent=body_style,
            fontName='Helvetica',
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#475569")
        )
        remediation_style = ParagraphStyle(
            'Remediation',
            parent=body_style,
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#0284C7")
        )
        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=7,
            leading=9.5,
            textColor=colors.HexColor("#64748B")
        )

        story = []

        # ---------------------------------------------------------
        # 1. Header Banner
        # ---------------------------------------------------------
        header_table_data = [
            [
                Paragraph("<b>PACKSURE AI</b><br/><font size=7 color='#06B6D4'>LEGAL METROLOGY REGULATORY COMPLIANCE SYSTEM</font>", title_style),
                Paragraph(f"<b>AUDIT CERTIFICATE</b><br/><font size=7 color='#64748B'>Report Code: {report_code}<br/>Generated: {datetime.datetime.now().strftime('%d %b %Y, %H:%M')}</font>", ParagraphStyle('RightMeta', parent=meta_style, alignment=2))
            ]
        ]
        t_header = Table(header_table_data, colWidths=[320, 220])
        t_header.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(t_header)
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0F172A"), spaceAfter=8))

        # ---------------------------------------------------------
        # 2. Executive Summary & Compliance Score Card
        # ---------------------------------------------------------
        score = float(scan_data.get("compliance_score", 0.0))
        status = str(scan_data.get("compliance_status", "UNKNOWN")).upper()
        risk = str(scan_data.get("risk_level", "UNKNOWN")).upper()
        ext_data = scan_data.get("extracted_data", {})
        fields = ext_data.get("fields", {})
        category = ext_data.get("category", "Food")
        formula_text = ext_data.get("formula", f"Score = {score:.1f}%")
        summary_text = ext_data.get("summary", "Compliance evaluation completed.")

        status_color = "#10B981" if score >= 90 else ("#06B6D4" if score >= 70 else ("#F59E0B" if score >= 40 else "#EF4444"))
        status_bg = "#ECFDF5" if score >= 90 else ("#ECFEFF" if score >= 70 else ("#FFFBEB" if score >= 40 else "#FEF2F2"))

        # Score & Metric Summary Box
        score_card_data = [
            [
                Paragraph(f"<font size=18 color='{status_color}'><b>{score:.1f}%</b></font><br/><font size=7 color='#64748B'><b>COMPLIANCE SCORE</b></font>", ParagraphStyle('Score', parent=body_style, alignment=1)),
                Paragraph(f"<font size=11 color='{status_color}'><b>{status}</b></font><br/><font size=7 color='#64748B'>STATUTORY VERDICT</font>", ParagraphStyle('Verdict', parent=body_style, alignment=1)),
                Paragraph(f"<font size=10 color='#0F172A'><b>{risk} RISK</b></font><br/><font size=7 color='#64748B'>ENFORCEMENT EXPOSURE</font>", ParagraphStyle('Risk', parent=body_style, alignment=1)),
                Paragraph(f"<font size=8 color='#0F172A'><b>{category}</b></font><br/><font size=7 color='#64748B'>PRODUCT CATEGORY</font>", ParagraphStyle('Cat', parent=body_style, alignment=1))
            ]
        ]
        t_score = Table(score_card_data, colWidths=[135, 135, 135, 135])
        t_score.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(status_bg)),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor(status_color)),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(t_score)
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<font size=7 color='#475569'><b>Deterministic Formula:</b> {formula_text} &nbsp;|&nbsp; <b>Standards:</b> 90-100% Compliant, 70-89% Mostly Compliant, 40-69% Needs Review, 0-39% High Risk</font>", meta_style))
        story.append(Spacer(1, 8))

        # ---------------------------------------------------------
        # 3. Product Details & Embedded Packaging Photo
        # ---------------------------------------------------------
        story.append(Paragraph("Product Declarations & Physical Label Image", section_heading))

        img_flowable = cls._create_image_flowable(image_path, max_w=140, max_h=130)
        if not img_flowable:
            img_flowable = Paragraph("<font size=8 color='#94A3B8'><i>Packaging Photo<br/>Not Attached</i></font>", ParagraphStyle('NoImg', parent=body_style, alignment=1))

        details_table_data = [
            [
                Paragraph("<b>Product / Commodity:</b>", body_style),
                Paragraph(fields.get("commodity_name") or product_name, body_bold),
                Paragraph("<b>Maximum Retail Price (MRP):</b>", body_style),
                Paragraph(fields.get("mrp") or "<font color='#EF4444'>Missing</font>", body_bold)
            ],
            [
                Paragraph("<b>Brand Name:</b>", body_style),
                Paragraph(fields.get("brand") or "Not Declared", body_style),
                Paragraph("<b>Net Quantity:</b>", body_style),
                Paragraph(fields.get("net_quantity") or "<font color='#EF4444'>Missing</font>", body_bold)
            ],
            [
                Paragraph("<b>Mfg / Packing Date:</b>", body_style),
                Paragraph(fields.get("mfg_date") or "<font color='#EF4444'>Missing</font>", body_style),
                Paragraph("<b>Unit Sale Price (USP):</b>", body_style),
                Paragraph(fields.get("unit_sale_price") or "<font color='#F59E0B'>Missing</font>", body_style)
            ],
            [
                Paragraph("<b>Expiry / Best Before:</b>", body_style),
                Paragraph(fields.get("expiry_date") or "Not Declared", body_style),
                Paragraph("<b>Country of Origin:</b>", body_style),
                Paragraph(fields.get("country_of_origin") or "India", body_style)
            ],
            [
                Paragraph("<b>Manufacturer Details:</b>", body_style),
                Paragraph(fields.get("manufacturer_details") or fields.get("address") or "<font color='#EF4444'>Missing</font>", body_style),
                Paragraph("<b>Consumer Care Helpline:</b>", body_style),
                Paragraph(fields.get("customer_care") or "<font color='#F59E0B'>Missing</font>", body_style)
            ]
        ]
        t_details = Table(details_table_data, colWidths=[90, 100, 95, 95])
        t_details.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        split_container = [
            [img_flowable, t_details]
        ]
        t_split = Table(split_container, colWidths=[150, 390])
        t_split.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('PADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(t_split)
        story.append(Spacer(1, 8))

        # ---------------------------------------------------------
        # 4. OCR Extraction Diagnostics Summary
        # ---------------------------------------------------------
        raw_text_snippet = ext_data.get("raw_text", "").replace("\n", " ")[:200]
        boxes_count = len(ext_data.get("bounding_boxes", []))
        story.append(Paragraph(
            f"<b>OCR Extraction Diagnostic:</b> Engine: <i>PaddleOCR v2.7 (DBNet + CRNN)</i> &nbsp;|&nbsp; "
            f"Detected Segments: <b>{boxes_count} bounding boxes</b> &nbsp;|&nbsp; "
            f"Raw Stream: <font size=7 color='#64748B'>\"{raw_text_snippet}...\"</font>",
            body_style
        ))
        story.append(Spacer(1, 8))

        # ---------------------------------------------------------
        # 5. Prioritized Violations & Status Counts Bar
        # ---------------------------------------------------------
        checks = ext_data.get("rule_checks", [])
        passed_cnt = sum(1 for c in checks if c.get("status") == "PASS")
        failed_cnt = sum(1 for c in checks if c.get("status") == "FAIL")
        warn_cnt = sum(1 for c in checks if c.get("status") == "WARNING")
        review_cnt = sum(1 for c in checks if c.get("status") == "MANUAL REVIEW")

        crit_cnt = ext_data.get("critical_violations_count", sum(1 for c in checks if c.get("priority") == "CRITICAL" and c.get("status") != "PASS"))
        hi_cnt = ext_data.get("high_violations_count", sum(1 for c in checks if c.get("priority") == "HIGH" and c.get("status") != "PASS"))
        med_cnt = ext_data.get("medium_violations_count", sum(1 for c in checks if c.get("priority") == "MEDIUM" and c.get("status") != "PASS"))
        lo_cnt = ext_data.get("low_violations_count", sum(1 for c in checks if c.get("priority") == "LOW" and c.get("status") != "PASS"))

        metrics_data = [
            [
                Paragraph(f"<b>PASSED:</b> {passed_cnt}", ParagraphStyle('P', parent=body_style, textColor=colors.HexColor("#10B981"))),
                Paragraph(f"<b>FAILED:</b> {failed_cnt}", ParagraphStyle('F', parent=body_style, textColor=colors.HexColor("#EF4444"))),
                Paragraph(f"<b>WARNINGS:</b> {warn_cnt}", ParagraphStyle('W', parent=body_style, textColor=colors.HexColor("#F59E0B"))),
                Paragraph(f"<b>MANUAL REVIEW:</b> {review_cnt}", ParagraphStyle('R', parent=body_style, textColor=colors.HexColor("#8B5CF6"))),
                Paragraph(f"<b>PRIORITY ISSUES:</b> <font color='#EF4444'>{crit_cnt} Critical</font>, <font color='#F97316'>{hi_cnt} High</font>, <font color='#8B5CF6'>{med_cnt} Med</font>", body_style),
            ]
        ]
        t_metrics = Table(metrics_data, colWidths=[70, 70, 80, 100, 220])
        t_metrics.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('PADDING', (0, 0), (-1, -1), 3.5),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(t_metrics)
        story.append(Spacer(1, 8))

        # ---------------------------------------------------------
        # 6. Detailed Statutory Declarations Audit Table (Sorted)
        # ---------------------------------------------------------
        story.append(Paragraph("Statutory Declarations Audit Breakdown (PCR 2011)", section_heading))

        rule_table_data = [[
            Paragraph("<b>Rule Reference & Code</b>", ParagraphStyle('TH1', parent=body_style, fontName='Helvetica-Bold', textColor=colors.white)),
            Paragraph("<b>Mandatory Declaration & Extracted Value</b>", ParagraphStyle('TH2', parent=body_style, fontName='Helvetica-Bold', textColor=colors.white)),
            Paragraph("<b>Verdict / Priority</b>", ParagraphStyle('TH3', parent=body_style, fontName='Helvetica-Bold', textColor=colors.white)),
            Paragraph("<b>Statutory Finding & Actionable Remediation</b>", ParagraphStyle('TH4', parent=body_style, fontName='Helvetica-Bold', textColor=colors.white)),
        ]]

        for r in checks:
            st = r.get("status", "FAIL")
            pri = r.get("priority", "LOW")
            st_color = "#10B981" if st == "PASS" else ("#F59E0B" if st == "WARNING" else ("#8B5CF6" if st == "MANUAL REVIEW" else "#EF4444"))
            pri_color = "#EF4444" if pri == "CRITICAL" else ("#F97316" if pri == "HIGH" else ("#8B5CF6" if pri == "MEDIUM" else "#3B82F6"))

            val_display = r.get("value") or "<font color='#EF4444'>Missing / Undetected</font>"

            rule_table_data.append([
                Paragraph(f"<b>{r.get('rule_code', '')}</b><br/><font size=6.5 color='#64748B'>{r.get('clause', '')}</font>", body_style),
                Paragraph(f"<b>{r.get('title', '')}</b><br/><font size=7 color='#334155'>{val_display}</font>", body_style),
                Paragraph(f"<font color='{st_color}'><b>{st}</b></font><br/><font size=6.5 color='{pri_color}'><b>{pri}</b></font>", body_style),
                Paragraph(f"{r.get('finding', '')}<br/><font color='#0284C7'><b>Fix:</b> {r.get('remediation', '')}</font>", finding_style)
            ])

        t_rules = Table(rule_table_data, colWidths=[105, 135, 75, 225])
        t_rules.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ]))
        story.append(t_rules)
        story.append(Spacer(1, 10))

        # ---------------------------------------------------------
        # 7. Actionable Regulatory Recommendations Checklist
        # ---------------------------------------------------------
        story.append(Paragraph("Actionable Statutory Packaging Recommendations", section_heading))
        non_pass = [c for c in checks if c.get("status") != "PASS"]
        if non_pass:
            rec_items = []
            for idx, item in enumerate(non_pass, start=1):
                rec_items.append([
                    Paragraph(f"<b>{idx}.</b>", body_bold),
                    Paragraph(f"<b>{item.get('title', '')} ({item.get('rule_code', '')}):</b> {item.get('remediation', '')} <font color='#64748B'><i>[Ref: {item.get('clause', '')}]</i></font>", body_style)
                ])
            t_rec = Table(rec_items, colWidths=[20, 520])
            t_rec.setStyle(TableStyle([
                ('PADDING', (0, 0), (-1, -1), 2.5),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(t_rec)
        else:
            story.append(Paragraph("<font color='#10B981'><b>✓ All mandatory declarations comply with Legal Metrology (Packaged Commodities) Rules, 2011. Packaging is legally cleared for commercial distribution.</b></font>", body_style))
        
        story.append(Spacer(1, 10))

        # ---------------------------------------------------------
        # 8. Statutory Legal Disclaimer
        # ---------------------------------------------------------
        story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#CBD5E1"), spaceAfter=6))
        story.append(Paragraph(
            "<b>STATUTORY REGULATORY DISCLAIMER:</b> This Legal Metrology Compliance Audit Certificate is generated deterministically "
            "by the PackSure AI Compliance Engine in strict conformance with the Legal Metrology Act, 2009 (Act No. 1 of 2010) and the "
            "Legal Metrology (Packaged Commodities) Rules, 2011 (as amended). This certificate provides a pre-market technical audit of "
            "mandatory statutory declarations. Final legal responsibility remains with the manufacturer, packer, or importer to maintain physical artwork compliance.",
            disclaimer_style
        ))

        doc.build(story)
        return output_path
