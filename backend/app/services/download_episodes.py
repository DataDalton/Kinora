"""
Episodes covered by a show or anime download.

When Kinora starts a download for a series, the release name says which episodes it
holds, such as S02E05, S02E05-E07, a season pack, or an anime batch. The ids of those
episodes are stored in download_history.episode_ids, so the calendar and other views
read exactly which episodes are downloading instead of only knowing the series.
"""

import logging
from typing import List, Optional

from app.services import release_matching

logger = logging.getLogger(__name__)

# Library episodes in the shape release_matching.coveredEpisodes reads, with each id.
_EPISODE_SQL = {
    "show": (
        "SELECT id, season_number AS season, episode_number AS episode, NULL::int AS absolute "
        "FROM episodes WHERE show_id = $1"
    ),
    "anime": (
        "SELECT id, COALESCE(season_number, 1) AS season, COALESCE(season_episode, episode_number) AS episode, "
        "episode_number AS absolute FROM anime_episodes WHERE anime_id = $1"
    ),
}

_SERIES_TITLE_SQL = {
    "show": "SELECT title, original_title FROM shows WHERE id = $1",
    "anime": "SELECT title, original_title FROM anime WHERE id = $1",
}


async def coveredEpisodeIds(conn, mediaType: str, seriesId: int, releaseTitle: str) -> Optional[List[int]]:
    """
    Ids of the library episodes a release covers, read from its name. Returns None for
    media types without episodes, and an empty list when the name names episodes that
    are not in the library.
    """
    if mediaType not in _EPISODE_SQL or not seriesId or not releaseTitle:
        return None
    seriesRow = await conn.fetchrow(_SERIES_TITLE_SQL[mediaType], seriesId)
    if not seriesRow:
        return None
    episodes = [dict(row) for row in await conn.fetch(_EPISODE_SQL[mediaType], seriesId)]
    titles = [title for title in (seriesRow["title"], seriesRow["original_title"]) if title]
    season, episode = release_matching.seasonEpisodeFromQuery(releaseTitle)
    absoluteEpisode = None
    if mediaType == "anime" and episode is None:
        # Anime releases usually number episodes absolutely, as in 'Frieren - 12'.
        numbers = set(release_matching.absoluteNumbers(releaseTitle, titles))
        if len(numbers) == 1:
            absoluteEpisode = episode = numbers.pop()
    target = release_matching.MatchTarget(
        kind=mediaType, titles=titles, season=season, episode=episode, absoluteEpisode=absoluteEpisode
    )
    covered = release_matching.coveredEpisodes(releaseTitle, target, episodes)
    if covered is None:
        return []
    return sorted({e["id"] for e in covered})


async def recordCoveredEpisodes(
    conn, torrentHash: str, mediaType: str, seriesId: int, releaseTitle: str, episodeId: Optional[int] = None
) -> None:
    """
    Store the episodes a download covers on its download_history row. A download made
    for one chosen episode stores that episode. Never raises, since a failure here must
    not stop a download.
    """
    if mediaType not in _EPISODE_SQL:
        return
    try:
        if episodeId:
            episodeIds = [episodeId]
        else:
            episodeIds = await coveredEpisodeIds(conn, mediaType, seriesId, releaseTitle)
        if episodeIds is None:
            return
        await conn.execute(
            """
            UPDATE download_history
            SET episode_ids = $2,
                episode_id = COALESCE(episode_id, CASE WHEN cardinality($2::int[]) = 1 THEN ($2::int[])[1] END)
            WHERE torrent_hash = $1
            """,
            torrentHash,
            episodeIds,
        )
    except Exception as e:
        logger.warning("Could not record covered episodes for %s: %s", torrentHash, e)


async def fillMissingCoveredEpisodes(conn, activeStatuses: List[str]) -> None:
    """
    Record covered episodes for active series downloads saved before episode_ids
    existed, so every active download has its episodes stored.
    """
    rows = await conn.fetch(
        """
        SELECT torrent_hash, media_type, media_id, torrent_title, episode_id
        FROM download_history
        WHERE media_type IN ('show', 'anime') AND episode_ids IS NULL AND status = ANY($1::text[])
        """,
        activeStatuses,
    )
    for row in rows:
        await recordCoveredEpisodes(
            conn, row["torrent_hash"], row["media_type"], row["media_id"], row["torrent_title"], row["episode_id"]
        )
