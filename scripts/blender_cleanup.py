"""Make a generated GLB game-ready with Blender, headless.

  Blender -b --factory-startup --python scripts/blender_cleanup.py -- in.glb out.glb SIZE_M FACES LODS

  SIZE_M  the largest dimension in metres after scaling (e.g. 1.0)
  FACES   the most faces LOD 0 may have (e.g. 20000)
  LODS    comma-separated ratios of LOD 0, the first being 1 (e.g. 1,0.5,0.25)

Writes out.glb (LOD 0) and out_lod1.glb, out_lod2.glb ...; origin at the bottom centre, +Y up in
glTF, transforms applied, materials and textures kept. Prints one line: AENEAS_RESULT {json}.
"""
import json
import os
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
src, out = os.path.abspath(args[0]), os.path.abspath(args[1])
size_m, max_faces = float(args[2]), int(args[3])
lods = [float(x) for x in args[4].split(",")] if len(args) > 4 else [1.0]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    raise SystemExit("no mesh in " + src)

# One object, transforms applied.
bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
obj = bpy.context.view_layer.objects.active
for o in list(bpy.context.scene.objects):
    if o.type == "EMPTY":
        bpy.data.objects.remove(o)
obj.parent = None
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# Scale so the largest dimension is size_m, origin at the bottom centre.
pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
scale = size_m / max((hi - lo).x, (hi - lo).y, (hi - lo).z)
obj.scale = (scale, scale, scale)
bpy.ops.object.transform_apply(scale=True)
pts = [v.co for v in obj.data.vertices]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
offset = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
for v in obj.data.vertices:
    v.co -= offset
obj.location = (0, 0, 0)


def faces():
    return len(obj.data.polygons)


def decimate(ratio):
    if ratio >= 0.999:
        return
    mod = obj.modifiers.new("decimate", "DECIMATE")
    mod.ratio = ratio
    bpy.ops.object.modifier_apply(modifier=mod.name)


def export(path):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True)


start = faces()
if start > max_faces:
    decimate(max_faces / start)
result = {"source_faces": start, "size_m": size_m, "lods": []}
base_faces = faces()
stem, ext = os.path.splitext(out)
for i, ratio in enumerate(lods):
    if i:
        decimate(ratio * base_faces / faces())
    path = out if i == 0 else f"{stem}_lod{i}{ext}"
    export(path)
    result["lods"].append({"file": os.path.basename(path), "faces": faces()})
dims = obj.dimensions
result["dimensions_m"] = [round(dims.x, 3), round(dims.y, 3), round(dims.z, 3)]
print("AENEAS_RESULT " + json.dumps(result))
