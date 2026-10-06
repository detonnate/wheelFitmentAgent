import os

from dotenv import load_dotenv

load_dotenv()

WHEELSIZE_API_KEY = os.getenv("WHEELSIZE_API_KEY", "")
WHEELSIZE_BASE_URL = "https://api.wheel-size.com/v2"
WHEELSIZE_MONTHLY_LIMIT = int(os.getenv("WHEELSIZE_MONTHLY_LIMIT", "300"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini")
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
