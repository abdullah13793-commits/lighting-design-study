# Lighting Design Study: interactive report

**Live report:** open the GitHub Pages link in this repository's "About" panel, or the `index.html` file.

![Render vs. illuminance](preview.jpg)

A demonstration lighting study for a 36 m² open-plan living/kitchen. The photoreal renders, lux plans and numbers all
come from the same IES photometric files:

- Point-by-point direct light plus radiosity interreflection, checked against LBNL Radiance (+1.4 % mean bias)
- Three scenes. Dinner and Sensory Calm have their dimming solved for lux targets at the lowest power (31-32 W)
- Blender Cycles renders calibrated so each pixel can be read as lux and cd/m². Drag the slider to compare
- Daylight factor study (CIE overcast sky)

Tools: Python, Radiance, Blender, IES (LM-63) photometry.

Demonstration project with generic photometry. It is not a compliance certificate.

Abdallah Alhussein · MSc Eng, Architectural Engineering, DTU (2026)
