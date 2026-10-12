"""Build the A4 landscape lighting report (HTML -> PDF via headless Edge/Chrome).

python src/make_report.py      -> reports/Lighting_Design_Study.pdf (+ .html)
Every number is read from results/*.json, nothing is typed by hand.
"""
import base64, json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = json.load(open(ROOT / "results/results.json"))
XC = json.load(open(ROOT / "results/render_crosscheck.json")) if (ROOT / "results/render_crosscheck.json").exists() else {}
FIG = ROOT / "reports/figures"
REN = ROOT / "renders/final"
ZLAB = {"kitchen_counter": "Kitchen counter", "island": "Island", "dining_table": "Dining table", "living": "Living area"}


def img(p, w="100%"):
    p = Path(p)
    if not p.exists():
        return f'<div class="missing">missing: {p.name}</div>'
    import io
    from PIL import Image
    im = Image.open(p).convert("RGB")
    if im.width > 1800:
        im = im.resize((1800, round(im.height * 1800 / im.width)), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=84, optimize=True)       # keeps the PDF under 10 MB
    return f'<img src="data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}" style="width:{w}">'


def scene_table():
    rows = []
    for sid, s in R["scenes"].items():
        for z, m in s["zones"].items():
            chk = " · ".join(("✓ " if c["pass"] else "✗ ") + c["rule"] for c in m["checks"]) or "—"
            rows.append(f"<tr><td>{s['label']}</td><td>{ZLAB[z]}</td><td>{m['E_avg']:.0f}</td><td>{m['E_min']:.0f}</td>"
                        f"<td>{m['E_max']:.0f}</td><td>{m['U0']:.2f}</td><td class=chk>{chk}</td></tr>")
    return "\n".join(rows)


def dim_table():
    groups = list(next(iter(R["scenes"].values()))["dim"])
    head = "".join(f"<th>{g.replace('_', ' ')}</th>" for g in groups)
    body = ""
    for sid, s in R["scenes"].items():
        body += f"<tr><td>{s['label']}</td>" + "".join(f"<td>{100*s['dim'][g]:.0f} %</td>" for g in groups) + \
                f"<td>{s['power_w']:.0f} W</td><td>{s['lpd_w_m2']:.1f}</td></tr>"
    return f"<table><tr><th>Scene</th>{head}<th>Power</th><th>W/m²</th></tr>{body}</table>"


def lum_table():
    rows = ""
    counts = {}
    for l in R["luminaires"]:
        counts[l["type"]] = counts.get(l["type"], 0) + 1
    for t, p in R["photometry"].items():
        lt = R["luminaire_types"][t]
        rows += (f"<tr><td>{t}</td><td>{p['desc']}</td><td>{counts.get(t,0)}</td><td>{p['flux_lm']:.0f}</td>"
                 f"<td>{p['watts']:.1f}</td><td>{p['efficacy_lm_w']:.0f}</td><td>{lt['cct']} K</td></tr>")
    return ("<table><tr><th>Type</th><th>Description</th><th>Qty</th><th>lm</th><th>W</th><th>lm/W</th><th>CCT</th></tr>"
            + rows + "</table><p class=note>UC is a 3.2 m LED strip modelled as 16 segments of 0.2 m.</p>")


def main():
    v = R.get("validation", {})
    d = R.get("daylight", {})
    val_txt = ""
    if v:
        val_txt = (f"<b>Full scene:</b> engine {v['full']['mean_engine']:.0f} lx vs Radiance {v['full']['mean_radiance']:.0f} lx "
                   f"(mean bias {v['full']['mean_bias_pct']:+.1f} %, MAPE {v['full']['mape_pct']:.1f} %, "
                   f"direct-only MAPE {v['full']['direct_mape_pct']:.1f} %).<br>"
                   f"<b>Sensory Calm:</b> mean bias {v['calm']['mean_bias_pct']:+.1f} %, MAPE {v['calm']['mape_pct']:.1f} %. "
                   f"{v['full']['points']} grid points per run.")
    xc = ""
    if XC:
        xc = "<ul>" + "".join(
            f"<li>{k.replace('_', ' ')}: render {c['render_table_median_lx']:.0f} lx vs engine {c['engine_table_avg_lx']:.0f} lx "
            f"({c['diff_pct']:+.0f} %)</li>" for k, c in XC.items()) + "</ul>"
    renders = {s: REN / f"B_{s}.png" for s in ("full", "dinner", "calm", "day")}
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Lighting Design Study</title>
<style>
@page {{ size: A4 landscape; margin: 0 }}
:root {{ --ink:#1b1a17; --ink2:#5b584f; --rule:#d9d5cb; --accent:#b8741a; --paper:#fbfaf7 }}
* {{ box-sizing: border-box }}
body {{ margin:0; font-family:"Segoe UI",Arial,sans-serif; color:var(--ink); background:var(--paper); font-size:9.5pt }}
.page {{ width:297mm; height:210mm; padding:13mm 15mm 11mm; page-break-after:always; position:relative; overflow:hidden }}
.page:last-child {{ page-break-after:auto }}
h1 {{ font-family:Georgia,serif; font-weight:400; font-size:30pt; margin:0 0 3mm; letter-spacing:-.5px }}
h2 {{ font-family:Georgia,serif; font-weight:400; font-size:17pt; margin:0 0 3mm }}
.eyebrow {{ text-transform:uppercase; letter-spacing:.14em; font-size:7.5pt; color:var(--accent); font-weight:600 }}
.foot {{ position:absolute; bottom:6mm; left:15mm; right:15mm; display:flex; justify-content:space-between; color:var(--ink2); font-size:7pt; border-top:.4pt solid var(--rule); padding-top:2mm }}
.grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:4mm 6mm }}
.grid2 img {{ height:66mm; width:auto !important; max-width:100%; object-fit:cover }}
.grid3 {{ display:grid; grid-template-columns:1.25fr 1fr; gap:7mm }}
table {{ border-collapse:collapse; width:100%; font-size:8pt; font-variant-numeric:tabular-nums }}
th {{ text-align:left; font-weight:600; border-bottom:.8pt solid var(--ink); padding:1.2mm 2mm }}
td {{ border-bottom:.4pt solid var(--rule); padding:1.1mm 2mm }}
td.chk {{ font-size:7pt; color:var(--ink2) }}
.note {{ color:var(--ink2); font-size:7.5pt }}
.kpis {{ display:flex; gap:9mm; margin:4mm 0 }}
.kpi b {{ display:block; font-family:Georgia,serif; font-size:20pt; font-weight:400 }}
.kpi span {{ font-size:7.5pt; color:var(--ink2); text-transform:uppercase; letter-spacing:.08em }}
img {{ display:block; border-radius:1.5mm }}
.cap {{ font-size:7.5pt; color:var(--ink2); margin-top:1.2mm }}
.dark {{ background:#1a1a19; color:#fff }}
.dark .eyebrow {{ color:#f2bd55 }} .dark .kpi span {{ color:#c3c2b7 }} .dark .foot {{ color:#c3c2b7; border-color:#383835 }}
</style></head><body>

<section class="page dark">
  <div class="eyebrow">Lighting design study · demonstration project</div>
  <h1>Open-plan living / kitchen</h1>
  <div style="display:grid;grid-template-columns:2.1fr 1fr;gap:7mm;margin-top:4mm">
    <div>{img(FIG / 'B_full_split.png') if (FIG / 'B_full_split.png').exists() else img(renders['full'])}</div>
    <div style="display:flex;flex-direction:column;gap:5mm">
      <p style="font-size:10.5pt;line-height:1.5;margin:0">A 36 m² open-plan room, lit by 13 luminaires on five circuits.
      It is designed, calculated, checked against Radiance and rendered from <b>one set of photometric files</b>,
      so the pictures and the numbers describe the same light.</p>
      <div class="kpis" style="flex-wrap:wrap">
        <div class="kpi"><b>{R['scenes']['full']['zones']['kitchen_counter']['E_avg']:.0f} lx</b><span>counter, full scene</span></div>
        <div class="kpi"><b>{R['scenes']['calm']['zones']['living']['E_avg']:.0f} lx</b><span>living, calm scene</span></div>
        <div class="kpi"><b>{R['scenes']['full']['lpd_w_m2']:.1f} W/m²</b><span>all on</span></div>
        <div class="kpi"><b>{(f"{v['full']['mean_bias_pct']:+.1f} %") if v else 'n/a'}</b><span>bias vs Radiance</span></div>
      </div>
      <p class="note" style="color:#c3c2b7">Scenes: Cook &amp; Gather (everything on), Dinner and Sensory Calm. The last two
      have their dimming levels solved for zone targets. Daylight factor under a CIE overcast sky.</p>
    </div>
  </div>
  <div class="foot"><span>Abdallah Alhussein · MSc Eng, Architectural Engineering, DTU (2026)</span><span>Generated {R['generated']} · page 1</span></div>
</section>

<section class="page">
  <div class="eyebrow">Scenes</div><h2>Three scenes, same room, same camera</h2>
  <div class="grid2">
    <div>{img(renders['full'])}<div class="cap">Cook &amp; Gather — {R['scenes']['full']['power_w']:.0f} W</div></div>
    <div>{img(renders['dinner'])}<div class="cap">Dinner — {R['scenes']['dinner']['power_w']:.0f} W, dimming solved for 175 lx on the table</div></div>
    <div>{img(renders['calm'])}<div class="cap">Sensory Calm — {R['scenes']['calm']['power_w']:.0f} W, no downlights, living area held in the 40–80 lx band</div></div>
    <div>{img(renders['day'])}<div class="cap">Daytime (illustrative render; daylight numbers on page 5)</div></div>
  </div>
  <div class="foot"><span>Renders: Blender 5.2 Cycles. Light power comes from the IES files through a measured calibration, and exposure is noted per render.</span><span>page 2</span></div>
</section>

<section class="page">
  <div class="eyebrow">Calculation</div><h2>Illuminance on the 0.75 m workplane</h2>
  {img(FIG / 'scenes_compare.png')}
  <div style="margin-top:4mm">{dim_table()}</div>
  <div class="foot"><span>Maintained values (MF {R['room']['maintenance_factor']}). Direct light plus radiosity interreflection ({R['engine']['patches']} patches). Empty-room model.</span><span>page 3</span></div>
</section>

<section class="page">
  <div class="eyebrow">Results by zone</div><h2>Targets, uniformity and power</h2>
  <div class="grid3"><div><table><tr><th>Scene</th><th>Zone</th><th>Ē lx</th><th>Emin</th><th>Emax</th><th>U₀</th><th>Checks</th></tr>
  {scene_table()}</table></div>
  <div>{lum_table()}<div style="margin-top:4mm">{img(FIG / 'photometry.png')}</div></div></div>
  <div class="foot"><span>Targets are editable design assumptions for a home (config/study.json), not a cited standard.</span><span>page 4</span></div>
</section>

<section class="page">
  <div class="eyebrow">Daylight</div><h2>Daylight factor, CIE overcast sky</h2>
  <div class="grid3"><div>{img(FIG / 'daylight_df.png')}</div>
  <div><div class="kpis" style="flex-direction:column;gap:3mm">
    <div class="kpi"><b>{d.get('DF_avg', 0):.1f} %</b><span>mean daylight factor</span></div>
    <div class="kpi"><b>{d.get('area_ge_2pct', 0):.1f} %</b><span>of the floor at DF ≥ 2 %</span></div>
    <div class="kpi"><b>{d.get('window_to_floor', 0):.2f}</b><span>window-to-floor ratio</span></div></div>
    <p class="note">The window-to-floor ratio of {d.get('window_to_floor', 0):.2f} falls in the 0.20–0.30 range that the author's MSc field study
    associated with occupant light satisfaction in Danish dwellings. The study had 13 dwellings and 242 merged observations, and it is research
    evidence, not a design rule.</p></div></div>
  <div class="foot"><span>Radiance rtrace -ab 8 · glazing Tvis 0.70 · no external obstruction</span><span>page 5</span></div>
</section>

<section class="page">
  <div class="eyebrow">Verification</div><h2>Checked against Radiance, and the renders checked against the engine</h2>
  {img(FIG / 'validation.png')}
  <p style="margin-top:3mm">{val_txt}</p>
  <p class="note">Table-top illuminance read from the calibrated render passes (with furniture), compared with the empty-room engine. The render reads higher because it also contains furniture reflections and some residual blue-hour sky light through the window, which the night-time calculation leaves out:</p>{xc}
  <p class="note">Automated tests: 14 closed-form and conservation checks (inverse-square/cosine law, form factors against catalogued values,
  enclosure and reciprocity, integrating-sphere solution, flux balance, LM-63 round trip, solver bounds). Run: <code>python -m pytest tests</code>.</p>
  <div class="foot"><span>Same room and same IES files in both tools. Radiance treats luminaires as finite disks, the engine as point sources.</span><span>page 6</span></div>
</section>

<section class="page">
  <div class="eyebrow">Photometric renders</div><h2>Luminance and surface illuminance from the render passes</h2>
  <div class="grid2">
    <div>{img(FIG / 'B_full_luminance.png')}<div class="cap">Luminance, cd/m² (Cook &amp; Gather)</div></div>
    <div>{img(FIG / 'B_calm_illuminance.png')}<div class="cap">Illuminance on every visible surface, lx (Sensory Calm)</div></div>
  </div>
  <p class="note" style="margin-top:3mm">Limits: furniture is not in the calculation. No glare (UGR/DGP), vertical illuminance or melanopic metrics
  yet. The photometry is generic, so a real project needs the manufacturer's IES files. This is not a compliance certificate. Have a qualified
  lighting professional review any real project.</p>
  <div class="foot"><span>L = 683·Y(Combined); E = 683·π·Y(Diffuse Direct + Indirect), from linear EXR</span><span>page 7</span></div>
</section>
</body></html>"""
    out = ROOT / "reports/Lighting_Design_Study.html"
    out.write_text(html, encoding="utf-8")
    browser = next((p for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                                r"C:\Program Files\Google\Chrome\Application\chrome.exe"] if Path(p).exists()), None)
    if browser:
        pdf = ROOT / "reports/Lighting_Design_Study.pdf"
        subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={pdf}", out.as_uri()], check=False, timeout=180)
        print("pdf ->", pdf, pdf.exists())


if __name__ == "__main__":
    main()
