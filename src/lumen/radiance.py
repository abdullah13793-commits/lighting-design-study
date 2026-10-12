"""Independent check with LBNL Radiance (ies2rad + oconv + rtrace).

Builds the same room in Radiance, converts the same LM-63 files with ies2rad,
and returns illuminance at the same points. Also runs the CIE overcast-sky
daylight-factor calculation (which the electric-light engine does not do).
"""
from __future__ import annotations
import os, shutil, subprocess
from pathlib import Path
import numpy as np

EFFICACY = 179.0  # Radiance white-light luminous efficacy, lm/W


def radiance_bin():
    for cand in [os.environ.get("RADIANCE_BIN"), str(Path.home() / "Tools/Radiance/bin")]:
        if cand and (Path(cand) / "rtrace.exe").exists():
            return Path(cand)
    exe = shutil.which("rtrace")
    if exe:
        return Path(exe).parent
    raise FileNotFoundError("Radiance not found: set RADIANCE_BIN or install it (see docs/SETUP.md)")


def _env(work):
    b = radiance_bin()
    env = dict(os.environ)
    env["PATH"] = f"{b}{os.pathsep}{env['PATH']}"
    env["RAYPATH"] = f".{os.pathsep}{b.parent / 'lib'}{os.pathsep}{work}"
    return env


def _run(cmd, work, stdin=None, stdout_file=None):
    out = open(stdout_file, "wb") if stdout_file else subprocess.PIPE
    r = subprocess.run(cmd, cwd=work, env=_env(work), input=stdin, stdout=out,
                       stderr=subprocess.PIPE, check=False)
    if stdout_file:
        out.close()
    if r.returncode:
        raise RuntimeError(f"{cmd[0]} failed: {r.stderr.decode(errors='ignore')}")
    return r.stdout


def _poly(mat, name, pts):
    flat = " ".join(f"{c:.4f}" for p in pts for c in p)
    return f"{mat} polygon {name}\n0\n0\n{3*len(pts)} {flat}\n"


def room_rad(cfg, daylight=False):
    L, W, H = cfg["room"]["size"]
    rho = cfg["room"]["reflectance"]
    win = cfg["room"]["window"]
    s = []
    for k in ("ceiling", "walls", "floor"):
        r = rho[k]
        s.append(f"void plastic m_{k}\n0\n0\n5 {r} {r} {r} 0 0\n")
    # inward-facing polygons (Radiance plastic is two-sided, order kept tidy anyway)
    s.append(_poly("m_floor", "floor", [(0, 0, 0), (L, 0, 0), (L, W, 0), (0, W, 0)]))
    s.append(_poly("m_ceiling", "ceiling", [(0, 0, H), (0, W, H), (L, W, H), (L, 0, H)]))
    s.append(_poly("m_walls", "wall_y1", [(0, W, 0), (L, W, 0), (L, W, H), (0, W, H)]))
    s.append(_poly("m_walls", "wall_x0", [(0, 0, 0), (0, W, 0), (0, W, H), (0, 0, H)]))
    s.append(_poly("m_walls", "wall_x1", [(L, 0, 0), (L, 0, H), (L, W, H), (L, W, 0)]))
    x0, x1 = win["x"]; z0, z1 = win["z"]
    # wall y0 split around the window opening
    for nm, pts in {"y0_left": [(0, 0, 0), (x0, 0, 0), (x0, 0, H), (0, 0, H)],
                    "y0_right": [(x1, 0, 0), (L, 0, 0), (L, 0, H), (x1, 0, H)],
                    "y0_below": [(x0, 0, 0), (x1, 0, 0), (x1, 0, z0), (x0, 0, z0)],
                    "y0_above": [(x0, 0, z1), (x1, 0, z1), (x1, 0, H), (x0, 0, H)]}.items():
        s.append(_poly("m_walls", nm, pts))
    wpts = [(x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1)]
    if daylight:
        tn = win["visible_transmittance"]
        t = (np.sqrt(0.8402528435 + 0.0072522239 * tn**2) - 0.9166530661) / 0.0036261119 / tn
        s.append(f"void glass m_glass\n0\n0\n3 {t:.4f} {t:.4f} {t:.4f}\n")
        s.append(_poly("m_glass", "window", wpts))
    else:
        r = rho["window"]
        s.append(f"void plastic m_window\n0\n0\n5 {r} {r} {r} 0 0\n")
        s.append(_poly("m_window", "window", wpts))
    return "".join(s)


def luminaires_rad(cfg, sources, ies_dir, work, mf=1.0):
    """One ies2rad conversion per (type, scale); instances placed with xform."""
    made, s = {}, []
    for src in sources:
        if src.scale == 0:
            continue
        typ = next(l["type"] for l in cfg["luminaires"] if src.id.startswith(l["id"]))
        key = (typ, round(src.scale, 4))
        if key not in made:
            name = f"lum_{typ}_{len(made)}"
            shutil.copy(Path(ies_dir) / f"{typ}.ies", Path(work) / f"{typ}.ies")
            _run([str(radiance_bin() / "ies2rad.exe"), "-dm", "-m", f"{src.scale:.5f}",
                  "-o", name, f"{typ}.ies"], work)
            made[key] = name
        x, y, z = src.pos
        s.append(f"!xform -rz {src.rot_deg} -t {x:.4f} {y:.4f} {z:.4f} {made[key]}.rad\n")
    return "".join(s)


def overcast_sky(horiz_lux=10000.0):
    b = horiz_lux / EFFICACY
    return (f"!gensky 12 21 12 -c -B {b:.4f}\n"
            "skyfunc glow sky_glow\n0\n0\n4 1 1 1 0\nsky_glow source sky\n0\n0\n4 0 0 1 180\n"
            "skyfunc glow ground_glow\n0\n0\n4 1 1 1 0\nground_glow source ground\n0\n0\n4 0 0 -1 180\n")


ACCURATE = ["-ab", "8", "-ad", "2048", "-as", "512", "-aa", "0.1", "-ar", "256", "-lw", "1e-5"]


def rtrace_lux(points, scene_text, work, params=ACCURATE, normals=None):
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    (work / "scene.rad").write_text(scene_text)
    _run([str(radiance_bin() / "oconv.exe"), "scene.rad"], work, stdout_file=work / "scene.oct")
    if normals is None:
        normals = np.tile([0, 0, 1.0], (len(points), 1))
    inp = "\n".join(f"{p[0]:.4f} {p[1]:.4f} {p[2]:.4f} {n[0]} {n[1]} {n[2]}"
                    for p, n in zip(points, normals)) + "\n"
    out = _run([str(radiance_bin() / "rtrace.exe"), "-h", "-I", *params, "scene.oct"], work,
               stdin=inp.encode())
    rgb = np.array([list(map(float, l.split())) for l in out.decode().strip().splitlines()])
    return EFFICACY * (0.265 * rgb[:, 0] + 0.670 * rgb[:, 1] + 0.065 * rgb[:, 2])


def version():
    return _run([str(radiance_bin() / "rtrace.exe"), "-version"], ".").decode().strip()
