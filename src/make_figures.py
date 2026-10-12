"""Figures for the report and the portfolio: lux plans, scene comparison, daylight
factor, Radiance validation and luminaire photometry.  python src/make_figures.py
"""
import json, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LogNorm, Normalize
from matplotlib.patches import Rectangle, Circle

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "reports/figures"; FIG.mkdir(parents=True, exist_ok=True)
R = json.load(open(ROOT / "results/results.json"))
L, W, H = R["room"]["size"]

# ---- design tokens (dark chart surface; palette.md dark steps) --------------------
SURF, PAGE, INK, INK2, MUTED, GRID = "#1a1a19", "#0d0d0d", "#ffffff", "#c3c2b7", "#8a897f", "#383835"
S1, S2, S3, S4 = "#3987e5", "#d95926", "#199e70", "#c98500"
GOOD, BAD = "#0ca30c", "#e66767"
# one-hue warm ramp, dark (little light) -> bright (much light)
LUX = LinearSegmentedColormap.from_list("lux", ["#221a12", "#4a3114", "#7a4d14", "#ad6d17", "#d99325", "#f2bd55", "#fde3a0", "#fff7e3"])
DFC = LinearSegmentedColormap.from_list("df", ["#0d1f38", "#104281", "#1c5cab", "#3987e5", "#6da7ec", "#b7d3f6", "#eef5fe"])

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 10, "text.color": INK,
    "axes.facecolor": SURF, "figure.facecolor": SURF, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.titleweight": "semibold", "axes.titlesize": 12,
    "savefig.facecolor": SURF, "savefig.dpi": 200})

# simplified furniture footprints (same layout as the Blender scene)
FURN = [("counter", 0, 0.65, 0.98, 4.42), ("tall", 0, 0.65, 4.42, 5.0), ("island", 1.6, 2.5, 1.6, 3.8),
        ("table", 3.15, 4.05, 1.7, 3.5), ("sofa", 4.6, 6.7, 4.05, 4.95), ("rug", 4.85, 6.95, 2.25, 4.35),
        ("armchair", 6.05, 6.85, 0.75, 1.5)]
ZLAB = {"kitchen_counter": "Counter", "island": "Island", "dining_table": "Dining", "living": "Living"}


def luminaire_marks(ax, size=1.0, labels=False):
    for lum in R["luminaires"]:
        if "line" in lum:
            (x0, y0, _), (x1, y1, _) = lum["line"]["start"], lum["line"]["end"]
            ax.plot([x0, x1], [y0, y1], color=INK, lw=2.2 * size, solid_capstyle="round", alpha=.9)
            continue
        x, y, _ = lum["pos"]
        mk = {"DL": "o", "PD": "D", "FL": "^"}[lum["type"]]
        ax.plot(x, y, mk, ms=6.5 * size, mfc="none", mec=INK, mew=1.4)
        if labels:
            ax.text(x + .12, y + .1, lum["id"], fontsize=6.5, color=SURF, alpha=.8)


def room_axes(ax):
    ax.set_xlim(-0.05, L + 0.05); ax.set_ylim(-0.25, W + 0.05); ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.add_patch(Rectangle((0, 0), L, W, fill=False, ec=INK, lw=2.2))
    wx = R["room"]["window"]["x"]
    ax.plot(wx, [0, 0], color=S1, lw=5, solid_capstyle="butt")
    ax.text(np.mean(wx), -0.17, "window", ha="center", va="center", fontsize=7.5, color=S1)
    for _, x0, x1, y0, y1 in FURN:
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec=INK, lw=.6, alpha=.35, ls="-"))


def lux_plan(ax, sid, vmin=10, vmax=1000, zones=True, title=True, labels=False):
    sc = R["scenes"][sid]
    E = np.array(sc["floor_grid"]["E"])
    gx, gy = np.array(R["grid"]["x"]), np.array(R["grid"]["y"])
    sp = R["grid"]["spacing"]
    im = ax.imshow(E, origin="lower", extent=(0, L, 0, W), cmap=LUX, norm=LogNorm(vmin, vmax),
                   interpolation="bicubic")
    lv = [l for l in (25, 50, 100, 200, 300, 500, 750) if E.min() < l < E.max()]
    cs = ax.contour(gx, gy, E, levels=lv, colors=[SURF], linewidths=.8, alpha=.85)
    ax.clabel(cs, fmt="%d", fontsize=7, colors=SURF, inline_spacing=2)
    room_axes(ax)
    luminaire_marks(ax, .85, labels)
    if zones:
        for z, m in sc["zones"].items():
            d = R["zones_def"][z]
            ok = all(c["pass"] for c in m["checks"]) if m["checks"] else None
            ax.add_patch(Rectangle((d["x"][0], d["y"][0]), d["x"][1] - d["x"][0], d["y"][1] - d["y"][0],
                                   fill=False, ec=INK, lw=1.0, ls=(0, (3, 2))))
            tx = d["x"][0] + .06 if z != "kitchen_counter" else 0.05
            ty = d["y"][1] - .08
            mark = "" if ok is None else (" ✓" if ok else " ✗")
            ax.text(tx, ty, f"{ZLAB[z]}\n{m['E_avg']:.0f} lx{mark}", va="top", fontsize=7.5, color=INK,
                    fontweight="semibold", bbox=dict(boxstyle="round,pad=.25", fc=SURF, ec="none", alpha=.78))
    if title:
        ax.set_title(f"{sc['label']}  ·  {sc['power_w']:.0f} W  ·  {sc['lpd_w_m2']:.1f} W/m²", loc="left")
    return im


def lux_ticks(cb, ticks=(10, 20, 50, 100, 200, 500, 1000)):
    cb.set_ticks(ticks); cb.set_ticklabels([str(t) for t in ticks]); cb.ax.minorticks_off()


def fig_plans():
    for sid in R["scenes"]:
        fig, ax = plt.subplots(figsize=(10, 7.4))
        im = lux_plan(ax, sid, labels=True)
        cb = fig.colorbar(im, ax=ax, fraction=.035, pad=.02)
        cb.set_label("Maintained horizontal illuminance at 0.75 m [lx]", color=INK2); lux_ticks(cb)
        cb.outline.set_visible(False)
        fig.text(.02, .02, f"Workplane grid {R['grid']['spacing']} m · MF {R['room']['maintenance_factor']} · "
                 "direct + radiosity interreflection · empty-room model", color=MUTED, fontsize=8)
        fig.savefig(FIG / f"plan_{sid}.png", bbox_inches="tight"); plt.close(fig)


def fig_compare():
    sids = list(R["scenes"])
    fig, axs = plt.subplots(1, len(sids), figsize=(16, 4.6))
    for ax, sid in zip(axs, sids):
        im = lux_plan(ax, sid)
    cb = fig.colorbar(im, ax=axs, fraction=.015, pad=.01)
    cb.set_label("lx (maintained, 0.75 m)", color=INK2); cb.outline.set_visible(False); lux_ticks(cb)
    fig.savefig(FIG / "scenes_compare.png", bbox_inches="tight"); plt.close(fig)


def fig_daylight():
    d = R.get("daylight")
    if not d:
        return
    DF = np.array(d["DF"])
    fig, ax = plt.subplots(figsize=(10, 7.4))
    im = ax.imshow(DF, origin="lower", extent=(0, L, 0, W), cmap=DFC, norm=LogNorm(0.3, 12),
                   interpolation="bicubic")
    cs = ax.contour(d["x"], d["y"], DF, levels=[0.5, 1, 2, 3, 5], colors=[SURF], linewidths=.8)
    ax.clabel(cs, fmt="%g%%", fontsize=7, colors=SURF)
    room_axes(ax)
    ax.set_title(f"Daylight factor, CIE overcast sky  ·  mean {d['DF_avg']:.1f}%  ·  median {d['DF_median']:.1f}%  ·  "
                 f"{d['area_ge_2pct']:.1f}% of floor ≥ 2%  ·  window/floor {d['window_to_floor']:.2f}", loc="left")
    cb = fig.colorbar(im, ax=ax, fraction=.035, pad=.02); cb.set_label("Daylight factor [%]", color=INK2)
    lux_ticks(cb, (0.5, 1, 2, 5, 10))
    cb.outline.set_visible(False)
    fig.text(.02, .02, f"Radiance {R.get('radiance_version','').split()[1] if R.get('radiance_version') else ''} · "
             "rtrace -ab 8 · glazing Tvis 0.70 · no external obstruction", color=MUTED, fontsize=8)
    fig.savefig(FIG / "daylight_df.png", bbox_inches="tight"); plt.close(fig)


def fig_validation():
    v = R.get("validation")
    if not v:
        return
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(13, 5.6), gridspec_kw=dict(width_ratios=[1.15, 1]))
    series = [("Full scene, total", v["full"]["radiance_total"], v["full"]["engine_total"], S1),
              ("Sensory Calm, total", v["calm"]["radiance_total"], v["calm"]["engine_total"], S2),
              ("Full scene, direct only", v["full"]["radiance_direct"], v["full"]["engine_direct"], S3)]
    allv = np.concatenate([np.array(s[1]) for s in series] + [np.array(s[2]) for s in series])
    lo, hi = max(5, allv.min() * .8), allv.max() * 1.2
    xx = np.geomspace(lo, hi, 50)
    ax.fill_between(xx, xx * .9, xx * 1.1, color=GRID, alpha=.6, lw=0, label="±10 %")
    ax.plot(xx, xx, color=INK2, lw=1)
    for lab, r, e, c in series:
        ax.plot(r, e, "o", ms=4.5, mfc=c, mec=SURF, mew=.8, alpha=.9, label=lab)
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.set_xlabel("Radiance rtrace [lx]"); ax.set_ylabel("This engine [lx]")
    ax.grid(True, color=GRID, lw=.5, which="major"); ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left", labelcolor=INK2)
    ax.set_title("Point-by-point agreement with Radiance (same room, same IES files)", loc="left")
    # error distributions
    for i, (lab, r, e, c) in enumerate(series):
        r, e = np.array(r), np.array(e)
        err = 100 * (e - r) / np.maximum(r, 1)
        bx.hist(err, bins=np.linspace(-20, 20, 41), color=c, alpha=.75, label=lab,
                histtype="stepfilled", ec=SURF, lw=.6)
    bx.axvline(0, color=INK2, lw=1)
    bx.set_xlabel("Engine vs Radiance, per point [%]"); bx.set_ylabel("Grid points")
    bx.grid(True, axis="y", color=GRID, lw=.5); bx.set_axisbelow(True)
    s = (f"Full: mean bias {v['full']['mean_bias_pct']:+.1f} %, MAPE {v['full']['mape_pct']:.1f} %, "
         f"direct MAPE {v['full']['direct_mape_pct']:.1f} %\n"
         f"Calm: mean bias {v['calm']['mean_bias_pct']:+.1f} %, MAPE {v['calm']['mape_pct']:.1f} %   "
         f"({v['full']['points']} points per run)")
    bx.set_title("Error distribution", loc="left")
    fig.text(.02, -.02, s, color=INK2, fontsize=9)
    fig.savefig(FIG / "validation.png", bbox_inches="tight"); plt.close(fig)


def fig_photometry():
    fig = plt.figure(figsize=(11, 4.2))
    names = {"DL": "Downlight 60°", "PD": "Pendant 70/30", "FL": "Uplighter", "UC": "LED strip (0.2 m)"}
    for i, (t, p) in enumerate(R["photometry"].items()):
        ax = fig.add_subplot(1, 4, i + 1, projection="polar")
        g = np.radians(p["curve"]["gamma"]); cd = np.array(p["curve"]["cd"])
        cdk = cd / (p["flux_lm"] / 1000)                           # cd/klm
        for sgn in (1, -1):
            ax.plot(sgn * g, cdk, color=[S1, S2, S3, S4][i], lw=2)
        ax.set_theta_zero_location("S"); ax.set_thetamin(-180); ax.set_thetamax(180)
        ax.set_facecolor(SURF); ax.grid(color=GRID, lw=.5)
        ax.set_xticks(np.radians([-150, -90, -30, 0, 30, 90, 150]))
        ax.set_xticklabels(["150°", "90°", "30°", "0°", "30°", "90°", "150°"], fontsize=7)
        ax.tick_params(axis="y", labelsize=6.5, colors=MUTED)
        ax.set_title(f"{names[t]}\n{p['flux_lm']:.0f} lm · {p['watts']:.0f} W · {p['efficacy_lm_w']:.0f} lm/W",
                     fontsize=9.5, color=INK, pad=12)
    fig.suptitle("Luminaire photometry (generic LM-63 files, cd/klm)", x=.02, ha="left", fontsize=12,
                 fontweight="semibold")
    fig.savefig(FIG / "photometry.png", bbox_inches="tight"); plt.close(fig)


if __name__ == "__main__":
    fig_plans(); fig_compare(); fig_daylight(); fig_validation(); fig_photometry()
    print("figures ->", FIG)
