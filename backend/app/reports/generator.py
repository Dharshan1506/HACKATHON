import os
import datetime
from typing import Dict, Any
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

class ReportGenerator:
    """
    Compliance Report Generator producing audit JSON reports and downloadable PDF files.
    """

    @classmethod
    def generate_pdf_report(cls, report_code: str, product_name: str, scan_data: Dict[str, Any], output_path: str) -> str:
        """
        Generates a professional PDF Legal Metrology Audit Certificate/Report.
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
        
        # Custom Styles
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#0F172A")
        )
        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            textColor=colors.HexColor("#64748B")
        )
        section_heading = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=12,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155")
        )

        story = []

        # Header Title
        story.append(Paragraph("PackSure AI – Legal Metrology Audit Report", title_style))
        story.append(Paragraph(f"Report Code: {report_code} | Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", subtitle_style))
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=15))

        # Overview Table
        score = scan_data.get("compliance_score", 0)
        status = scan_data.get("compliance_status", "UNKNOWN")
        risk = scan_data.get("risk_level", "UNKNOWN")

        status_color = "#10B981" if status == "PASS" else ("#F59E0B" if status == "WARNING" else "#EF4444")

        overview_data = [
            [
                Paragraph("<b>Product Name:</b>", body_style),
                Paragraph(product_name, body_style),
                Paragraph("<b>Compliance Score:</b>", body_style),
                Paragraph(f"<b>{score:.1f}%</b>", body_style)
            ],
            [
                Paragraph("<b>Audit Status:</b>", body_style),
                Paragraph(f"<font color='{status_color}'><b>{status}</b></font>", body_style),
                Paragraph("<b>Legal Risk Level:</b>", body_style),
                Paragraph(risk, body_style)
            ]
        ]
        t_overview = Table(overview_data, colWidths=[110, 180, 110, 140])
        t_overview.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(t_overview)
        story.append(Spacer(1, 15))

        # Executive Summary
        story.append(Paragraph("Executive Summary", section_heading))
        summary_text = scan_data.get("extracted_data", {}).get("summary", "Audit evaluation completed.")
        story.append(Paragraph(summary_text, body_style))
        story.append(Spacer(1, 15))

        # Rule Checks Breakdown Table
        story.append(Paragraph("Legal Metrology (Packaged Commodities) Rules 2011 Audit Breakdown", section_heading))
        
        table_data = [["Rule Clause", "Mandatory Declaration", "Status", "Finding & Remediation"]]
        
        rule_checks = scan_data.get("extracted_data", {}).get("rule_checks", [])
        for r in rule_checks:
            r_status = r.get("status", "FAIL")
            st_color = "#10B981" if r_status == "PASS" else ("#F59E0B" if r_status == "WARNING" else "#EF4444")
            
            table_data.append([
                Paragraph(f"<b>{r.get('rule_code', '')}</b><br/>{r.get('clause', '')}", body_style),
                Paragraph(f"<b>{r.get('title', '')}</b><br/><i>{r.get('value') or 'Not Found'}</i>", body_style),
                Paragraph(f"<font color='{st_color}'><b>{r_status}</b></font>", body_style),
                Paragraph(f"{r.get('finding', '')}<br/><b>Action:</b> {r.get('remediation', '')}", body_style)
            ])

        rule_table = Table(table_data, colWidths=[110, 150, 60, 220])
        rule_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(rule_table)
        story.append(Spacer(1, 20))

        # Footer Notice
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=10))
        story.append(Paragraph("Generated automatically by PackSure AI Compliance Engine. Enforces Legal Metrology Act, 2009 & Packaged Commodities Rules 2011.", subtitle_style))

        doc.build(story)
        return output_path
