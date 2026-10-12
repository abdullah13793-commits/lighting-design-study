# Method

## 1. Photometry
Luminaires are described by LM-63 (IES) type-C candela tables. `src/lumen/ies.py` reads every LM-63
symmetry case (0°, 0–90°, 0–180°, 0–360°) with bilinear interpolation in (γ, C), so manufacturer files drop in.
The demo uses **generic analytic distributions** (`src/lumen/library.py`), normalised to the rated flux
(checked by numerical integration over the sphere):

| Type | Distribution | Flux | Power |
|---|---|---|---|
| DL | cosᵐγ, half-max at 30° (60° beam), soft cutoff 65–75° | 900 lm | 9 W |
| PD | 70 % down (cos²γ) / 30 % up (cos) | 1200 lm | 12 W |
| FL | 85 % up (cos^1.5) / 15 % down (cos) | 2000 lm | 20 W |
| UC | Lambertian, 0.2 m segments, 400 lm/m | 80 lm/seg | 0.7 W/seg |

## 2. Direct illuminance
E_d(P) = Σ I(γ, C) · cos θ / d², with γ measured from nadir, θ the incidence angle on the receiver.

## 3. Interreflection (radiosity)
The six room faces are split into ~0.25 m Lambertian patches (2 238 in the demo). Form factors use the
**exact differential-area-to-polygon formula**

F(dA→A) = 1/(2π) · Σₖ βₖ · (n · ĝₖ),  ĝₖ = (Rₖ × Rₖ₊₁)/|Rₖ × Rₖ₊₁|,

averaged over 2×2 receiver samples per patch. Because the room is an empty convex box, every patch on another
face is fully visible; receivers on the workplane clip wall patches to the half-space above the plane. Exitance
follows from (I − ρF) M = ρ E₀, solved directly (all bounces, no truncation). Indirect workplane illuminance is
Σ M_j F(P→A_j). Checks: enclosure rule ΣF = 1, reciprocity A_iF_ij = A_jF_ji, integrating-sphere solution
M = ρE₀/(1−ρ), and flux balance (absorbed = emitted) — see `tests/`.

## 4. Scene solving
Illuminance is linear in each circuit's dimming level, so one calculation per circuit gives a matrix
A (zones × circuits). Scene levels d ∈ [lo, hi] minimise Σ((A d)_z / t_z − 1)² + λ‖w ⊙ d‖² (relative error
per zone + a small power penalty), solved with bounded least squares (`scipy.optimize.lsq_linear`).

## 5. Metrics
Maintained values = initial × maintenance factor (0.80). Per zone: Ē, E_min, E_max, U₀ = E_min/Ē on a
cell-centred grid (0.1 m in zones, 0.2 m for the full plan). Power and LPD per scene assume linear dimming.

## 6. Independent check with Radiance
`src/lumen/radiance.py` rebuilds the identical room in LBNL Radiance 6.0, converts the same IES files with
`ies2rad`, and runs `rtrace -I` (direct: `-ab 0`; total: `-ab 8 -ad 2048 -as 512 -aa 0.1 -ar 256`).
Initial (MF = 1) values are compared point by point. Radiance models luminaires as finite emitters
(disks/cylinders from the IES dimensions) while the engine uses point sources, so small near-field
differences are expected.

## 7. Daylight factor
Radiance, CIE overcast sky (`gensky -c`) scaled to 10 000 lx unobstructed horizontal illuminance, glazing
with visible transmittance 0.70, no external obstruction, `-ab 8`. DF = E_in / E_out × 100 %.

## 8. Calibrated renders
Blender 5.2 Cycles renders the same room with furniture and materials. Each luminaire is a point light whose
**IES texture is the same LM-63 file**. A calibration render (`src/blender/calibrate.py`: one IES light over a
Lambertian plane, no world light, linear view transform) measured that **P = 0.2603 W reproduces the file's
candela as I/683 W·sr⁻¹**. The ratio was the same to 0.02 % for three different distributions, and it followed
the IES shape within 0.14 % from 0 to 60°. Light power is therefore set as 0.2603 × dimming × MF for every
light. The linear EXR is in physical units:

- luminance L = 683 · Y(Combined)  [cd/m²]
- surface illuminance E = 683 · π · Y(Diffuse Direct + Diffuse Indirect)  [lx]

Display exposure is set like a camera from the calculated workplane illuminance, with partial compensation
(0.45 EV per stop of light), so dim scenes still look dimmer. The EV used is logged next to every render.
The daylight render is illustrative; the daylight numbers come from Radiance.

## 9. Known limitations
- Furniture is ignored in the engine and Radiance (empty box); it is present in the renders. The render-derived
  table-top illuminance is reported next to the engine value so the effect is visible.
- No glare (UGR/DGP), vertical illuminance or spectral/melanopic metrics yet.
- Generic photometry; residential targets are editable design assumptions (no national standard is claimed).
