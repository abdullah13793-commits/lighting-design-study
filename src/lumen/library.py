"""Generic (synthetic) luminaire photometry, written as valid LM-63 files.

These are analytic distributions, not measurements of any real product, so
they can be published freely. Swap in a manufacturer's .ies file for a real
project: the engine reads any type-C LM-63 file.
"""
import numpy as np
from .ies import Photometry

V = np.arange(0, 180.5, 2.5)


def _scale_to_flux(shape, lumens):
    p = Photometry(V, np.array([0.0]), shape[None, :])
    p.candela *= lumens / p.flux()
    return p


def downlight(lumens=900, beam_deg=60, cutoff_deg=65, watts=9.0, name="DL"):
    """Recessed downlight: cos^m with half-max at beam/2 and a soft cutoff."""
    m = np.log(0.5) / np.log(np.cos(np.radians(beam_deg / 2)))
    g = np.radians(V)
    shape = np.where(V < 90, np.cos(np.minimum(g, np.pi / 2)) ** m, 0)
    shape *= np.clip((cutoff_deg + 5 - V) / 10, 0, 1)
    p = _scale_to_flux(shape, lumens)
    p.width, p.input_watts = -0.08, watts
    p.keywords = {"LUMCAT": name, "LUMINAIRE": f"Recessed downlight {beam_deg} deg, {lumens} lm"}
    return p


def pendant(lumens=1200, down_frac=0.7, watts=12.0, name="PD"):
    """Direct-indirect pendant: down cos^2 lobe + broad up lobe."""
    g = np.radians(V)
    down = np.where(V < 90, np.cos(np.minimum(g, np.pi / 2)) ** 2, 0)
    up = np.where(V > 90, np.cos(np.pi - np.maximum(g, np.pi / 2)) ** 1, 0)
    pd_ = _scale_to_flux(down, lumens * down_frac).candela[0]
    pu = _scale_to_flux(up, lumens * (1 - down_frac)).candela[0]
    p = Photometry(V, np.array([0.0]), (pd_ + pu)[None, :])
    p.width, p.input_watts = -0.30, watts      # flat disk: ies2rad emits up and down
    p.keywords = {"LUMCAT": name, "LUMINAIRE": f"Pendant direct/indirect {int(down_frac*100)}/{int(100-down_frac*100)}, {lumens} lm"}
    return p


def uplighter(lumens=2000, up_frac=0.85, watts=20.0, name="FL"):
    """Floor uplighter: wide upward cos lobe + small diffuse downward part."""
    g = np.radians(V)
    up = np.where(V > 90, np.cos(np.pi - np.maximum(g, np.pi / 2)) ** 1.5, 0)
    down = np.where(V < 90, np.cos(np.minimum(g, np.pi / 2)), 0)
    pu = _scale_to_flux(up, lumens * up_frac).candela[0]
    pdn = _scale_to_flux(down, lumens * (1 - up_frac)).candela[0]
    p = Photometry(V, np.array([0.0]), (pu + pdn)[None, :])
    p.width, p.input_watts = -0.35, watts      # flat disk: ies2rad emits up and down
    p.keywords = {"LUMCAT": name, "LUMINAIRE": f"Floor uplighter {int(up_frac*100)}% up, {lumens} lm"}
    return p


def strip_segment(lumens=80, watts=0.7, name="UC"):
    """One 0.2 m piece of an under-cabinet LED strip (Lambertian, downward)."""
    g = np.radians(V)
    shape = np.where(V < 90, np.cos(np.minimum(g, np.pi / 2)), 0)
    p = _scale_to_flux(shape, lumens)
    p.width, p.input_watts = -0.02, watts
    p.keywords = {"LUMCAT": name, "LUMINAIRE": f"LED strip segment 0.2 m, {lumens} lm"}
    return p


FACTORY = {"downlight": downlight, "pendant": pendant, "uplighter": uplighter, "strip": strip_segment}
