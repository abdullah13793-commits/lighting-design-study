# SPEC — Lighting Design Study Kit (SERVICE-0001, release 2026-10-11)

## Buyer and job-to-be-done
Homeowners, interior designers, architects and small developers who need to know **how a room will be
lit before buying fixtures**: will the kitchen counter, the dining table and the living area get enough
light, how even is it, what does it cost in watts, and what will it *look* like in the evening.

Trigger to buy: a renovation or new-build with a lighting plan to sign off; an interior designer who needs
numbers behind a concept; a developer who needs marketing visuals that are also technically defensible.

## Market evidence (from `freelance_research/data`, see `product_factory/opportunities/2026-10-11_shortlist.md`)
- 97 paid jobs matching lighting design / photometric / DIALux work from 10 specialist sellers; median paid
  value $300, top jobs $2,000–2,700 ("Custom Photometric Report", "Lighting Design for Residential Building").
- Typical deliverable: DIALux evo screenshots, a false-colour plan, a luminaire schedule, sometimes renders.
- Observed gaps (hypotheses, tested by this build): (1) renders and calculations are separate artefacts, so the
  "pretty picture" is not tied to the numbers; (2) dimming scenes are chosen by eye, not computed; (3) no
  independent check of the calculation is shown; (4) static PDFs, no interactive way to compare scenes.

## Inputs
Room geometry and reflectances, window, luminaire positions, LM-63 (.ies) photometry, maintenance factor,
zone targets, scene targets — all in `config/study.json` and `config/cameras.json`.

## Deliverables and acceptance criteria
| Deliverable | Acceptance criterion | Status |
|---|---|---|
| Illuminance engine (direct + radiosity) | 14 closed-form/conservation tests pass | see tests |
| Independent validation | engine vs Radiance 6.0 on identical inputs; mean bias and MAPE reported | see `results/results.json` |
| Scene presets solved for targets | bounded least squares; achieved values reported next to targets | done |
| Zone metrics | Ē, Emin, Emax, U0, pass/fail per target, W and W/m² per scene | done |
| Daylight factor (CIE overcast, Radiance) | DF map, mean/median, % area ≥ 2 % | see results |
| Photoreal scene renders | light power from the same IES files and a measured Cycles calibration | done |
| Photometric render maps | luminance (cd/m²) and surface illuminance (lx) from the linear EXR passes; render vs engine table-top check | see `results/render_crosscheck.json` |
| Report + interactive viewer | PDF report; HTML viewer with scene switcher and before/after slider | `reports/` |

**Must-have:** engine, tests, validation, zone metrics, plans, renders, report.
**Differentiators:** solved scenes, calibrated renders, luminance/illuminance render maps, sensory-calm scene,
interactive viewer. **Future:** furniture occlusion in the engine, UGR, vertical/cylindrical illuminance,
circadian (melanopic EDI) metrics, Revit/IFC import.

## Limits and human review
Empty-room calculation (furniture ignored in the numbers; it is in the renders). Generic photometry (swap in
the manufacturer's .ies files for a real project). Not a code-compliance certificate; residential targets are
editable design assumptions, not a cited standard. A qualified lighting designer/engineer should review a
real project.

## Demo scenario
Open-plan living/kitchen, 7.2 × 5.0 × 2.7 m, 13 luminaires on 5 circuits, three scenes:
**Cook & Gather** (everything on), **Dinner** (solved: table 175 lx, living 80 lx),
**Sensory Calm** (solved: no downlights, living held in 40–80 lx). The calm band draws on the author's
MSc field study of light and indoor well-being of autistic adults (DTU, 2025), where fewer than 40 lx
satisfied most occupants in summer and 60–80 lx was preferred in winter.
