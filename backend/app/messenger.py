"""All outbound messages go through deliver(). Photon is behind one small class so a mock can swap in.

SAFETY: only numbers in ALLOWED_REAL_NUMBERS, or people who texted us live, ever get a real message.
Every seeded number is fake and goes to the mock.
"""
import logging

from . import clock, config, db

log = logging.getLogger("lifeline.messenger")


class PhotonMessenger:
    """TODO(teammate): fill these in from the Photon 2.0 docs (get them at the sponsor booth).

    Don't guess the API. Typical shape: an HTTP POST with the API key, a recipient, a channel
    (sms / imessage / whatsapp) and the text. Voice calls take a text-to-speech script.
    """

    def send(self, to: str, text: str, channel: str = "sms") -> None:
        raise NotImplementedError("Photon send not wired yet; see PhotonMessenger in messenger.py")

    def call(self, to: str, script: str) -> None:
        raise NotImplementedError("Photon voice not wired yet")


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
