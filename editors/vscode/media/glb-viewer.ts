// The .glb viewer: three.js with orbit controls, a 1 m grid, wireframe, and the model's real size.
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";

const stage = document.getElementById("stage") as HTMLDivElement;
const stats = document.getElementById("stats") as HTMLDivElement;
const loading = document.getElementById("loading");
const dark = document.body.classList.contains("vscode-dark") || document.body.classList.contains("vscode-high-contrast");

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
stage.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(40, 1, 0.001, 1000);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

// Soft studio light without an environment file: a sky/ground fill plus a key and a rim light.
scene.add(new THREE.HemisphereLight(0xffffff, dark ? 0x202020 : 0x8a8a8a, 2.2));
const key = new THREE.DirectionalLight(0xffffff, 2.4);
key.position.set(3, 5, 4);
scene.add(key);
const rim = new THREE.DirectionalLight(0xffffff, 1.2);
rim.position.set(-4, 3, -3);
scene.add(rim);

const grid = new THREE.GridHelper(10, 100, dark ? 0x555555 : 0x999999, dark ? 0x333333 : 0xdddddd);
scene.add(grid);

let model: THREE.Object3D | undefined;
let frame = () => {};

function resize() {
  const w = stage.clientWidth, h = Math.max(240, stage.clientHeight);
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(stage);
resize();

function fmt(n: number) {
  return n.toLocaleString("en-US");
}

new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).load(
  stage.dataset.src!,
  (gltf) => {
    loading?.remove();
    model = gltf.scene;
    scene.add(model);
    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    const centre = box.getCenter(new THREE.Vector3());
    grid.position.y = box.min.y;
    const radius = Math.max(size.x, size.y, size.z) || 1;
    grid.scale.setScalar(Math.max(0.1, Math.pow(10, Math.floor(Math.log10(radius)))));
    frame = () => {
      controls.target.copy(centre);
      camera.position.copy(centre).add(new THREE.Vector3(1.2, 0.8, 1.6).multiplyScalar(radius));
      camera.near = radius / 100;
      camera.far = radius * 100;
      camera.updateProjectionMatrix();
      controls.update();
    };
    frame();
    let vertices = 0, triangles = 0, meshes = 0;
    const materials = new Set<string>(), textures = new Set<string>();
    model.traverse((o: any) => {
      if (!o.isMesh) return;
      meshes++;
      const g = o.geometry as THREE.BufferGeometry;
      vertices += g.attributes.position?.count ?? 0;
      triangles += g.index ? g.index.count / 3 : (g.attributes.position?.count ?? 0) / 3;
      for (const m of [].concat(o.material)) {
        materials.add((m as any).uuid);
        for (const k of ["map", "normalMap", "roughnessMap", "metalnessMap", "aoMap", "emissiveMap"]) if ((m as any)[k]) textures.add((m as any)[k].uuid);
      }
    });
    const m = (v: number) => (v >= 1 ? `${v.toFixed(2)} m` : `${(v * 100).toFixed(1)} cm`);
    stats.textContent = `${fmt(Math.round(triangles))} triangles · ${fmt(vertices)} vertices · ${meshes} mesh${meshes === 1 ? "" : "es"} · ` +
      `${materials.size} material${materials.size === 1 ? "" : "s"} · ${textures.size} texture${textures.size === 1 ? "" : "s"} · ` +
      `size ${m(size.x)} × ${m(size.y)} × ${m(size.z)} (glTF units are metres)` +
      (gltf.animations.length ? ` · ${gltf.animations.length} animation${gltf.animations.length === 1 ? "" : "s"}` : "");
    (window as any).__aeneasModel = { triangles: Math.round(triangles), vertices, size: [size.x, size.y, size.z] };
  },
  undefined,
  (err) => {
    if (loading) loading.textContent = `Could not load the model: ${(err as any)?.message ?? err}`;
  },
);

(document.getElementById("wire") as HTMLInputElement).addEventListener("change", (e) => {
  const on = (e.target as HTMLInputElement).checked;
  model?.traverse((o: any) => o.isMesh && [].concat(o.material).forEach((m: any) => (m.wireframe = on)));
});
(document.getElementById("grid") as HTMLInputElement).addEventListener("change", (e) => (grid.visible = (e.target as HTMLInputElement).checked));
const spin = document.getElementById("spin") as HTMLInputElement;
spin.addEventListener("change", () => (controls.autoRotate = spin.checked));
document.getElementById("reset")!.addEventListener("click", () => frame());

renderer.setAnimationLoop(() => {
  controls.update();
  renderer.render(scene, camera);
});
