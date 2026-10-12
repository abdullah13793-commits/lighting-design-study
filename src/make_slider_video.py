"""Slider walkthrough video (what the interactive viewer does): render <-> illuminance wipe per scene.

python src/make_slider_video.py                       -> publish/slider_walkthrough.mp4       (1600x1200, Upwork)
python src/make_slider_video.py --size 1080x1350 --out publish/linkedin/lighting_slider_4x5.mp4   (LinkedIn feed)
"""
import argparse, json, math, subprocess
from pathlib import Path
import numpy as np
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FIG, REN, PUB = ROOT / "reports/figures", ROOT / "renders/final", ROOT / "publish"
R = json.load(open(ROOT / "results/results.json"))
FPS = 30
BG, INK, INK2, MUTED, LAMP = (18, 17, 16), (243, 239, 230), (185, 178, 163), (138, 132, 120), (242, 189, 85)


def font(sz, bold=False, serif=False):
    for n in (["georgia.ttf"] if serif else []) + (["segoeuib.ttf"] if bold else ["segoeui.ttf"]):
        try:
            return ImageFont.truetype(n, sz)
        except OSError:
            pass
    return ImageFont.load_default()


def wrap(d, text, f, width):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=f) <= width:
            cur = t
        else:
            lines.append(cur); cur = w_
    return lines + [cur] if cur else lines


class Layout:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.k = W / 1600 if W >= H else W / 1080          # type scale
        m = int(40 * self.k) if W >= H else 48
        if W >= H:                                          # landscape: stage centred, captions below
            sw, sh = int(W * 0.75), int(W * 0.75 * 0.725)
            self.stage = ((W - sw) // 2, int(150 * self.k), sw, sh)
        else:                                               # portrait 4:5: full-width 4:3 stage in the middle
            sw = W - 2 * m
            self.stage = (m, 250, sw, int(sw * 3 / 4))
        self.m = m


def load(p, L):
    _, _, w, h = L.stage
    im = Image.open(p).convert("RGB")
    s = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x0, y0 = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x0, y0, x0 + w, y0 + h))


def frame(L, base, top, cut, label, sub, kpi, step=None):
    W, H, k = L.W, L.H, L.k
    c = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(c)
    x, y, w, h = L.stage
    if W >= H:
        d.text((L.m, int(36 * k)), "Lighting Design Study", font=font(int(46 * k), serif=True), fill=INK)
        d.text((L.m + 2, int(98 * k)), "Drag between the render and the calibrated illuminance map",
               font=font(int(22 * k)), fill=LAMP)
    else:
        d.text((L.m, 56), "LIGHTING DESIGN STUDY", font=font(24, True), fill=LAMP)
        d.text((L.m, 92), "Render vs. measured light", font=font(58, serif=True), fill=INK)
        d.text((L.m + 2, 176), "Same room, same photometric files, calibrated to lux", font=font(26), fill=INK2)
    xc = int(w * cut)
    st = base.copy(); st.paste(top.crop((xc, 0, w, h)), (xc, 0))
    c.paste(st, (x, y))
    d.line([(x + xc, y), (x + xc, y + h)], fill=INK, width=3)
    r = int(24 * max(k, 1))
    cy = y + h // 2
    d.ellipse([x + xc - r, cy - r, x + xc + r, cy + r], fill=INK)
    a = int(r * 0.62)
    d.polygon([(x + xc - a, cy), (x + xc - a // 3, cy - a * 0.6), (x + xc - a // 3, cy + a * 0.6)], fill=BG)
    d.polygon([(x + xc + a, cy), (x + xc + a // 3, cy - a * 0.6), (x + xc + a // 3, cy + a * 0.6)], fill=BG)
    tag = font(int(18 * max(k, 1)), True)
    for txt, tx, anc in (("Render", x + 14, "lb"), ("Illuminance, lx", x + w - 14, "rb")):
        bb = d.textbbox((tx, y + h - 14), txt, font=tag, anchor=anc)
        d.rounded_rectangle([bb[0] - 8, bb[1] - 6, bb[2] + 8, bb[3] + 6], radius=6, fill=BG)
        d.text((tx, y + h - 14), txt, font=tag, fill=INK, anchor=anc)
    by = y + h + int(24 * max(k, 1))
    if W >= H:
        d.text((x, by), label, font=font(int(34 * k), True), fill=INK)
        d.text((x, by + int(48 * k)), sub, font=font(int(22 * k)), fill=INK2)
        d.text((x + w, by + int(6 * k)), kpi, font=font(int(26 * k)), fill=INK, anchor="ra")
        d.text((W - L.m, H - int(30 * k)), "demonstration project · Blender Cycles + Radiance-checked engine",
               font=font(int(17 * k)), fill=MUTED, anchor="rs")
    else:
        d.text((x, by + 10), label, font=font(48, True), fill=INK)
        d.text((x, by + 80), kpi, font=font(32), fill=LAMP)
        for i, line in enumerate(wrap(d, sub, font(26), w)[:2]):
            d.text((x, by + 140 + i * 36), line, font=font(26), fill=INK2)
        if step:
            n, tot = step
            for i in range(tot):
                cx_ = W // 2 + (i - (tot - 1) / 2) * 30
                d.ellipse([cx_ - 7, H - 112, cx_ + 7, H - 98], fill=LAMP if i == n else (70, 66, 60))
        d.text((W // 2, H - 52), "Abdallah Alhussein · MSc Eng, Architectural Engineering, DTU",
               font=font(22), fill=MUTED, anchor="ms")
    return c


def scene_info(sid):
    s = R["scenes"].get(sid)
    label = s["label"] if s else "Daytime (illustrative)"
    sub = s["desc"] if s else "Sun at 32°. The overcast-sky daylight factor is computed separately in Radiance."
    if s:
        z = s["zones"]
        kpi = f"{s['power_w']:.0f} W · table {z['dining_table']['E_avg']:.0f} lx · living {z['living']['E_avg']:.0f} lx"
    else:
        kpi = f"mean daylight factor {R['daylight']['DF_avg']:.1f} %"
    return label, sub, kpi


SCENES = ("full", "dinner", "calm", "day")


def ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="1600x1200")
    ap.add_argument("--out", default=str(PUB / "slider_walkthrough.mp4"))
    a = ap.parse_args()
    W, H = map(int, a.size.split("x"))
    L = Layout(W, H)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-preset", "slow",
           "-movflags", "+faststart", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    for n, sid in enumerate(SCENES):
        base, top = load(REN / f"B_{sid}.png", L), load(FIG / f"B_{sid}_illuminance_clean.png", L)
        label, sub, kpi = scene_info(sid)
        keys = [(0.9, 0.9, 0.5), (0.9, 0.12, 1.6), (0.12, 0.12, 0.8), (0.12, 0.55, 1.2), (0.55, 0.55, 0.7)]
        for a_, b_, dur in keys:
            m = int(dur * FPS)
            for i in range(m):
                cut = a_ + (b_ - a_) * ease(i / max(1, m - 1))
                p.stdin.write(np.asarray(frame(L, base, top, cut, label, sub, kpi, (n, len(SCENES)))).tobytes())
    p.stdin.close(); p.wait()
    print("video ->", out, round(out.stat().st_size / 1e6, 1), "MB")


if __name__ == "__main__":
    main()
