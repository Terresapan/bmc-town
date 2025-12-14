"""PDF Generation Service for Business Model Canvas.

This module provides functionality to generate professional PDF documents
from the Business Model Canvas data stored in BusinessUser profiles.
"""

from io import BytesIO
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from bmc.domain.business_user import BusinessUser, BusinessInsights


# BMC Block Display Names (in correct grid order)
BMC_BLOCKS = {
    "key_partnerships": "Key Partners",
    "key_activities": "Key Activities",
    "key_resources": "Key Resources",
    "value_propositions": "Value Propositions",
    "customer_relationships": "Customer Relationships",
    "channels": "Channels",
    "customer_segments": "Customer Segments",
    "cost_structure": "Cost Structure",
    "revenue_streams": "Revenue Streams",
}


def _format_block_content(items: list[str], style: ParagraphStyle) -> Paragraph:
    """Format a list of items into a bullet-pointed Paragraph."""
    if not items:
        return Paragraph("<i>Not defined yet</i>", style)
    
    bullet_text = "<br/>".join([f"• {item}" for item in items])
    return Paragraph(bullet_text, style)


def _create_block_cell(title: str, items: list[str], styles: dict) -> list:
    """Create a cell with title and content for a BMC block."""
    title_para = Paragraph(f"<b>{title}</b>", styles["block_title"])
    content_para = _format_block_content(items, styles["block_content"])
    return [title_para, Spacer(1, 0.1 * inch), content_para]


def generate_bmc_pdf(user: BusinessUser) -> bytes:
    """Generate a PDF representation of the Business Model Canvas.
    
    Args:
        user: The BusinessUser containing the canvas data.
        
    Returns:
        PDF content as bytes.
    """
    buffer = BytesIO()
    
    # Create document (A4 Landscape)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )
    
    # Define brand colors
    # Brand: from-fuchsia-500 (#d946ef) via-purple-500 (#a855f7) to-indigo-500 (#6366f1)
    c_indigo = colors.HexColor("#6366f1")
    c_purple = colors.HexColor("#a855f7")
    c_fuchsia = colors.HexColor("#d946ef")
    c_dark = colors.HexColor("#111827")
    c_gray = colors.HexColor("#6B7280")
    
    # Tints for backgrounds
    tint_indigo = colors.HexColor("#EEF2FF")
    tint_purple = colors.HexColor("#F3E8FF")
    tint_fuchsia = colors.HexColor("#FDF4FF")
    
    # Define styles
    base_styles = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "Title",
            parent=base_styles["Heading1"],
            fontSize=28,
            alignment=TA_CENTER,
            spaceAfter=18,
            textColor=c_indigo,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base_styles["Normal"],
            fontSize=11,
            alignment=TA_CENTER,
            spaceAfter=20,
            textColor=c_gray,
        ),
        "block_title": ParagraphStyle(
            "BlockTitle",
            parent=base_styles["Heading4"],
            fontSize=10,
            textColor=c_dark,
            spaceAfter=4,
        ),
        "block_content": ParagraphStyle(
            "BlockContent",
            parent=base_styles["Normal"],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#374151"),
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=base_styles["Normal"],
            fontSize=8,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#9CA3AF"),
        ),
    }
    
    # Build content
    elements = []
    
    # Header
    elements.append(Paragraph("Business Model Canvas", styles["title"]))
    elements.append(Paragraph(
        f"<b>{user.business_name}</b> | Owner: {user.owner_name} | Sector: {user.sector}",
        styles["subtitle"]
    ))
    
    # Get canvas data with defaults
    canvas_state = user.key_insights.canvas_state if user.key_insights else {}
    
    # Create BMC Grid Layout
    # The BMC layout is a 5-column grid:
    # Row 1: Key Partners | Key Activities | Value Props | Customer Rel | Customer Seg
    #                    | Key Resources  |             | Channels     |
    # Row 2: Cost Structure (spans 2.5 cols) | Revenue Streams (spans 2.5 cols)
    
    # Calculate column widths (total available width is ~10 inches for landscape A4)
    page_width = landscape(A4)[0] - 1 * inch  # Subtract margins
    col_width = page_width / 5
    half_width = page_width / 2
    
    # Build the main grid cells
    def get_block(key: str) -> list:
        return _create_block_cell(
            BMC_BLOCKS[key],
            canvas_state.get(key, []),
            styles
        )
    
    # Row 1: Top portion (Key Partners, Activities/Resources, Value Props, Relationships/Channels, Segments)
    # Using a nested table approach for the split cells
    
    # Activities + Resources cell (split vertically)
    # Each cell should be half of 4.2 inches = 2.1 inches
    activities_resources = Table(
        [
            [get_block("key_activities")],
            [get_block("key_resources")],
        ],
        colWidths=[col_width],
        rowHeights=[2.1 * inch, 2.1 * inch],
    )
    activities_resources.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (0, 0), 0.5, c_purple),
    ]))
    
    # Relationships + Channels cell (split vertically)
    # Each cell should be half of 4.2 inches = 2.1 inches
    relationships_channels = Table(
        [
            [get_block("customer_relationships")],
            [get_block("channels")],
        ],
        colWidths=[col_width],
        rowHeights=[2.1 * inch, 2.1 * inch],
    )
    relationships_channels.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (0, 0), 0.5, c_purple),
    ]))
    
    # Main grid - Top section
    top_row = Table(
        [[
            get_block("key_partnerships"),
            activities_resources,
            get_block("value_propositions"),
            relationships_channels,
            get_block("customer_segments"),
        ]],
        colWidths=[col_width] * 5,
        rowHeights=[4.2 * inch],
    )
    top_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, c_purple),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        # Tint for value propositions (center) - Uses Fuchsia tint
        ("BACKGROUND", (2, 0), (2, 0), tint_fuchsia),
        # Slight tint for others to distinguish? Let's keep others white or very subtle purple
        ("BACKGROUND", (0, 0), (1, 0), tint_purple), # Left side
        ("BACKGROUND", (3, 0), (4, 0), tint_purple), # Right side
    ]))
    
    elements.append(top_row)
    
    # Bottom row: Cost Structure | Revenue Streams
    bottom_row = Table(
        [[
            get_block("cost_structure"),
            get_block("revenue_streams"),
        ]],
        colWidths=[half_width, half_width],
        rowHeights=[1.8 * inch],
    )
    bottom_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, c_purple),
        # Cost Structure (Left) - Indigo Tint (Matching Revenue Streams)
        ("BACKGROUND", (0, 0), (0, 0), tint_indigo),
        # Revenue Streams (Right) - Indigo Tint
        ("BACKGROUND", (1, 0), (1, 0), tint_indigo),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    
    elements.append(bottom_row)
    
    # Extra Insights Section (Constraints, Preferences, Pending Topics)
    if user.key_insights:
        insights_data = []
        
        # Constraints
        constraints = user.key_insights.constraints or []
        if constraints:
            constraints_text = "<br/>".join([f"• {c}" for c in constraints])
        else:
            constraints_text = "<i>None defined</i>"
        insights_data.append([
            Paragraph("<b>🚫 Constraints</b>", styles["block_title"]),
            Paragraph(constraints_text, styles["block_content"])
        ])
        
        # Preferences
        preferences = user.key_insights.preferences or []
        if preferences:
            preferences_text = "<br/>".join([f"• {p}" for p in preferences])
        else:
            preferences_text = "<i>None defined</i>"
        insights_data.append([
            Paragraph("<b>⭐ Preferences</b>", styles["block_title"]),
            Paragraph(preferences_text, styles["block_content"])
        ])
        
        # Pending Topics
        pending = user.key_insights.pending_topics or []
        if pending:
            pending_text = "<br/>".join([f"• {t}" for t in pending])
        else:
            pending_text = "<i>None defined</i>"
        insights_data.append([
            Paragraph("<b>❓ Pending Topics</b>", styles["block_title"]),
            Paragraph(pending_text, styles["block_content"])
        ])
        
        # Only add if there's any content
        if constraints or preferences or pending:
            # Add a page break before insights
            elements.append(PageBreak())
            
            # Add header for insights page
            elements.append(Paragraph("Additional Insights", styles["title"]))
            elements.append(Spacer(1, 0.2 * inch))
            
            # Add insights as simple paragraphs (no grid)
            # Style for insight headers
            insight_header = ParagraphStyle(
                "InsightHeader",
                parent=base_styles["Normal"],
                fontSize=10,
                textColor=c_indigo,
                spaceAfter=4,
            )
            insight_content = ParagraphStyle(
                "InsightContent",
                parent=base_styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#374151"),
                leftIndent=15,
            )
            
            if constraints:
                elements.append(Paragraph("<b>Constraints:</b>", insight_header))
                for c in constraints:
                    elements.append(Paragraph(f"• {c}", insight_content))
                elements.append(Spacer(1, 0.1 * inch))
            
            if preferences:
                elements.append(Paragraph("<b>Preferences:</b>", insight_header))
                for p in preferences:
                    elements.append(Paragraph(f"• {p}", insight_content))
                elements.append(Spacer(1, 0.1 * inch))
            
            if pending:
                elements.append(Paragraph("<b>Pending Topics:</b>", insight_header))
                for t in pending:
                    elements.append(Paragraph(f"• {t}", insight_content))
    
    # Footer is drawn via onPage callback - no need to add to elements
    generated_date = datetime.now().strftime("%B %d, %Y")
    footer_text = f"Generated on {generated_date} | Made with BMC Town"
    
    def add_page_footer(canvas_obj, doc_obj):
        """Draw footer at the bottom of each page."""
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.setFillColor(colors.HexColor("#9CA3AF"))
        page_width = landscape(A4)[0]
        canvas_obj.drawCentredString(page_width / 2, 0.35 * inch, footer_text)
        canvas_obj.restoreState()
    
    # Build PDF with footer callback
    doc.build(elements, onFirstPage=add_page_footer, onLaterPages=add_page_footer)
    
    return buffer.getvalue()
