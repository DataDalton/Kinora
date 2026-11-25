"""
Release matching.

Checks that a release is for the item being searched before any quality scoring. A
search for "Alien 1979" returns releases of Aliens, Alien Romulus and unrelated titles
that share a word, and without this check the best-scored one could be downloaded.

Movies need every significant title word and a year within one of the item's year.
Shows and anime need the title and the wanted season, accepting single episodes of it,
season packs, season ranges that include it, and complete-series packs. Anime also
accepts absolute episode numbers. An episode upgrade search sets singleEpisode, which
accepts only releases of that one episode, so a pack never replaces other episodes' files.
Albums need both the artist and the album words.
Every title an item is known by (main, original, and alternative titles) is tried.
"""

import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional

_stopWords = {"the", "a", "an", "of", "and", "&"}
_yearPattern = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")
_episodePattern = re.compile(r"\bs(\d{1,2})[ ._-]?e(\d{1,3})(?:[ ._-]?e?(\d{1,3}))?\b", re.IGNORECASE)
_seasonRangePattern = re.compile(
    r"\bs(?:eason)?[ ._-]?(\d{1,2})[ ._]*(?:-|to|~)[ ._]*s?(?:eason)?[ ._-]?(\d{1,2})\b", re.IGNORECASE
)
_seasonPattern = re.compile(r"\b(?:s|season[ ._-]?)(\d{1,2})\b(?![ ._-]?e\d)", re.IGNORECASE)
_completePattern = re.compile(r"\b(complete|integrale|all[ ._-]seasons)\b", re.IGNORECASE)
_absoluteEpisodePattern = re.compile(r"(?:^|[\s_\-\]])(\d{1,4})(?:v\d)?(?=[\s_\[\(.]|$)")
_absoluteRangePattern = re.compile(r"(?:^|[\s_\[\(])(\d{1,4})\s?[-~]\s?(\d{1,4})(?=[\s_\]\).]|$)")


@dataclass
class MatchTarget:
    """What a search is looking for, used to reject releases of something else."""

    kind: str  # movie, show, anime or album
    titles: List[str] = field(default_factory=list)
    year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    # Anime episode number counted from the first episode of the series, for releases
    # numbered absolutely. When None, episode is used.
    absoluteEpisode: Optional[int] = None
    # Accept only a release of the single episode, never a pack, range or batch.
    singleEpisode: bool = False
    # Further check on a whole release after the title match, such as the episode upgrade
    # check that every episode a pack would replace gets a better file. True keeps it.
    releaseCheck: Optional[Callable[[object], bool]] = None
    artist: Optional[str] = None


def normalize(text: Optional[str]) -> str:
    """Lowercase words separated by single spaces, with & read as and and apostrophes dropped."""
    text = (text or "").lower().replace("&", " and ")
    text = re.sub(r"['’`]", "", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def significantWords(title: str) -> List[str]:
    """The words of a title that must all appear in a matching release."""
    return [word for word in normalize(title).split() if word not in _stopWords]


def titleMatches(releaseTitle: str, title: str) -> bool:
    """
    True when every significant word of the title appears in the release title. Words
    may also appear joined, so "spider man" matches "Spiderman". A title with no
    significant words falls back to its full normalized form.
    """
    words = significantWords(title)
    normalizedRelease = normalize(releaseTitle)
    releaseWords = set(normalizedRelease.split())
    compactRelease = normalizedRelease.replace(" ", "")
    if not words:
        full = normalize(title)
        return bool(full) and full.replace(" ", "") in compactRelease
    return all(word in releaseWords or (len(word) > 2 and word in compactRelease) for word in words)


def anyTitleMatches(releaseTitle: str, titles: Iterable[str]) -> bool:
    return any(titleMatches(releaseTitle, title) for title in titles if title)


def _yearsIn(releaseTitle: str) -> List[int]:
    return [int(year) for year in _yearPattern.findall(releaseTitle)]


def _movieYearMatches(releaseTitle: str, target: MatchTarget) -> bool:
    """A release without a year is accepted. A release with years needs one within one of the item's year."""
    if not target.year:
        return True
    years = _yearsIn(releaseTitle)
    if not years:
        return True
    return any(abs(year - target.year) <= 1 for year in years)


def _seasonMatches(releaseTitle: str, target: MatchTarget) -> bool:
    """Single episodes of the wanted season, packs and ranges that include it, and complete packs."""
    if target.season is None:
        return True
    for match in _episodePattern.finditer(releaseTitle):
        if int(match.group(1)) == target.season:
            if target.episode is None:
                return True
            first = int(match.group(2))
            last = int(match.group(3)) if match.group(3) else first
            if first <= target.episode <= last:
                return True
    if _episodePattern.search(releaseTitle):
        # Episodes of some other season, or another episode of this one.
        return False
    for match in _seasonRangePattern.finditer(releaseTitle):
        if int(match.group(1)) <= target.season <= int(match.group(2)):
            return True
    seasons = [int(s) for s in _seasonPattern.findall(releaseTitle)]
    if seasons:
        return target.season in seasons
    if _seasonRangePattern.search(releaseTitle):
        return False
    if _completePattern.search(releaseTitle):
        return True
    # No season marker at all. Anime batches often carry none, and a show's single
    # season (a miniseries) is usually named without one.
    return target.kind == "anime" or target.season == 1


def _stripAnimeTags(releaseTitle: str, titles: Iterable[str] = ()) -> str:
    """
    An anime title without bracketed tags, resolutions, codecs and the series name, leaving
    the episode numbers. Removing the series name keeps a number inside it, such as the 8
    in Kaiju No. 8, from being read as an episode or as the start of a range.
    """
    title = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", releaseTitle)
    title = re.sub(r"\b(1080|720|480|2160|1440)p?\b|\b(x|h)\.?26[45]\b", " ", title, flags=re.IGNORECASE)
    for name in sorted({t for t in titles if t}, key=len, reverse=True):
        words = normalize(name).split()
        if words:
            title = re.sub(r"\b" + r"[\W_]+".join(map(re.escape, words)) + r"\b", " ", title, flags=re.IGNORECASE)
    return title


def _animeEpisodeMatches(releaseTitle: str, target: MatchTarget) -> bool:
    """Absolute numbering for anime, such as 'Frieren - 12' or a batch '01-28'."""
    episode = target.absoluteEpisode or target.episode
    if episode is None:
        return True
    title = _stripAnimeTags(releaseTitle, target.titles)
    for match in _absoluteRangePattern.finditer(title):
        if int(match.group(1)) <= episode <= int(match.group(2)):
            return True
    numbers = [int(n) for n in _absoluteEpisodePattern.findall(title) if not _yearPattern.fullmatch(n)]
    return not numbers or episode in numbers


def _absoluteNumbers(releaseTitle: str, titles: Iterable[str]) -> List[int]:
    """Absolute episode numbers in an anime title, ignoring tags, resolutions, codecs, the series name and years."""
    title = _stripAnimeTags(releaseTitle, titles)
    if _absoluteRangePattern.search(title):
        return []
    return [int(n) for n in _absoluteEpisodePattern.findall(title) if not _yearPattern.fullmatch(n)]


def absoluteNumbers(releaseTitle: str, titles: Iterable[str]) -> List[int]:
    """Absolute episode numbers in an anime release name, such as 12 in 'Frieren - 12'."""
    return _absoluteNumbers(releaseTitle, titles)


def isSingleEpisode(releaseTitle: str, target: MatchTarget) -> bool:
    """
    True when the release holds only the target episode. A release must name the episode
    itself, as one SxxEyy marker with no second episode, or for anime as one absolute
    number. Season packs, ranges, batches and complete packs are rejected.
    """
    if target.episode is None:
        return False
    if _completePattern.search(releaseTitle) or _seasonRangePattern.search(releaseTitle):
        return False
    markers = list(_episodePattern.finditer(releaseTitle))
    if markers:
        if len(markers) != 1 or markers[0].group(3):
            return False
        season, episode = int(markers[0].group(1)), int(markers[0].group(2))
        return (target.season is None or season == target.season) and episode == target.episode
    if target.kind != "anime":
        return False
    numbers = set(_absoluteNumbers(releaseTitle, target.titles))
    return len(numbers) == 1 and numbers == {target.absoluteEpisode or target.episode}


def coveredEpisodes(releaseTitle: str, target: MatchTarget, episodes: List[dict]) -> Optional[List[dict]]:
    """
    The episodes of a series a release holds, picked from episodes (dicts with season,
    episode and, for anime, absolute). Reads episode markers and ranges, season packs,
    season ranges, anime batches and complete packs. A release with no marker at all is
    taken to hold the whole series. Returns None when the release names episodes in a way
    that cannot be read, so the caller can reject it rather than guess.
    """
    if isSingleEpisode(releaseTitle, target):
        return [
            e
            for e in episodes
            if (e.get("season") == target.season and e.get("episode") == target.episode)
            or (target.absoluteEpisode is not None and e.get("absolute") == target.absoluteEpisode)
        ]
    if _completePattern.search(releaseTitle):
        return list(episodes)
    markers = list(_episodePattern.finditer(releaseTitle))
    if markers:
        covered = []
        for marker in markers:
            season, first = int(marker.group(1)), int(marker.group(2))
            last = int(marker.group(3)) if marker.group(3) else first
            covered.extend(e for e in episodes if e.get("season") == season and first <= e.get("episode", -1) <= last)
        return covered
    seasonRange = _seasonRangePattern.search(releaseTitle)
    if seasonRange:
        low, high = int(seasonRange.group(1)), int(seasonRange.group(2))
        return [e for e in episodes if low <= (e.get("season") or 0) <= high]
    seasons = {int(s) for s in _seasonPattern.findall(releaseTitle)}
    if seasons:
        return [e for e in episodes if e.get("season") in seasons]
    if target.kind == "anime":
        # Batches often put their range in parentheses, such as (01-12), so parentheses
        # are opened up rather than dropped like other tags.
        title = _stripAnimeTags(re.sub(r"\(([^)]*)\)", r" \1 ", releaseTitle), target.titles)
        batch = _absoluteRangePattern.search(title)
        if batch:
            low, high = int(batch.group(1)), int(batch.group(2))
            return [e for e in episodes if e.get("absolute") is not None and low <= e["absolute"] <= high]
        if _absoluteNumbers(releaseTitle, target.titles):
            return None
    return list(episodes)


def releaseMatches(releaseTitle: str, target: Optional[MatchTarget]) -> bool:
    """True when the release is for the target item. A missing target accepts everything."""
    if target is None or not releaseTitle:
        return True
    if target.kind == "album":
        artistOk = not target.artist or titleMatches(releaseTitle, target.artist)
        return artistOk and (not target.titles or anyTitleMatches(releaseTitle, target.titles))
    if target.titles and not anyTitleMatches(releaseTitle, target.titles):
        return False
    if target.kind == "movie":
        return _movieYearMatches(releaseTitle, target)
    if target.kind in ("show", "anime"):
        seasonOk = _seasonMatches(releaseTitle, target)
        # Anime releases without SxxEyy are numbered absolutely, so the episode number
        # (or batch range) decides, alongside any season marker they carry.
        if target.singleEpisode and not isSingleEpisode(releaseTitle, target):
            return False
        if target.kind == "anime" and not _episodePattern.search(releaseTitle):
            return seasonOk and _animeEpisodeMatches(releaseTitle, target)
        return seasonOk
    return True


def seasonEpisodeFromQuery(query: str):
    """The season and episode a search query asks for, from SxxEyy or Sxx tokens."""
    match = _episodePattern.search(query or "")
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"\bs(\d{1,2})\b|\bseason\s*(\d{1,2})\b", query or "", re.IGNORECASE)
    if match:
        return int(match.group(1) or match.group(2)), None
    return None, None


def alternativeTitles(metadata) -> List[str]:
    """Alternative titles stored in an item's metadata, under the keys the metadata providers use."""
    if not isinstance(metadata, dict):
        return []
    titles = []
    for key in ("alternative_titles", "alt_titles", "synonyms", "aliases", "also_known_as"):
        value = metadata.get(key)
        if isinstance(value, list):
            titles.extend(v if isinstance(v, str) else (v or {}).get("title", "") for v in value)
    for key in ("title_romaji", "title_english", "title_native", "romaji", "english", "original_title"):
        value = metadata.get(key)
        if isinstance(value, str):
            titles.append(value)
    nested = metadata.get("title")
    if isinstance(nested, dict):
        titles.extend(v for v in nested.values() if isinstance(v, str))
    return [t for t in titles if t]
