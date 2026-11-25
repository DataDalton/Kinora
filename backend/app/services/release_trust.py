"""
Release trust.

A profile's safety template decides which releases it may download, from two separate
lists. Sources are the sites a torrent is listed on, each in a tier. Uploader categories
say whether the uploader is trusted.

Source tiers:
    balanced  1337x, YTS, Nyaa
    open      every other site (EZTV, RARBG, ThePirateBay, UIndex, DHT, the regional
              trackers, uploads made straight to ext.to, and the rest)

Uploader categories that count as trusted:
    kinora_list   a name on the Kinora trusted list, matched exactly against the name
                  the listing shows for that indexer
    ext_verified  ext.to's Trusted Uploader badge
    nyaa_trusted  rows Nyaa's staff mark trusted
    indexer_trusted  any release from a user-defined indexer the administrator put in
                  the trusted tier
Everything else is unverified.

User-defined indexers (see app.services.indexers.custom) are sources too, each with its
own site key custom:<id> and the tier the administrator chose for it. A new indexer is
open, so neither the Trusted nor the Balanced template accepts its releases until the
administrator moves it to balanced or trusted. Copies are never merged across a
user-defined indexer and another source, so its tier cannot spread to a public copy
that happens to share a title.

Templates:
    trusted   the uploader is trusted, on any source
    balanced  the uploader is trusted, or a source the torrent is listed on is balanced
    open      always

The same torrent often appears more than once in one search, through 1337x directly and
through ext.to. Copies are merged first, so a release keeps the best trust any copy has
and every site any copy is listed on.
"""

import re
import time
from typing import Dict, Iterable, List, Optional, Tuple

TEMPLATES = ("trusted", "balanced", "open")
DEFAULT_TEMPLATE_FOR_NEW_PROFILES = "trusted"

BALANCED_SOURCES = {"1337x", "yts", "nyaa"}

# Canonical site keys, with a readable name for the UI and the tier each belongs to.
SITES: Dict[str, Tuple[str, str]] = {
    "1337x": ("1337x", "balanced"),
    "yts": ("YTS", "balanced"),
    "nyaa": ("Nyaa", "balanced"),
    "ext": ("EXT Torrents", "open"),
    "eztv": ("EZTV", "open"),
    "rarbg": ("RARBG", "open"),
    "tpb": ("ThePirateBay", "open"),
    "uindex": ("UIndex", "open"),
    "dht": ("DHT", "open"),
    "ilcorsaronero": ("ILCorsaroNero", "open"),
    "oxtorrent": ("OxTorrent", "open"),
    "yggtorrent": ("YggTorrent", "open"),
    "dontorrent": ("DonTorrent", "open"),
    "sktorrent": ("SkTorrent", "open"),
    "polskietorrenty": ("Polskie Torrenty", "open"),
    "rutracker": ("RuTracker", "open"),
    "audiobookbay": ("AudioBookBay", "open"),
    "fitgirl": ("FitGirl Repacks", "open"),
}

# Substrings of icon names and site labels, checked in order, mapped to site keys.
_SITE_PATTERNS = [
    ("1337x", "1337x"),
    ("piratebay", "tpb"),
    ("tpb", "tpb"),
    ("eztv", "eztv"),
    ("yts", "yts"),
    ("nyaa", "nyaa"),
    ("rarbg", "rarbg"),
    ("uindex", "uindex"),
    ("dht", "dht"),
    ("corsaro", "ilcorsaronero"),
    ("oxtorrent", "oxtorrent"),
    ("ygg", "yggtorrent"),
    ("dontorrent", "dontorrent"),
    ("sktorrent", "sktorrent"),
    ("polskie", "polskietorrenty"),
    ("rutracker", "rutracker"),
    ("audiobook", "audiobookbay"),
    ("fitgirl", "fitgirl"),
    ("ext", "ext"),
]

CATEGORY_LABELS = {
    "kinora_list": "Kinora trusted list",
    "ext_verified": "ext.to verified",
    "nyaa_trusted": "Nyaa trusted",
    "indexer_trusted": "Trusted indexer",
    None: "Unverified",
}
_CATEGORY_RANK = {"indexer_trusted": 4, "kinora_list": 3, "ext_verified": 2, "nyaa_trusted": 1}

CUSTOM_SITE_PREFIX = "custom:"
# User-defined indexer site keys to (name, tier, active), set by the indexer registry on
# every load. active is False when the indexer is turned off for both search and RSS.
_customSites: Dict[str, Tuple[str, str, bool]] = {}


def setCustomSites(sites: Dict[str, Tuple[str, str, bool]]) -> None:
    """Replace the user-defined indexer sites. Tiers are open, balanced or trusted."""
    global _customSites
    _customSites = dict(sites)


def _inactiveCustomSite(release) -> Optional[str]:
    """The site key of a user-defined indexer the release came from that is deleted or turned off, or None."""
    for site in getattr(release, "origin_sites", None) or []:
        if isCustomSite(site):
            entry = _customSites.get(site)
            if entry is None or not entry[2]:
                return site
    return None


def isCustomSite(site: Optional[str]) -> bool:
    return bool(site) and site.startswith(CUSTOM_SITE_PREFIX)


# Seconds the trusted list is kept in memory before it is read from the database again.
_LIST_TTL_SECONDS = 300
_listCache: Dict[str, object] = {"loadedAt": 0.0, "entries": []}


def canonicalSite(label: Optional[str]) -> Optional[str]:
    """The site key for an icon name or site label such as 'thepiratebay.org' or 'EZTVx.to'."""
    text = (label or "").strip().lower()
    if not text:
        return None
    for needle, key in _SITE_PATTERNS:
        if needle in text:
            return key
    return None


def sourceTier(site: Optional[str]) -> str:
    """balanced or open. A user-defined indexer in the trusted tier is also a balanced source."""
    if isCustomSite(site):
        tier = _customSites.get(site, ("", "open", False))[1]
        return "balanced" if tier in ("balanced", "trusted") else "open"
    return SITES.get(site or "", ("", "open"))[1]


def _name(value: Optional[str]) -> str:
    return (value or "").strip().lower()


async def loadTrustedList(force: bool = False) -> List[dict]:
    """Enabled entries of the Kinora trusted list, cached briefly in memory."""
    now = time.monotonic()
    if not force and now - float(_listCache["loadedAt"]) < _LIST_TTL_SECONDS:
        return list(_listCache["entries"])
    try:
        from app.db import get_pool

        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT display_name, ext_name, leetx_name FROM trusted_uploaders WHERE enabled = TRUE"
            )
        _listCache["entries"] = [dict(r) for r in rows]
        _listCache["loadedAt"] = now
    except Exception as e:
        print(f"Could not load the trusted uploader list: {e}")
    return list(_listCache["entries"])


def clearTrustedListCache() -> None:
    _listCache["loadedAt"] = 0.0


def categoryFor(release, trustedList: Iterable[dict]) -> Optional[str]:
    """
    The trusted uploader category of one listing, or None. On ext.to a Kinora list name
    only counts with the Trusted Uploader badge, or on a listing labeled 1337x with the
    1337x name, because ext.to also shows names copied from sites that never verified them.
    """
    uploader = _name(getattr(release, "uploader", None))
    indexer = (getattr(release, "indexer", "") or "").lower()
    badge = getattr(release, "uploader_badge", None)
    sites = getattr(release, "origin_sites", None) or []
    firstSite = sites[0] if sites else None

    if uploader:
        for entry in trustedList:
            extName = _name(entry.get("ext_name"))
            leetxName = _name(entry.get("leetx_name"))
            if indexer == "1337x" and leetxName and uploader == leetxName:
                return "kinora_list"
            if indexer == "ext.to":
                if badge == "ext_verified" and extName and uploader == extName:
                    return "kinora_list"
                if firstSite == "1337x" and leetxName and uploader == leetxName:
                    return "kinora_list"
    if any(isCustomSite(site) and _customSites.get(site, ("", "open", False))[1] == "trusted" for site in sites):
        return "indexer_trusted"
    if badge == "ext_verified":
        return "ext_verified"
    if badge == "nyaa_trusted":
        return "nyaa_trusted"
    return None


def _mergeKey(release) -> Tuple[str, ...]:
    """
    Hash when known, otherwise normalized title, so copies of one torrent share a key.
    Releases of a user-defined indexer get keys of their own, so they only merge with
    other copies from the same indexer.
    """
    infoHash = (getattr(release, "info_hash", None) or "").lower()
    title = re.sub(r"[^a-z0-9]+", "", (release.title or "").lower())
    customSite = next((site for site in (getattr(release, "origin_sites", None) or []) if isCustomSite(site)), None)
    if customSite:
        return ("custom", customSite, infoHash or title)
    if infoHash:
        return ("hash", infoHash)
    return ("title", title)


def _sameSize(a, b) -> bool:
    if not a.size or not b.size:
        return True
    return abs(a.size - b.size) <= max(a.size, b.size) * 0.01


def _keepPreference(release) -> Tuple[int, int, int]:
    """Prefer a copy whose download source is already known, then a direct indexer, then seeders."""
    hasSource = 1 if (release.magnet or release.torrent_url) else 0
    direct = 0 if (release.indexer or "").lower() == "ext.to" else 1
    return (hasSource, direct, release.seeders or 0)


async def annotate(releases: List, trustedList: Optional[List[dict]] = None) -> List:
    """
    Merge copies of the same torrent and set trust_category on every release. Copies
    match on info hash, or on normalized title with a size within one percent when a
    hash is not known yet. The kept copy carries every site and the best trust of all.
    """
    if not releases:
        return releases
    if trustedList is None:
        trustedList = await loadTrustedList()
    await _loadCustomSites()

    groups: Dict[Tuple[str, ...], List[list]] = {}
    order: List[Tuple[Tuple[str, ...], int]] = []
    for release in releases:
        release.trust_category = categoryFor(release, trustedList)
        key = _mergeKey(release)
        buckets = groups.setdefault(key, [])
        for bucket in buckets:
            if _sameSize(bucket[0], release):
                bucket.append(release)
                break
        else:
            buckets.append([release])
            order.append((key, len(buckets) - 1))

    merged = []
    for key, index in order:
        copies = groups[key][index]
        kept = max(copies, key=_keepPreference)
        sites: List[str] = []
        for copy in copies:
            for site in copy.origin_sites or []:
                if site and site not in sites:
                    sites.append(site)
        kept.origin_sites = sites
        best = max((c.trust_category for c in copies), key=lambda c: _CATEGORY_RANK.get(c, 0))
        kept.trust_category = best
        if not kept.info_hash:
            kept.info_hash = next((c.info_hash for c in copies if c.info_hash), None)
        if kept.uploader_badge is None:
            kept.uploader_badge = next((c.uploader_badge for c in copies if c.uploader_badge), None)
        merged.append(kept)
    return merged


def isAllowed(release, template: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Whether a profile's template allows a release, with the reason when it does not. Call annotate first."""
    template = template if template in TEMPLATES else "open"
    if _inactiveCustomSite(release):
        return False, "The indexer this release came from was deleted or is turned off"
    if template == "open":
        return True, None
    trusted = getattr(release, "trust_category", None) is not None
    if trusted:
        return True, None
    if template == "balanced":
        sites = getattr(release, "origin_sites", None) or []
        if any(sourceTier(site) == "balanced" for site in sites):
            return True, None
        return (
            False,
            "Not allowed by the Balanced template, because the uploader is unverified and every site it is on is open tier",
        )
    return False, "Not allowed by the Trusted template, because the uploader is not trusted"


def siteCheckCouldAllow(release, template: Optional[str]) -> bool:
    """
    Whether reading the release's detail page could change a Balanced rejection. An ext.to
    search result names only the first site a torrent is on, so an unverified upload can
    also be on a Balanced site the result does not show. Trusted rejects on the uploader
    alone, so its verdict cannot change.
    """
    return (
        template == "balanced"
        and getattr(release, "trust_category", None) is None
        and getattr(release, "indexer", None) == "ext.to"
        and bool(getattr(release, "detail_url", None))
    )


async def _loadCustomSites() -> None:
    """Load the user-defined indexers so their site tiers are known in this process."""
    try:
        from app.services.indexers.custom import registry

        await registry.ensureLoaded()
    except Exception as e:
        print(f"Could not load user-defined indexer tiers: {e}")


def describeTemplate(template: str) -> dict:
    """
    Tables the profile editor shows for a template: every site with its tier, and the
    uploader categories. User-defined indexers are listed with the tier the administrator
    chose. A trusted indexer shows as a balanced source here, and its releases also count
    as trusted uploads.
    """
    sources = [{"key": key, "name": name, "tier": tier} for key, (name, tier) in SITES.items()]
    sources.extend(
        {"key": key, "name": name, "tier": sourceTier(key), "custom": True, "custom_tier": tier}
        for key, (name, tier, _active) in sorted(_customSites.items(), key=lambda item: item[1][0].lower())
    )
    return {
        "template": template,
        "sources": sources,
        "uploader_categories": [
            {"key": key, "name": CATEGORY_LABELS[key], "trusted": key is not None}
            for key in ("kinora_list", "ext_verified", "nyaa_trusted", "indexer_trusted", None)
        ],
    }
