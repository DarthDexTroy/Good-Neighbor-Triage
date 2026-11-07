import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "lifeline.db"))
DEMO_MODE = os.getenv("DEMO_MODE", "1") == "1"
SIM_SPEED = float(os.getenv("SIM_SPEED", "60"))

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NEMOTRON_MODEL = os.getenv("NEMOTRON_MODEL", "")

PHOTON_API_KEY = os.getenv("PHOTON_API_KEY", "")
ALLOWED_REAL_NUMBERS = {n.strip() for n in os.getenv("ALLOWED_REAL_NUMBERS", "").split(",") if n.strip()}


def llm_configured() -> bool:
    return bool(NVIDIA_API_KEY and NEMOTRON_MODEL)


def photon_configured() -> bool:
    return bool(PHOTON_API_KEY)
