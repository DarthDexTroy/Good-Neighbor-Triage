"""All outbound messages go through deliver(). Photon is behind one small class so a mock can swap in.

SAFETY: only numbers in ALLOWED_REAL_NUMBERS, or people who texted us live, ever get a real message.
Every seeded number is fake and goes to the mock.
"""
import logging

from . import clock, config, db

log = logging.getLogger("lifeline.messenger")


class PhotonMessenger:
    """Photon 2.0 (beta) REST API: https://photon.codes/docs/beta (base https://api.photon.codes/v1).

    Shared iMessage lines can't start a conversation, so we can only reply into a space the person
    opened by texting the agent number first. photon.py records {handle: (space_id, agent_user_id)}
    from every inbound message; send() looks it up here.
    """

    def _space(self, to):
        return (db.get("meta", "photon:spaces") or {}).get(to)

    def send(self, to: str, text: str, channel: str = "sms") -> None:
        import uuid

        import httpx
        if config.PHOTON_BRIDGE_URL:  # Photon stable via photon-bridge/ (Spectrum SDK)
            r = httpx.post(f"{config.PHOTON_BRIDGE_URL}/send", json={"to": to, "text": text}, timeout=20)
            if r.status_code >= 300:
                raise RuntimeError(f"Photon bridge {r.status_code}: {r.text[:200]}")
            return
        space = self._space(to)
        if not space:
            raise RuntimeError(f"No Photon conversation with {to[-4:]} yet: they must text the agent number first")
        r = httpx.post(
            f"{config.PHOTON_BASE_URL}/v1/projects/{config.PHOTON_PROJECT_ID}/messages",
            headers={"Authorization": f"Bearer {config.PHOTON_API_KEY}", "idempotency-key": f"gn-{uuid.uuid4()}"},
            json={"spaceId": space["space_id"], "senderId": space["agent_id"],
                  "content": {"type": "text", "format": "plain", "text": text}},
            timeout=15,
        )
        if r.status_code >= 300:
            raise RuntimeError(f"Photon send {r.status_code}: {r.text[:200]}")

    def call(self, to: str, script: str) -> None:
        raise NotImplementedError("Photon voice not wired (shared iMessage lines don't support calls)")


_photon = PhotonMessenger()


def is_real_recipient(household: dict) -> bool:
    return household.get("source") == "live" or household.get("phone") in config.ALLOWED_REAL_NUMBERS


def deliver(household: dict, text: str, channel: str = "sms") -> str:
    via = "mock"
    if household.get("phone") and is_real_recipient(household) and config.photon_configured():
        try:
            _photon.send(household["phone"], text, channel)
            via = "photon"
        except Exception as e:  # keep the demo alive; the message still shows in the dashboard
            log.warning("Photon send failed, falling back to mock: %s", e)
            via = "mock (photon failed)"
    db.append("messages", {"household_id": household["id"], "direction": "out", "channel": channel,
                           "body": text, "t": clock.now(), "via": via})
    return via
