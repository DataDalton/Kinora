"""
Blocklist by torrent info hash.

Title entries in the blocklist stay per item, as before. Hash entries identify one exact
torrent. A torrent that fails validation is blocklisted by hash for every item, because
a torrent carrying an executable or a disguised file is unsafe wherever it is picked.
Every add path checks the hash before handing the torrent to the download client.
"""

import base64
import re
from typing import Optional

SCOPE_ITEM = "item"
SCOPE_ALL = "all"

_btihPattern = re.compile(r"xt=urn:btih:([A-Za-z0-9]+)", re.IGNORECASE)


def normalizeHash(value: Optional[str]) -> Optional[str]:
    """A lowercase hex info hash, converting the base32 form magnets sometimes carry."""
    if not value:
        return None
    value = value.strip()
    if re.fullmatch(r"[0-9a-fA-F]{40}", value):
        return value.lower()
    if re.fullmatch(r"[A-Za-z2-7]{32}", value):
        try:
            return base64.b32decode(value.upper()).hex()
        except ValueError:
            return None
    return None


def infoHashFromSource(source: Optional[str]) -> Optional[str]:
    """The info hash inside a magnet link, or None for a .torrent URL."""
    if not source:
        return None
    match = _btihPattern.search(source)
    return normalizeHash(match.group(1)) if match else None


async def isHashBlocked(conn, infoHash: Optional[str], mediaType: Optional[str] = None, mediaId=None) -> bool:
    """True when the hash is blocklisted for every item, or for this item."""
    infoHash = normalizeHash(infoHash)
    if not infoHash:
        return False
    row = await conn.fetchval(
        """
        SELECT 1 FROM blocklist
        WHERE info_hash = $1
          AND (scope = 'all' OR (media_type = $2 AND media_id = $3))
        LIMIT 1
        """,
        infoHash,
        mediaType,
        mediaId,
    )
    return row is not None


async def blockHash(conn, infoHash, releaseTitle, reason, mediaType, mediaId, scope=SCOPE_ALL) -> bool:
    """Add a hash entry unless one already covers it. Returns True when a row was added."""
    infoHash = normalizeHash(infoHash)
    if not infoHash:
        return False
    exists = await conn.fetchval(
        "SELECT 1 FROM blocklist WHERE info_hash = $1 AND scope = $2 LIMIT 1",
        infoHash,
        scope,
    )
    if exists:
        return False
    await conn.execute(
        """
        INSERT INTO blocklist (media_type, media_id, release_title, reason, info_hash, scope)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        mediaType or "manual",
        mediaId or 0,
        releaseTitle or infoHash,
        reason,
        infoHash,
        scope,
    )
    return True
