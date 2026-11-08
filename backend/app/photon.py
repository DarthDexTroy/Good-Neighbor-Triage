"""Photon 2.0 inbound: poll the project's received iMessages and hand them to services.handle_inbound.

Polling (GET /v1/projects/{id}/messages) means no public webhook or tunnel is needed for the demo.
Docs: https://photon.codes/docs/beta/get-started/imessage
"""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

import httpx

from . import config, db

log = logging.getLogger("lifeline.photon")
POLL_S = 2.0
_stop = threading.Event()
_thread = None


def _iso(dt):
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _text(content):
    if not isinstance(content, dict):
        return ""
    if content.get("type") == "text":
        return content.get("text", "")
    parts = content.get("parts") or []
    return " ".join(p.get("text", "") for p in parts if isinstance(p, dict) and p.get("type") == "text")


def remember_space(handle, space_id, agent_id):
    spaces = db.get("meta", "photon:spaces") or {"id": "photon:spaces"}
    spaces[handle] = {"space_id": space_id, "agent_id": agent_id}
    db.put("meta", "photon:spaces", spaces)


def process(item, seen):
    """Returns True if the message was handed to the app. Pure enough to unit-test with a dict."""
    from . import services
    if item.get("id") in seen or item.get("status") != "received":
        return False
    seen.add(item["id"])
    sender, agent, space = item.get("sentBy") or {}, item.get("receivedBy") or {}, item.get("space") or {}
    if sender.get("kind") != "human" or agent.get("kind") != "agent" or not sender.get("handle"):
        return False
    remember_space(sender["handle"], space.get("id"), agent.get("id"))
    text = _text(item.get("content")).strip()
    if not text:
        if (item.get("content") or {}).get("type") == "image":
            text = "[photo]"  # a picture message: counts as the pre-storm photo action
        else:
            return False
    if services.meta()["phase"] == "idle":
        return False
    services.handle_inbound(sender["handle"], text, "imessage")
    return True


def _run():
    started = datetime.now(timezone.utc)
    since = _iso(started - timedelta(seconds=5))
    seen = set()
    url = f"{config.PHOTON_BASE_URL}/v1/projects/{config.PHOTON_PROJECT_ID}/messages"
    headers = {"Authorization": f"Bearer {config.PHOTON_API_KEY}"}
    with httpx.Client(timeout=15) as client:
        while not _stop.is_set():
            try:
                query = {"createdSince": since, "direction": "received", "order": "asc", "pageSize": 100,
                         "platform": config.PHOTON_PLATFORM}
                while True:
                    r = client.get(url, headers=headers, params=query)
                    if r.status_code == 429:
                        time.sleep(float(r.headers.get("retry-after", 5)))
                        break
                    r.raise_for_status()
                    page = r.json()
                    for item in page.get("items", []):
                        try:
                            if datetime.fromisoformat(item["createdAt"].replace("Z", "+00:00")) >= started:
                                process(item, seen)
                        except Exception as e:
                            log.warning("Photon message skipped: %s", e)
                    token = page.get("nextPageToken")
                    if not isinstance(token, str):
                        break
                    query["pageToken"] = token
                set_status("polling", None)
            except Exception as e:
                log.warning("Photon poll failed: %s", e)
                set_status("error", str(e)[:200])
            _stop.wait(POLL_S)


_status = {"state": "off", "error": None}


def set_status(state, error):
    _status.update(state=state, error=error)


def status():
    return dict(_status)


def start():
    global _thread
    if not config.photon_rest_configured() or (_thread and _thread.is_alive()):
        return
    _stop.clear()
    _thread = threading.Thread(target=_run, daemon=True)
    _thread.start()
    set_status("starting", None)


def stop():
    _stop.set()
