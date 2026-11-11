"""
desk_style.py — The Desk / Enelyst brand tokens for charts.

From the Enelyst / The Desk design system (built from the Feb 5, 2025 issue). Brand colors are exact
from the PDF; the chart-* colors were sampled from placed images and are still to be confirmed
against John's InDesign swatches. SURVEY_* colors are sampled from John's own survey chart (his
9 Nov 2026 email) and kept so the panel reads the same as his.

Charts for The Desk: one column wide (3.4 in), 300 dpi, white ground, Arial.
"""
import matplotlib.pyplot as plt

# brand (exact)
DESK_GREEN = "#6DB253"        # ribbons, rules
DESK_GREEN_FOLD = "#6D9042"   # ribbon fold
DESK_GREEN_TINT = "#C5E0BA"   # stat panels, title bands
DESK_GREEN_WASH = "#E2F0DD"   # data-page panels
INK = "#231F20"
PAPER = "#FFFFFF"

# charts (sampled — confirm with John)
CHART_EOS = "#EE7C2D"         # EOS estimate bars
CHART_HH = "#5E9AD1"          # Henry Hub price line
CHART_CUR = "#20285D"         # current year
CHART_PRIOR = "#6CA5D8"       # prior year
CHART_RANGE = "#A6A4A4"       # 5-yr range, reference lines

# survey panel (sampled from John's survey chart)
SURVEY_RED = "#C00000"        # week dates, average marker
GRID = "#E3E3E3"
MUTED = "#595959"

COLUMN_IN = 3.4               # one Desk column
DPI = 300


def use_desk_fonts():
    """Arial on John's and Merek's machines; Liberation Sans (metric-identical) elsewhere."""
    from matplotlib import font_manager
    have = {f.name for f in font_manager.fontManager.ttflist}
    fams = [f for f in ("Arial", "Liberation Sans", "Helvetica", "DejaVu Sans") if f in have]
    plt.rcParams["font.family"] = fams or ["sans-serif"]
    plt.rcParams["text.parse_math"] = False
    plt.rcParams["axes.edgecolor"] = INK
    plt.rcParams["text.color"] = INK


def ribbon(fig, x, y, w, h, label, fontsize=8.5):
    """Desk ribbon bar: desk-green band with a fold triangle under its left edge.
    Label in ink bold caps (the design system flags paper-on-green below 11 pt)."""
    from matplotlib.patches import Polygon, Rectangle
    fig.patches.append(Rectangle((x, y), w, h, transform=fig.transFigure, fc=DESK_GREEN, ec="none", zorder=-1))
    fw, fh = fig.get_size_inches()
    fold_w, fold_h = 0.06 / fw, 0.05 / fh
    fig.patches.append(Polygon([(x, y), (x + fold_w, y), (x + fold_w, y - fold_h)], closed=True,
                               transform=fig.transFigure, fc=DESK_GREEN_FOLD, ec="none", zorder=-1))
    fig.text(x + w / 2, y + h / 2, label.upper(), color=INK, fontsize=fontsize, fontweight="bold",
             ha="center", va="center")
