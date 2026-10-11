"""WebRTC peer-connection factory with public STUN/TURN servers.

STUN lets the two peers discover their public addresses and connect directly
(works on most home networks). TURN relays the media when a direct path can't
be punched through a strict/symmetric NAT; we include a well-known free TURN
service as a best-effort fallback.
"""
from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection

_ICE_SERVERS = [
    RTCIceServer(urls="stun:stun.l.google.com:19302"),
    RTCIceServer(urls="stun:stun1.l.google.com:19302"),
    # Free public TURN (best effort). If it is down, STUN still covers most NATs.
    RTCIceServer(
        urls=[
            "turn:openrelay.metered.ca:80",
            "turn:openrelay.metered.ca:443",
            "turn:openrelay.metered.ca:443?transport=tcp",
        ],
        username="openrelayproject",
        credential="openrelayproject",
    ),
]


def make_peer_connection() -> RTCPeerConnection:
    return RTCPeerConnection(RTCConfiguration(iceServers=list(_ICE_SERVERS)))
