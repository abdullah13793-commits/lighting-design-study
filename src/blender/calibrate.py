"""Calibrate Cycles light power against LM-63 photometry.

Renders one IES point light (1 W) 2 m above a diffuse plane (albedo 0.5) with an
orthographic camera and a linear view transform, then reads the exitance back:
    E_bl = L * pi / rho          (W/m2, Blender radiometric units)
    I_bl(gamma) = E_bl * d^2 / cos^3(gamma)   at the point under angle gamma
Cycles' IES output relative to the file's candela gives watts_per_cd, the power
to set on a light so that it emits I_cd/683 W/sr, i.e. 1 lux == 1/683 W/m2.

blender -b --factory-startup --python calibrate.py -- <ies_file> <out_json>
"""
import bpy, sys, json, math, os, tempfile
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
ies_path, out_json = argv[0], argv[1]

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 256
sc.cycles.use_denoising = False
sc.cycles.max_bounces = 0                      # direct light only
sc.view_settings.view_transform = "Standard"
sc.view_settings.look = "None"
sc.view_settings.exposure = 0.0
sc.view_settings.gamma = 1.0
sc.render.resolution_x = sc.render.resolution_y = 81
sc.render.image_settings.file_format = "OPEN_EXR"
sc.render.image_settings.color_depth = "32"
sc.world = None                                # no ambient: direct light only

# plane 8 x 8 m at z = 0, albedo 0.5 diffuse
bpy.ops.mesh.primitive_plane_add(size=8)
mat = bpy.data.materials.new("grey")
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.5, 0.5, 0.5, 1)
bsdf.inputs["Roughness"].default_value = 1.0
bsdf.inputs["Specular IOR Level"].default_value = 0.0
bpy.context.object.data.materials.append(mat)

H = 2.0
ld = bpy.data.lights.new("ies", "POINT")
ld.energy = 1.0
ld.shadow_soft_size = 0.005
ld.use_nodes = True
lnt = ld.node_tree
ies = lnt.nodes.new("ShaderNodeTexIES")
ies.mode = "EXTERNAL"
ies.filepath = ies_path
emi = lnt.nodes["Emission"]
lnt.links.new(ies.outputs["Fac"], emi.inputs["Strength"])
lo = bpy.data.objects.new("ies", ld)
sc.collection.objects.link(lo)
lo.location = (0, 0, H)

cam = bpy.data.cameras.new("cam")
cam.type = "ORTHO"
cam.ortho_scale = 8.0
co = bpy.data.objects.new("cam", cam)
sc.collection.objects.link(co)
co.location = (0, 0, 10)
sc.camera = co

out = os.path.join(tempfile.gettempdir(), "calib.exr")
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
img = bpy.data.images.load(out)
px = np.array(img.pixels[:]).reshape(81, 81, 4)[..., 0]
# pixel centre coordinates in metres
c = (np.arange(81) + 0.5) / 81 * 8 - 4
X, Y = np.meshgrid(c, c)
r = np.hypot(X, Y)
E_bl = px * math.pi / 0.5
gamma = np.degrees(np.arctan2(r, H))
I_bl = E_bl * (r**2 + H**2) / np.cos(np.radians(gamma))  # W/sr (inverse square + cosine)

# candela of the file
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lumen.ies import read_lm63
p = read_lm63(ies_path)
I_cd = p.intensity(gamma, 0)
m = I_cd > 0.2 * I_cd.max()
ratio = I_bl[m] / I_cd[m]                    # W/sr per cd, at P = 1 W
res = dict(ies=os.path.basename(ies_path), blender=bpy.app.version_string,
           w_per_sr_per_cd_at_1W=float(np.median(ratio)), spread_pct=float(100 * ratio.std() / ratio.mean()),
           peak_cd=float(p.peak()),
           # power so that 1 cd == 1/683 W/sr
           watts_per_cd=float((1 / 683) / np.median(ratio)))
bins = np.arange(0, 75, 5)
res["profile"] = [dict(gamma=float(b), I_bl=float(I_bl[(gamma >= b) & (gamma < b + 5)].mean()),
                       I_cd=float(I_cd[(gamma >= b) & (gamma < b + 5)].mean()))
                  for b in bins if ((gamma >= b) & (gamma < b + 5)).any()]
for q in res["profile"]:
    print("PROF %5.1f  bl %.4f  cd %.1f  ratio %.6f" % (q["gamma"], q["I_bl"], q["I_cd"], q["I_bl"] / max(q["I_cd"], 1e-9)))
json.dump(res, open(out_json, "w"), indent=1)
print("CALIB", res)
