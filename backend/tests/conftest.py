"""Tests never use real services: blank out keys before app.config loads backend/.env
(load_dotenv does not override variables that are already set)."""
import os

for name in ("NVIDIA_API_KEY", "PHOTON_API_KEY", "PHOTON_PROJECT_ID", "PHOTON_BRIDGE_URL", "DEMO_FAMILY_PHONE",
             "ALLOWED_REAL_NUMBERS"):
    os.environ[name] = ""
