"""Upwork publish pack: 1600x1200 (4:3) cover + gallery images, JPEG.  python src/make_publish.py"""
import json, shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FIG, REN, PUB = ROOT / "reports/figures", ROOT / "renders/final", ROOT / "publish"
PUB.mkdir(exist_ok=True)
R = json.load(open(ROOT / "results/results.json"))
W, H, BG, INK, INK2, LAMP = 1600, 1200, (18, 17, 16), (243, 239, 230), (185, 178, 163), (242, 189, 85)


def font(sz, bold=False, serif=False):
    names = (["georgia.ttf"] if serif else []) + (["segoeuib.ttf"] if bold else ["segoeui.ttf"]) + ["arial.ttf"]
    for n in names:
        try:
            return ImageFont.truetype(n, sz)
        except OSError:
            pass
    return ImageFont.load_default()


def fit(im, w, h):
    """Scale to fit inside w x h (no crop)."""
    s = min(w / im.width, h / im.height)
    return im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)


def canvas(title, sub):
    c = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(c)
    d.text((56, 44), title, font=font(46, serif=True), fill=INK)
    d.text((58, 104), sub, font=font(22), fill=INK2)
    d.text((W - 56, H - 40), "Lighting Design Study · demonstration project", font=font(18), fill=(138, 132, 120), anchor="rs")
    return c, d


def place(c, im, box):
    x, y, w, h = box
    im = fit(im, w, h)
    c.paste(im, (x + (w - im.width) // 2, y + (h - im.height) // 2))


# 1 cover: split render (crop to 4:3, add a quiet title band)
cov = Image.open(FIG / "B_full_split.png").convert("RGB")
cov = cov.resize((W, round(cov.height * W / cov.width)), Image.LANCZOS).crop((0, 0, W, H))
d = ImageDraw.Draw(cov, "RGBA")
d.rounded_rectangle([40, 36, 760, 176], radius=14, fill=(18, 17, 16, 215))
d.text((64, 52), "Lighting Design Study", font=font(46, serif=True), fill=INK)
d.text((66, 116), "Calibrated renders · Radiance-checked lux · solved scenes", font=font(22), fill=LAMP)
cov.save(PUB / "cover.jpg", quality=92)

# 2 scenes grid
c, d = canvas("Three scenes, same room", "Cook & Gather · Dinner · Sensory Calm, plus an illustrative daytime view")
labels = {"full": f"Cook & Gather · {R['scenes']['full']['power_w']:.0f} W", "dinner": f"Dinner · {R['scenes']['dinner']['power_w']:.0f} W (solved)",
          "calm": f"Sensory Calm · {R['scenes']['calm']['power_w']:.0f} W (solved)", "day": "Daytime · illustrative"}
for i, sid in enumerate(("full", "dinner", "calm", "day")):
    p = REN / f"B_{sid}.png"
    if not p.exists():
        continue
    im = fit(Image.open(p).convert("RGB"), 700, 470)
    x, y = (W - 2 * im.width - 24) // 2 + (i % 2) * (im.width + 24), 160 + (i // 2) * (im.height + 20)
    c.paste(im, (x, y))
    d.rounded_rectangle([x + 12, y + im.height - 50, x + 12 + 20 + d.textlength(labels[sid], font=font(20, True)), y + im.height - 14],
                        radius=8, fill=BG)
    d.text((x + 22, y + im.height - 46), labels[sid], font=font(20, True), fill=INK)
c.save(PUB / "02_scenes.jpg", quality=90)

# 3 lux plans
c, d = canvas("Lux on the workplane, per scene", "Maintained illuminance at 0.75 m · zone averages · lighting power")
place(c, Image.open(FIG / "scenes_compare.png").convert("RGB"), (40, 170, W - 80, 560))
place(c, Image.open(FIG / "photometry.png").convert("RGB"), (120, 760, W - 240, 380))
c.save(PUB / "03_lux_plans.jpg", quality=90)

# 4 luminance
c, d = canvas("Luminance from the calibrated render", "cd/m², read from the linear EXR · same IES files as the calculation")
place(c, Image.open(FIG / "B_full_luminance.png").convert("RGB"), (56, 160, W - 112, H - 220))
c.save(PUB / "04_luminance.jpg", quality=90)

# 5 validation
v = R["validation"]
c, d = canvas("Checked against Radiance 6.0", f"Full scene bias {v['full']['mean_bias_pct']:+.1f} % · direct light {v['full']['direct_mape_pct']:.1f} % · "
              f"Calm scene {v['calm']['mean_bias_pct']:+.1f} % · 14/14 automated tests")
place(c, Image.open(FIG / "validation.png").convert("RGB"), (40, 170, W - 80, H - 240))
c.save(PUB / "05_validation.jpg", quality=90)

# 6 daylight
dl = R["daylight"]
c, d = canvas("Daylight factor, CIE overcast sky", f"Mean {dl['DF_avg']:.1f} % · median {dl['DF_median']:.1f} % · window/floor {dl['window_to_floor']:.2f}")
place(c, Image.open(FIG / "daylight_df.png").convert("RGB"), (56, 160, W - 112, H - 220))
c.save(PUB / "06_daylight.jpg", quality=90)

pdf = ROOT / "reports/Lighting_Design_Study.pdf"
if pdf.exists():
    shutil.copy(pdf, PUB / pdf.name)
print("publish pack ->", sorted(p.name for p in PUB.iterdir()))
