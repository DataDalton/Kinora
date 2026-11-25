"""
Download links for user-defined indexers.

Download links from private trackers carry the account's passkey, API token or RSS key.
They are never stored or sent to the browser as they are. Each one is encrypted with the
same key as other secret settings and wrapped as

    kinora-indexer://<indexer id>/<encrypted link>

The wrapped link goes wherever a torrent URL goes: search results, the release index and
download history. qBittorrent never sees it. When a wrapped link is added, the indexer
that produced it fetches the .torrent file with its own credentials, and the file is
uploaded to qBittorrent unchanged, so the private flag and the tracker list stay exactly
as the tracker issued them.
"""

import hashlib
from dataclasses import dataclass
from typing import Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken

PRIVATE_LINK_PREFIX = "kinora-indexer://"


def _fernet() -> Fernet:
    from app.api.v1.endpoints.setup import get_encryption_key

    return Fernet(get_encryption_key())


def encryptText(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decryptText(value: str) -> Optional[str]:
    """The plain text of an encrypted value, or None when it cannot be decrypted."""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken, ValueError, TypeError:
        return None


def isPrivateLink(source: Optional[str]) -> bool:
    return bool(source) and source.startswith(PRIVATE_LINK_PREFIX)


def wrapLink(indexerId: int, link: str) -> str:
    return f"{PRIVATE_LINK_PREFIX}{indexerId}/{encryptText(link)}"


def unwrapLink(source: str) -> Tuple[int, str]:
    """The indexer id and the original link inside a wrapped link. Raises ValueError when it is not one."""
    if not isPrivateLink(source):
        raise ValueError("Not a Kinora indexer link")
    body = source[len(PRIVATE_LINK_PREFIX) :]
    idText, _, token = body.partition("/")
    if not idText.isdigit() or not token:
        raise ValueError("Malformed Kinora indexer link")
    link = decryptText(token)
    if link is None:
        raise ValueError("The indexer link could not be decrypted. SECRET_KEY may have changed since it was saved")
    return int(idText), link


@dataclass
class ResolvedSource:
    """What a wrapped link resolves to, either a magnet or the bytes of a .torrent file."""

    magnet: Optional[str] = None
    fileBytes: Optional[bytes] = None
    infoHash: Optional[str] = None
    isPrivate: bool = False


async def resolveLink(source: str) -> ResolvedSource:
    """Fetch what a wrapped link points to through the indexer that issued it."""
    indexerId, link = unwrapLink(source)
    from app.services.indexers.custom import registry

    indexer = await registry.byIdLoaded(indexerId)
    if indexer is None:
        raise ValueError(f"The indexer that issued this download (id {indexerId}) no longer exists")
    if link.startswith("magnet:"):
        return ResolvedSource(magnet=link, infoHash=_magnetHash(link))
    data = await indexer.downloadTorrentFile(link)
    infoHash, isPrivate = torrentFileInfo(data)
    return ResolvedSource(fileBytes=data, infoHash=infoHash, isPrivate=isPrivate)


def _magnetHash(magnet: str) -> Optional[str]:
    import re

    match = re.search(r"xt=urn:btih:([0-9a-fA-F]{40})", magnet)
    return match.group(1).lower() if match else None


# ---------------------------------------------------------------------------
# Bencode reading, enough to find the info dictionary and its private flag.
# ---------------------------------------------------------------------------


class BencodeError(ValueError):
    pass


def _decode(data: bytes, index: int):
    """Decode one bencoded value at index and return (value, next index)."""
    if index >= len(data):
        raise BencodeError("Unexpected end of data")
    lead = data[index : index + 1]
    if lead == b"i":
        end = data.index(b"e", index)
        return int(data[index + 1 : end]), end + 1
    if lead == b"l":
        index += 1
        items = []
        while data[index : index + 1] != b"e":
            item, index = _decode(data, index)
            items.append(item)
        return items, index + 1
    if lead == b"d":
        index += 1
        result = {}
        while data[index : index + 1] != b"e":
            key, index = _decode(data, index)
            if not isinstance(key, bytes):
                raise BencodeError("Dictionary key is not a string")
            start = index
            value, index = _decode(data, index)
            result[key] = (value, start, index)
        return result, index + 1
    if lead.isdigit():
        colon = data.index(b":", index)
        length = int(data[index:colon])
        start = colon + 1
        if start + length > len(data):
            raise BencodeError("String runs past the end of data")
        return data[start : start + length], start + length
    raise BencodeError(f"Unexpected byte {lead!r} at {index}")


def torrentFileInfo(data: bytes) -> Tuple[str, bool]:
    """
    The v1 info hash (lowercase hex) and private flag of a .torrent file. Raises
    ValueError when the bytes are not a torrent, such as an HTML login page.
    """
    if not data or data[:1] != b"d":
        snippet = (data or b"")[:80].decode("utf-8", "replace").strip()
        raise ValueError(f"The indexer returned something other than a .torrent file ({snippet or 'empty'})")
    try:
        top, _end = _decode(data, 0)
    except (BencodeError, ValueError, IndexError) as e:
        raise ValueError(f"The .torrent file could not be read: {e}")
    if b"info" not in top:
        raise ValueError("The .torrent file has no info dictionary")
    info, start, end = top[b"info"]
    infoHash = hashlib.sha1(data[start:end]).hexdigest()
    private = isinstance(info, dict) and b"private" in info and info[b"private"][0] == 1
    return infoHash, bool(private)
