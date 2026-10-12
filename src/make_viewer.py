"""Interactive study viewer (single HTML page + image files) for the portfolio.

python src/make_viewer.py  -> reports/viewer/index.html, reports/viewer/img/*.jpg
"""
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
R = json.load(open(ROOT / "results/results.json"))
XC = json.load(open(ROOT / "results/render_crosscheck.json")) if (ROOT / "results/render_crosscheck.json").exists() else {}
OUT = ROOT / "reports/viewer"; (OUT / "img").mkdir(parents=True, exist_ok=True)
FIG, REN = ROOT / "reports/figures", ROOT / "renders/final"


def jpg(src, name, w=1440):
    src = Path(src)
    if not src.exists():
        return None
    im = Image.open(src).convert("RGB")
    if im.width > w:
        im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    im.save(OUT / "img" / name, quality=86, optimize=True, progressive=True)
    return f"img/{name}"


scenes = []
for sid in ("full", "dinner", "calm", "day"):
    s = R["scenes"].get(sid)
    scenes.append(dict(
        id=sid, label=s["label"] if s else "Daytime", desc=s["desc"] if s else "Illustrative daylight render, sun at 32°.",
        render=jpg(REN / f"B_{sid}.png", f"B_{sid}.jpg"),
        map=jpg(FIG / f"B_{sid}_illuminance.png", f"B_{sid}_E.jpg"),
        lum=jpg(FIG / f"B_{sid}_luminance.png", f"B_{sid}_L.jpg"),
        power=s["power_w"] if s else 0, lpd=s["lpd_w_m2"] if s else 0,
        dim=s["dim"] if s else {}, zones=s["zones"] if s else {},
        grid=s["floor_grid"]["E"] if s else None, solved=s.get("solved") if s else None))
jpg(FIG / "validation.png", "validation.jpg", 1600)
jpg(FIG / "daylight_df.png", "daylight.jpg", 1400)

data = dict(scenes=scenes, room=R["room"]["size"], window=R["room"]["window"], grid=R["grid"],
            luminaires=R["luminaires"], zones=R["zones_def"], validation={
                k: {kk: vv for kk, vv in v.items() if not isinstance(vv, list)} for k, v in R.get("validation", {}).items()},
            daylight={k: v for k, v in R.get("daylight", {}).items() if not isinstance(v, list)},
            crosscheck=XC, mf=R["room"]["maintenance_factor"], patches=R["engine"]["patches"])

tpl = (ROOT / "src/viewer_template.html").read_text(encoding="utf-8")
(OUT / "index.html").write_text(tpl.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":"))), encoding="utf-8")
print("viewer ->", OUT / "index.html")
