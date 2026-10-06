import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WHEELSIZE_API_KEY = os.getenv("WHEELSIZE_API_KEY", "")
WHEELSIZE_BASE_URL = "https://api.wheel-size.com/v2"
WHEELSIZE_MONTHLY_LIMIT = int(os.getenv("WHEELSIZE_MONTHLY_LIMIT") or "300")

DATA_DIR = Path(os.getenv("WHEEL_FITMENT_DATA_DIR") or Path.home() / ".wheel-fitment-agent")

# Only needed for the optional render tool; GitHub Copilot has no image generation.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL") or "gpt-4.1-mini"
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL") or "gpt-image-1"

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
