"""Build the study room in Blender/Cycles from config/study.json and render a lighting scene.

Light power comes from the IES photometry and the Cycles calibration
(results/blender/calibration_*.json), so the linear EXR is in physical units:
    luminance  [cd/m2] = 683 * Y(Combined)
    illuminance [lx]   = 683 * pi * Y(DiffDir + DiffInd)      (any visible diffuse surface)

blender -b --factory-startup --python build_scene.py -- --scene calm --camera B
        [--res 1600 1200] [--samples 256] [--out renders/] [--clay]
"""
import bpy, bmesh, sys, json, math, argparse, os
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--scene", default="full")          # full | dinner | calm | day
ap.add_argument("--camera", default="B")
ap.add_argument("--res", nargs=2, type=int, default=[1600, 1200])
ap.add_argument("--samples", type=int, default=256)
ap.add_argument("--out", default=str(ROOT / "renders"))
ap.add_argument("--clay", action="store_true", help="white clay materials (for illuminance views)")
ap.add_argument("--save-blend", action="store_true")
a = ap.parse_args(argv)

cfg = json.load(open(ROOT / "config/study.json"))
res = json.load(open(ROOT / "results/results.json"))
cal = json.load(open(ROOT / "results/blender/calibration_DL.json"))
W_PER_CD = cal["watts_per_cd"]
L, W, H = cfg["room"]["size"]
win = cfg["room"]["window"]

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
col = sc.collection


# ------------------------------------------------------------------ materials
def principled(name, color, rough=0.6, spec=0.5, metal=0.0, coat=0.0, emit=None, emit_strength=0.0):
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes["Principled BSDF"]
    if a.clay and not emit:
        color, metal, coat, spec, rough = (0.62, 0.62, 0.62), 0.0, 0.0, 0.0, 1.0
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = spec
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = emit_strength
    return m


def wood_floor():
    m = principled("oak_floor", (0.38, 0.25, 0.15), rough=0.45, spec=0.5, coat=0.15)
    if a.clay:
        return m
    nt = m.node_tree; N = nt.nodes; Lk = nt.links
    b = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord")
    brick = N.new("ShaderNodeTexBrick")
    brick.offset, brick.offset_frequency = 0.37, 1
    brick.inputs["Scale"].default_value = 1.0
    brick.inputs["Mortar Size"].default_value = 0.0015
    brick.inputs["Brick Width"].default_value = 1.4
    brick.inputs["Row Height"].default_value = 0.19
    brick.inputs["Color1"].default_value = (0.46, 0.33, 0.20, 1)
    brick.inputs["Color2"].default_value = (0.30, 0.20, 0.11, 1)
    brick.inputs["Mortar"].default_value = (0.12, 0.08, 0.05, 1)
    mp = N.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1.0, 22.0, 1.0)
    noise = N.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 6.0
    noise.inputs["Detail"].default_value = 8.0
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 0.55
    Lk.new(tc.outputs["Object"], brick.inputs["Vector"])
    Lk.new(tc.outputs["Object"], mp.inputs["Vector"])
    Lk.new(mp.outputs["Vector"], noise.inputs["Vector"])
    Lk.new(brick.outputs["Color"], mix.inputs["A"])
    Lk.new(noise.outputs["Color"], mix.inputs["B"])
    Lk.new(mix.outputs["Result"], b.inputs["Base Color"])
    rr = N.new("ShaderNodeMapRange"); rr.inputs["To Min"].default_value = 0.35; rr.inputs["To Max"].default_value = 0.6
    Lk.new(noise.outputs["Fac"], rr.inputs["Value"]); Lk.new(rr.outputs["Result"], b.inputs["Roughness"])
    return m


def wood(name, c1, c2, scale=(1.0, 40.0, 1.0), rough=(0.35, 0.55), coat=0.1):
    """Procedural wood: stretched noise grain + wave rings, two-tone, roughness follows grain."""
    m = principled(name, c1, rough=rough[0], spec=0.5, coat=coat)
    if a.clay:
        return m
    nt = m.node_tree; N = nt.nodes; Lk = nt.links; b = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord"); mp = N.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = scale
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 3.0; nz.inputs["Detail"].default_value = 10.0
    nz.inputs["Distortion"].default_value = 0.6
    wv = N.new("ShaderNodeTexWave"); wv.inputs["Scale"].default_value = 1.6; wv.inputs["Distortion"].default_value = 6.0
    wv.inputs["Detail"].default_value = 4.0
    mx = N.new("ShaderNodeMix"); mx.data_type = "FLOAT"; mx.inputs["Factor"].default_value = 0.5
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c2, 1); ramp.color_ramp.elements[1].color = (*c1, 1)
    rr = N.new("ShaderNodeMapRange"); rr.inputs["To Min"].default_value = rough[0]; rr.inputs["To Max"].default_value = rough[1]
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.08; bump.inputs["Distance"].default_value = 0.002
    Lk.new(tc.outputs["Object"], mp.inputs["Vector"]); Lk.new(mp.outputs["Vector"], nz.inputs["Vector"])
    Lk.new(mp.outputs["Vector"], wv.inputs["Vector"])
    Lk.new(nz.outputs["Fac"], mx.inputs["A"]); Lk.new(wv.outputs["Fac"], mx.inputs["B"])
    Lk.new(mx.outputs["Result"], ramp.inputs["Fac"]); Lk.new(ramp.outputs["Color"], b.inputs["Base Color"])
    Lk.new(mx.outputs["Result"], rr.inputs["Value"]); Lk.new(rr.outputs["Result"], b.inputs["Roughness"])
    Lk.new(mx.outputs["Result"], bump.inputs["Height"]); Lk.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def fabric(name, color):
    m = principled(name, color, rough=1.0, spec=0.1)
    if a.clay:
        return m
    nt = m.node_tree; N = nt.nodes; b = N["Principled BSDF"]
    b.inputs["Sheen Weight"].default_value = 0.4
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 180.0; nz.inputs["Detail"].default_value = 2.0
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.25; bump.inputs["Distance"].default_value = 0.001
    nt.links.new(nz.outputs["Fac"], bump.inputs["Height"]); nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def glass():
    m = bpy.data.materials.new("glass")
    nt = m.node_tree; N = nt.nodes
    for n in list(N):
        if n.type != "OUTPUT_MATERIAL":
            N.remove(n)
    tr = N.new("ShaderNodeBsdfTransparent")
    gl = N.new("ShaderNodeBsdfGlossy"); gl.inputs["Roughness"].default_value = 0.02
    fr = N.new("ShaderNodeFresnel"); fr.inputs["IOR"].default_value = 1.52
    mx = N.new("ShaderNodeMixShader")
    nt.links.new(fr.outputs[0], mx.inputs[0]); nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(gl.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], N["Material Output"].inputs[0])
    return m


rho = cfg["room"]["reflectance"]
M = dict(
    wall=principled("wall", (rho["walls"], rho["walls"] * 0.97, rho["walls"] * 0.92), rough=0.9, spec=0.3),
    ceiling=principled("ceiling", (rho["ceiling"],) * 3, rough=0.95, spec=0.2),
    floor=wood_floor(),
    counter=principled("stone", (0.72, 0.70, 0.66), rough=0.25, spec=0.6),
    cabinet=principled("cabinet", (0.10, 0.15, 0.14), rough=0.5, spec=0.4),
    oak=wood("walnut", (0.22, 0.13, 0.07), (0.12, 0.07, 0.035), rough=(0.32, 0.5), coat=0.2),
    black=principled("black_metal", (0.02, 0.02, 0.02), rough=0.35, spec=0.5, metal=0.6),
    brass=principled("brass", (0.80, 0.58, 0.30), rough=0.25, metal=1.0),
    fabric=fabric("fabric", (0.34, 0.32, 0.29)),
    fabric2=fabric("fabric_rust", (0.40, 0.17, 0.09)),
    rug=principled("rug", (0.55, 0.52, 0.47), rough=1.0, spec=0.05),
    frame=principled("frame", (0.03, 0.03, 0.03), rough=0.4, metal=0.5),
    art=principled("art", (0.70, 0.45, 0.30), rough=0.8),
    art2=principled("art2", (0.42, 0.46, 0.38), rough=0.85),
    ceramic=principled("ceramic", (0.80, 0.77, 0.70), rough=0.3, spec=0.5),
    ceramic2=principled("ceramic2", (0.12, 0.12, 0.11), rough=0.4, spec=0.5),
    leaf=principled("leaf", (0.05, 0.16, 0.06), rough=0.6),
    pot=principled("pot", (0.60, 0.55, 0.50), rough=0.7),
    grass=principled("grass", (0.10, 0.13, 0.05), rough=1.0, spec=0.1),
    tree=principled("tree", (0.03, 0.05, 0.025), rough=0.9),
    trim=principled("trim", (1, 1, 1), emit=(1.0, 0.85, 0.65), emit_strength=8.0),
    glass=glass(),
)


# ------------------------------------------------------------------ geometry helpers
def box(name, x0, x1, y0, y1, z0, z1, mat, bevel=0.006, shadow=True):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    r = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(x1 - x0, y1 - y0, z1 - z0), verts=bm.verts)
    bmesh.ops.translate(bm, vec=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), verts=bm.verts)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    me.materials.append(mat)
    if bevel:
        md = ob.modifiers.new("bevel", "BEVEL"); md.width = bevel; md.segments = 2
        md.harden_normals = False
    ob.visible_shadow = shadow
    return ob


def cyl(name, x, y, z0, z1, r, mat, seg=32, r2=None, shadow=True, smooth=True):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2,
                          depth=z1 - z0)
    bmesh.ops.translate(bm, vec=(x, y, (z0 + z1) / 2), verts=bm.verts)
    if smooth:
        for f in bm.faces:
            f.smooth = abs(f.normal.z) < 0.9
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    me.materials.append(mat)
    ob.visible_shadow = shadow
    return ob


def sphere(name, x, y, z, r, mat, scale=(1, 1, 1), shadow=True):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=r)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location, ob.scale = (x, y, z), scale
    col.objects.link(ob)
    me.materials.append(mat)
    ob.visible_shadow = shadow
    return ob


def hide_from_light(ob):
    """Fixture housings: seen by camera/reflections but they do not block or emit light
    (the IES distribution already contains the luminaire's optics)."""
    ob.visible_shadow = False
    ob.visible_diffuse = False
    return ob


# ------------------------------------------------------------------ shell (thick walls)
T = 0.2
box("floor", -T, L + T, -T, W + T, -T, 0, M["floor"], bevel=0)
box("ceiling", -T, L + T, -T, W + T, H, H + T, M["ceiling"], bevel=0)
box("wall_x0", -T, 0, 0, W, 0, H, M["wall"], bevel=0)
box("wall_x1", L, L + T, 0, W, 0, H, M["wall"], bevel=0)
box("wall_y1", 0, L, W, W + T, 0, H, M["wall"], bevel=0)
x0, x1 = win["x"]; z0, z1 = win["z"]
box("wall_y0_l", 0, x0, -T, 0, 0, H, M["wall"], bevel=0)
box("wall_y0_r", x1, L, -T, 0, 0, H, M["wall"], bevel=0)
box("wall_y0_b", x0, x1, -T, 0, 0, z0, M["wall"], bevel=0)
box("wall_y0_t", x0, x1, -T, 0, z1, H, M["wall"], bevel=0)
# window frame + mullions + glass
fw = 0.05
for nm, (ax0, ax1, az0, az1) in {"fb": (x0, x1, z0, z0 + fw), "ft": (x0, x1, z1 - fw, z1),
                                 "fl": (x0, x0 + fw, z0, z1), "fr": (x1 - fw, x1, z0, z1)}.items():
    box("win_" + nm, ax0, ax1, -0.12, -0.06, az0, az1, M["frame"], bevel=0.003)
for k in (1, 2):
    xm = x0 + k * (x1 - x0) / 3
    box(f"win_m{k}", xm - fw / 2, xm + fw / 2, -0.12, -0.06, z0, z1, M["frame"], bevel=0.003)
g = box("glass", x0, x1, -0.095, -0.085, z0, z1, M["glass"], bevel=0)
box("sill", x0 - 0.05, x1 + 0.05, -0.06, 0.04, z0 - 0.03, z0, M["stone"] if "stone" in M else M["counter"], bevel=0.004)
box("skirting", 0, L, W - 0.012, W, 0, 0.08, M["wall"], bevel=0.002)

# ------------------------------------------------------------------ kitchen
box("base_cab", 0, 0.60, 1.0, 4.4, 0.10, 0.86, M["cabinet"])
box("plinth", 0, 0.55, 1.0, 4.4, 0, 0.10, M["black"], bevel=0)
box("counter", 0, 0.65, 0.98, 4.42, 0.86, 0.90, M["counter"], bevel=0.004)
for i in range(6):                                           # door gaps
    y = 1.0 + (i + 1) * 3.4 / 6
    box(f"gap{i}", 0.600, 0.604, y - 0.002, y + 0.002, 0.12, 0.84, M["black"], bevel=0)
box("upper_cab", 0, 0.35, 1.0, 4.4, 1.50, 2.30, M["cabinet"])
box("tall_cab", 0, 0.65, 4.42, 5.0, 0, 2.30, M["cabinet"])
box("backsplash", 0, 0.012, 1.0, 4.4, 0.90, 1.50, M["counter"], bevel=0)
box("hob", 0.12, 0.52, 2.45, 3.05, 0.90, 0.905, M["black"], bevel=0.002)
# under-cabinet strip housing (emissive line, hidden from lighting)
# (strip housing is created with the luminaires, so its glow follows the dimming)
# island + stools
box("island", 1.62, 2.48, 1.62, 3.78, 0, 0.86, M["oak"])
box("island_top", 1.60, 2.50, 1.60, 3.80, 0.86, 0.90, M["counter"], bevel=0.004)
# ------------------------------------------------------------------ dining
box("table_top", 3.15, 4.05, 1.70, 3.50, 0.72, 0.75, M["oak"], bevel=0.004)
for (tx, ty) in ((3.22, 1.77), (3.98, 1.77), (3.22, 3.43), (3.98, 3.43)):
    box("table_leg", tx - 0.03, tx + 0.03, ty - 0.03, ty + 0.03, 0, 0.72, M["oak"], bevel=0.002)
for side, xs in ((1, 4.35),):
    for y in (2.05, 2.6, 3.15):
        box("chair_seat", xs - 0.22, xs + 0.22, y - 0.21, y + 0.21, 0.43, 0.47, M["oak"], bevel=0.004)
        bx = xs + side * 0.20
        box("chair_back", bx - 0.02, bx + 0.02, y - 0.20, y + 0.20, 0.47, 0.86, M["oak"], bevel=0.004)
        for (cx, cy) in ((xs - 0.19, y - 0.18), (xs + 0.19, y - 0.18), (xs - 0.19, y + 0.18), (xs + 0.19, y + 0.18)):
            box("chair_leg", cx - 0.016, cx + 0.016, cy - 0.016, cy + 0.016, 0, 0.43, M["black"], bevel=0)
box("bowl", 3.52, 3.68, 2.52, 2.68, 0.75, 0.80, M["pot"], bevel=0.02)
# ------------------------------------------------------------------ living
box("rug", 4.85, 6.95, 2.25, 4.35, 0, 0.012, M["rug"], bevel=0.003)
box("sofa_base", 4.60, 6.70, 4.05, 4.95, 0.08, 0.42, M["fabric"], bevel=0.03)
box("sofa_back", 4.60, 6.70, 4.70, 4.95, 0.42, 0.85, M["fabric"], bevel=0.04)
box("sofa_arm_l", 4.60, 4.80, 4.05, 4.95, 0.42, 0.62, M["fabric"], bevel=0.04)
box("sofa_arm_r", 6.50, 6.70, 4.05, 4.95, 0.42, 0.62, M["fabric"], bevel=0.04)
for i in range(3):
    cx = 4.80 + (i + 0.5) * 1.70 / 3
    box(f"cushion{i}", cx - 0.27, cx + 0.27, 4.10, 4.70, 0.42, 0.52, M["fabric"], bevel=0.04)
box("pillow", 4.95, 5.35, 4.55, 4.70, 0.50, 0.85, M["fabric2"], bevel=0.05)
cyl("coffee_table", 5.95, 3.30, 0.36, 0.40, 0.45, M["oak"], seg=64)
cyl("coffee_leg", 5.95, 3.30, 0.0, 0.36, 0.06, M["black"])
box("armchair", 6.05, 6.85, 0.75, 1.50, 0.08, 0.42, M["fabric2"], bevel=0.04)
box("armchair_back", 6.05, 6.85, 0.75, 0.95, 0.42, 0.85, M["fabric2"], bevel=0.04)
box("art", 5.40, 6.60, W - 0.03, W - 0.01, 1.30, 2.05, M["art"], bevel=0.002)
box("art_frame", 5.37, 6.63, W - 0.025, W - 0.012, 1.27, 2.08, M["frame"], bevel=0.002)
cyl("plant_pot", 0.95, 0.45, 0.0, 0.42, 0.20, M["pot"], r2=0.17)
for i, (dx, dy, dz, s) in enumerate([(0, 0, 0.9, 0.28), (0.12, 0.05, 1.15, 0.22), (-0.1, -0.06, 1.25, 0.2),
                                    (0.05, -0.1, 0.7, 0.24), (-0.05, 0.1, 1.45, 0.16)]):
    sphere(f"leaf{i}", 0.95 + dx, 0.45 + dy, dz, s, M["leaf"], scale=(1, 0.8, 1.3))
# sideboard and art on the end wall (seen from camera B)
box("sideboard", L - 0.45, L, 2.0, 3.8, 0.12, 0.70, M["oak"], bevel=0.004)
box("sideboard_plinth", L - 0.42, L, 2.05, 3.75, 0, 0.12, M["black"], bevel=0)
for i in range(3):
    yy = 2.0 + (i + 1) * 1.8 / 4
    box(f"sb_gap{i}", L - 0.452, L - 0.448, yy - 0.002, yy + 0.002, 0.15, 0.67, M["black"], bevel=0)
box("art2", L - 0.03, L - 0.01, 2.35, 3.45, 1.10, 1.95, M["art2"], bevel=0.002)
box("art2_frame", L - 0.025, L - 0.012, 2.32, 3.48, 1.07, 1.98, M["frame"], bevel=0.002)
cyl("vase", L - 0.22, 2.35, 0.70, 1.02, 0.08, M["ceramic"], r2=0.05, seg=48)
cyl("bowl2", L - 0.22, 3.30, 0.70, 0.76, 0.14, M["ceramic2"], r2=0.10, seg=48)
for i, (h, c) in enumerate(((0.035, "fabric2"), (0.03, "ceramic"), (0.04, "black"))):
    box(f"book{i}", L - 0.36, L - 0.12, 2.85, 3.10, 0.70 + 0.04 * i, 0.70 + 0.04 * i + h, M[c], bevel=0.002)

# ------------------------------------------------------------------ exterior (seen through the window)
box("ground", -40, 50, -60, -T, -0.3, -0.25, M["grass"], bevel=0)
for i, (hx0, hx1, hy, hh) in enumerate([(-60, 70, -90, 1.6)]):           # distant tree line
    box(f"hedge{i}", hx0, hx1, hy - 1.5, hy, -0.25, hh, M["tree"], bevel=0)

# ------------------------------------------------------------------ luminaires
dims = res["scenes"].get(a.scene, {}).get("dim", {}) if a.scene != "day" else {}
mf = cfg["room"]["maintenance_factor"]
types = cfg["luminaire_types"]
peak = {t: res["photometry"][t]["peak_cd"] for t in types}


def ies_light(name, loc, typ, scale, radius):
    ld = bpy.data.lights.new(name, "POINT")
    # Cycles: P[W] = watts_per_cd * (cd scaling); candela values come from the IES file itself
    ld.energy = W_PER_CD * scale
    ld.shadow_soft_size = radius
    ld.use_temperature = True
    ld.temperature = types[typ]["cct"]
    ld.use_nodes = True
    n = ld.node_tree.nodes.new("ShaderNodeTexIES")
    n.mode = "EXTERNAL"
    n.filepath = str(ROOT / "data/ies" / f"{typ}.ies")
    ld.node_tree.links.new(n.outputs["Fac"], ld.node_tree.nodes["Emission"].inputs["Strength"])
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    ob.visible_camera = False
    col.objects.link(ob)
    return ob


on = lambda grp: dims.get(grp, 0.0) if a.scene != "day" else 0.0
_glow = {}


def glow(s, off):
    """Visible emitter surface whose brightness follows the dimming level (not photometric)."""
    if s <= 0:
        return M[off]
    k = round(s, 2)
    if k not in _glow:
        _glow[k] = principled(f"glow_{k}", (1, 1, 1), emit=(1.0, 0.85, 0.65), emit_strength=10.0 * k)
    return _glow[k]


for lum in cfg["luminaires"]:
    s = on(lum["group"]) * mf
    typ = lum["type"]
    if "line" in lum:
        p0, p1 = Vector(lum["line"]["start"]), Vector(lum["line"]["end"])
        n = max(1, round((p1 - p0).length / lum["line"]["pitch"]))
        hide_from_light(box("uc_strip", 0.30, 0.34, 1.05, 4.35, 1.485, 1.50, glow(s, "black"), bevel=0))
        for k in range(n):
            if s > 0:
                ies_light(f"{lum['id']}-{k}", p0 + (k + 0.5) / n * (p1 - p0), typ, s, 0.01)
        continue
    x, y, z = lum["pos"]
    if typ == "DL":
        hide_from_light(cyl(lum["id"] + "_trim", x, y, H - 0.008, H - 0.004, 0.055,
                            glow(s, "black"), seg=32))
        cyl(lum["id"] + "_ring", x, y, H - 0.004, H - 0.001, 0.07, M["black"], seg=32, r2=0.07)
        if s > 0:
            ies_light(lum["id"], (x, y, H - 0.015), typ, s, 0.03)
    elif typ == "PD":
        hide_from_light(cyl(lum["id"] + "_shade", x, y, z, z + 0.20, 0.22, M["brass"], seg=48, r2=0.05))
        hide_from_light(cyl(lum["id"] + "_diff", x, y, z - 0.005, z + 0.002, 0.20,
                            glow(s, "pot"), seg=48))
        cyl(lum["id"] + "_cord", x, y, z + 0.2, H, 0.004, M["black"], seg=8)
        if s > 0:
            ies_light(lum["id"], (x, y, z), typ, s, 0.08)
    elif typ == "FL":
        cyl(lum["id"] + "_pole", x, y, 0.02, z - 0.08, 0.012, M["black"], seg=12)
        cyl(lum["id"] + "_base", x, y, 0, 0.02, 0.14, M["black"], seg=32)
        hide_from_light(cyl(lum["id"] + "_bowl", x, y, z - 0.10, z, 0.06, M["black"], seg=48, r2=0.18))
        hide_from_light(cyl(lum["id"] + "_glow", x, y, z - 0.002, z + 0.001, 0.17,
                            glow(s, "black"), seg=48))
        if s > 0:
            ies_light(lum["id"], (x, y, z + 0.02), typ, s, 0.10)

# ------------------------------------------------------------------ world / sky
world = bpy.data.worlds.new("sky")
sc.world = world
wn = world.node_tree.nodes
sky = wn.new("ShaderNodeTexSky")
sky.sky_type = "MULTIPLE_SCATTERING"
bg = wn["Background"]
world.node_tree.links.new(sky.outputs["Color"], bg.inputs["Color"])
if a.scene == "day":
    sky.sun_elevation = math.radians(32); sky.sun_rotation = math.radians(200)
    sky.sun_disc = False
    bg.inputs["Strength"].default_value = 1.0
    sun = bpy.data.lights.new("sun", "SUN")
    sun.angle = math.radians(0.53)
    sun.energy = 3.5
    so = bpy.data.objects.new("sun", sun)
    so.rotation_euler = (math.radians(90 - 32), 0, math.radians(200 - 180))
    col.objects.link(so)
else:   # blue hour behind the glass
    sky.sun_elevation = math.radians(-3.5); sky.sun_rotation = math.radians(250)
    bg.inputs["Strength"].default_value = 0.6

# ------------------------------------------------------------------ cameras
cams = json.load(open(ROOT / "config/cameras.json"))      # shared with render_maps.py
cam = cams[a.camera]
loc, tgt, f = cam["loc"], cam["target"], cam["lens_mm"]
cd = bpy.data.cameras.new("cam"); cd.lens = f; cd.sensor_width = 36; cd.sensor_fit = "HORIZONTAL"
cd.clip_start = 0.05
co = bpy.data.objects.new("cam", cd); col.objects.link(co)
co.location = loc
d = Vector(tgt) - Vector(loc)
yaw = math.atan2(-d.x, d.y)
co.rotation_euler = (math.radians(90), 0, yaw)       # level camera: verticals stay vertical
cd.shift_y = cam.get("shift_y", 0.0)
sc.camera = co

# ------------------------------------------------------------------ render settings
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = a.samples
sc.cycles.use_adaptive_sampling = True
sc.cycles.adaptive_threshold = 0.02
sc.cycles.use_denoising = True
try:
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
except Exception:
    pass
sc.cycles.max_bounces = 8
sc.cycles.diffuse_bounces = 5
sc.cycles.glossy_bounces = 3
sc.cycles.transparent_max_bounces = 8
sc.cycles.transmission_bounces = 4
sc.cycles.sample_clamp_indirect = 10.0
sc.cycles.use_light_tree = True
sc.render.resolution_x, sc.render.resolution_y = a.res
sc.render.resolution_percentage = 100
sc.view_settings.view_transform = "AgX"
try:
    sc.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass

# exposure from the calculated workplane illuminance (camera-like), noted in the render log
E_ref = res["scenes"][a.scene]["floor_grid"]["E_avg"] if a.scene in res["scenes"] else None
if a.scene == "day":
    ev = 0.4
else:
    # partial compensation: dim scenes still look dimmer, as they would to the eye
    E_full = res["scenes"]["full"]["floor_grid"]["E_avg"]
    ev = 1.7 + 0.45 * math.log2(E_full / E_ref)
sc.view_settings.exposure = ev
try:                                    # warm, but not orange (camera white balance)
    sc.view_settings.use_white_balance = True
    sc.view_settings.white_balance_temperature = 3700 if a.scene != "day" else 7200
except Exception as e:
    print("no white balance:", e)

vl = sc.view_layers[0]
vl.use_pass_diffuse_direct = True
vl.use_pass_diffuse_indirect = True
vl.use_pass_diffuse_color = True
sc.render.use_compositing = False          # write raw render-layer passes into the multilayer EXR

out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
stem = f"{a.camera}_{a.scene}" + ("_clay" if a.clay else "")
if hasattr(sc.render.image_settings, "media_type"):          # Blender 5.x
    sc.render.image_settings.media_type = "MULTI_LAYER_IMAGE"
    sc.render.image_settings.file_format = "OPEN_EXR_MULTILAYER"
else:
    sc.render.image_settings.file_format = "OPEN_EXR_MULTILAYER"
sc.render.image_settings.color_depth = "32"
sc.render.image_settings.exr_codec = "ZIP"
sc.render.filepath = str(out / f"{stem}.exr")
if a.save_blend:
    bpy.ops.wm.save_as_mainfile(filepath=str(out / f"{stem}.blend"))
import time
t = time.time()
bpy.ops.render.render(write_still=True)
dt = time.time() - t
img = bpy.data.images["Render Result"]
s2 = sc.render.image_settings
if hasattr(s2, "media_type"):
    s2.media_type = "IMAGE"
s2.file_format = "PNG"; s2.color_depth = "8"; s2.color_mode = "RGB"
img.save_render(str(out / f"{stem}.png"), scene=sc)
json.dump(dict(scene=a.scene, camera=a.camera, exposure_ev=ev, samples=a.samples, res=a.res,
               seconds=round(dt, 1), blender=bpy.app.version_string, watts_per_cd=W_PER_CD,
               clay=a.clay), open(out / f"{stem}.json", "w"), indent=1)
print(f"RENDERED {stem} in {dt:.0f}s, EV {ev:.2f}")
