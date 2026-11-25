"""
Search context for indexers that accept structured ids.

BaseIndexer.search takes only a query string. Trackers such as UNIT3D and Torznab
servers also search by IMDb, TMDB or TVDB id, season and episode, or artist and album.
The search engine sets the item being searched for here before a search, and indexers
that understand ids read it. Indexers that only take text ignore it.

The value lives in a context variable, so concurrent searches in one process never see
each other's item, and tasks started inside a search inherit it.
"""

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Optional

# Kinora media types to the media type names indexers are configured with.
MEDIA_TYPE_SCOPE = {
    "movie": "movies",
    "movies": "movies",
    "show": "shows",
    "shows": "shows",
    "episode": "shows",
    "tv": "shows",
    "anime": "anime",
    "album": "music",
    "music": "music",
    "track": "music",
}

SCOPES = ("movies", "shows", "anime", "music")


@dataclass
class SearchContext:
    """The item a search is for. Every field is optional."""

    scope: Optional[str] = None  # movies, shows, anime or music
    title: Optional[str] = None
    year: Optional[int] = None
    imdbId: Optional[str] = None  # with the tt prefix
    tmdbId: Optional[int] = None
    tvdbId: Optional[int] = None
    malId: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    singleEpisode: bool = False
    artist: Optional[str] = None
    album: Optional[str] = None

    @property
    def imdbNumeric(self) -> Optional[str]:
        """The IMDb id without its tt prefix, as Newznab style APIs expect."""
        if not self.imdbId:
            return None
        digits = self.imdbId.lower().removeprefix("tt")
        return digits if digits.isdigit() else None

    def hasIds(self) -> bool:
        return bool(self.imdbId or self.tmdbId or self.tvdbId)


_current: contextvars.ContextVar[Optional[SearchContext]] = contextvars.ContextVar(
    "indexerSearchContext", default=None
)


def scopeFor(mediaType: Optional[str], category: Optional[str] = None) -> str:
    """The indexer scope for a Kinora media type or search category, movies when neither names one."""
    for value in (mediaType, category):
        scope = MEDIA_TYPE_SCOPE.get((value or "").lower())
        if scope:
            return scope
    return "movies"


def current() -> Optional[SearchContext]:
    return _current.get()


@contextmanager
def using(context: Optional[SearchContext]) -> Iterator[None]:
    """Set the search context for the duration of a block and restore the previous one after."""
    token = _current.set(context)
    try:
        yield
    finally:
        _current.reset(token)


_ITEM_SQL = {
    "movie": "SELECT title, imdb_id, tmdb_id, NULL::int AS tvdb_id, NULL::int AS mal_id FROM movies WHERE id = $1",
    "show": "SELECT title, imdb_id, tmdb_id, tvdb_id, NULL::int AS mal_id FROM shows WHERE id = $1",
    "anime": "SELECT title, imdb_id, tmdb_id, NULL::int AS tvdb_id, mal_id FROM anime WHERE id = $1",
}


async def forItem(conn, mediaType: Optional[str], mediaId: Optional[int], matchTarget=None) -> SearchContext:
    """
    Build the context for a library item, reading its external ids. matchTarget, a
    release_matching.MatchTarget, supplies the year, season, episode and artist. Any
    lookup failure leaves the ids empty, so the search falls back to text.
    """
    context = SearchContext(scope=scopeFor(mediaType))
    if matchTarget is not None:
        context.title = (matchTarget.titles or [None])[0]
        context.year = matchTarget.year
        context.season = matchTarget.season
        context.episode = matchTarget.episode
        context.singleEpisode = bool(matchTarget.singleEpisode)
        context.artist = matchTarget.artist
        if mediaType in ("album", "music"):
            context.album = context.title
    sql = _ITEM_SQL.get(mediaType or "")
    if not sql or not mediaId:
        return context
    try:
        if conn is not None:
            row = await conn.fetchrow(sql, mediaId)
        else:
            from app.db import get_pool

            pool = await get_pool()
            async with pool.acquire() as poolConn:
                row = await poolConn.fetchrow(sql, mediaId)
    except Exception as e:
        print(f"Could not load external ids for {mediaType} {mediaId}: {e}")
        return context
    if row:
        context.title = context.title or row["title"]
        imdb = (row["imdb_id"] or "").strip()
        context.imdbId = imdb if imdb.lower().startswith("tt") else (f"tt{imdb}" if imdb.isdigit() else None)
        context.tmdbId = row["tmdb_id"]
        context.tvdbId = row["tvdb_id"]
        context.malId = row["mal_id"]
    return context
