"""Render a .glb to a PNG preview with Blender, headless.

  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
      --python scripts/render_glb.py -- model.glb preview.png [size]

A three-quarter view on a transparent background, soft studio light, Cycles on the GPU.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
src, dst = os.path.abspath(args[0]), os.path.abspath(args[1])  # Blender cannot save to a relative path without a .blend file
size = int(args[2]) if len(args) > 2 else 1024

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]

# Frame the model: its bounding box in world space.
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
centre, radius = (lo + hi) / 2, (hi - lo).length / 2

scene = bpy.context.scene
cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
scene.collection.objects.link(cam)
cam.data.lens = 70
dist = radius / math.tan(cam.data.angle / 2) * 1.15
direction = Vector((math.cos(math.radians(-50)), math.sin(math.radians(-50)), 0.55)).normalized()
cam.location = centre + direction * dist
cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
scene.camera = cam

for name, energy, loc in [("key", 900, (1.2, -1.6, 1.8)), ("fill", 300, (-1.8, -0.6, 0.8)), ("rim", 500, (-0.4, 1.8, 1.4))]:
    light = bpy.data.objects.new(name, bpy.data.lights.new(name, "AREA"))
    light.data.energy = energy * radius ** 2
    light.data.size = radius * 2
    light.location = centre + Vector(loc) * radius * 2.2
    light.rotation_euler = (centre - light.location).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(light)

world = bpy.data.worlds.new("world")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[1].default_value = 0.35
scene.world = world

scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "METAL"
prefs.get_devices()
for d in prefs.devices:
    d.use = True
scene.cycles.device = "GPU"
scene.cycles.samples = 96
scene.cycles.use_denoising = True
scene.render.film_transparent = True
scene.render.resolution_x = scene.render.resolution_y = size
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.view_settings.view_transform = "AgX"
scene.render.filepath = dst
bpy.ops.render.render(write_still=True)
