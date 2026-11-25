import asyncio
import time
from datetime import datetime

from app.tasks.celery_app import celery_app, runAsync
from app.db import get_pool
from app.services.automation.search_engine import search_engine
from app.services.media_profile import MediaProfile
from app.services.media_status import ACTIVE_DOWNLOAD_STATUSES
from app.services.search_backoff import eligibilityClause, recordSearchAttempt
from app.core.cache import cacheSet

# (media_type, table, category, year_column, backoff_date_column)
# The backoff date column enables the fast retry window for recent releases.
# Shows and anime keep files and quality per episode, so they are upgraded one episode at
# a time by the episode pass below rather than here.
_UPGRADE_TYPES = (("movie", "movies", "movies", "release_date", "release_date"),)

# Episodes searched per run, and per series in one run, so one long series cannot use the
# whole run while the rest wait.
EPISODES_PER_RUN = 50
EPISODES_PER_SERIES = 3


def _episodeSql(
    episodeTable, alias, seriesTable, seriesAlias, seriesColumn, mediaType, seasonSql, episodeSql, absoluteSql
):
    """
    SQL selecting episodes due for an upgrade search, ranked within each series so no more
    than EPISODES_PER_SERIES of one series are picked. A series with a download in progress
    is skipped, so an episode is never downloaded twice at once.
    """
    return f"""
        SELECT * FROM (
            SELECT {alias}.id, {alias}.{seriesColumn} AS series_id, {seasonSql} AS season,
                   {episodeSql} AS episode, {absoluteSql} AS absolute_episode,
                   {alias}.quality_detected, {alias}.last_search_at, {seriesAlias}.title,
                   {seriesAlias}.media_profile_id,
                   COALESCE({seriesAlias}.upgrade_allowed, mp.upgrade_allowed) AS effective_upgrade,
                   ROW_NUMBER() OVER (
                       PARTITION BY {alias}.{seriesColumn}
                       ORDER BY {alias}.last_search_at ASC NULLS FIRST, {seasonSql}, {episodeSql}
                   ) AS series_rank
            FROM {episodeTable} {alias}
            INNER JOIN {seriesTable} {seriesAlias} ON {seriesAlias}.id = {alias}.{seriesColumn}
            INNER JOIN media_profiles mp ON mp.id = {seriesAlias}.media_profile_id
            WHERE {seriesAlias}.monitored = TRUE AND {alias}.monitored = TRUE AND {alias}.has_file = TRUE
              AND {alias}.quality_detected IS NOT NULL
              AND COALESCE({seriesAlias}.upgrade_allowed, mp.upgrade_allowed) = TRUE
              AND {eligibilityClause(alias, "air_date")}
              AND NOT EXISTS (
                  SELECT 1 FROM download_history dh
                  WHERE dh.media_type = '{mediaType}' AND dh.media_id = {seriesAlias}.id
                    AND dh.status = ANY($1::text[])
              )
        ) due
        WHERE series_rank <= $2
        ORDER BY last_search_at ASC NULLS FIRST
        LIMIT $3
    """


# Per series type, the episode table, search category and selection SQL. Each row carries
# the season and episode to match on and, for anime, the absolute episode number.
_EPISODE_SOURCES = {
    "show": {
        "table": "episodes",
        "seriesTable": "shows",
        "category": "tv",
        "librarySql": (
            "SELECT season_number AS season, episode_number AS episode, NULL::int AS absolute, "
            "quality_detected AS quality FROM episodes WHERE show_id = $1 AND has_file"
        ),
        "sql": _episodeSql(
            "episodes", "e", "shows", "s", "show_id", "show", "e.season_number", "e.episode_number", "NULL::int"
        ),
    },
    "anime": {
        "table": "anime_episodes",
        "seriesTable": "anime",
        "category": "anime",
        "librarySql": (
            "SELECT COALESCE(season_number, 1) AS season, COALESCE(season_episode, episode_number) AS episode, "
            "episode_number AS absolute, quality_detected AS quality FROM anime_episodes "
            "WHERE anime_id = $1 AND has_file"
        ),
        "sql": _episodeSql(
            "anime_episodes",
            "ae",
            "anime",
            "a",
            "anime_id",
            "anime",
            "COALESCE(ae.season_number, 1)",
            "COALESCE(ae.season_episode, ae.episode_number)",
            "ae.episode_number",
        ),
    },
}


@celery_app.task(name="app.tasks.upgrade_search.search_upgrades")
def search_upgrades():
    """
    Search for higher-quality releases of items that already have a file and whose
    effective upgrade_allowed (item override, else profile) is TRUE.
    """
    return runAsync(async_search_upgrades())


def _query_year(year_src):
    if not year_src:
        return None
    return year_src.year if hasattr(year_src, "year") else year_src


def _episodeQuery(mediaType: str, episode: dict) -> str:
    """
    The search text for one episode. Shows use SxxEyy. Anime uses the absolute episode
    number, which is how fansub releases are named.
    """
    if mediaType == "anime":
        return f"{episode['title']} {episode['absolute_episode']:02d}"
    return f"{episode['title']} S{episode['season']:02d}E{episode['episode']:02d}"


def _episodeTags(mediaType: str, episode: dict) -> list:
    """Download client tags for one episode, in the same form the RSS monitor uses."""
    if mediaType == "anime":
        return ["kinora", f"anime-{episode['series_id']}", f"e{episode['absolute_episode']:03d}"]
    return ["kinora", f"show-{episode['series_id']}", f"s{episode['season']:02d}e{episode['episode']:02d}"]


async def _searchEpisodeUpgrades(conn, mediaType: str) -> int:
    """
    Search for a better release of each due episode of monitored shows or anime, one
    episode at a time. A season pack or batch is accepted only when every episode of the
    series it holds would get a better file, so an upgrade never replaces an episode with
    the same or a lower quality. A download sets the series to downloading, and the
    import or the download's removal sets it back.
    """
    source = _EPISODE_SOURCES[mediaType]
    rows = await conn.fetch(source["sql"], list(ACTIVE_DOWNLOAD_STATUSES), EPISODES_PER_SERIES, EPISODES_PER_RUN)
    if not rows:
        return 0

    profileIds = list({r["media_profile_id"] for r in rows})
    profileRows = await conn.fetch("SELECT * FROM media_profiles WHERE id = ANY($1)", profileIds)
    profiles = {r["id"]: MediaProfile.from_row(dict(r)) for r in profileRows}

    downloaded = 0
    # Episodes with a file per series, with their quality, loaded once per series.
    libraries = {}
    # Series that got an upgrade this run. Their other episodes wait for the next run, so a
    # second download never starts while the first is still validating.
    seriesDownloading = set()
    for row in rows:
        episode = dict(row)
        profile = profiles.get(episode["media_profile_id"])
        if not profile or episode["series_id"] in seriesDownloading:
            continue

        query = _episodeQuery(mediaType, episode)
        if episode["series_id"] not in libraries:
            libraries[episode["series_id"]] = [
                dict(r) for r in await conn.fetch(source["librarySql"], episode["series_id"])
            ]
        searchStats = {}
        try:
            torrentHash = await search_engine.search_and_download(
                query=query,
                profile=profile,
                category=source["category"],
                tags=_episodeTags(mediaType, episode),
                media_type=mediaType,
                history_conn=conn,
                history_media_id=episode["series_id"],
                current_quality=episode["quality_detected"],
                grab_mode="upgrade",
                upgrade_allowed=episode["effective_upgrade"],
                search_stats=searchStats,
                episode_target={
                    "season": episode["season"],
                    "episode": episode["episode"],
                    "absolute_episode": episode["absolute_episode"],
                    "library": libraries[episode["series_id"]],
                },
            )
            await recordSearchAttempt(
                conn,
                source["table"],
                episode["id"],
                found=bool(torrentHash),
                indexer_outage=searchStats.get("all_indexers_failed", False),
            )
            if torrentHash:
                await conn.execute(
                    f"UPDATE {source['seriesTable']} SET status = 'downloading', updated_at = NOW() WHERE id = $1",
                    episode["series_id"],
                )
                seriesDownloading.add(episode["series_id"])
                downloaded += 1
        except Exception as e:
            print(f"Episode upgrade search error for {query}: {e}")

        # Pause only when live indexer queries actually ran.
        if searchStats.get("live_queries"):
            await asyncio.sleep(2)
    return downloaded


async def async_search_upgrades():
    taskName = "upgrade_search"
    startTime = time.time()
    status = "success"

    try:
        grabbed = 0
        pool = await get_pool()

        async with pool.acquire() as conn:
            for media_type, table, category, year_col, backoff_date_col in _UPGRADE_TYPES:
                rows = await conn.fetch(f"""
                    SELECT t.id, t.title, t.media_profile_id, t.quality_detected,
                           t.{year_col} AS year_src,
                           COALESCE(t.upgrade_allowed, mp.upgrade_allowed) AS effective_upgrade
                    FROM {table} t
                    INNER JOIN media_profiles mp ON t.media_profile_id = mp.id
                    WHERE t.monitored = TRUE AND t.has_file = TRUE
                      AND t.status NOT IN ('downloading', 'processing')
                      AND COALESCE(t.upgrade_allowed, mp.upgrade_allowed) = TRUE
                      AND t.quality_detected IS NOT NULL
                      AND {eligibilityClause("t", backoff_date_col)}
                    ORDER BY t.last_search_at ASC NULLS FIRST
                    LIMIT 50
                    """)
                if not rows:
                    continue

                profileIds = list({r["media_profile_id"] for r in rows})
                profileRows = await conn.fetch("SELECT * FROM media_profiles WHERE id = ANY($1)", profileIds)
                profiles = {r["id"]: MediaProfile.from_row(dict(r)) for r in profileRows}

                for row in rows:
                    item = dict(row)
                    profile = profiles.get(item["media_profile_id"])
                    if not profile:
                        continue

                    query = item["title"]
                    year = _query_year(item.get("year_src"))
                    if media_type == "movie" and year:
                        query += f" {year}"

                    searchStats = {}
                    try:
                        torrent_hash = await search_engine.search_and_download(
                            query=query,
                            profile=profile,
                            category=category,
                            tags=["kinora", f"{media_type}-{item['id']}"],
                            media_type=media_type,
                            history_conn=conn,
                            history_media_id=item["id"],
                            current_quality=item["quality_detected"],
                            grab_mode="upgrade",
                            upgrade_allowed=item["effective_upgrade"],
                            search_stats=searchStats,
                        )
                        await recordSearchAttempt(
                            conn,
                            table,
                            item["id"],
                            found=bool(torrent_hash),
                            indexer_outage=searchStats.get("all_indexers_failed", False),
                        )
                        if torrent_hash:
                            await conn.execute(
                                f"UPDATE {table} SET status = 'downloading', updated_at = NOW() WHERE id = $1",
                                item["id"],
                            )
                            grabbed += 1
                    except Exception as e:
                        print(f"Upgrade search error for {query}: {e}")

                    # Pause only when live indexer queries actually ran.
                    if searchStats.get("live_queries"):
                        await asyncio.sleep(2)

            # Shows and anime upgrade one episode at a time.
            for episodeMediaType in ("show", "anime"):
                try:
                    grabbed += await _searchEpisodeUpgrades(conn, episodeMediaType)
                except Exception as e:
                    print(f"Episode upgrade search error for {episodeMediaType}: {e}")

            # Music albums upgrade by quality tier rather than resolution.
            album_rows = await conn.fetch(f"""
                SELECT al.id, al.title, al.media_profile_id, al.quality_detected,
                       ar.name AS artist_name,
                       COALESCE(al.upgrade_allowed, mp.upgrade_allowed) AS effective_upgrade
                FROM albums al
                INNER JOIN media_profiles mp ON al.media_profile_id = mp.id
                LEFT JOIN artists ar ON al.artist_id = ar.id
                WHERE al.monitored = TRUE AND al.has_file = TRUE
                  AND al.status NOT IN ('downloading', 'processing')
                  AND COALESCE(al.upgrade_allowed, mp.upgrade_allowed) = TRUE
                  AND al.quality_detected IS NOT NULL
                  AND {eligibilityClause("al", "release_date")}
                ORDER BY al.last_search_at ASC NULLS FIRST
                LIMIT 50
                """)
            if album_rows:
                album_profile_ids = list({r["media_profile_id"] for r in album_rows})
                album_profile_rows = await conn.fetch(
                    "SELECT * FROM media_profiles WHERE id = ANY($1)", album_profile_ids
                )
                album_profiles = {r["id"]: MediaProfile.from_row(dict(r)) for r in album_profile_rows}

                for row in album_rows:
                    item = dict(row)
                    profile = album_profiles.get(item["media_profile_id"])
                    if not profile:
                        continue

                    artist_name = item.get("artist_name")
                    query = f"{artist_name} {item['title']}".strip() if artist_name else item["title"]

                    searchStats = {}
                    try:
                        torrent_hash = await search_engine.search_music_and_download(
                            query=query,
                            profile=profile,
                            tags=["kinora", "music", f"album-{item['id']}"],
                            history_conn=conn,
                            history_media_id=item["id"],
                            current_quality=item["quality_detected"],
                            grab_mode="upgrade",
                            upgrade_allowed=item["effective_upgrade"],
                            search_stats=searchStats,
                        )
                        await recordSearchAttempt(
                            conn,
                            "albums",
                            item["id"],
                            found=bool(torrent_hash),
                            indexer_outage=searchStats.get("all_indexers_failed", False),
                        )
                        if torrent_hash:
                            await conn.execute(
                                "UPDATE albums SET status = 'downloading', updated_at = NOW() WHERE id = $1",
                                item["id"],
                            )
                            grabbed += 1
                    except Exception as e:
                        print(f"Album upgrade search error for {query}: {e}")

                    # Pause only when live indexer queries actually ran.
                    if searchStats.get("live_queries"):
                        await asyncio.sleep(2)

        return {
            "status": "success",
            "upgrades_grabbed": grabbed,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        status = "failed"
        print(f"Upgrade search error: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        elapsedMs = int((time.time() - startTime) * 1000)
        await cacheSet(
            f"task:last_run:{taskName}",
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "status": status,
                "durationMs": elapsedMs,
            },
            expire=86400,
        )
