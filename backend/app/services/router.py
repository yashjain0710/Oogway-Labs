"""Agent routing layer: understandable, testable, logged keyword router.

Routes: chat (grounded Q&A) | essay (Ship 30 for 30) | artifact (md/html doc).
Deliberately not autonomous — the assignment needs predictable skills.
"""
import logging
import re

log = logging.getLogger("lenny.router")

_ESSAY = re.compile(r"ship\s*30|essay|1250\s*words|write\s+(me\s+)?an?\s+essay|blog\s*post", re.I)
_ARTIFACT = re.compile(
    r"artifact|render\s+(as\s+)?html|html\s*(page|snippet|doc)|markdown\s*(doc|file|artifact)|"
    r"create\s+a\s+(markdown|html|doc|page|one-pager|strategy\s+doc)|strategy\s+document|landing\s+page",
    re.I,
)


def route_message(message: str) -> str:
    msg = message.strip()
    if _ESSAY.search(msg):
        route = "essay"
    elif _ARTIFACT.search(msg):
        route = "artifact"
    else:
        route = "chat"
    log.info("router route=%s msg=%.80s", route, msg)
    return route
