"""Engine checks against closed-form cases.  python -m pytest -q tests"""
import json, sys, math
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lumen import calc, ies, library


@pytest.mark.parametrize("kind", ["downlight", "pendant", "uplighter", "strip"])
def test_flux_matches_rating(kind):
    p = library.FACTORY[kind]()
    rated = {"downlight": 900, "pendant": 1200, "uplighter": 2000, "strip": 80}[kind]
    assert p.flux() == pytest.approx(rated, rel=1e-3)


def test_lm63_roundtrip(tmp_path):
    p = library.pendant()
    p.to_lm63(tmp_path / "pd.ies")
    q = ies.read_lm63(tmp_path / "pd.ies")
    g = np.linspace(0, 180, 37)
    assert np.allclose(p.intensity(g, 0), q.intensity(g, 0), rtol=1e-3, atol=0.01)
    assert q.flux() == pytest.approx(1200, rel=2e-3)


def test_quadrant_symmetric_file(tmp_path):
    """C-plane interpolation and symmetry folding of a non-axisymmetric file."""
    v = np.array([0, 45, 90.0]); h = np.array([0, 45, 90.0])
    cd = np.array([[100, 50, 0], [100, 70, 0], [100, 90, 0]], float)
    p = ies.Photometry(v, h, cd)
    assert p.intensity(45, 90) == pytest.approx(90)
    assert p.intensity(45, 270) == pytest.approx(90)          # folded
    assert p.intensity(45, 135) == pytest.approx(70)          # 180-135 = 45
    assert p.intensity(45, 22.5) == pytest.approx(60)         # bilinear


def test_inverse_square_cosine_law():
    p = library.downlight()
    s = calc.Source(np.array([0, 0, 2.0]), p)
    pts = np.array([[0, 0, 0], [1.0, 0, 0], [2.0, 0, 0]])
    E = calc.direct(pts, np.tile([0, 0, 1.0], (3, 1)), [s])
    for (x, _, _), e in zip(pts, E):
        d = math.hypot(x, 2.0); g = math.degrees(math.atan2(x, 2.0))
        assert e == pytest.approx(p.intensity(g, 0) * (2.0 / d) / d**2, rel=1e-9)


def test_form_factor_parallel_square():
    # dA at the centre, 1x1 square at distance 1: F = 0.2395 (Howell catalogue B-3)
    v = np.array([[[-.5, -.5, 1], [.5, -.5, 1], [.5, .5, 1], [-.5, .5, 1]]], float)
    assert calc.point_to_polys(np.zeros((1, 3)), np.array([[0, 0, 1.0]]), v)[0, 0] == pytest.approx(0.23946, abs=2e-5)


def test_form_factor_perpendicular_strip():
    # dA on the floor at the foot of an infinite-ish wall: F -> 0.5
    v = np.array([[[1e-9, -500, 0], [1e-9, 500, 0], [1e-9, 500, 500], [1e-9, -500, 500]]], float)
    assert calc.point_to_polys(np.zeros((1, 3)), np.array([[0, 0, 1.0]]), v)[0, 0] == pytest.approx(0.5, abs=2e-3)


@pytest.fixture(scope="module")
def box():
    P = calc.box_patches(4.0, 3.0, 2.5, 0.25, {"ceiling": .7, "walls": .5, "floor": .2, "window": .5})
    return P, calc.form_factor_matrix(P)


def test_enclosure_rule(box):
    P, F = box
    assert np.allclose(F.sum(1), 1.0, atol=2e-3)


def test_reciprocity(box):
    P, F = box
    AF = P.area[:, None] * F
    assert np.allclose(AF, AF.T, atol=2e-4)


def test_uniform_room_integrating_sphere(box):
    """All surfaces rho, uniform first-bounce E0 -> M = rho*E0/(1-rho) (sphere formula)."""
    P, F = box
    P.rho[:] = 0.6
    M = calc.solve_radiosity(P, F, np.full(len(P.area), 100.0))
    assert np.allclose(M, 0.6 * 100 / 0.4, rtol=5e-3)


def test_energy_balance_empty_room():
    """Total flux absorbed by all surfaces equals the luminaire flux (nothing lost)."""
    cfg = json.load(open(ROOT / "config/study.json"))
    cfg = json.loads(json.dumps(cfg))
    cfg["room"]["size"] = [4.0, 3.0, 2.5]; cfg["radiosity_patch"] = 0.25
    cfg["luminaires"] = [{"id": "DL-1", "type": "DL", "group": "g", "pos": [2.0, 1.5, 2.5]}]
    room = calc.Room(cfg, {"DL": library.downlight()})
    P = room.patches; S = P.samples.shape[1]
    src = room.sources()
    E0 = calc.direct(P.samples.reshape(-1, 3), np.repeat(P.normal, S, axis=0), src).reshape(-1, S).mean(1)
    assert (E0 * P.area).sum() == pytest.approx(900, rel=0.02)       # direct flux lands on surfaces
    M = calc.solve_radiosity(P, room.Fr, E0)
    absorbed = ((E0 + room.Fr @ M) * (1 - P.rho) * P.area).sum()
    assert absorbed == pytest.approx((E0 * P.area).sum(), rel=0.01)


def test_scene_solver_is_linear_and_bounded():
    cfg = json.load(open(ROOT / "config/study.json"))
    phot = {t: library.FACTORY[s["kind"]](name=t, **{k: v for k, v in s.items() if k not in ("kind", "cct")})
            for t, s in cfg["luminaire_types"].items()}
    cfg["radiosity_patch"] = 0.5
    room = calc.Room(cfg, phot)
    zp = {z: calc.grid(d["x"], d["y"], d["z"], 0.3)[0] for z, d in cfg["zones"].items()}
    dim, ach = room.solve_scene(zp, {"living": 60, "dining_table": 80}, {"kitchen_downlights": [0, 0]})
    assert all(0 <= v <= 1 for v in dim.values()) and dim["kitchen_downlights"] == 0
    Ed, Ei = room.illuminance(zp["living"], dim=dim)
    # dimming levels are reported to 0.1 % steps (dimmer resolution), so allow 0.5 %
    assert (Ed + Ei).mean() == pytest.approx(ach["living"], rel=5e-3)
