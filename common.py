"""Shared helpers for AnyHelp."""
import secrets

# Characters chosen to avoid look-alikes (no O/0, I/1/L).
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

# All peer ids on the public signaling server live in one flat namespace,
# so we prefix ours to avoid colliding with unrelated PeerJS users.
PEER_PREFIX = "anyhelp-"


def gen_code(length: int = 6) -> str:
    """A short, human-readable session code the host reads out loud."""
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


def host_peer_id(code: str) -> str:
    return PEER_PREFIX + code.upper()


def controller_peer_id() -> str:
    return PEER_PREFIX + "ctl-" + secrets.token_hex(4)
