#!/usr/bin/env python3
"""Create an editable PDF catalog for validating all 40 Actu Foot templates."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import actu_foot_event_templates as events


OUT = ROOT / "artifacts" / "MR_XPRONOS_Validation_Templates_Actu_Foot.pdf"

TEMPLATES = [
    ("poteau", "POTEAU"),
    ("occasion_manquee", "OCCASION MANQUÉE"),
    ("arret_decisif", "ARRÊT DÉCISIF"),
    ("carton_jaune_full", "CARTON JAUNE - joueur connu"),
    ("carton_jaune_unknown", "CARTON JAUNE - joueur inconnu"),
    ("carton_rouge_full", "CARTON ROUGE - joueur connu"),
    ("carton_rouge_unknown", "CARTON ROUGE - joueur inconnu"),
    ("remplacement_full", "REMPLACEMENT - entrant + sortant"),
    ("remplacement_entrant", "REMPLACEMENT - entrant seulement"),
    ("remplacement_sortant", "REMPLACEMENT - sortant seulement"),
    ("intervention_medicale", "INTERVENTION MÉDICALE"),
    ("blessure_confirmee", "BLESSURE CONFIRMÉE"),
    ("retour_au_jeu", "RETOUR AU JEU"),
    ("match_suspendu", "MATCH SUSPENDU"),
    ("match_interrompu_full", "MATCH INTERROMPU - motif connu"),
    ("match_interrompu_unknown", "MATCH INTERROMPU - motif inconnu"),
    ("match_reporte", "MATCH REPORTÉ"),
    ("match_annule", "MATCH ANNULÉ"),
    ("reprise_match", "REPRISE DU MATCH"),
    ("temps_additionnel", "TEMPS ADDITIONNEL"),
    ("fin_1re_mi_temps", "FIN DE LA 1RE MI-TEMPS"),
    ("debut_2e_mi_temps", "DÉBUT DE LA 2E MI-TEMPS"),
    ("fin_temps_reglementaire", "FIN DU TEMPS RÉGLEMENTAIRE"),
    ("prolongation", "PROLONGATION"),
    ("mi_temps_prolongation", "MI-TEMPS DE LA PROLONGATION"),
    ("tirs_au_but", "TIRS AU BUT"),
    ("tir_au_but_marque", "TIR AU BUT MARQUÉ"),
    ("tir_au_but_manque", "TIR AU BUT MANQUÉ"),
    ("fin_tirs_au_but", "FIN DES TIRS AU BUT"),
    ("composition_probable_full", "COMPOSITION PROBABLE - onze complet"),
    ("composition_probable_partial", "COMPOSITION PROBABLE - partielle"),
    ("changement_composition", "CHANGEMENT DE COMPOSITION"),
    ("absence_confirmee", "ABSENCE CONFIRMÉE"),
    ("retour_groupe", "RETOUR DANS LE GROUPE"),
    ("score_live_two_logos", "SCORE LIVE CONFIRMÉ - deux logos"),
    ("score_live_one_logo", "SCORE LIVE CONFIRMÉ - un seul logo"),
    ("score_live_no_logos", "SCORE LIVE CONFIRMÉ - aucun logo"),
    ("score_live_no_minute", "SCORE LIVE CONFIRMÉ - minute absente"),
    ("but_full", "BUT - buteur + passeur disponibles"),
    ("but_scorer_only", "BUT - buteur connu / passeur inconnu"),
]


def register_fonts():
    candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DV"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DV-Bold"),
    ]
    for path, name in candidates:
        if Path(path).is_file():
            pdfmetrics.registerFont(TTFont(name, path))
    return (
        "DV" if "DV" in pdfmetrics.getRegisteredFontNames() else "Helvetica",
        "DV-Bold" if "DV-Bold" in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold",
    )


def fit_text(c, text, font, max_size, min_size, max_width):
    size = max_size
    while size > min_size and pdfmetrics.stringWidth(text, font, size) > max_width:
        size -= 0.5
    c.setFont(font, size)
    return size


def add_header(c, regular, bold, page_no=None):
    w, h = A4
    c.setFillColor(colors.HexColor("#071521"))
    c.rect(0, 0, w, h, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#D7A83E"))
    c.setLineWidth(1.2)
    c.roundRect(8*mm, 8*mm, w-16*mm, h-16*mm, 4*mm, fill=0, stroke=1)
    c.setFillColor(colors.HexColor("#F3C65F"))
    c.setFont(bold, 11)
    c.drawString(14*mm, h-15*mm, "MR XPRONOS  •  ACTU FOOT")
    c.setFillColor(colors.white)
    c.setFont(regular, 8)
    c.drawRightString(w-14*mm, h-15*mm, "PDF de validation des templates")
    if page_no is not None:
        c.setFillColor(colors.HexColor("#B8C2CB"))
        c.setFont(regular, 7)
        c.drawRightString(w-14*mm, 12*mm, f"Page {page_no}")


def cover(c, regular, bold):
    w, h = A4
    add_header(c, regular, bold)
    c.setFillColor(colors.white)
    c.setFont(bold, 24)
    c.drawCentredString(w/2, h-62*mm, "VALIDATION DES TEMPLATES")
    c.setFillColor(colors.HexColor("#F3C65F"))
    c.setFont(bold, 19)
    c.drawCentredString(w/2, h-78*mm, "MR XPRONOS - ACTU FOOT")

    c.setFillColor(colors.HexColor("#D7DEE5"))
    c.setFont(regular, 11)
    lines = [
        "40 templates actuellement intégrés au projet.",
        "Chaque template dispose de cases de validation et d'un champ de notes modifiable.",
        "Coche VALIDÉ si le design est cohérent.",
        "Coche À RECRÉER si le template doit être regénéré/remplacé.",
        "Important : les templates marqués FALLBACK PYTHON correspondent aux fonds techniques",
        "actuellement utilisés par le projet quand aucun PNG premium n'est présent.",
    ]
    y = h-110*mm
    for line in lines:
        c.drawCentredString(w/2, y, line)
        y -= 7*mm

    c.setFillColor(colors.HexColor("#102A3B"))
    c.roundRect(24*mm, 42*mm, w-48*mm, 44*mm, 5*mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(bold, 10)
    c.drawString(32*mm, 73*mm, "Mode d'emploi")
    c.setFont(regular, 9)
    c.drawString(32*mm, 64*mm, "1. Parcours les pages et vérifie chaque visuel.")
    c.drawString(32*mm, 57*mm, "2. Coche une seule décision : VALIDÉ ou À RECRÉER.")
    c.drawString(32*mm, 50*mm, "3. Ajoute les corrections souhaitées dans le champ Notes.")
    c.showPage()


def summary_pages(c, regular, bold, source_map):
    w, h = A4
    rows_per_page = 20
    for page_idx in range(2):
        add_header(c, regular, bold, 2 + page_idx)
        c.setFillColor(colors.white)
        c.setFont(bold, 16)
        c.drawString(16*mm, h-29*mm, "Sommaire de validation")
        c.setFont(regular, 8)
        c.setFillColor(colors.HexColor("#B8C2CB"))
        c.drawString(16*mm, h-36*mm, "Source = PNG PREMIUM si un fichier image existe dans le dépôt ; sinon FALLBACK PYTHON.")

        start = page_idx * rows_per_page
        end = min(len(TEMPLATES), start + rows_per_page)
        y = h - 48*mm
        for i in range(start, end):
            key, label = TEMPLATES[i]
            lot = i // 5 + 1
            source = source_map[key]
            source_color = "#46C37B" if source == "PNG PREMIUM" else "#F3A34A"
            c.setFillColor(colors.HexColor("#102A3B"))
            c.roundRect(15*mm, y-6*mm, w-30*mm, 10*mm, 2*mm, fill=1, stroke=0)
            c.setFillColor(colors.HexColor("#F3C65F"))
            c.setFont(bold, 8)
            c.drawString(19*mm, y-1.7*mm, f"{i+1:02d}")
            c.setFillColor(colors.white)
            fit_text(c, label, bold, 8.5, 6.5, 105*mm)
            c.drawString(30*mm, y-1.7*mm, label)
            c.setFillColor(colors.HexColor(source_color))
            c.setFont(bold, 6.6)
            c.drawRightString(w-19*mm, y-1.7*mm, f"LOT {lot} • {source}")
            y -= 11.4*mm
        c.showPage()


def template_page(c, regular, bold, idx, key, label, source, tmpdir):
    w, h = A4
    page_no = idx + 4
    add_header(c, regular, bold, page_no)

    lot = idx // 5 + 1
    c.setFillColor(colors.HexColor("#F3C65F"))
    c.setFont(bold, 7.5)
    c.drawString(15*mm, h-27*mm, f"TEMPLATE {idx+1:02d}/40  •  LOT {lot}  •  {key}")

    c.setFillColor(colors.white)
    fit_text(c, label, bold, 16, 10, w-30*mm)
    c.drawString(15*mm, h-36*mm, label)

    source_color = "#46C37B" if source == "PNG PREMIUM" else "#F3A34A"
    c.setFillColor(colors.HexColor(source_color))
    c.setFont(bold, 7.5)
    c.drawRightString(w-15*mm, h-27*mm, source)

    # Render/get background exactly as the project currently resolves it.
    image = events.background(key, {})
    preview = Path(tmpdir) / f"{idx:02d}_{key}.jpg"
    image.convert("RGB").save(preview, "JPEG", quality=86, optimize=True)

    # Large preview.
    x = 26*mm
    y = 75*mm
    pw = w - 52*mm
    ph = 174*mm
    iw, ih = image.size
    scale = min(pw/iw, ph/ih)
    dw, dh = iw*scale, ih*scale
    dx = x + (pw-dw)/2
    dy = y + (ph-dh)/2
    c.setFillColor(colors.HexColor("#02080D"))
    c.roundRect(x-2*mm, y-2*mm, pw+4*mm, ph+4*mm, 3*mm, fill=1, stroke=0)
    c.drawImage(str(preview), dx, dy, width=dw, height=dh, preserveAspectRatio=True, mask='auto')

    # Review box.
    box_y = 18*mm
    c.setFillColor(colors.HexColor("#102A3B"))
    c.roundRect(15*mm, box_y, w-30*mm, 49*mm, 4*mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(bold, 8.5)
    c.drawString(20*mm, box_y+40*mm, "Décision")

    form = c.acroForm
    form.checkbox(
        name=f"valid_{key}",
        tooltip=f"Valider {label}",
        x=21*mm, y=box_y+29*mm,
        buttonStyle="check",
        borderWidth=1,
        borderColor=colors.HexColor("#F3C65F"),
        fillColor=colors.HexColor("#071521"),
        textColor=colors.HexColor("#46C37B"),
        size=5*mm,
        checked=False,
        forceBorder=True,
    )
    c.setFillColor(colors.white)
    c.setFont(bold, 8.5)
    c.drawString(28*mm, box_y+30.2*mm, "VALIDÉ")

    form.checkbox(
        name=f"recreate_{key}",
        tooltip=f"Recréer {label}",
        x=63*mm, y=box_y+29*mm,
        buttonStyle="check",
        borderWidth=1,
        borderColor=colors.HexColor("#F3C65F"),
        fillColor=colors.HexColor("#071521"),
        textColor=colors.HexColor("#E65A5A"),
        size=5*mm,
        checked=False,
        forceBorder=True,
    )
    c.setFillColor(colors.white)
    c.drawString(70*mm, box_y+30.2*mm, "À RECRÉER")

    c.setFont(regular, 7)
    c.setFillColor(colors.HexColor("#B8C2CB"))
    c.drawString(115*mm, box_y+30.2*mm, "Coche une seule décision.")

    c.setFillColor(colors.HexColor("#D7DEE5"))
    c.setFont(bold, 7.5)
    c.drawString(20*mm, box_y+20*mm, "Notes / corrections :")
    form.textfield(
        name=f"notes_{key}",
        tooltip=f"Notes pour {label}",
        x=20*mm, y=box_y+4*mm,
        width=w-40*mm, height=13*mm,
        borderStyle="underlined",
        borderWidth=1,
        borderColor=colors.HexColor("#607D8B"),
        fillColor=colors.HexColor("#081722"),
        textColor=colors.white,
        fontName=regular,
        fontSize=8,
        fieldFlags=4096,
        forceBorder=True,
    )
    c.showPage()


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    regular, bold = register_fonts()

    source_map = {}
    for key, _ in TEMPLATES:
        source_map[key] = "PNG PREMIUM" if events.template_path(key, {}).is_file() else "FALLBACK PYTHON"

    c = canvas.Canvas(str(OUT), pagesize=A4, pageCompression=1)
    c.setTitle("MR XPRONOS - Validation des templates Actu Foot")
    c.setAuthor("MR XPRONOS")

    cover(c, regular, bold)
    summary_pages(c, regular, bold, source_map)

    with tempfile.TemporaryDirectory(prefix="mrx-validation-") as tmpdir:
        for idx, (key, label) in enumerate(TEMPLATES):
            template_page(c, regular, bold, idx, key, label, source_map[key], tmpdir)

    c.save()
    print("PDF_CREATED", OUT, OUT.stat().st_size)
    print("PREMIUM_COUNT", sum(v == "PNG PREMIUM" for v in source_map.values()))
    print("FALLBACK_COUNT", sum(v == "FALLBACK PYTHON" for v in source_map.values()))


if __name__ == "__main__":
    main()
