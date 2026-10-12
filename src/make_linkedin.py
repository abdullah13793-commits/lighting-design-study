"""LinkedIn pack: swipeable PDF carousel (1080x1350 pages) + self-contained interactive HTML.

python src/make_linkedin.py -> publish/linkedin/Lighting_Study_carousel.pdf
                               publish/linkedin/Lighting_Study_interactive.html
"""
import base64, json, re
from pathlib import Path
from PIL import Image, ImageDraw

import make_slider_video as V

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "publish/linkedin"; OUT.mkdir(parents=True, exist_ok=True)
FIG, REN, R = V.FIG, V.REN, V.R
W, H = 1080, 1350
BG, INK, INK2, MUTED, LAMP = V.BG, V.INK, V.INK2, V.MUTED, V.LAMP
font = V.font


def page():
    c = Image.new("RGB", (W, H), BG)
    return c, ImageDraw.Draw(c)


def footer(d, n, tot):
    for i in range(tot):
        x = W // 2 + (i - (tot - 1) / 2) * 26
        d.ellipse([x - 6, H - 108, x + 6, H - 96], fill=LAMP if i == n else (70, 66, 60))
    d.text((W // 2, H - 52), "Abdallah Alhussein · MSc Eng, Architectural Engineering, DTU", font=font(22),
           fill=MUTED, anchor="ms")


def trim(im, pad=12):
    """Crop away the uniform background margin of a figure."""
    import numpy as np
    a = np.asarray(im.convert("RGB")).astype(int)
    m = (abs(a - a[2, 2]).sum(axis=2) > 24)
    ys, xs = np.where(m)
    if len(xs) == 0:
        return im
    return im.crop((max(0, xs.min() - pad), max(0, ys.min() - pad), min(im.width, xs.max() + pad), min(im.height, ys.max() + pad)))


def fit(im, w, h):
    s = min(w / im.width, h / im.height)
    return im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)


def carousel():
    pages = []
    tot = 9
    L = V.Layout(W, H)
    # 1 title
    c, d = page()
    d.text((48, 70), "LIGHTING DESIGN STUDY · DEMO PROJECT", font=font(24, True), fill=LAMP)
    for i, line in enumerate(["One room.", "Three lighting scenes.", "One set of numbers."]):
        d.text((48, 120 + i * 78), line, font=font(68, serif=True), fill=INK)
    hero = fit(Image.open(FIG / "B_full_split.png").convert("RGB"), W - 96, 640)
    c.paste(hero, ((W - hero.width) // 2, 390))
    y = 390 + hero.height + 40
    for i, line in enumerate(V.wrap(d, "The renders, the lux plans and the numbers come from the same photometric "
                                        "files. The renders are calibrated to lux, and the calculation is checked "
                                        "against Radiance.", font(30), W - 96)):
        d.text((48, y + i * 42), line, font=font(30), fill=INK2)
    d.text((W - 48, H - 140), "Swipe  →", font=font(34, True), fill=LAMP, anchor="rs")
    footer(d, 0, tot); pages.append(c)
    # 2-5 scenes: slider at mid position
    for n, sid in enumerate(V.SCENES):
        base = V.load(REN / f"B_{sid}.png", L)
        top = V.load(FIG / f"B_{sid}_illuminance_clean.png", L)
        label, sub, kpi = V.scene_info(sid)
        im = V.frame(L, base, top, 0.5, label, sub, kpi)
        d = ImageDraw.Draw(im)
        d.rectangle([0, H - 130, W, H], fill=BG)
        footer(d, n + 1, tot); pages.append(im)
    # 6 plans
    c, d = page()
    d.text((48, 70), "THE CALCULATION", font=font(24, True), fill=LAMP)
    d.text((48, 110), "Lux on the table, counter and sofa", font=font(54, serif=True), fill=INK)
    d.text((48, 190), "Maintained illuminance at 0.75 m: direct light plus all interreflections", font=font(26), fill=INK2)
    im = fit(trim(Image.open(FIG / "plan_full.png").convert("RGB")), W - 96, 700)
    c.paste(im, ((W - im.width) // 2, 250))
    y = 250 + im.height + 30
    zl = {"kitchen_counter": "Counter", "island": "Island", "dining_table": "Table", "living": "Living"}
    d.text((48, y), "lx", font=font(24, True), fill=MUTED)
    for j, z in enumerate(zl):
        d.text((330 + j * 175, y), zl[z], font=font(24, True), fill=MUTED)
    for i, sid in enumerate(("full", "dinner", "calm")):
        s = R["scenes"][sid]; yy = y + 44 + i * 50
        d.text((48, yy), s["label"], font=font(28), fill=INK)
        for j, z in enumerate(zl):
            d.text((330 + j * 175, yy), f"{s['zones'][z]['E_avg']:.0f}", font=font(28), fill=LAMP if sid != "full" else INK)
    footer(d, 5, tot); pages.append(c)
    # 7 solved scenes
    c, d = page()
    d.text((48, 70), "SCENES ARE SOLVED, NOT GUESSED", font=font(24, True), fill=LAMP)
    d.text((48, 110), "Dimming computed for targets", font=font(54, serif=True), fill=INK)
    y = 230
    names = {"kitchen_downlights": "Kitchen downlights", "living_downlights": "Living downlights",
             "pendants": "Pendants", "floor_lamp": "Uplighters", "under_cabinet": "Under-cabinet strip"}
    for sid in ("full", "dinner", "calm"):
        s = R["scenes"][sid]
        d.text((48, y), s["label"], font=font(36, True), fill=INK)
        d.text((W - 48, y + 6), f"{s['power_w']:.0f} W", font=font(32), fill=LAMP, anchor="ra")
        y += 62
        for g, v in s["dim"].items():
            d.text((48, y), names[g], font=font(24), fill=INK2)
            d.rounded_rectangle([380, y + 10, 940, y + 22], radius=6, fill=(46, 43, 39))
            if v > 0:
                d.rounded_rectangle([380, y + 10, 380 + int(560 * v), y + 22], radius=6, fill=LAMP)
            d.text((W - 48, y), f"{100 * v:.0f}%", font=font(24), fill=INK2, anchor="ra")
            y += 40
        y += 30
    for i, line in enumerate(V.wrap(d, "Light is linear in each circuit's dimming level, so a bounded least-squares "
                                        "fit finds the levels that hit each zone's target at the lowest power. The "
                                        "Sensory Calm band (40-80 lx) comes from my MSc field study.",
                                     font(26), W - 96)):
        d.text((48, y + i * 38), line, font=font(26), fill=INK2)
    footer(d, 6, tot); pages.append(c)
    # 8 validation
    v = R["validation"]
    c, d = page()
    d.text((48, 70), "VERIFIED", font=font(24, True), fill=LAMP)
    d.text((48, 110), "Checked against Radiance", font=font(54, serif=True), fill=INK)
    im = fit(trim(Image.open(FIG / "validation.png").convert("RGB")), W - 96, 560)
    c.paste(im, ((W - im.width) // 2, 220))
    y = 220 + im.height + 50
    xc = json.load(open(ROOT / "results/render_crosscheck.json"))
    diffs = [x["diff_pct"] for x in xc.values()]
    for i, (big, small) in enumerate([(f"{v['full']['mean_bias_pct']:+.1f} %", "bias vs Radiance (full scene)"),
                                      (f"{v['full']['direct_mape_pct']:.1f} %", "direct-light error"),
                                      ("14 / 14", "automated physics tests"),
                                      (f"+{min(diffs):.0f}-{max(diffs):.0f} %", "render vs engine (furniture + dusk sky)")]):
        x = 48 + (i % 2) * 500; yy = y + (i // 2) * 130
        d.text((x, yy), big, font=font(52, serif=True), fill=INK)
        d.text((x + 2, yy + 66), small, font=font(22), fill=INK2)
    footer(d, 7, tot); pages.append(c)
    # 9 closing
    c, d = page()
    d.text((48, 70), "WHAT YOU GET", font=font(24, True), fill=LAMP)
    d.text((48, 110), "For your floor plan", font=font(54, serif=True), fill=INK)
    items = ["Lux, uniformity and power for every zone", "Scenes solved for your targets",
             "Photoreal renders calibrated to the numbers", "Daylight factor study (optional)",
             "PDF report + interactive viewer", "Independent check in Radiance"]
    for i, t in enumerate(items):
        d.ellipse([52, 238 + i * 70, 68, 254 + i * 70], fill=LAMP)
        d.text((90, 228 + i * 70), t, font=font(32), fill=INK)
    im = fit(trim(Image.open(FIG / "daylight_df.png").convert("RGB")), W - 96, 420)
    c.paste(im, ((W - im.width) // 2, 680))
    d.text((48, 1150), "Demonstration project. Generic photometry, not a compliance certificate.", font=font(22), fill=MUTED)
    footer(d, 8, tot); pages.append(c)
    out = OUT / "Lighting_Study_carousel.pdf"
    pages[0].save(out, save_all=True, append_images=pages[1:], resolution=144, quality=90)
    for i, p in enumerate(pages):
        p.save(OUT / f"carousel_{i + 1:02d}.jpg", quality=90)
    return out


def standalone_html():
    """Viewer with every image inlined as data: URIs, so one file works offline and on any host."""
    src = (ROOT / "reports/viewer/index.html").read_text(encoding="utf-8")

    def inline(m):
        p = ROOT / "reports/viewer" / m.group(1)
        return '"data:image/jpeg;base64,' + base64.b64encode(p.read_bytes()).decode() + '"'
    body = re.sub(r'"(img/[^"]+\.jpg)"', inline, src)
    html = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '<style>html,body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n'
            + body.replace("<title>", "<title>", 1) + "\n</html>\n")
    out = OUT / "Lighting_Study_interactive.html"
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    p = carousel(); h = standalone_html()
    print(p, round(p.stat().st_size / 1e6, 1), "MB"); print(h, round(h.stat().st_size / 1e6, 1), "MB")
