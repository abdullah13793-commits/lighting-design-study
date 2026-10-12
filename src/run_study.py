"""Run the full lighting study: photometry -> scenes -> zones -> daylight -> validation.

    python src/run_study.py [--config config/study.json] [--skip-radiance]

Writes data/ies/*.ies, results/results.json and results/*.csv.
"""
import argparse, json, platform, time, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from lumen import library, calc, radiance

ROOT = Path(__file__).resolve().parents[1]


def build_photometry(cfg, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    phot = {}
    for typ, spec in cfg["luminaire_types"].items():
        args = {k: v for k, v in spec.items() if k not in ("kind", "cct")}
        p = library.FACTORY[spec["kind"]](name=typ, **args)
        p.to_lm63(out_dir / f"{typ}.ies")
        phot[typ] = p
    return phot


def zone_metrics(E, target=None, min_u0=None, band=None):
    avg, mn, mx = float(E.mean()), float(E.min()), float(E.max())
    m = dict(E_avg=round(avg, 1), E_min=round(mn, 1), E_max=round(mx, 1),
             U0=round(mn / avg, 2) if avg else 0.0)
    checks = []
    if target is not None:
        checks.append(("E_avg >= %d lx" % target, avg >= target))
    if min_u0 is not None:
        checks.append(("U0 >= %.2f" % min_u0, m["U0"] >= min_u0))
    if band is not None:
        checks.append(("%d-%d lx band (avg)" % tuple(band), band[0] <= avg <= band[1]))
    m["checks"] = [{"rule": r, "pass": bool(p)} for r, p in checks]
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config/study.json"))
    ap.add_argument("--skip-radiance", action="store_true")
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8"))
    t0 = time.time()
    res_dir = ROOT / "results"; res_dir.mkdir(exist_ok=True)
    phot = build_photometry(cfg, ROOT / "data/ies")
    room = calc.Room(cfg, phot)
    mf = cfg["room"]["maintenance_factor"]
    L, W, H = cfg["room"]["size"]
    floor_area = L * W
    t_ff = time.time() - t0

    # ---------------------------------------------------------- scenes
    gpts, gshape, gx, gy = calc.grid([0, L], [0, W], cfg["grid"]["z"], cfg["grid"]["spacing"])
    zone_pts = {z: calc.grid(d["x"], d["y"], d["z"], cfg["grid"]["spacing"] / 2)[0]
                for z, d in cfg["zones"].items()}
    scenes = {}
    for sid, sc in cfg["scenes"].items():
        solved = None
        if "solve" in sc:
            dim, achieved = room.solve_scene(zone_pts, sc["solve"]["targets"], sc["solve"].get("bounds", {}), mf)
            sc["dim"] = dim
            solved = dict(targets=sc["solve"]["targets"], achieved=achieved)
            print(f"[{sid}] solved dimming {dim}")
        Ed, Ei = room.illuminance(gpts, sid, mf)
        E = Ed + Ei
        zones = {}
        for z, d in cfg["zones"].items():
            zd, zi = room.illuminance(zone_pts[z], sid, mf)
            st = cfg.get("scene_targets", {}).get(sid, {}).get(z, {})
            if sid == "full":
                zones[z] = zone_metrics(zd + zi, d.get("target_lx"), d.get("min_u0"))
            else:
                zones[z] = zone_metrics(zd + zi, st.get("target_lx"), None, st.get("band_lx"))
        pw = room.power_w(sid)
        scenes[sid] = dict(label=sc["label"], desc=sc["desc"], dim=sc["dim"], solved=solved,
                           power_w=round(pw, 1), lpd_w_m2=round(pw / floor_area, 2),
                           floor_grid=dict(E=np.round(E.reshape(gshape), 1).tolist(),
                                           E_direct=np.round(Ed.reshape(gshape), 1).tolist(),
                                           E_avg=round(float(E.mean()), 1),
                                           indirect_share=round(float(Ei.sum() / E.sum()), 3)),
                           zones=zones)
        np.savetxt(res_dir / f"grid_{sid}.csv",
                   np.column_stack([gpts, Ed, Ei, E]), delimiter=",", fmt="%.3f",
                   header="x_m,y_m,z_m,E_direct_lx,E_indirect_lx,E_total_lx (maintained)", comments="")
        print(f"[{sid}] {sc['label']}: workplane avg {E.mean():.0f} lx, {pw:.1f} W, "
              + ", ".join(f"{z} {m['E_avg']:.0f} lx" for z, m in zones.items()))

    out = dict(project=cfg["project"], generated=time.strftime("%Y-%m-%d %H:%M"),
               room=cfg["room"], floor_area_m2=floor_area,
               grid=dict(x=np.round(gx, 3).tolist(), y=np.round(gy, 3).tolist(), z=cfg["grid"]["z"],
                         spacing=cfg["grid"]["spacing"]),
               luminaires=cfg["luminaires"], luminaire_types=cfg["luminaire_types"],
               photometry={t: dict(flux_lm=round(p.flux(), 1), peak_cd=round(p.peak(), 1),
                                   watts=p.input_watts, efficacy_lm_w=round(p.flux() / p.input_watts, 1),
                                   desc=p.keywords["LUMINAIRE"],
                                   curve=dict(gamma=p.v_angles.tolist(), cd=np.round(p.candela[0], 2).tolist()))
                           for t, p in phot.items()},
               scenes=scenes, zones_def=cfg["zones"],
               engine=dict(patches=int(len(room.patches.area)), form_factor_row_sum=[
                   round(float(room.Fr.sum(1).min()), 4), round(float(room.Fr.sum(1).max()), 4)],
                   form_factor_seconds=round(t_ff, 1)),
               environment=dict(python=platform.python_version(), numpy=np.__version__,
                                os=platform.platform()))

    # checkpoint: scene results are usable (renders, figures) while Radiance runs
    prev = res_dir / "results.json"
    if prev.exists():                       # keep earlier validation/daylight until replaced
        old = json.load(open(prev))
        for k in ("validation", "daylight", "radiance_version"):
            if k in old and k not in out:
                out[k] = old[k]
    json.dump(out, open(prev, "w"), indent=1)

    # ---------------------------------------------------------- radiance: validation + daylight
    if not a.skip_radiance:
        out["radiance_version"] = radiance.version()
        vpts, vshape, vx, vy = calc.grid([0, L], [0, W], cfg["grid"]["z"], 0.4)
        val = {}
        for sid in ("full", "calm"):
            src = room.sources(sid, 1.0)
            ies_dir = ROOT / "data/ies"
            work = ROOT / f"results/radiance/{sid}"
            work.mkdir(parents=True, exist_ok=True)
            lum = radiance.luminaires_rad(cfg, src, ies_dir, work)
            scene = radiance.room_rad(cfg, daylight=False) + lum
            t = time.time()
            r_tot = radiance.rtrace_lux(vpts, scene, work)
            r_dir = radiance.rtrace_lux(vpts, scene, work, params=["-ab", "0"]) if sid == "full" else None
            Ed, Ei = room.illuminance(vpts, sid, 1.0)
            e_tot = Ed + Ei
            d = dict(points=int(len(vpts)), seconds=round(time.time() - t, 1),
                     engine_total=np.round(e_tot, 1).tolist(), radiance_total=np.round(r_tot, 1).tolist(),
                     mean_engine=round(float(e_tot.mean()), 1), mean_radiance=round(float(r_tot.mean()), 1),
                     mean_bias_pct=round(float(100 * (e_tot.mean() / r_tot.mean() - 1)), 2),
                     mape_pct=round(float(100 * np.mean(np.abs(e_tot - r_tot) / r_tot)), 2),
                     p95_ape_pct=round(float(100 * np.percentile(np.abs(e_tot - r_tot) / r_tot, 95)), 2))
            if r_dir is not None:
                d.update(engine_direct=np.round(Ed, 1).tolist(), radiance_direct=np.round(r_dir, 1).tolist(),
                         direct_mape_pct=round(float(100 * np.mean(np.abs(Ed - r_dir) / np.maximum(r_dir, 1))), 2))
            val[sid] = d
            print(f"[validate {sid}] engine {d['mean_engine']} vs radiance {d['mean_radiance']} lx, "
                  f"bias {d['mean_bias_pct']}%, MAPE {d['mape_pct']}%"
                  + (f", direct MAPE {d['direct_mape_pct']}%" if r_dir is not None else ""))
        out["validation"] = val

        dpts, dshape, dx, dy = calc.grid([0, L], [0, W], cfg["grid"]["z"], 0.25)
        work = ROOT / "results/radiance/daylight"
        df = radiance.rtrace_lux(dpts, radiance.overcast_sky(10000) + radiance.room_rad(cfg, daylight=True),
                                 work) / 10000 * 100
        wx = cfg["room"]["window"]["x"]; wz = cfg["room"]["window"]["z"]
        out["daylight"] = dict(sky="CIE overcast, 10 000 lx unobstructed horizontal", grid_spacing=0.25,
                               x=np.round(dx, 3).tolist(), y=np.round(dy, 3).tolist(),
                               DF=np.round(df.reshape(dshape), 2).tolist(),
                               DF_avg=round(float(df.mean()), 2), DF_median=round(float(np.median(df)), 2),
                               area_ge_2pct=round(float((df >= 2).mean() * 100), 1),
                               area_ge_1pct=round(float((df >= 1).mean() * 100), 1),
                               window_to_floor=round((wx[1] - wx[0]) * (wz[1] - wz[0]) / floor_area, 3))
        print(f"[daylight] DF avg {out['daylight']['DF_avg']}%, median {out['daylight']['DF_median']}%, "
              f">=2%: {out['daylight']['area_ge_2pct']}% of floor, WFR {out['daylight']['window_to_floor']}")

    out["runtime_seconds"] = round(time.time() - t0, 1)
    json.dump(out, open(res_dir / "results.json", "w"), indent=1)
    print(f"done in {out['runtime_seconds']} s -> results/results.json")


if __name__ == "__main__":
    main()
