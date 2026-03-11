"""ExportService — Génération de fichiers depuis un ReportResult.

Formats supportés :
    - PDF  : en-tête Mercator coloré, tableau mis en forme (reportlab)
    - CSV  : séparateur point-virgule, encodage UTF-8 BOM (Excel FR)
    - MD   : tableau Markdown standard (compatible GitHub, Obsidian, etc.)

Usage :
    from src.services.export import ExportService
    from src.models.report import ExportFormat

    pdf_bytes = ExportService.to_pdf(result)
    csv_str   = ExportService.to_csv(result)
    md_str    = ExportService.to_markdown(result)
"""
import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

from src.models.report import ReportResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Palette Mercator — thème clair (impression-friendly)
# ---------------------------------------------------------------------------

CYAN        = colors.HexColor("#0099bb")   # cyan foncé lisible sur blanc
VIOLET      = colors.HexColor("#5b21b6")
WHITE       = colors.white
LIGHT_BG    = colors.white
HEADER_BG   = colors.HexColor("#0f172a")   # quasi-noir uniquement pour l'en-tête titre
SUBHEAD_BG  = colors.HexColor("#f1f5f9")   # gris très clair pour sous-en-tête
ROW_ALT     = colors.HexColor("#f8fafc")   # alternance lignes très légère
ROW_MAIN    = colors.white
BORDER_COL  = colors.HexColor("#e2e8f0")   # bordures grises légères
COL_HEADER  = colors.HexColor("#1e293b")   # texte en-tête colonnes
TEXT_DARK   = colors.HexColor("#1e293b")   # texte principal
TEXT_MUTED  = colors.HexColor("#64748b")   # texte secondaire
CYAN_LINE   = colors.HexColor("#0099bb")   # ligne décorative
# Couleurs CIAT — gardées vives car ce sont des indicateurs
GREEN   = colors.HexColor("#059669")
AMBER   = colors.HexColor("#d97706")
RED     = colors.HexColor("#dc2626")
PURPLE  = colors.HexColor("#7c3aed")


# ---------------------------------------------------------------------------
# ExportService
# ---------------------------------------------------------------------------

class ExportService:
    """Service d'export de rapports dans différents formats."""

    # -------------------------------------------------------------------------
    # PDF
    # -------------------------------------------------------------------------

    @staticmethod
    def to_pdf(result: ReportResult) -> bytes:
        """Génère un PDF avec en-tête Mercator et tableau stylé.

        Utilise le format A4 paysage si le rapport a plus de 6 colonnes.

        Returns:
            Bytes du PDF généré.
        """
        buffer = io.BytesIO()
        cols = result.metadata.columns
        page_size = landscape(A4) if len(cols) > 6 else A4

        doc = SimpleDocTemplate(
            buffer,
            pagesize=page_size,
            leftMargin=1.5 * cm,
            rightMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=2 * cm,
            title=result.metadata.title or "Rapport Mercator",
            author="Mercator BI Explorer",
        )

        styles = _build_styles()
        story = []

        # En-tête
        story.extend(_build_header(result, styles, page_size))
        story.append(Spacer(1, 0.5 * cm))

        # Tableau de données
        if result.is_empty:
            story.append(Paragraph("Aucun résultat pour ce rapport.", styles["muted"]))
        else:
            story.append(_build_table(result, page_size))

        # Pied de page (dans le contenu, pas en overlay)
        story.append(Spacer(1, 0.5 * cm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_COL))
        story.append(Spacer(1, 0.2 * cm))
        footer_text = (
            f"Généré le {datetime.now(timezone.utc).strftime('%d/%m/%Y à %H:%M')} UTC  •  "
            f"Mercator BI Explorer  •  {result.metadata.total_items} enregistrement(s)"
        )
        story.append(Paragraph(footer_text, styles["footer"]))

        doc.build(story)
        return buffer.getvalue()

    # -------------------------------------------------------------------------
    # CSV
    # -------------------------------------------------------------------------

    @staticmethod
    def to_csv(result: ReportResult) -> str:
        """Génère un CSV UTF-8 BOM avec séparateur point-virgule.

        UTF-8 BOM assure l'ouverture correcte dans Excel FR sans conversion.

        Returns:
            Chaîne CSV complète (avec BOM).
        """
        output = io.StringIO()
        # BOM UTF-8 pour Excel FR
        output.write("\ufeff")

        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

        # Métadonnées en commentaire
        writer.writerow([f"# Rapport : {result.metadata.title or result.metadata.endpoint}"])
        writer.writerow([f"# Généré le : {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC"])
        writer.writerow([f"# Total : {result.metadata.total_items} enregistrement(s)"])
        writer.writerow([])  # ligne vide

        # En-têtes
        writer.writerow(result.metadata.columns)

        # Données
        for row in result.rows:
            writer.writerow([
                _format_cell_csv(row.data.get(col))
                for col in result.metadata.columns
            ])

        return output.getvalue()

    # -------------------------------------------------------------------------
    # Markdown
    # -------------------------------------------------------------------------

    @staticmethod
    def to_markdown(result: ReportResult) -> str:
        """Génère un tableau Markdown standard.

        Compatible GitHub, Obsidian, Notion, et tout éditeur Markdown.

        Returns:
            Chaîne Markdown complète.
        """
        lines = []
        cols = result.metadata.columns

        # En-tête document
        title = result.metadata.title or result.metadata.endpoint
        lines.append(f"# {title}")
        lines.append("")
        lines.append(
            f"*Généré le {datetime.now(timezone.utc).strftime('%d/%m/%Y à %H:%M')} UTC — "
            f"{result.metadata.total_items} enregistrement(s)*"
        )
        lines.append("")

        if result.is_empty:
            lines.append("*Aucun résultat pour ce rapport.*")
            return "\n".join(lines)

        # Calcul largeurs de colonnes pour alignement
        col_widths = {col: len(col) for col in cols}
        rows_data = []
        for row in result.rows:
            row_vals = {col: _format_cell_md(row.data.get(col)) for col in cols}
            rows_data.append(row_vals)
            for col in cols:
                col_widths[col] = max(col_widths[col], len(row_vals[col]))

        # Tableau
        def pad(s: str, width: int) -> str:
            return s.ljust(width)

        # Header row
        header = "| " + " | ".join(pad(col, col_widths[col]) for col in cols) + " |"
        separator = "| " + " | ".join("-" * col_widths[col] for col in cols) + " |"
        lines.append(header)
        lines.append(separator)

        for row_vals in rows_data:
            line = "| " + " | ".join(pad(row_vals[col], col_widths[col]) for col in cols) + " |"
            lines.append(line)

        lines.append("")
        lines.append(
            f"> **Endpoint** : `{result.metadata.endpoint}` — "
            f"**Filtres actifs** : {result.metadata.filters_applied}"
        )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers PDF
# ---------------------------------------------------------------------------

def _build_styles() -> dict:
    """Construit les styles ReportLab personnalisés."""
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "MercatorTitle",
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=WHITE,       # blanc sur fond sombre de l'en-tête
            spaceAfter=4,
            leading=20,
        ),
        "subtitle": ParagraphStyle(
            "MercatorSubtitle",
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.HexColor("#94a3b8"),
            spaceAfter=2,
        ),
        "meta": ParagraphStyle(
            "MercatorMeta",
            fontName="Helvetica",
            fontSize=8,
            textColor=TEXT_MUTED,
        ),
        "muted": ParagraphStyle(
            "MercatorMuted",
            fontName="Helvetica-Oblique",
            fontSize=10,
            textColor=TEXT_MUTED,
            spaceAfter=6,
        ),
        "footer": ParagraphStyle(
            "MercatorFooter",
            fontName="Helvetica",
            fontSize=7,
            textColor=TEXT_MUTED,
            alignment=TA_CENTER,
        ),
    }


def _build_header(result: ReportResult, styles: dict, page_size) -> list:
    """Construit l'en-tête du PDF avec fond sombre et infos rapport."""
    elements = []
    page_w = page_size[0]
    content_w = page_w - 3 * cm  # marges

    title_text = result.metadata.title or result.metadata.endpoint
    generated = datetime.now(timezone.utc).strftime("%d/%m/%Y à %H:%M UTC")

    # Bloc en-tête — bandeau sombre uniquement pour le logo/titre (économique en encre)
    header_data = [[
        Paragraph(f'<font color="#0099bb">Mercator</font> <font color="#94a3b8">BI Explorer</font>',
                  styles["subtitle"]),
    ]]
    header_table = Table(header_data, colWidths=[content_w])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HEADER_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(header_table)

    # Titre — fond sombre compact
    title_data = [[Paragraph(title_text, styles["title"])]]
    title_table = Table(title_data, colWidths=[content_w])
    title_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HEADER_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(title_table)

    # Métadonnées — fond gris très clair
    meta_text = (
        f"Endpoint : <b>{result.metadata.endpoint}</b>  •  "
        f"Résultats : <b>{result.metadata.total_items}</b>  •  "
        f"Filtres : <b>{result.metadata.filters_applied}</b>  •  "
        f"Généré le : <b>{generated}</b>"
    )
    meta_data = [[Paragraph(meta_text, styles["meta"])]]
    meta_table = Table(meta_data, colWidths=[content_w])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SUBHEAD_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -1), 2, CYAN_LINE),
    ]))
    elements.append(meta_table)

    return elements


def _build_table(result: ReportResult, page_size) -> Table:
    """Construit le tableau de données principal."""
    page_w = page_size[0]
    content_w = page_w - 3 * cm
    cols = result.metadata.columns
    n_cols = len(cols)

    # Calcul largeurs de colonnes (répartition équitable)
    col_w = content_w / n_cols

    # Header row
    header_row = [Paragraph(f"<b>{col}</b>", ParagraphStyle(
        "th",
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=WHITE,
    )) for col in cols]

    # Data rows
    data_rows = []
    for row in result.rows:
        data_row = []
        for col in cols:
            val = row.data.get(col)
            cell_text = _format_cell_pdf(val, col)
            data_row.append(Paragraph(cell_text, ParagraphStyle(
                "td",
                fontName="Helvetica",
                fontSize=8,
                textColor=TEXT_DARK,
            )))
        data_rows.append(data_row)

    all_rows = [header_row] + data_rows
    table = Table(all_rows, colWidths=[col_w] * n_cols, repeatRows=1)

    style_cmds = [
        # Header — fond sombre, texte blanc
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, CYAN_LINE),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 1), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # Bordures légères
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COL),
        ("INNERGRID", (0, 1), (-1, -1), 0.25, BORDER_COL),
    ]

    # Alternance fond lignes — blanc / gris très clair
    for i in range(1, len(all_rows)):
        bg = ROW_ALT if i % 2 == 0 else ROW_MAIN
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))

    table.setStyle(TableStyle(style_cmds))
    return table


# ---------------------------------------------------------------------------
# Formatage des valeurs
# ---------------------------------------------------------------------------

def _format_cell_pdf(value: Any, column: str = "") -> str:
    if value is None:
        return '<font color="#55556a">—</font>'
    if isinstance(value, bool):
        return "Oui" if value else "Non"

    # Niveaux CIAT — barre ASCII + libellé
    CIAT_COLS = {
        "Confidentialité", "Intégrité", "Disponibilité", "Traçabilité",
        "C", "I", "A", "T",
    }
    if column in CIAT_COLS and isinstance(value, (int, float)):
        v = int(value)
        bars    = {1: "█░░░", 2: "██░░", 3: "███░", 4: "████"}
        labels  = {1: "Faible", 2: "Moyen", 3: "Élevé", 4: "Critique"}
        colors_ = {1: "#059669", 2: "#d97706", 3: "#dc2626", 4: "#7c3aed"}
        bar = bars.get(v, "░░░░")
        lbl = labels.get(v, str(v))
        col = colors_.get(v, "#ffffff")
        return f'<font color="{col}">{bar}  {lbl}</font>'

    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


def _format_cell_csv(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


def _format_cell_md(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    # Échapper les pipes Markdown
    return str(value).replace("|", "\\|")