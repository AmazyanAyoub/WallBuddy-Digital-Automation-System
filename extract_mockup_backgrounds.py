"""
One-time script: extracts the 5 room background JPGs from mockup1.psd.
Hides all POSTER HERE layers, composites, crops each artboard, saves to /mockups/.
Run once: python extract_mockup_backgrounds.py
"""
import os
import sys
from PIL import Image
from psd_tools import PSDImage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PSD_PATH    = os.path.join(os.path.dirname(__file__), "mockups", "mockup1.psd")
OUTPUT_DIR  = os.path.join(os.path.dirname(__file__), "mockups")

print("Opening PSD...")
psd = PSDImage.open(PSD_PATH)

# Hide all POSTER HERE layers
all_posters = [l for l in psd.descendants() if l.name == "POSTER HERE"]
for l in all_posters:
    l.visible = False
print(f"Hidden {len(all_posters)} POSTER HERE layer(s)")

# Composite full PSD
print("Compositing background (this takes ~10 seconds)...")
bg = psd.composite()
if bg.mode != "RGB":
    bg = bg.convert("RGB")
print(f"Full composite size: {bg.size}")

# Get artboards that had visible poster slots
artboards = []
for layer in psd:
    if layer.kind != "artboard":
        continue
    # skip artboards with no poster slots (info page)
    had_posters = any(
        l.name == "POSTER HERE" for l in layer.descendants()
    )
    if had_posters:
        artboards.append(layer)

print(f"Found {len(artboards)} artboard(s) to export\n")

for idx, ab in enumerate(artboards, start=1):
    crop = bg.crop((ab.left, ab.top, ab.right, ab.bottom))
    out_path = os.path.join(OUTPUT_DIR, f"bg_{idx}.jpg")
    crop.save(out_path, format="JPEG", quality=95)
    print(f"Saved bg_{idx}.jpg  —  artboard '{ab.name}'  size={crop.size}  bbox=({ab.left},{ab.top},{ab.right},{ab.bottom})")

print("\nDone. Open the mockups/ folder and check the 5 bg_*.jpg files.")
print("Then tell me the poster placement coordinates for each one.")
