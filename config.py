import os

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR  = os.path.join(BASE_DIR, "INPUT")
OUTPUT_DIR = os.path.join(BASE_DIR, "OUTPUT")
LOG_DIR    = os.path.join(BASE_DIR, "logs")
MOCKUP_DIR = os.path.join(BASE_DIR, "mockups")

# ── API Keys (fill in before use) ─────────────────────────────────────────────
OPENAI_API_KEY           = "sk-..."
GOOGLE_DRIVE_CREDENTIALS = os.path.join(BASE_DIR, "credentials.json")
GOOGLE_DRIVE_FOLDER_ID   = "1TqkOB-QCn-NcCuLnLaSuHY55zhOPb5gA"   # replace with your actual Drive folder ID

# ── Image Export Settings ──────────────────────────────────────────────────────
JPEG_QUALITY = 92
DPI          = 300

# ── Upscaling Thresholds ───────────────────────────────────────────────────────
UPSCALE_THRESHOLD = 7000   # upscale if longest side is below this
UPSCALE_X4_BELOW  = 3500   # use x4 if longest side < this, else x2

# Real-ESRGAN weights (relative to project root)
WEIGHTS_DIR    = os.path.join(BASE_DIR, "weights")
WEIGHTS_4X     = os.path.join(WEIGHTS_DIR, "RealESRGAN_x4plus.pth")
WEIGHTS_2X     = os.path.join(WEIGHTS_DIR, "RealESRGAN_x2plus.pth")

# ── Print Format Definitions ───────────────────────────────────────────────────
# (filename_stem, width_px, height_px)
PRINT_FORMATS = [
    ("2x3_ratio_24x36",  7200, 10800),
    ("3x4_ratio_18x24",  5400,  7200),
    ("4x5_ratio_16x20",  4800,  6000),
    ("ISO_A1",           7016,  9933),
    ("11x14_ratio",      3300,  4200),
]

# Accepted image extensions for input scanning
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
