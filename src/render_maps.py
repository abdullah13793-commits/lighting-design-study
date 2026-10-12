"""Turn calibrated Cycles EXRs into photometric images.

  luminance   L [cd/m2] = 683 * Y(Combined)
  illuminance E [lx]    = 683 * pi * Y(Diffuse Direct + Diffuse Indirect)

Y uses Rec.709 weights (the scene-linear space of the render). Also writes a
split "render | false colour" image and checks the render-derived table-top
illuminance against the engine.

python src/render_maps.py renders/final B_full B_dinner B_calm ...
"""
import json, math, sys
from pathlib import Path
import numpy as np
import OpenEXR
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import median_filter, gaussian_filter

sys.path.insert(0, str(Path(__file__).parent))
from make_figures import LUX, SURF, INK, INK2, MUTED, R, ROOT

Y709 = np.array([0.2126, 0.7152, 0.0722])
CAMS = json.load(open(ROOT / "config/cameras.json"))


def read_exr(path):
    f = OpenEXR.File(str(path), separate_channels=True)
    out = {}
    for p in f.parts:
        ch = p.channels
        name = p.name().split(".", 1)[1]
        rgb = [ch[k].pixels for k in sorted(ch) if k[-1] in "RGB"]
        # sorted keys -> B, G, R
        out[name] = np.dstack([rgb[2], rgb[1], rgb[0]]).astype(np.float64)
    return out


def project(cam, pts, w, h):
    """World points -> pixel coords for the level Blender camera in config/cameras.json."""
    loc, tgt = np.array(cam["loc"]), np.array(cam["target"])
    d = tgt - loc
    yaw = math.atan2(-d[0], d[1])
    fwd = np.array([-math.sin(yaw), math.cos(yaw), 0.0])
    right = np.array([math.cos(yaw), math.sin(yaw), 0.0])
    up = np.array([0, 0, 1.0])
    v = pts - loc
    zf, xr, yu = v @ fwd, v @ right, v @ up
    fpx = cam["lens_mm"] / 36.0 * w
    u = w / 2 + fpx * xr / zf - cam.get("shift_x", 0) * w
    vv = h / 2 - fpx * yu / zf + cam.get("shift_y", 0) * w
    return u, vv


def overlay(base_rgb, field, norm, levels):
    """Greyscale render underneath, false colour on top, contour lines."""
    g = (base_rgb @ Y709)
    g = (g / (np.percentile(g, 99) + 1e-9)).clip(0, 1) ** (1 / 2.2)
    col = LUX(norm(np.clip(np.nan_to_num(field, nan=norm.vmin), norm.vmin, norm.vmax)))[..., :3]
    mix = 0.68 * col + 0.32 * g[..., None]
    grey = (0.55 * g)[..., None].repeat(3, axis=2)          # masked pixels (glass, sky): plain render
    return np.where(np.isfinite(field)[..., None], mix, grey)


def font(sz, bold=False):
    for n in (("segoeuib.ttf" if bold else "segoeui.ttf"), "arial.ttf"):
        try:
            return ImageFont.truetype(n, sz)
        except OSError:
            pass
    return ImageFont.load_default()


def save_map(stem, out_dir, field, base, norm, unit, title, ticks, tag):
    h, w = field.shape
    fig = plt.figure(figsize=(w / 200, h / 200 + 0.0), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.imshow(overlay(base, field, norm, ticks))
    cs = ax.contour(gaussian_filter(np.clip(np.nan_to_num(field, nan=norm.vmin), norm.vmin, norm.vmax), 2.5), levels=[t for t in ticks if norm.vmin < t < norm.vmax],
                    colors=[SURF], linewidths=0.6, alpha=0.7)
    ax.clabel(cs, fmt=lambda x: f"{x:g}", fontsize=5, colors=SURF)
    cax = fig.add_axes([0.952, 0.14, 0.016, 0.40])
    sm = plt.cm.ScalarMappable(norm=norm, cmap=LUX)
    cb = fig.colorbar(sm, cax=cax)
    cb.set_ticks(ticks); cb.set_ticklabels([f"{t:g}" for t in ticks]); cb.ax.minorticks_off()
    cb.ax.yaxis.set_ticks_position("left"); cb.ax.yaxis.set_label_position("left")
    cb.ax.tick_params(labelsize=6, colors=INK); cb.outline.set_visible(False)
    cb.set_label(unit, color=INK, fontsize=6.5)
    if title:
        fig.text(0.035, 0.955, title, color=INK, fontsize=9, fontweight="bold", va="top",
                 bbox=dict(boxstyle="round,pad=.35", fc=SURF, ec="none", alpha=.8))
    p = out_dir / f"{stem}_{tag}.png"
    fig.savefig(p, dpi=200, facecolor=SURF); plt.close(fig)
    return p


def split_image(render_png, map_png, out, label_l, label_r):
    a, b = Image.open(render_png).convert("RGB"), Image.open(map_png).convert("RGB").resize(Image.open(render_png).size)
    w, h = a.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).polygon([(int(w * .56), 0), (w, 0), (w, h), (int(w * .44), h)], fill=255)
    c = Image.composite(b, a, mask)
    d = ImageDraw.Draw(c)
    d.line([(int(w * .56), 0), (int(w * .44), h)], fill=(255, 255, 255), width=max(2, w // 500))
    f = font(max(14, w // 60), bold=True)
    for txt, x, anchor in ((label_l, int(w * .03), "lb"), (label_r, int(w * .97), "rb")):
        bb = d.textbbox((x, h - int(h * .04)), txt, font=f, anchor=anchor)
        d.rounded_rectangle([bb[0] - 10, bb[1] - 8, bb[2] + 10, bb[3] + 8], radius=8, fill=(26, 26, 25))
        d.text((x, h - int(h * .04)), txt, font=f, fill=(255, 255, 255), anchor=anchor)
    c.save(out)


def main():
    rdir = ROOT / sys.argv[1]
    stems = sys.argv[2:]
    out = ROOT / "reports/figures"; out.mkdir(parents=True, exist_ok=True)
    checks = {}
    for stem in stems:
        cam_id, sid = stem.split("_")[0], stem.split("_")[1]
        P = read_exr(rdir / f"{stem}.exr")
        comb = P["Combined"][..., :3]
        Lum = 683 * comb @ Y709
        # raw (unbiased, noisy) illuminance from the diffuse light passes -> used for the numeric check
        E = 683 * math.pi * (P["Diffuse Direct"] + P["Diffuse Indirect"]) @ Y709
        # display map: denoised luminance / albedo (E = pi L / rho, matte surfaces); mask glass, sky, dark albedo
        alb = P["Diffuse Color"] @ Y709
        Edisp = np.where(alb > 0.04, math.pi * Lum / np.maximum(alb, 1e-6), np.nan)
        Edisp = np.where(np.isfinite(Edisp), median_filter(np.nan_to_num(Edisp, nan=0), size=3), np.nan)
        Edisp[alb <= 0.04] = np.nan
        # glossy highlights (varnished wood) inflate pi*L/rho: cap at 1.3x the smoothed unbiased diffuse-pass value
        Esm = gaussian_filter(median_filter(E, size=9), 3)
        Edisp = np.where(np.isfinite(Edisp), np.minimum(Edisp, 1.3 * Esm), np.nan)
        h, w = Lum.shape
        # mask the glazing: what is seen through it is outdoors, not a room surface
        win = R["room"]["window"]
        quad = np.array([[win["x"][0], -0.09, win["z"][0]], [win["x"][1], -0.09, win["z"][0]],
                         [win["x"][1], -0.09, win["z"][1]], [win["x"][0], -0.09, win["z"][1]]])
        qu, qv = project(CAMS[cam_id], quad, w, h)
        mk = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mk).polygon(list(zip(qu.tolist(), qv.tolist())), fill=255)
        Edisp[np.array(mk) > 0] = np.nan
        label = R["scenes"].get(sid, {}).get("label", "Daylight")
        lm = save_map(stem, out, Lum, comb, LogNorm(1, 1000), "cd/m²",
                      f"Luminance · {label}", (1, 3, 10, 30, 100, 300, 1000), "luminance")
        em = save_map(stem, out, Edisp, comb, LogNorm(10, 1000), "lx",
                      f"Illuminance on surfaces · {label}", (10, 20, 50, 100, 200, 500, 1000), "illuminance")
        split_image(rdir / f"{stem}.png", em, out / f"{stem}_split.png", label, "Illuminance, lx")
        save_map(stem, out, Edisp, comb, LogNorm(10, 1000), "lx", "",
                 (10, 20, 50, 100, 200, 500, 1000), "illuminance_clean")          # no title: for slider formats
        # cross-check: table top
        if sid in R["scenes"]:
            z = R["zones_def"]["dining_table"]
            xs = np.linspace(z["x"][0] + .1, z["x"][1] - .1, 12); ys = np.linspace(z["y"][0] + .1, z["y"][1] - .1, 20)
            X, Y = np.meshgrid(xs, ys)
            pts = np.column_stack([X.ravel(), Y.ravel(), np.full(X.size, 0.7505)])
            u, v = project(CAMS[cam_id], pts, w, h)
            ok = (u >= 0) & (u < w) & (v >= 0) & (v < h)
            # EXR rows are top-to-bottom
            samp = E[v[ok].astype(int), u[ok].astype(int)]
            eng = R["scenes"][sid]["zones"]["dining_table"]["E_avg"] / R["room"]["maintenance_factor"] * \
                R["room"]["maintenance_factor"]
            checks[stem] = dict(render_table_median_lx=round(float(np.median(samp)), 1),
                                render_table_mean_lx=round(float(np.mean(samp)), 1),
                                engine_table_avg_lx=eng, samples=int(ok.sum()),
                                diff_pct=round(float(100 * (np.median(samp) / eng - 1)), 1))
            print(stem, checks[stem])
        print("maps ->", lm.name, em.name)
    if checks:
        p = ROOT / "results/render_crosscheck.json"
        old = json.load(open(p)) if p.exists() else {}
        old.update(checks)
        json.dump(old, open(p, "w"), indent=1)


if __name__ == "__main__":
    main()
