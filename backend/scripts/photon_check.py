"""Check the Photon 2.0 setup: key + project work, shared iMessage line assigned, recent inbound messages.

    backend/.venv/bin/python backend/scripts/photon_check.py
Needs PHOTON_API_KEY (pho_sk_..., project:read + project:write) and PHOTON_PROJECT_ID (pho_prj_...) in backend/.env.
"""
import os
import sys

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import config  # noqa: E402

if not config.photon_configured():
    sys.exit("Set PHOTON_API_KEY and PHOTON_PROJECT_ID in backend/.env first.")
base = f"{config.PHOTON_BASE_URL}/v1/projects/{config.PHOTON_PROJECT_ID}"
h = {"Authorization": f"Bearer {config.PHOTON_API_KEY}"}
with httpx.Client(timeout=15, headers=h) as c:
    r = c.get(f"{base}/platforms/imessage/assignments")
    print("iMessage assignments:", r.status_code, r.text[:600])
    r = c.get(f"{base}/messages", params={"direction": "received", "order": "desc", "pageSize": 5,
                                         "platform": config.PHOTON_PLATFORM})
    print("Recent received:", r.status_code)
    if r.is_success:
        for m in r.json().get("items", []):
            print(" ", m.get("createdAt"), (m.get("sentBy") or {}).get("handle"), "→",
                  (m.get("receivedBy") or {}).get("handle"), repr((m.get("content") or {}).get("text", ""))[:60])
    else:
        print(r.text[:400])
print("DEMO_FAMILY_PHONE:", config.DEMO_FAMILY_PHONE or "(not set: the Reyes family uses a fake 555 number)")
