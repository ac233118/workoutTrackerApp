"""
PDF generation service for workout reports.
Uses reportlab only — no external fonts needed.

Usage:
    from app.services.pdf_service import generate_workout_pdf
    buf = generate_workout_pdf(workout_doc)   # returns io.BytesIO
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.colors import HexColor

# ── Palette ───────────────────────────────────────────────────────────────────
C_BG         = colors.white
C_TEXT       = HexColor("#1a1a2e")
C_ACCENT     = HexColor("#6C63FF")
C_GOLD       = HexColor("#F5A623")
C_GRAY_BG    = HexColor("#F5F5F5")
C_BORDER     = HexColor("#E0E0E0")
C_LABEL_GRAY = HexColor("#888888")

# ── Page constants ────────────────────────────────────────────────────────────
PW, PH   = A4                        # 595.3 × 841.9 pt
MARGIN   = 20 * mm                   # 20 mm on each side
CONTENT_W = PW - 2 * MARGIN


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_date(dt: Optional[datetime]) -> str:
    if dt is None:
        return "Unknown date"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%A, %d %B %Y · %I:%M %p IST")


def _total_sets(exercises: list[dict]) -> int:
    return sum(len(ex.get("sets", [])) for ex in exercises)


def _total_volume(exercises: list[dict]) -> float:
    total = 0.0
    for ex in exercises:
        for s in ex.get("sets", []):
            total += (s.get("weight_kg") or 0) * (s.get("reps") or 0)
    return total


def _exercise_volume(ex: dict) -> float:
    return sum(
        (s.get("weight_kg") or 0) * (s.get("reps") or 0)
        for s in ex.get("sets", [])
    )


def _pr_set_idx(sets: list[dict]) -> int:
    """Return index of set with the highest weight (Personal Best marker)."""
    if not sets:
        return -1
    max_w = max((s.get("weight_kg") or 0) for s in sets)
    if max_w == 0:
        return -1
    for i, s in enumerate(sets):
        if (s.get("weight_kg") or 0) == max_w:
            return i
    return -1


def _rounded_rect(c: pdfcanvas.Canvas, x, y, w, h, r=4):
    """Draw a filled rounded rectangle."""
    c.roundRect(x, y, w, h, r, stroke=0, fill=1)


# ── Main generator ────────────────────────────────────────────────────────────

def generate_workout_pdf(workout: dict) -> io.BytesIO:
    """
    Generates a styled A4 PDF for a workout document.
    Returns an io.BytesIO buffer ready to be streamed.
    """
    buf = io.BytesIO()
    c   = pdfcanvas.Canvas(buf, pagesize=A4)
    c.setTitle(workout.get("title", "Workout Report"))

    exercises = sorted(
        workout.get("exercises", []),
        key=lambda e: e.get("order", 0),
    )

    y = PH - MARGIN   # cursor starts at top

    # ── HEADER ────────────────────────────────────────────────────────────────
    y = _draw_header(c, workout, y)

    # ── STATS ROW ─────────────────────────────────────────────────────────────
    y = _draw_stats(c, workout, exercises, y)

    # ── EXERCISES ─────────────────────────────────────────────────────────────
    y = _draw_exercises(c, exercises, y)

    # ── VOLUME CHART ──────────────────────────────────────────────────────────
    if exercises:
        y = _draw_volume_chart(c, exercises, y)

    # ── FOOTER ────────────────────────────────────────────────────────────────
    _draw_footer(c)

    c.save()
    buf.seek(0)
    return buf


# ── Section renderers ─────────────────────────────────────────────────────────

def _draw_header(c: pdfcanvas.Canvas, workout: dict, y: float) -> float:
    x = MARGIN

    # App name
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(C_ACCENT)
    c.drawString(x, y - 18, "WorkoutTracker")

    # Workout title
    y -= 36
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(C_TEXT)
    c.drawString(x, y, workout.get("title", "Workout"))

    # Date line
    y -= 20
    c.setFont("Helvetica", 10)
    c.setFillColor(C_LABEL_GRAY)
    c.drawString(x, y, _fmt_date(workout.get("date")))

    # Divider
    y -= 14
    c.setStrokeColor(C_BORDER)
    c.setLineWidth(0.8)
    c.line(x, y, PW - MARGIN, y)

    return y - 14


def _draw_stats(
    c: pdfcanvas.Canvas,
    workout: dict,
    exercises: list[dict],
    y: float,
) -> float:
    box_w    = (CONTENT_W - 12) / 3
    box_h    = 52
    x        = MARGIN
    gap      = 6

    duration = workout.get("duration_minutes")
    sets     = _total_sets(exercises)
    volume   = _total_volume(exercises)

    stats = [
        (f"{duration or '—'}", "min", "Duration"),
        (f"{sets}",            "sets", "Total sets"),
        (f"{int(volume):,}",  "kg",   "Total volume"),
    ]

    for i, (value, unit, label) in enumerate(stats):
        bx = x + i * (box_w + gap)
        by = y - box_h

        # Box background
        c.setFillColor(C_GRAY_BG)
        _rounded_rect(c, bx, by, box_w, box_h, r=6)

        # Value
        c.setFont("Helvetica-Bold", 18)
        c.setFillColor(C_TEXT)
        c.drawCentredString(bx + box_w / 2, by + box_h - 26, value)

        # Unit
        c.setFont("Helvetica", 10)
        c.setFillColor(C_ACCENT)
        c.drawCentredString(bx + box_w / 2, by + box_h - 38, unit)

        # Label
        c.setFont("Helvetica", 9)
        c.setFillColor(C_LABEL_GRAY)
        c.drawCentredString(bx + box_w / 2, by + 8, label)

    return y - box_h - 20


def _draw_exercises(
    c: pdfcanvas.Canvas,
    exercises: list[dict],
    y: float,
) -> float:
    x = MARGIN

    # Section header
    y -= 6
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(C_ACCENT)
    c.drawString(x, y, "EXERCISES")

    y -= 8
    c.setStrokeColor(C_BORDER)
    c.setLineWidth(0.5)
    c.line(x, y, PW - MARGIN, y)
    y -= 12

    for idx, ex in enumerate(exercises):
        name  = ex.get("exercise_name", ex.get("name", f"Exercise {idx+1}"))
        sets  = ex.get("sets", [])
        pr_i  = _pr_set_idx(sets)

        # Alternating row background
        row_h = 16 * (len(sets) + 1) + 10
        if idx % 2 == 0:
            c.setFillColor(C_GRAY_BG)
            c.rect(x - 4, y - row_h + 6, CONTENT_W + 8, row_h, stroke=0, fill=1)

        # Exercise name
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(C_TEXT)
        c.drawString(x, y, f"{idx + 1}.  {name}")
        y -= 16

        # Sets
        for si, s in enumerate(sets):
            w    = s.get("weight_kg")
            r    = s.get("reps")
            dur  = s.get("duration_sec")
            is_pr = si == pr_i

            if w and r:
                line = f"    Set {si + 1}:  {w} kg × {r} reps"
            elif dur:
                line = f"    Set {si + 1}:  {dur} sec"
            else:
                line = f"    Set {si + 1}"

            c.setFont("Helvetica", 10)
            c.setFillColor(C_TEXT)
            c.drawString(x + 10, y, line)

            if is_pr:
                # Gold PR badge
                line_w = c.stringWidth(line, "Helvetica", 10)
                c.setFont("Helvetica-Bold", 9)
                c.setFillColor(C_GOLD)
                c.drawString(x + 10 + line_w + 6, y, "★  Personal Best")

            y -= 15

        y -= 8

        # Page overflow guard — add new page if running out of space
        if y < MARGIN + 80:
            c.showPage()
            y = PH - MARGIN

    return y - 8


def _draw_volume_chart(
    c: pdfcanvas.Canvas,
    exercises: list[dict],
    y: float,
) -> float:
    x = MARGIN

    # Check we have enough room; otherwise start a new page
    needed = 30 + len(exercises) * 26 + 20
    if y - needed < MARGIN + 40:
        c.showPage()
        y = PH - MARGIN

    # Section header
    y -= 6
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(C_ACCENT)
    c.drawString(x, y, "VOLUME BY EXERCISE")

    y -= 8
    c.setStrokeColor(C_BORDER)
    c.setLineWidth(0.5)
    c.line(x, y, PW - MARGIN, y)
    y -= 16

    volumes = [(ex.get("exercise_name", "?"), _exercise_volume(ex)) for ex in exercises]
    max_vol = max((v for _, v in volumes), default=1) or 1

    label_w  = 110          # space for exercise name on the left
    val_w    = 42           # space for the volume number on the right
    bar_area = CONTENT_W - label_w - val_w - 8
    bar_h    = 14

    for name, vol in volumes:
        bar_len = max(4, (vol / max_vol) * bar_area)

        # Exercise label
        c.setFont("Helvetica", 9)
        c.setFillColor(C_TEXT)
        # Truncate long names
        short = name if len(name) <= 18 else name[:16] + "…"
        c.drawRightString(x + label_w, y + 3, short)

        # Bar
        c.setFillColor(C_ACCENT)
        _rounded_rect(c, x + label_w + 4, y, bar_len, bar_h, r=3)

        # Volume value
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(C_TEXT)
        c.drawString(x + label_w + 4 + bar_len + 5, y + 3, f"{int(vol):,} kg")

        y -= 24

    return y - 8


def _draw_footer(c: pdfcanvas.Canvas) -> None:
    today  = datetime.now().strftime("%d %B %Y")
    text   = f"Generated by WorkoutTracker  ·  workouttracker.app  ·  {today}"
    y      = MARGIN - 6

    c.setStrokeColor(C_BORDER)
    c.setLineWidth(0.5)
    c.line(MARGIN, y + 14, PW - MARGIN, y + 14)

    c.setFont("Helvetica", 8)
    c.setFillColor(C_LABEL_GRAY)
    c.drawCentredString(PW / 2, y, text)
