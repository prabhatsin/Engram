# settings and limits

# Model name, limits, allowlists, loaded from one place

import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("ENGRAM_MODEL", "gemini-3.8-flash")
# Means “use the ENGRAM_MODEL environment variable if it’s set, otherwise fall back to this default name.”
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30

