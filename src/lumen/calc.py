"""Illuminance engine for a rectangular room.

E(P) = E_direct(P) + E_indirect(P)

* Direct: point-by-point from LM-63 photometry, inverse-square and cosine law.
* Indirect: radiosity on the six room faces (Lambertian patches). Form factors
  use the exact differential-area-to-polygon formula, so there is no
  near-corner singularity. The room is an empty convex box, so every patch on
  another face is fully visible; receivers below/above a patch are handled by
  clipping the patch against the receiver's tangent plane.

Assumptions (also listed in docs/METHOD.md): empty room (furniture ignored),
Lambertian surfaces, luminaires as point sources (strips as point series),
luminaires do not obstruct light, window glass treated as a low-reflectance
surface with transmitted light lost (night-time electric-light calculation).
"""
from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from .ies import Photometry

DOWN = np.array([0.0, 0.0, -1.0])


@dataclass
class Source:
    pos: np.ndarray        # (3,)
    phot: Photometry
    scale: float = 1.0     # dimming x maintenance etc.
    rot_deg: float = 0.0   # C-plane rotation about z
    group: str = ""
    id: str = ""


# ------------------------------------------------------------------ direct
def direct(points, normals, sources):
    """Direct illuminance (lx) at points (N,3) with unit normals (N,3)."""
    E = np.zeros(len(points))
    for s in sources:
        if s.scale == 0:
            continue
        v = points - s.pos
        d2 = np.einsum("ij,ij->i", v, v)
        d = np.sqrt(d2)
        u = v / d[:, None]
        gamma = np.degrees(np.arccos(np.clip(u @ DOWN, -1, 1)))
        c = np.degrees(np.arctan2(u[:, 1], u[:, 0])) - s.rot_deg
        cos_inc = np.clip(-np.einsum("ij,ij->i", u, normals), 0, None)
        E += s.scale * s.phot.intensity(gamma, c) * cos_inc / d2
    return E


# ------------------------------------------------------------------ geometry
@dataclass
class Patches:
    verts: np.ndarray      # (M,4,3) counter-clockwise seen from inside
    normal: np.ndarray     # (M,3) inward
    center: np.ndarray     # (M,3)
    area: np.ndarray       # (M,)
    face: np.ndarray       # (M,) face index 0..5
    rho: np.ndarray        # (M,)
    samples: np.ndarray    # (M,S,3) receiver sample points


FACES = ["floor", "ceiling", "y0", "y1", "x0", "x1"]


def box_patches(L, W, H, size, rho, window=None, nsub=2):
    """Discretise the inside of a box [0,L]x[0,W]x[0,H] into patches."""
    defs = {  # origin, axis u, axis v, normal; u x v must equal the inward normal
        "floor":   ((0, 0, 0), (L, 0, 0), (0, W, 0), (0, 0, 1)),
        "ceiling": ((0, 0, H), (0, W, 0), (L, 0, 0), (0, 0, -1)),
        "y0":      ((0, 0, 0), (0, 0, H), (L, 0, 0), (0, 1, 0)),
        "y1":      ((0, W, 0), (L, 0, 0), (0, 0, H), (0, -1, 0)),
        "x0":      ((0, 0, 0), (0, W, 0), (0, 0, H), (1, 0, 0)),
        "x1":      ((L, 0, 0), (0, 0, H), (0, W, 0), (-1, 0, 0)),
    }
    V, N, C, A, F, R, S = [], [], [], [], [], [], []
    for fi, name in enumerate(FACES):
        o, a, b, n = (np.array(x, float) for x in defs[name])
        la, lb = np.linalg.norm(a), np.linalg.norm(b)
        na, nb = max(1, round(la / size)), max(1, round(lb / size))
        ua, ub = a / na, b / nb
        sub = (np.arange(nsub) + 0.5) / nsub
        for i in range(na):
            for j in range(nb):
                p0 = o + i * ua + j * ub
                quad = np.array([p0, p0 + ua, p0 + ua + ub, p0 + ub])
                c = p0 + 0.5 * (ua + ub)
                V.append(quad); N.append(n); C.append(c); A.append(np.linalg.norm(np.cross(ua, ub)))
                F.append(fi)
                r = rho["walls"] if name.startswith(("x", "y")) else rho[name]
                if window and name == window["wall"] and window["x"][0] <= c[0] <= window["x"][1] \
                        and window["z"][0] <= c[2] <= window["z"][1]:
                    r = rho["window"]
                R.append(r)
                S.append([p0 + si * ua + sj * ub for si in sub for sj in sub])
    return Patches(np.array(V), np.array(N), np.array(C), np.array(A), np.array(F), np.array(R), np.array(S))


def point_to_polys(p, n, verts):
    """Exact form factor from differential areas (P,3)/(P,3) to polygons (M,k,3).

    Polygons must lie in front of each receiver plane (clip first). Returns (P,M).
    """
    R = verts[None, :, :, :] - p[:, None, None, :]                 # (P,M,k,3)
    R1 = np.roll(R, -1, axis=2)
    cr = np.cross(R, R1)
    crn = np.linalg.norm(cr, axis=-1, keepdims=True)
    g = np.divide(cr, crn, out=np.zeros_like(cr), where=crn > 1e-12)
    nr = np.linalg.norm(R, axis=-1) * np.linalg.norm(R1, axis=-1)
    cos_t = np.clip(np.einsum("pmkd,pmkd->pmk", R, R1) / np.maximum(nr, 1e-12), -1, 1)
    theta = np.arccos(cos_t)
    ff = np.einsum("pmk,pmkd,pd->pm", theta, g, n) / (2 * np.pi)
    return np.abs(ff)


def clip_quads_z(verts, zmin=None, zmax=None):
    """Clip axis-aligned quads to a z-range. Fully clipped quads collapse to a
    degenerate (zero-area) quad, which gives a zero form factor."""
    v = verts.copy()
    z = v[..., 2]
    if zmin is not None:
        z = np.maximum(z, zmin)
    if zmax is not None:
        z = np.minimum(z, zmax)
    v[..., 2] = z
    return v


def form_factor_matrix(P: Patches, chunk=64):
    """F[i,j] = fraction of energy leaving i that reaches j, via reciprocity
    from the receiver-averaged exact point-to-polygon factor."""
    M = len(P.area)
    Fr = np.zeros((M, M))                 # Fr[i,j]: form factor dA_i -> A_j, averaged over i
    S = P.samples.shape[1]
    for i0 in range(0, M, chunk):
        idx = np.arange(i0, min(M, i0 + chunk))
        pts = P.samples[idx].reshape(-1, 3)
        nrm = np.repeat(P.normal[idx], S, axis=0)
        ff = point_to_polys(pts, nrm, P.verts).reshape(len(idx), S, M).mean(axis=1)
        same = P.face[idx][:, None] == P.face[None, :]
        ff[same] = 0.0
        Fr[idx] = ff
    return Fr


def solve_radiosity(P: Patches, Fr, E0):
    """Exitance M (lm/m2) of every patch: M = rho (E0 + Fr M)."""
    A = np.eye(len(P.area)) - P.rho[:, None] * Fr
    return np.linalg.solve(A, P.rho * E0)


def indirect_up(points, P: Patches, M, chunk=200):
    """Indirect illuminance on upward-facing points from the patch exitances."""
    E = np.zeros(len(points))
    nrm = np.tile([0.0, 0.0, 1.0], (len(points), 1))
    for z in np.unique(points[:, 2]):
        sel = np.where(points[:, 2] == z)[0]
        verts = clip_quads_z(P.verts, zmin=z)
        keep = P.face != 0                                   # floor is below
        for i0 in range(0, len(sel), chunk):
            s = sel[i0:i0 + chunk]
            ff = point_to_polys(points[s], nrm[s], verts[keep])
            E[s] = ff @ M[keep]
    return E


# ------------------------------------------------------------------ study
class Room:
    def __init__(self, cfg, phot_by_type):
        self.cfg = cfg
        L, W, H = cfg["room"]["size"]
        self.size = (L, W, H)
        self.patches = box_patches(L, W, H, cfg["radiosity_patch"], cfg["room"]["reflectance"],
                                   cfg["room"]["window"])
        self.Fr = form_factor_matrix(self.patches)
        self.phot = phot_by_type
        self.sources_all = self._sources()

    def _sources(self):
        out = []
        for lum in self.cfg["luminaires"]:
            ph = self.phot[lum["type"]]
            if "line" in lum:
                a, b = np.array(lum["line"]["start"]), np.array(lum["line"]["end"])
                n = max(1, round(np.linalg.norm(b - a) / lum["line"]["pitch"]))
                for k in range(n):
                    p = a + (k + 0.5) / n * (b - a)
                    out.append(Source(p, ph, 1.0, 0.0, lum["group"], f"{lum['id']}-{k+1:02d}"))
            else:
                out.append(Source(np.array(lum["pos"], float), ph, 1.0, lum.get("rot", 0.0),
                                  lum["group"], lum["id"]))
        return out

    def sources(self, scene=None, mf=1.0, dim=None):
        if dim is None:
            dim = self.cfg["scenes"][scene]["dim"] if scene else {}
        return [Source(s.pos, s.phot, mf * dim.get(s.group, 1.0), s.rot_deg, s.group, s.id)
                for s in self.sources_all]

    def groups(self):
        return list(dict.fromkeys(s.group for s in self.sources_all))

    def illuminance(self, points, scene=None, mf=1.0, bounce=True, dim=None):
        """Upward-facing horizontal illuminance (lx) at points."""
        src = self.sources(scene, mf, dim)
        up = np.tile([0.0, 0.0, 1.0], (len(points), 1))
        Ed = direct(points, up, src)
        if not bounce:
            return Ed, np.zeros_like(Ed)
        P = self.patches
        S = P.samples.shape[1]
        E0 = direct(P.samples.reshape(-1, 3), np.repeat(P.normal, S, axis=0), src).reshape(-1, S).mean(1)
        M = solve_radiosity(P, self.Fr, E0)
        return Ed, indirect_up(points, P, M)

    def power_w(self, scene=None, dim=None):
        if dim is None:
            dim = self.cfg["scenes"][scene]["dim"] if scene else {}
        return sum(s.phot.input_watts * dim.get(s.group, 1.0) for s in self.sources_all)

    def solve_scene(self, zone_pts, targets, bounds, mf=1.0, power_weight=0.02):
        """Dimming levels that hit zone targets (lx) with least power.

        Illuminance is linear in each group's dimming level, so one calculation
        per group gives a matrix A (zones x groups); the levels come from a
        bounded least-squares fit (relative error per zone + small power penalty).
        """
        from scipy.optimize import lsq_linear
        groups = self.groups()
        zones = list(targets)
        A = np.zeros((len(zones), len(groups)))
        for j, g in enumerate(groups):
            only = {h: (1.0 if h == g else 0.0) for h in groups}
            for i, z in enumerate(zones):
                Ed, Ei = self.illuminance(zone_pts[z], mf=mf, dim=only)
                A[i, j] = (Ed + Ei).mean()
        t = np.array([targets[z] for z in zones], float)
        Ar = A / t[:, None]                                   # relative error rows
        w = np.array([self.power_w(dim={h: (1.0 if h == g else 0.0) for h in groups}) for g in groups])
        Ap = np.vstack([Ar, power_weight * np.diag(w / w.max())])
        bp = np.concatenate([np.ones(len(zones)), np.zeros(len(groups))])
        lo = np.array([bounds.get(g, [0, 1])[0] for g in groups])
        hi = np.array([bounds.get(g, [0, 1])[1] for g in groups])
        hi = np.maximum(hi, lo + 1e-9)
        sol = lsq_linear(Ap, bp, bounds=(lo, hi))
        dim = {g: round(float(v), 3) for g, v in zip(groups, sol.x)}
        achieved = {z: round(float(A[i] @ sol.x), 1) for i, z in enumerate(zones)}
        return dim, achieved


def grid(x, y, z, spacing):
    """Cell-centred calculation grid (EN 12464-1 style), returns (N,3) and shape."""
    nx = max(1, int(round((x[1] - x[0]) / spacing)))
    ny = max(1, int(round((y[1] - y[0]) / spacing)))
    xs = x[0] + (np.arange(nx) + 0.5) * (x[1] - x[0]) / nx
    ys = y[0] + (np.arange(ny) + 0.5) * (y[1] - y[0]) / ny
    X, Y = np.meshgrid(xs, ys)
    pts = np.column_stack([X.ravel(), Y.ravel(), np.full(X.size, z)])
    return pts, X.shape, xs, ys
