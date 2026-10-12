"""IES LM-63 photometry: read, write and evaluate type-C candela distributions.

Supports every LM-63 horizontal-symmetry case (0 deg rotationally symmetric,
0-90 quadrant, 0-180 bilateral, 0-360 full) with bilinear interpolation, so
real manufacturer files work as well as the generic files made by library.py.
"""
from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field


@dataclass
class Photometry:
    v_angles: np.ndarray            # gamma, deg, 0 = nadir
    h_angles: np.ndarray            # C-plane, deg
    candela: np.ndarray             # shape (nH, nV), absolute cd
    keywords: dict = field(default_factory=dict)
    width: float = 0.0              # luminous opening, m (negative = circular)
    length: float = 0.0
    height: float = 0.0
    input_watts: float = 0.0

    # ---------------------------------------------------------------- eval
    def intensity(self, gamma_deg, c_deg):
        """Candela towards (gamma, C). Arrays broadcast."""
        g = np.clip(np.asarray(gamma_deg, float), 0.0, 180.0)
        c = np.mod(np.asarray(c_deg, float), 360.0)
        h_max = self.h_angles[-1]
        if len(self.h_angles) == 1:                    # rotationally symmetric
            return np.interp(g, self.v_angles, self.candela[0], left=0.0, right=0.0)
        if h_max == 90:                                 # quadrant symmetric
            c = np.where(c > 180, 360 - c, c)
            c = np.where(c > 90, 180 - c, c)
        elif h_max == 180:                              # bilateral about 0-180
            c = np.where(c > 180, 360 - c, c)
        # bilinear in (C, gamma)
        ci = np.clip(np.searchsorted(self.h_angles, c, side="right") - 1, 0, len(self.h_angles) - 2)
        c0, c1 = self.h_angles[ci], self.h_angles[ci + 1]
        t = np.where(c1 > c0, (c - c0) / np.where(c1 > c0, c1 - c0, 1), 0.0)
        out = np.empty(np.broadcast(g, c).shape)
        gb, cib, tb = np.broadcast_arrays(g, ci, t)
        for k in np.unique(cib):
            m = cib == k
            a = np.interp(gb[m], self.v_angles, self.candela[k], left=0, right=0)
            b = np.interp(gb[m], self.v_angles, self.candela[k + 1], left=0, right=0)
            out[m] = a * (1 - tb[m]) + b * tb[m]
        return out

    def flux(self, n_gamma=721, n_c=73):
        """Luminous flux (lm) by numerical integration over the sphere."""
        g = np.linspace(0, 180, n_gamma)
        c = np.linspace(0, 360, n_c)[:-1]
        G, C = np.meshgrid(g, c)
        I = self.intensity(G, C).mean(axis=0)
        return 2 * np.pi * np.trapezoid(I * np.sin(np.radians(g)), np.radians(g))

    def peak(self):
        return float(self.candela.max())

    # ---------------------------------------------------------------- io
    def to_lm63(self, path):
        kw = {"TEST": "GENERIC", "MANUFAC": "Lumen Study Kit (generic photometry)",
              "LAMP": "LED module (absolute photometry)", **self.keywords}
        lines = ["IESNA:LM-63-2002"] + [f"[{k}] {v}" for k, v in kw.items()] + ["TILT=NONE"]
        length = self.width if self.width < 0 and self.length == 0 else self.length  # circular: both negative
        lines.append(f"1 -1 1 {len(self.v_angles)} {len(self.h_angles)} 1 2 "
                     f"{self.width:.3f} {length:.3f} {self.height:.3f}")
        lines.append(f"1.0 1.0 {self.input_watts:.1f}")
        lines.append(_wrap(self.v_angles))
        lines.append(_wrap(self.h_angles))
        for row in self.candela:
            lines.append(_wrap(row))
        with open(path, "w", newline="\r\n") as f:
            f.write("\n".join(lines) + "\n")


def _wrap(vals, per=10):
    vals = [f"{v:.2f}".rstrip("0").rstrip(".") if v else "0" for v in vals]
    return "\n".join(" ".join(vals[i:i + per]) for i in range(0, len(vals), per))


def read_lm63(path) -> Photometry:
    with open(path, encoding="latin-1") as f:
        text = f.read()
    head, _, rest = text.partition("TILT=")
    keywords = {}
    for line in head.splitlines():
        if line.startswith("["):
            k, _, v = line[1:].partition("]")
            keywords[k.strip()] = v.strip()
    tilt_line, _, body = rest.partition("\n")
    if tilt_line.strip() == "INCLUDE":
        tokens = body.split()
        n = int(tokens[1])
        tokens = tokens[2 + 2 * n:]
    else:
        tokens = body.split()
    t = list(map(float, tokens))
    n_lamps, lm_lamp, mult, nV, nH, ptype, units, w, l, h = t[:10]
    ballast, _, watts = t[10:13]
    nV, nH = int(nV), int(nH)
    p = 13
    v = np.array(t[p:p + nV]); p += nV
    hh = np.array(t[p:p + nH]); p += nH
    cd = np.array(t[p:p + nV * nH]).reshape(nH, nV) * mult * ballast
    if lm_lamp > 0:                                  # relative photometry
        cd = cd * 1.0                                # keep values as given (cd at rated lumens)
    k = 0.3048 if units == 1 else 1.0               # feet -> m
    return Photometry(v, hh, cd, keywords, w * k, l * k, h * k, watts)
