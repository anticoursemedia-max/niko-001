#!/usr/bin/env python3
"""Выкройка закрытых кожаных шлёпанцев (slide, цельный верх с вырезами) в масштабе 1:1.
Запуск: python3 make_pattern.py --foot 27.0   (длина стопы в см)
Результат: pattern_<длина>cm.pdf — A4, склеивается из листов.
"""
import argparse, math
import numpy as np
from shapely.geometry import Polygon, LineString, Point, box
from shapely.ops import unary_union
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont("DV", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DVB", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))

ap = argparse.ArgumentParser()
ap.add_argument("--foot", type=float, default=27.0, help="длина стопы, см")
ap.add_argument("--out", default=None)
a = ap.parse_args()
F = a.foot
LS = F + 1.5            # длина подошвы (запас под носок 1.5 см)
ALLOW = 1.0             # припуск на затяжку под стельку, см
y0f = 0.30              # где начинается верх (доля длины от пятки)

# ---------- подошва / стелька (правая нога, вид сверху, +x = внутренняя сторона) ----------
pts = [(0, 0), (0.07, .01), (0.105, .06), (0.105, .14), (0.09, .26), (0.095, .40), (0.13, .55),
       (0.17, .66), (0.19, .74), (0.18, .84), (0.13, .94), (0.06, .99), (-0.04, .985),
       (-0.12, .94), (-0.17, .86), (-0.19, .74), (-0.185, .70), (-0.17, .55), (-0.14, .40),
       (-0.125, .26), (-0.115, .14), (-0.105, .06), (-0.07, .01)]
P = np.array([(x * LS, y * LS) for x, y in pts])

def catmull_closed(P, n=24):
    out = []
    N = len(P)
    for i in range(N):
        p0, p1, p2, p3 = P[(i - 1) % N], P[i], P[(i + 1) % N], P[(i + 2) % N]
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    return np.array(out)

sole = Polygon(catmull_closed(P)).buffer(0)

def width_at(y):
    ln = LineString([(-50, y), (50, y)]).intersection(sole)
    xs = [c[0] for c in ln.coords]
    return min(xs), max(xs)

# ---------- верх: развёртка по сечениям ----------
prof = [(0.30, .185), (0.40, .195), (0.50, .185), (0.62, .15), (0.74, .11), (0.86, .085), (0.95, .05), (1.0, .0)]
py = np.array([p[0] for p in prof]) * LS
ph = np.array([p[1] for p in prof]) * LS
ys = np.linspace(y0f * LS, LS * 0.975, 400)
hs = np.interp(ys, py, ph)
ws = []
for y in ys:
    try:
        lo, hi = width_at(y); ws.append(hi - lo)
    except Exception:
        ws.append(0.0)
ws = np.array(ws)
s = np.concatenate([[0], np.cumsum(np.hypot(np.diff(ys), np.diff(hs)))])
A, B = ws / 2, hs
arc = 0.5 * math.pi * (3 * (A + B) - np.sqrt((3 * A + B) * (A + 3 * B)))   # длина дуги сечения поперёк
arc = np.maximum(arc, ws)
half = arc / 2

# длина боковой кромки: развёртка vs. подошва (для контроля посадки)
edge_flat = np.sum(np.hypot(np.diff(half), np.diff(s)))
lat = np.array([width_at(y)[0] for y in ys]); med = np.array([width_at(y)[1] for y in ys])
edge_sole = (np.sum(np.hypot(np.diff(lat), np.diff(ys))) + np.sum(np.hypot(np.diff(med), np.diff(ys)))) / 2
print(f"кромка верха {edge_flat:.1f} см, кромка подошвы {edge_sole:.1f} см, соотношение {edge_flat/edge_sole:.3f}")

REAR_EXT = 2.0
Lp = [(-half[0], -REAR_EXT)] + [(-h, v) for h, v in zip(half, s)]
Rp = [(half[0], -REAR_EXT)] + [(h, v) for h, v in zip(half, s)]
# носок: сходим к точке
S_END = s[-1]
toe = [(-half[-1], S_END), (0, S_END + 0.6), (half[-1], S_END)]
fold_pts = Lp + toe[1:2] + Rp[::-1]
fold = Polygon(fold_pts).buffer(0)

A0 = half[0]
def rear(x):
    x = abs(x)
    return -1.5 * (x / A0) ** 2 + 3.4 * max(0.0, 1 - x / 2.5) ** 1.5
xs_ = np.linspace(-A0 - 3, A0 + 3, 400)
clip = Polygon([(x, rear(x)) for x in xs_] + [(A0 + 3, 60), (-A0 - 3, 60)])

def edge_x(sv):
    return float(np.interp(sv, s, half))

# вырезы по бортам: (центр по s, ширина, высота)
cut_specs = [(S_END * 0.30, 3.4, 2.4), (S_END * 0.55, 4.4, 2.2), (S_END * 0.82, 3.2, 1.7)]
cuts = []
for sc, cw, ch in cut_specs:
    for side in (-1, 1):
        pts_c = []
        for t in np.linspace(0, math.pi, 30):
            sv = sc + cw / 2 * math.cos(t)
            pts_c.append((side * (edge_x(sv) - ch * math.sin(t)), sv))
        sv_e, sv_s = sc - cw / 2, sc + cw / 2
        pts_c += [(side * (edge_x(sv_e) + 2.5), sv_e), (side * (edge_x(sv_s) + 2.5), sv_s)]
        cuts.append(Polygon(pts_c).buffer(0))
cutU = unary_union(cuts)

upper_cut = fold.buffer(ALLOW).intersection(clip).difference(cutU)
upper_cut = max(upper_cut.geoms, key=lambda g: g.area) if upper_cut.geom_type == "MultiPolygon" else upper_cut

# отверстия под обмётку
hole_pts = []
def sample(ring, step=0.7):
    L = ring.length
    return [ring.interpolate(d) for d in np.arange(0, L, step)]
inner = fold.buffer(-0.45)
for p in sample(inner.exterior):
    if p.y > 0.2 and not cutU.buffer(0.2).contains(p) and clip.contains(p):
        hole_pts.append((p.x, p.y))
for c in cuts:
    ring = c.buffer(0.45).exterior
    for p in sample(ring, 0.6):
        if fold.buffer(-0.2).contains(p) and not c.contains(p) and clip.contains(p) and p.y > 0.2:
            hole_pts.append((p.x, p.y))

# ---------- метки (надсечки) на кромках: 25/50/75 % ----------
def frac_points(xy, fracs=(0.25, 0.5, 0.75)):
    ln = LineString(xy)
    return [ln.interpolate(f, normalized=True) for f in fracs]
sole_edge_m = [(width_at(y)[1], y) for y in ys]
sole_edge_l = [(width_at(y)[0], y) for y in ys]
sole_marks = frac_points(sole_edge_m) + frac_points(sole_edge_l)
up_marks = frac_points([(h, v) for h, v in zip(half, s)]) + frac_points([(-h, v) for h, v in zip(half, s)])

# ---------- вывод в PDF ----------
PW, PH, MG, OVL = 21.0, 29.7, 1.0, 1.0
minx, miny, maxx, maxy = upper_cut.bounds
sx0, sy0, sx1, sy1 = sole.bounds
GAP = 1.5
SOLE_OX, SOLE_OY = 1.0 - sx0, 1.0 - sy0
UP_OX = (PW - 2 * 1.0 - 1.0) + 1.4 - minx  # верх целиком на колонке 2
UP_OY = 1.0 - miny + 0.5
W_TOT = UP_OX + maxx + 1.0
H_TOT = max(SOLE_OY + sy1, UP_OY + maxy) + 1.5

TW, TH = PW - 2 * MG, PH - 2 * MG
STEP_X, STEP_Y = TW - OVL, TH - OVL
nx = max(1, math.ceil((W_TOT - OVL) / STEP_X)); ny = max(1, math.ceil((H_TOT - OVL) / STEP_Y))

out = a.out or f"pattern_{F:g}cm.pdf"
c = canvas.Canvas(out, pagesize=(PW * cm, PH * cm))

def poly_path(cv, pg, ox, oy):
    p = cv.beginPath()
    rings = [pg.exterior] + list(pg.interiors)
    for r in rings:
        co = list(r.coords)
        p.moveTo((co[0][0] + ox) * cm, (co[0][1] + oy) * cm)
        for x, y in co[1:]:
            p.lineTo((x + ox) * cm, (y + oy) * cm)
        p.close()
    return p

def draw_geometry(cv):
    cv.setLineWidth(0.9); cv.setStrokeColorRGB(0, 0, 0)
    cv.drawPath(poly_path(cv, sole, SOLE_OX, SOLE_OY), stroke=1, fill=0)
    # ось подошвы
    cv.setDash(6, 3); cv.setLineWidth(0.4)
    cv.line(SOLE_OX * cm, (SOLE_OY - .3) * cm, SOLE_OX * cm, (SOLE_OY + LS + .3) * cm)
    cv.setDash()
    cv.setLineWidth(0.5)
    ang_y = SOLE_OY + y0f * LS
    cv.setDash(2, 2); cv.line((SOLE_OX - 0.2 * LS) * cm, ang_y * cm, (SOLE_OX + 0.2 * LS) * cm, ang_y * cm); cv.setDash()
    cv.setFont("DV", 7)
    cv.drawString((SOLE_OX - 0.19 * LS) * cm, (ang_y + .15) * cm, "начало верха")
    for i, m in enumerate(sole_marks):
        n = (i % 3) + 1
        sgn = 1 if i < 3 else -1
        cv.line((m.x + SOLE_OX) * cm, (m.y + SOLE_OY) * cm, (m.x + SOLE_OX + sgn * 0.5) * cm, (m.y + SOLE_OY) * cm)
        cv.drawString((m.x + SOLE_OX + sgn * 0.6 - (0.3 if sgn < 0 else 0)) * cm, (m.y + SOLE_OY - .1) * cm, str(n))
    cv.setFont("DVB", 10)
    cv.drawCentredString(SOLE_OX * cm, (SOLE_OY + 0.30 * LS) * cm - 2 * cm if False else (SOLE_OY + .08 * LS) * cm,
                         "СТЕЛЬКА / ПОДОШВА")
    cv.setFont("DV", 8)
    cv.drawCentredString(SOLE_OX * cm, (SOLE_OY + .08 * LS) * cm - 0.5 * cm, "правая нога · для левой — зеркально")
    cv.drawCentredString(SOLE_OX * cm, (SOLE_OY + .08 * LS) * cm - 1.0 * cm, "кроить: стелька ×2 (пара), подошва ×2")
    # верх
    cv.setLineWidth(0.9)
    cv.drawPath(poly_path(cv, upper_cut, UP_OX, UP_OY), stroke=1, fill=0)
    cv.setLineWidth(0.5); cv.setDash(5, 2)
    cv.setStrokeColorRGB(.2, .2, .8)
    cv.drawPath(poly_path(cv, fold.intersection(clip), UP_OX, UP_OY), stroke=1, fill=0)
    cv.setDash(); cv.setStrokeColorRGB(0, 0, 0)
    cv.setDash(8, 3, ); cv.line(UP_OX * cm, (UP_OY - 1.5) * cm, UP_OX * cm, (UP_OY + S_END + 0.8) * cm); cv.setDash()
    cv.setLineWidth(0.4)
    for x, y in hole_pts:
        cv.circle((x + UP_OX) * cm, (y + UP_OY) * cm, 0.6, stroke=1, fill=0)
    cv.setFont("DV", 7)
    for i, m in enumerate(up_marks):
        n = (i % 3) + 1
        sgn = 1 if i < 3 else -1
        cv.line((m.x + UP_OX) * cm, (m.y + UP_OY) * cm, (m.x + UP_OX - sgn * 0.5) * cm, (m.y + UP_OY) * cm)
        cv.drawString((m.x + UP_OX - sgn * 0.6 - (0.3 if sgn > 0 else 0)) * cm, (m.y + UP_OY - .1) * cm, str(n))
    cv.setFont("DVB", 10)
    cv.drawCentredString(UP_OX * cm, (UP_OY + S_END * 0.42) * cm, "ВЕРХ")
    cv.setFont("DV", 8)
    cv.drawCentredString(UP_OX * cm, (UP_OY + S_END * 0.42) * cm - 0.5 * cm, "кроить ×2 (симметричная деталь,")
    cv.drawCentredString(UP_OX * cm, (UP_OY + S_END * 0.42) * cm - 0.95 * cm, "подходит на левую и правую)")
    cv.drawCentredString(UP_OX * cm, (UP_OY + S_END * 0.42) * cm - 1.4 * cm, "пунктир синий — линия сгиба / края стельки")
    cv.drawCentredString(UP_OX * cm, (UP_OY + S_END * 0.42) * cm - 1.85 * cm, "кружки — отверстия под обмётку")
    cv.setFont("DV", 7)
    cv.drawString((UP_OX + 0.3) * cm, (UP_OY - 1.3) * cm, "центр спинки")
    cv.drawString((UP_OX + 0.3) * cm, (UP_OY + S_END - 0.2) * cm, "центр носка")

# --- стр. 1: инструкция ---
def instr():
    c.setFont("DVB", 15); c.drawString(2 * cm, 27.8 * cm, "Выкройка кожаных шлёпанцев (закрытый носок, вырезы)")
    c.setFont("DV", 9)
    lines = [
        f"Размер: длина стопы {F:g} см (≈ EU {round((F + 1.5) * 1.5, 1):g}). Подошва длиннее стопы на 1,5 см (запас под носок).",
        "Для другой длины стопы: python3 make_pattern.py --foot <см>.",
        "",
        "ПЕЧАТЬ",
        "1. Печатайте в масштабе 100 % (без «по размеру страницы»). Проверьте квадрат 5×5 см ниже.",
        f"2. Страниц с деталями: {sum(exists.values())} (номер «ряд-колонка» в углу; перекрытие 1 см — склеивайте по рамке).",
        "3. Обрежьте поля и склейте листы по меткам-уголкам по перекрытию, вырежьте детали.",
        "",
        "МАТЕРИАЛЫ",
        "• Верх: кожа растительного дубления (краст/«вегтан») 1,8–2,2 мм, ~ 30×40 см на пару.",
        "• Стелька: пробка 3–4 мм + кожа/замша сверху (или готовая пробковая стелька, подрезать по выкройке).",
        "• Подошва: резина-крепёж/кожа 4–5 мм (или готовый лист «резина-профиль»).",
        "• Клей контактный (типа «Момент»/Barge), вощёный шнур 1–1,5 мм или кожаный ремешок 2 мм для обмётки,",
        "  шило, дырокол Ø1,5–2 мм, нож/скальпель, молоток, игла с тупым концом.",
        "",
        "СБОРКА",
        "1. Вырежьте 2 верха, 2 стельки (зеркально: правая и левая), 2 подошвы (зеркально).",
        "2. Верх: вырежьте вырезы по бортам, пробейте отверстия под обмётку (кружки на выкройке).",
        "3. Сложите кожу верха пополам по ходу стопы и смочите до мягкости (рекомендуется), затем придайте форму",
        "   на колодке/на ноге в плёнке: центр спинки верха = центр стельки, метки 1-2-3 на кромках совпадают.",
        "4. Сначала приклейте кромку верха к стельке с припуском 1 см загнутым под стельку (технология «моккасин»):",
        "   вдоль кромок между вырезами; в вырезах припуск не нужен — там видна стелька.",
        "5. Подошву приклейте снизу (контактный клей, прижать молотком/прессом), срежьте излишки по контуру.",
        "6. Обмётка: прошивка через отверстия вдоль кромки верха и вокруг вырезов вощёным шнуром (шов «через край»).",
        "7. Сушите шлёпанцы 24 часа, укрепите края воском или краской для кожи.",
        "",
        "ЗАМЕТКИ",
        "• Верх — развёртка сечений по вашему размеру: после намокания растягивается/формуется до ±2 см, поэтому",
        "  примерьте на стопе перед тем, как окончательно приклеить к стельке. Лучше сначала сделать пробу из картона/ткани.",
        f"• Контроль: кромка верха {edge_flat:.1f} см, кромка подошвы {edge_sole:.1f} см (посадка {edge_flat/edge_sole:.2f}).",
    ]
    from reportlab.lib.utils import simpleSplit
    merged = []
    for ln in lines:
        if merged and ln and (ln.startswith("  ") or ln[0].islower()) and merged[-1]:
            merged[-1] += " " + ln.strip()
        else:
            merged.append(ln)
    lines = merged
    y = 26.9
    for ln in lines:
        fn = "DVB" if ln.isupper() and ln else "DV"
        c.setFont(fn, 9)
        for part in (simpleSplit(ln, fn, 9, 17 * cm) or [""]):
            c.drawString(2 * cm, y * cm, part); y -= 0.45
        y -= 0.1
    c.setStrokeColorRGB(0, 0, 0); c.setLineWidth(0.8)
    c.rect(2 * cm, 1.2 * cm, 5 * cm, 5 * cm)
    c.setFont("DV", 8); c.drawString(7.5 * cm, 3.5 * cm, "Квадрат 5×5 см — проверка масштаба 100 %")
    c.showPage()

geom = unary_union([Polygon(np.array(sole.exterior.coords) + [SOLE_OX, SOLE_OY]),
                    Polygon(np.array(upper_cut.exterior.coords) + [UP_OX, UP_OY])])
def tile_box(r, col):
    return box(col * STEP_X, (ny - 1 - r) * STEP_Y, col * STEP_X + TW, (ny - 1 - r) * STEP_Y + TH)
exists = {(r, col): tile_box(r, col).intersection(geom).area > 0.5 for r in range(ny) for col in range(nx)}
def ex(r, col): return exists.get((r, col), False)
instr()
for r in range(ny):
    for col in range(nx):
        # ряд 1 — верхний
        ox = col * STEP_X
        oy = H_TOT - (r + 1) * STEP_Y - OVL if False else (ny - 1 - r) * STEP_Y
        if not exists[(r, col)]:
            continue
        c.saveState()
        c.translate(MG * cm, MG * cm)
        p = c.beginPath(); p.rect(0, 0, TW * cm, TH * cm); c.clipPath(p, stroke=0, fill=0)
        c.translate(-ox * cm, -oy * cm)
        draw_geometry(c)
        c.restoreState()
        # рамка и метки
        c.setLineWidth(0.3); c.setStrokeColorRGB(.5, .5, .5)
        c.rect(MG * cm, MG * cm, TW * cm, TH * cm)
        c.setFont("DVB", 11); c.setFillColorRGB(0, 0, 0)
        c.drawString((MG + .3) * cm, (PH - MG - .6) * cm, f"{r + 1}-{col + 1}")
        c.setFont("DV", 6)
        if ex(r, col + 1): c.drawRightString((PW - MG - .3) * cm, (PH / 2) * cm, f"→ {r + 1}-{col + 2}")
        if ex(r, col - 1): c.drawString((MG + .3) * cm, (PH / 2) * cm, f"← {r + 1}-{col}")
        if ex(r + 1, col): c.drawCentredString(PW / 2 * cm, (MG + .3) * cm, f"↓ {r + 2}-{col + 1}")
        if ex(r - 1, col): c.drawCentredString(PW / 2 * cm, (PH - MG - .5) * cm, f"↑ {r}-{col + 1}")
        c.showPage()
c.save()
print(out, f"{nx}x{ny} листов + инструкция; полотно {W_TOT:.1f}×{H_TOT:.1f} см")
