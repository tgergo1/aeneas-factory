#!/bin/sh
# Remake the README's gallery (docs/gallery) with the factory itself, with fixed seeds.
# Needs every tool and model (make install); Blender and ffmpeg for the previews.
# A step whose output already exists is skipped: delete a file to make it again.
# About 20 minutes on an M5 Pro.
set -eu
cd "$(dirname "$0")/.."
G=docs/gallery
BLENDER="${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"
mkdir -p "$G"
cd "$G"
B=../../bin

# 1. Text to image (Z-Image Turbo)
[ -f chest.png ] || $B/ai-image "a weathered wooden treasure chest with iron bands and a brass lock, a single object centred on a plain white background, soft studio light, product photo" \
  --size 1024 --seed 11 -o chest.png

# 2. Editing from a reference (FLUX.2 klein)
[ -f chest-blue.png ] || $B/ai-image "paint the wooden planks of the chest a deep blue, keep the iron bands, the brass lock and the white background" \
  --model flux2-klein-4b --ref chest.png --size 1024 --seed 11 -o chest-blue.png

# 3. A seamless texture (Z-Image Turbo, --tile), and four copies of it side by side to show the seams are gone
[ -f cobbles.png ] || $B/ai-image "rounded grey river cobblestones packed tightly together, green moss growing in the gaps between the stones, seen from directly above, soft overcast daylight, photographic ground texture" \
  --tile --size 512 --seed 21 -o cobbles.png
[ -f cobbles-2x2.png ] || ffmpeg -loglevel error -y -i cobbles.png \
  -filter_complex "[0]split=4[a][b][c][d];[a][b]hstack[top];[c][d]hstack[bottom];[top][bottom]vstack" cobbles-2x2.png

# 4. Image to 3D (TRELLIS.2), from the chest of step 1, and a rendered preview of the model
[ -f chest.glb ] || { $B/ai-3d chest.png --res 1024 --seed 1 -o chest.glb; rm -f chest.ply chest_base.png; }
[ -f chest-3d.png ] || "$BLENDER" -b --factory-startup --python ../../scripts/render_glb.py -- chest.glb chest-3d.png 1024 >/dev/null

# 5. A sound effect (MOSS-SoundEffect), and a picture of its waveform
[ -f chest-creak.wav ] || $B/ai-sfx "an old wooden chest lid creaks open slowly, then thuds shut" --seconds 5 --seed 3 -o chest-creak.wav
[ -f chest-creak-wave.png ] || ffmpeg -loglevel error -y -i chest-creak.wav \
  -filter_complex "showwavespic=s=1600x280:colors=0x0d9488:split_channels=0:scale=sqrt:draw=full" -frames:v 1 chest-creak-wave.png

# 6. Explicit tools (make explicit): the outputs are rendered from the sources in explicit/, no models
cd explicit
[ -f pipeline.png ] || ../$B/aen diagram pipeline.d2 --kind d2 --local -o pipeline.png >/dev/null
[ -f potion.png ] || ../$B/aen svg potion.svg --width 256 --local -o potion.png >/dev/null
[ -f tavern.wav ] || ../$B/aen music tavern.abc --local -o tavern.wav >/dev/null
# Pixel art: the chest of step 1 cut out, cut down to 48 px and 12 colours, then enlarged without smoothing
[ -f chest-pixel.png ] || ../$B/aen tool magick -- ../chest.png -fuzz 8% -fill none -draw "color 0,0 floodfill" \
  -filter Triangle -resize 48x48 -channel A -threshold 50% +channel -dither None -colors 12 \
  -filter point -scale 800% chest-pixel.png
cd ..

rm -f ./*.log explicit/*.log
echo "gallery remade in $G"
