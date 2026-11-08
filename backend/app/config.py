import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "lifeline.db"))
DEMO_MODE = os.getenv("DEMO_MODE", "1") == "1"
SIM_SPEED = float(os.getenv("SIM_SPEED", "60"))

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NEMOTRON_MODEL = os.getenv("NEMOTRON_MODEL", "") or "nvidia/nemotron-3.5-super-vl-120b-a12b"
# Off by default: "thinking" adds seconds before the first tool call, and the live text demo needs speed.
NEMOTRON_THINKING = os.getenv("NEMOTRON_THINKING", "0") == "1"

PHOTON_API_KEY = os.getenv("PHOTON_API_KEY", "")          # project API key, pho_sk_...
PHOTON_PROJECT_ID = os.getenv("PHOTON_PROJECT_ID", "")    # pho_prj_...
PHOTON_BASE_URL = os.getenv("PHOTON_BASE_URL", "https://api.photon.codes")
PHOTON_PLATFORM = os.getenv("PHOTON_PLATFORM", "imessage")
# Photon stable (Spectrum, app.photon.codes): run photon-bridge/ and point this at it, e.g. http://localhost:8787
PHOTON_BRIDGE_URL = os.getenv("PHOTON_BRIDGE_URL", "").rstrip("/")
# Your own iPhone number (E.164). If set, the demo family (Reyes) uses this number, so Photon texts reach you.
DEMO_FAMILY_PHONE = os.getenv("DEMO_FAMILY_PHONE", "").strip()
ALLOWED_REAL_NUMBERS = {n.strip() for n in os.getenv("ALLOWED_REAL_NUMBERS", "").split(",") if n.strip()}
if DEMO_FAMILY_PHONE:
    ALLOWED_REAL_NUMBERS.add(DEMO_FAMILY_PHONE)


def llm_configured() -> bool:
    return bool(NVIDIA_API_KEY and NEMOTRON_MODEL)


def photon_configured() -> bool:
    return bool(PHOTON_BRIDGE_URL or (PHOTON_API_KEY and PHOTON_PROJECT_ID))


def photon_rest_configured() -> bool:
    """Photon 2.0 beta REST API (polled by photon.py). The Spectrum bridge needs no polling."""
    return bool(PHOTON_API_KEY and PHOTON_PROJECT_ID) and not PHOTON_BRIDGE_URL
