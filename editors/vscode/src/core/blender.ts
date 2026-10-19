import * as path from "path";

// Blender opens a .blend directly; everything else is imported into an empty scene. The path arrives as an
// argument after "--", never inside the Python text.
const BLENDER_IMPORT = `
import bpy, sys, os
f = sys.argv[sys.argv.index("--") + 1]
ext = os.path.splitext(f)[1].lower()
bpy.ops.wm.read_factory_settings(use_empty=True)
ops = {".glb": bpy.ops.import_scene.gltf, ".gltf": bpy.ops.import_scene.gltf, ".fbx": bpy.ops.import_scene.fbx,
       ".obj": bpy.ops.wm.obj_import, ".stl": bpy.ops.wm.stl_import, ".ply": bpy.ops.wm.ply_import,
       ".usd": bpy.ops.wm.usd_import, ".usdz": bpy.ops.wm.usd_import, ".bvh": bpy.ops.import_anim.bvh}
ops[ext](filepath=f)
`;

export function blenderArgs(file: string): string[] {
  return path.extname(file).toLowerCase() === ".blend" ? [file] : ["--python-expr", BLENDER_IMPORT, "--", file];
}
