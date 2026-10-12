# Case study: a lighting study where the pictures and the numbers agree

*Demonstration project, built 2026-10-11.*

**Problem.** Before buying fixtures, a homeowner or designer wants to know whether the counter, the table and the
sofa will have the right light, what it costs in watts, and what the room will feel like in the evening.

**Market pattern.** Across the 97 paid lighting jobs in my research set (10 specialist sellers, median $300 and up to
about $2.7k), the usual deliverable is a DIALux plan with false colours and a luminaire list, sometimes with separate renders. The
renders and the calculation are usually separate artefacts, scene dimming is chosen by eye, and the calculation is
rarely checked independently.

**What I built.**
- One configuration file and one set of IES files drive the calculation, the Radiance check and the Blender renders.
- Two of the three scenes are **solved**: the dimming levels hit zone targets (table 175 lx; living 40–80 lx) at the least power.
- The calculation (direct light plus radiosity, all bounces) is checked against Radiance 6.0. Full scene bias is +1.4 % and
  direct light agrees to 0.4 %.
- Cycles lights are calibrated against the photometry, so the renders also produce luminance and surface-illuminance maps.
- A daylight factor study and an interactive viewer with a render/false-colour slider are included.

**Sensory Calm scene.** My MSc thesis (DTU, 2025) analysed a 12-month field study of light and indoor well-being of
autistic adults in 13 Danish dwellings. Fewer than 40 lx satisfied most occupants in summer, and 60–80 lx was preferred in
winter. The Calm scene turns that into a target band, uses indirect light only and draws 31 W. This is research evidence
used as a design input, not a clinical claim.

**Evidence.** 14 automated checks (closed-form cases, conservation laws). Radiance comparison on 216 points per scene.
Render-vs-engine table-top check: the calibrated render reads 8-14 % above the empty-room engine, which is consistent with the furniture reflections and residual dusk sky light it contains (`results/render_crosscheck.json`).

**Tools.** Python (numpy/scipy), LBNL Radiance 6.0, Blender 5.2 Cycles, LM-63 photometry.

**Limits.** Furniture is not in the calculation, there are no glare or melanopic metrics yet, the photometry is generic,
and it is not a compliance document.

**Offer.** For your floor plan and chosen fixtures: a fixed-price lighting study with zone lux, uniformity, power, solved
scenes, calibrated renders and a PDF report, with a daylight factor study as an option.
