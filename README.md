# WallBuddy Digital Automation System

A fully automated pipeline for Etsy digital wall art sellers. Drop artwork folders into `INPUT/`, run `main.py`, and get print-ready files, mockup images, a Google Drive ZIP link, and a complete Etsy CSV row — all without touching anything manually.

---

## What It Does

For each artwork set in `INPUT/`, the pipeline runs 6 steps automatically:

1. **Image Processing** — detects resolution, AI-upscales if needed, exports 5 print-ready JPGs per artwork
2. **Mockup Generation** — warps artwork into 5 room scene backgrounds using perspective transform
3. **ZIP Creation** — packages all print files into a single downloadable ZIP
4. **Google Drive Upload** — uploads the ZIP and generates a public shareable link
5. **Content Generation** — calls Gemini AI to write an Etsy-optimized title, description, and 13 tags
6. **CSV Export** — appends a row to `OUTPUT/output.csv` ready to import into Etsy

Multiple sets are processed in parallel (up to 4 workers).

---

## Project Structure

```
WallBuddy-Digital-Automation-System/
│
├── INPUT/                          # Drop artwork folders here
│   └── set_name/
│       ├── image1.jpg
│       └── image2.jpg
│
├── OUTPUT/                         # All generated files land here
│   ├── set_name/
│   │   ├── print_files/
│   │   │   ├── Print_1/
│   │   │   │   ├── 2x3_ratio_24x36.jpg
│   │   │   │   ├── 3x4_ratio_18x24.jpg
│   │   │   │   ├── 4x5_ratio_16x20.jpg
│   │   │   │   ├── ISO_A1.jpg
│   │   │   │   └── 11x14_ratio.jpg
│   │   │   └── Print_2/ ...
│   │   ├── mockups/
│   │   │   ├── set_name_mockup_1.jpg
│   │   │   └── ... (5 mockups total)
│   │   └── set_name.zip
│   └── output.csv                  # Etsy-ready CSV (all sets)
│
├── mockups/                        # Room background JPGs
│   ├── bg_1.jpg
│   ├── bg_2.jpg
│   ├── bg_3.jpg
│   ├── bg_4.jpg
│   └── bg_5.jpg
│
├── weights/                        # Real-ESRGAN model weights
│   ├── RealESRGAN_x4plus.pth
│   └── RealESRGAN_x2plus.pth
│
├── modules/
│   ├── image_processor.py          # Upscaling + print file export
│   ├── mockup_generator.py         # Perspective warp compositing
│   ├── zip_creator.py              # ZIP packaging
│   ├── drive_uploader.py           # Google Drive OAuth2 upload
│   ├── content_generator.py        # Gemini AI Etsy copywriting
│   └── csv_writer.py               # Thread-safe CSV append
│
├── utils/
│   └── logger.py                   # Dual file + console logging
│
├── config.py                       # All paths, keys, and settings
├── mockup_config.json              # 4-corner coordinates per mockup slot
├── main.py                         # Entry point — runs full pipeline
├── extract_mockup_backgrounds.py   # One-time: extracts bg JPGs from PSD
└── test_mockup.py                  # Quick mockup test (single set)
```

---

## Print Formats

Each artwork is exported in 5 standard print sizes at 300 DPI with sRGB ICC profile:

| File | Physical Size | Pixels | Aspect Ratio |
|------|--------------|--------|--------------|
| `2x3_ratio_24x36.jpg` | 24×36 in | 7200×10800 | 2:3 |
| `3x4_ratio_18x24.jpg` | 18×24 in | 5400×7200 | 3:4 |
| `4x5_ratio_16x20.jpg` | 16×20 in | 4800×6000 | 4:5 |
| `ISO_A1.jpg` | A1 paper | 7016×9933 | ISO A |
| `11x14_ratio.jpg` | 11×14 in | 3300×4200 | 11:14 |

Each format uses fit-and-blur-fill scaling — the artwork is resized to fit fully within the canvas (no cropping, no stretching). If the aspect ratios differ, the remaining space is filled with a blurred, stretched version of the same image instead of white bars.

---

## AI Upscaling

If an artwork's longest side is below **7000px**, Real-ESRGAN automatically upscales it:

- Longest side < 3500px → 4x upscale pass
- Longest side 3500–7000px → 2x upscale pass
- Passes repeat until the image reaches 7000px
- Uses CUDA if available, otherwise CPU
- Tiled processing (512px tiles) to handle large images without running out of memory

Model weights must be placed in `weights/`:
- `RealESRGAN_x4plus.pth`
- `RealESRGAN_x2plus.pth`

---

## Mockup Generation

Artwork is composited onto 5 room background photos using OpenCV perspective transform (`cv2.getPerspectiveTransform`). The placement coordinates for each background are stored in `mockup_config.json` as 4-corner pixel coordinates (top-left, top-right, bottom-right, bottom-left).

To add or adjust a mockup frame:
1. Open the background JPG in any image editor
2. Note the pixel coordinates of the 4 corners of the frame opening
3. Update `mockup_config.json` with those coordinates

---

## Setup

### 1. Install dependencies

```bash
pip install opencv-python pillow numpy torch realesrgan basicsr \
            psd-tools aggdraw langchain-openai google-api-python-client \
            google-auth-oauthlib
```

### 2. Configure `config.py`

```python
GOOGLE_DRIVE_FOLDER_ID = "your_drive_folder_id_here"
```

### 3. Google Drive credentials

- Go to Google Cloud Console → Create a project → Enable Drive API
- Download OAuth2 credentials as `credentials.json` and place it in the project root
- On first run, a browser window will open for authentication
- The token is saved as `token.pickle` for subsequent runs

### 4. Gemini proxy

The content generator connects to a local OpenAI-compatible proxy at `http://localhost:3001/openai/v1` using `gemini-2.0-flash`. Start your proxy before running the pipeline.

### 5. Add Real-ESRGAN weights

Download from the [Real-ESRGAN releases](https://github.com/xinntao/Real-ESRGAN/releases) and place in `weights/`.

---

## Running

### Full pipeline (all sets in INPUT/)

```bash
python main.py
```

### Test mockup generation only

```bash
python test_mockup.py
```

### One-time: extract backgrounds from PSD

```bash
python extract_mockup_backgrounds.py
```

---

## Output CSV

`OUTPUT/output.csv` contains one row per processed set:

| Column | Description |
|--------|-------------|
| `Title` | Etsy listing title (120–140 chars) |
| `Description` | Etsy listing description (150–250 words) |
| `Tags` | 13 comma-separated Etsy tags |
| `Drive_Link` | Public Google Drive download link |

---

## Logs

Logs are written to `logs/errors.log` and also printed to the console. Each log line is prefixed with `[set_name]` so you can track multiple sets running in parallel.
