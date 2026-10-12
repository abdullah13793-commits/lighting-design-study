"""Cover image for the MSc thesis portfolio item (author's own figures).  -> publish/thesis/thesis_cover.jpg"""
import io
from pathlib import Path
import pymupdf
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
THESIS = Path(r"C:\Users\testt\Desktop\upwork\ai-job-search\attachment\Thesis_Alhussein_compressed.pdf")
OUT = ROOT / "publish/thesis"; OUT.mkdir(parents=True, exist_ok=True)
W, H, BG, INK, INK2, LAMP = 1600, 1200, (18, 17, 16), (243, 239, 230), (185, 178, 163), (242, 189, 85)


def font(sz, bold=False, serif=False):
    for n in (["georgia.ttf"] if serif else []) + (["segoeuib.ttf"] if bold else ["segoeui.ttf"]):
        try:
            return ImageFont.truetype(n, sz)
        except OSError:
            pass
    return ImageFont.load_default()


def biggest_image(doc, page):
    best = None
    for info in doc[page].get_images(full=True):
        pix = pymupdf.Pixmap(doc, info[0])
        if pix.n - pix.alpha >= 4:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        if best is None or pix.width * pix.height > best.width * best.height:
            best = pix
    if best is None:                      # vector figure: rasterise the page instead
        return Image.open(io.BytesIO(doc[page].get_pixmap(dpi=150).tobytes("png"))).convert("RGB")
    return Image.open(io.BytesIO(best.tobytes("png"))).convert("RGB")


def card(c, im, box, caption):
    x, y, w, h = box
    d = ImageDraw.Draw(c)
    d.rounded_rectangle([x, y, x + w, y + h], radius=14, fill=(250, 248, 243))
    s = min((w - 30) / im.width, (h - 70) / im.height)
    im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    c.paste(im, (x + (w - im.width) // 2, y + 15 + (h - 70 - im.height) // 2))
    d.text((x + 18, y + h - 42), caption, font=font(20, True), fill=(40, 38, 34))


doc = pymupdf.open(THESIS)
c = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(c)
d.text((56, 44), "MSc Thesis · DTU · Indoor Climate", font=font(22, True), fill=LAMP)
d.text((56, 78), "Light and indoor well-being of autistic adults", font=font(52, serif=True), fill=INK)
d.text((58, 150), "12-month field study in 13 Danish dwellings · sensor data + questionnaires · Random Forest, SHAP",
       font=font(23), fill=INK2)
card(c, biggest_image(doc, 38), (56, 210, 740, 560), "Illuminance vs light satisfaction, by season")
card(c, biggest_image(doc, 68), (812, 210, 732, 560), "SHAP summary: what drives satisfaction")
card(c, biggest_image(doc, 70), (56, 790, 740, 360), "ROC curve: satisfaction model, AUC 0.80")
x0 = 830
for i, (big, small) in enumerate([("79.6 %", "accuracy, light-satisfaction model"),
                                  ("<40 / 60-80 lx", "satisfied most in summer / preferred in winter"),
                                  ("0.20-0.30", "window-to-floor ratio linked to satisfaction")]):
    yy = 810 + i * 112
    d.text((x0, yy), big, font=font(46, serif=True), fill=INK)
    d.text((x0 + 4, yy + 58), small, font=font(20), fill=INK2)
d.text((W - 56, H - 26), "Abdallah Alhussein · MSc Eng, Architectural Engineering, DTU (2026)", font=font(18),
       fill=(138, 132, 120), anchor="rs")
c.save(OUT / "thesis_cover.jpg", quality=92)
print("->", OUT / "thesis_cover.jpg")
