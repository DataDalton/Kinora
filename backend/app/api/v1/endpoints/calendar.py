"""
Release calendar across movies, show episodes, anime episodes and albums.

Each media type is read with one query over the requested date range. Every entry carries
a status worked out from its date, its file, its active downloads and its monitoring, plus
the time the next automated search or RSS check can pick it up.
"""

import math
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.endpoints.auth import get_current_user
from app.core.cache import cacheGet
from app.db import get_db
from app.schemas.user import UserWithPermissions
from app.services.media_status import ACTIVE_DOWNLOAD_STATUSES
from app.services import download_episodes
from app.services.search_backoff import nextEligibleSql

router = APIRouter()

# Days after its release date that an item without a file counts as missing rather than
# waiting for its first release to appear.
MISSING_AFTER_DAYS = 7

# Longest range one request may cover, in days. A month view with leading and trailing
# weeks stays well inside it.
MAX_RANGE_DAYS = 100

# Range used when start or end is left out, in days before and after today.
DEFAULT_DAYS_BEFORE = 7
DEFAULT_DAYS_AFTER = 28

# Seconds between dispatcher ticks, the soonest a due task can fire.
DISPATCHER_TICK_SECONDS = 60

# Calendar media type -> view permission prefix.
MEDIA_PERMISSION_PREFIX = {
    "movie": "movies",
    "show": "shows",
    "anime": "anime",
    "album": "music",
}

# Calendar media type -> dispatcher key of the task that searches for it. Movies and
# albums have a backoff-scheduled search. Missing episodes are picked up by the RSS check.
SEARCH_TASK_KEYS = {
    "movie": "wanted_search",
    "album": "music_wanted_search",
    "show": "rss_monitor",
    "anime": "rss_monitor",
}


def _activeDownloadSql(mediaType: str, mediaIdSql: str) -> str:
    """SQL condition true when the item has a download in an active status."""
    return f"""EXISTS (
        SELECT 1 FROM download_history dh
        WHERE dh.media_type = '{mediaType}' AND dh.media_id = {mediaIdSql}
          AND dh.status = ANY($3::text[])
    )"""


def _episodeDownloadSql(mediaType: str, seriesIdSql: str, alias: str) -> str:
    """
    SQL condition true when an active download covers the episode. Each series download
    stores the ids of the episodes its release holds in episode_ids when it starts.
    """
    return f"""EXISTS (
        SELECT 1 FROM download_history dh
        WHERE dh.media_type = '{mediaType}' AND dh.media_id = {seriesIdSql}
          AND dh.status = ANY($3::text[])
          AND (dh.episode_id = {alias}.id OR {alias}.id = ANY(dh.episode_ids))
    )"""


MOVIE_SQL = f"""
    SELECT * FROM (
        SELECT m.id, m.title, m.poster_path, m.monitored, m.has_file, m.status,
               m.release_date::date AS release_day,
               m.digital_release_date, m.physical_release_date, m.theatrical_release_date,
               COALESCE(m.digital_release_date, m.physical_release_date,
                        m.theatrical_release_date, m.release_date::date) AS calendar_date,
               EXISTS (SELECT 1 FROM media_profiles mp WHERE mp.id = m.media_profile_id) AS searchable,
               {nextEligibleSql("m", "release_date")} AS next_eligible_at,
               {_activeDownloadSql("movie", "m.id")} AS downloading
        FROM movies m
        WHERE ($4 = FALSE OR m.monitored)
    ) movie_dates
    WHERE calendar_date BETWEEN $1 AND $2
    ORDER BY calendar_date, title
"""

SHOW_SQL = f"""
    SELECT e.id AS episode_id, e.show_id AS series_id, s.title, s.poster_path,
           e.title AS episode_title, e.season_number, e.episode_number,
           e.air_date AS calendar_date, e.has_file,
           (s.monitored AND e.monitored) AS monitored,
           EXISTS (SELECT 1 FROM media_profiles mp WHERE mp.id = s.media_profile_id) AS searchable,
           {_episodeDownloadSql("show", "s.id", "e")} AS downloading
    FROM episodes e
    INNER JOIN shows s ON s.id = e.show_id
    WHERE e.air_date BETWEEN $1 AND $2
      AND ($4 = FALSE OR (s.monitored AND e.monitored))
    ORDER BY e.air_date, s.title, e.season_number, e.episode_number
"""

# Anime episodes by air date, plus anime without episode rows (films and specials) by
# their release date.
ANIME_SQL = f"""
    SELECT ae.id AS episode_id, ae.anime_id AS series_id, a.title, a.poster_path,
           ae.title AS episode_title, ae.season_number, ae.episode_number,
           ae.air_date AS calendar_date, ae.has_file,
           (a.monitored AND ae.monitored) AS monitored,
           EXISTS (SELECT 1 FROM media_profiles mp WHERE mp.id = a.media_profile_id) AS searchable,
           {_episodeDownloadSql("anime", "a.id", "ae")} AS downloading
    FROM anime_episodes ae
    INNER JOIN anime a ON a.id = ae.anime_id
    WHERE ae.air_date BETWEEN $1 AND $2
      AND ($4 = FALSE OR (a.monitored AND ae.monitored))
    UNION ALL
    SELECT NULL::int AS episode_id, a.id AS series_id, a.title, a.poster_path,
           NULL AS episode_title, NULL::int AS season_number, NULL::int AS episode_number,
           a.release_date::date AS calendar_date, a.has_file,
           a.monitored,
           EXISTS (SELECT 1 FROM media_profiles mp WHERE mp.id = a.media_profile_id) AS searchable,
           {_activeDownloadSql("anime", "a.id")} AS downloading
    FROM anime a
    WHERE a.release_date::date BETWEEN $1 AND $2
      AND ($4 = FALSE OR a.monitored)
      AND NOT EXISTS (SELECT 1 FROM anime_episodes ae2 WHERE ae2.anime_id = a.id)
    ORDER BY calendar_date, title, season_number NULLS FIRST, episode_number NULLS FIRST
"""

ALBUM_SQL = f"""
    SELECT al.id, al.title, al.artist_id, COALESCE(al.artist_name, ar.name) AS artist_name,
           COALESCE(al.cover_medium, al.cover) AS cover, al.record_type,
           al.release_date::date AS calendar_date, al.monitored, al.status,
           (al.has_file OR al.status = 'completed') AS has_file,
           (al.status = 'wanted') AS searchable,
           {nextEligibleSql("al", "release_date")} AS next_eligible_at,
           {_activeDownloadSql("album", "al.id")} AS downloading
    FROM albums al
    LEFT JOIN artists ar ON ar.id = al.artist_id
    WHERE al.release_date::date BETWEEN $1 AND $2
      AND ($4 = FALSE OR al.monitored)
    ORDER BY calendar_date, artist_name, al.title
"""


def entryStatus(day: date, today: date, hasFile: bool, downloading: bool, monitored: bool) -> str:
    """
    Calendar status of one entry. A file wins over an active download, which wins over
    the date. Released items without a file are waiting until MISSING_AFTER_DAYS have
    passed and missing after that, or unmonitored when nothing searches for them.
    """
    if hasFile:
        return "available"
    if downloading:
        return "downloading"
    if day > today:
        return "upcoming"
    if not monitored:
        return "unmonitored"
    if (today - day).days >= MISSING_AFTER_DAYS:
        return "missing"
    return "waiting"


async def _loadTaskSchedules(conn: asyncpg.Connection) -> Dict[str, Dict[str, float]]:
    """
    Last dispatch time and interval in seconds for each task behind SEARCH_TASK_KEYS,
    read from the same cache markers and app settings the dispatcher uses.
    """
    from app.tasks.dispatcher import SCHEDULED_TASKS

    taskKeys = set(SEARCH_TASK_KEYS.values())
    settingKeys = [SCHEDULED_TASKS[k]["setting"] for k in taskKeys if "setting" in SCHEDULED_TASKS[k]]
    settingRows = await conn.fetch("SELECT key, value FROM app_settings WHERE key = ANY($1)", settingKeys)
    settingValues = {row["key"]: row["value"] for row in settingRows}

    schedules = {}
    for taskKey in taskKeys:
        spec = SCHEDULED_TASKS[taskKey]
        try:
            minutes = int(settingValues.get(spec.get("setting", "")) or spec["default_minutes"])
        except TypeError, ValueError:
            minutes = spec["default_minutes"]
        lastDispatch = await cacheGet(f"dispatch:last:{taskKey}")
        schedules[taskKey] = {
            "lastDispatch": float(lastDispatch) if isinstance(lastDispatch, (int, float)) else None,
            "intervalSeconds": max(1, minutes) * 60,
        }
    return schedules


def _nextRunAt(schedule: Dict[str, Any], notBefore: Optional[datetime], nowTs: float) -> datetime:
    """
    First run of a dispatched task at or after notBefore. Runs fall on the last dispatch
    plus whole intervals. An overdue or never-dispatched task fires on the next tick.
    """
    intervalSeconds = schedule["intervalSeconds"]
    lastDispatch = schedule["lastDispatch"]
    nextTs = lastDispatch + intervalSeconds if lastDispatch is not None else nowTs
    if nextTs < nowTs + DISPATCHER_TICK_SECONDS:
        nextTs = nowTs + DISPATCHER_TICK_SECONDS
    if notBefore is not None:
        notBeforeTs = (
            notBefore.replace(tzinfo=timezone.utc).timestamp() if notBefore.tzinfo is None else notBefore.timestamp()
        )
        if notBeforeTs > nextTs:
            nextTs += math.ceil((notBeforeTs - nextTs) / intervalSeconds) * intervalSeconds
    return datetime.fromtimestamp(nextTs, tz=timezone.utc).replace(microsecond=0)


def _isoDay(value: Optional[date]) -> Optional[str]:
    return value.isoformat() if value else None


def _parseTypes(types: Optional[str]) -> List[str]:
    """Requested media types, defaulting to all. Unknown names are rejected."""
    if not types:
        return list(MEDIA_PERMISSION_PREFIX)
    requested = [t.strip().lower() for t in types.split(",") if t.strip()]
    unknown = [t for t in requested if t not in MEDIA_PERMISSION_PREFIX]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown media type: {', '.join(unknown)}",
        )
    return requested


@router.get("/")
async def get_calendar(
    start: Optional[date] = Query(None, description="First day of the range, inclusive."),
    end: Optional[date] = Query(None, description="Last day of the range, inclusive."),
    types: Optional[str] = Query(None, description="Comma separated media types: movie, show, anime, album."),
    monitoredOnly: bool = Query(False),
    current_user: UserWithPermissions = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Releases dated within the range for every media type the user can view, sorted by
    date. Media types without view permission are left out.
    """
    today = date.today()
    rangeStart = start or today - timedelta(days=DEFAULT_DAYS_BEFORE)
    rangeEnd = end or today + timedelta(days=DEFAULT_DAYS_AFTER)
    if rangeEnd < rangeStart:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end must not be before start")
    if (rangeEnd - rangeStart).days > MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Range may cover at most {MAX_RANGE_DAYS} days",
        )

    permissions = set(current_user.permissions or [])
    viewableTypes = [t for t in MEDIA_PERMISSION_PREFIX if f"{MEDIA_PERMISSION_PREFIX[t]}.view" in permissions]
    if not viewableTypes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No media view permission")
    selectedTypes = [t for t in _parseTypes(types) if t in viewableTypes]

    activeStatuses = list(ACTIVE_DOWNLOAD_STATUSES)
    # Active downloads saved before episode_ids existed get their episodes recorded first.
    await download_episodes.fillMissingCoveredEpisodes(conn, activeStatuses)
    queryArgs = (rangeStart, rangeEnd, activeStatuses, monitoredOnly)
    schedules = await _loadTaskSchedules(conn)
    nowTs = time.time()
    entries: List[Dict[str, Any]] = []

    def searchFields(mediaType: str, row, entryState: str, notBefore: Optional[datetime]) -> Dict[str, Any]:
        """Next search time for entries that an automated search or RSS check still covers."""
        if entryState not in ("waiting", "missing") or not row["monitored"] or not row["searchable"]:
            return {"nextSearchAt": None, "nextSearchKind": None}
        taskKey = SEARCH_TASK_KEYS[mediaType]
        nextRun = _nextRunAt(schedules[taskKey], notBefore, nowTs)
        return {
            "nextSearchAt": nextRun.isoformat().replace("+00:00", "Z"),
            "nextSearchKind": "rss" if taskKey == "rss_monitor" else "search",
        }

    if "movie" in selectedTypes:
        for row in await conn.fetch(MOVIE_SQL, *queryArgs):
            day = row["calendar_date"]
            if row["digital_release_date"]:
                dateKind = "digital"
            elif row["physical_release_date"]:
                dateKind = "physical"
            elif row["theatrical_release_date"]:
                dateKind = "theatrical"
            else:
                dateKind = "release"
            hasFile = bool(row["has_file"])
            downloading = bool(row["downloading"]) or row["status"] in ("downloading", "processing")
            entryState = entryStatus(day, today, hasFile, downloading, row["monitored"])
            entries.append(
                {
                    "key": f"movie-{row['id']}",
                    "mediaType": "movie",
                    "mediaId": row["id"],
                    "episodeId": None,
                    "title": row["title"],
                    "subtitle": None,
                    "seasonNumber": None,
                    "episodeNumber": None,
                    "date": day.isoformat(),
                    "dateKind": dateKind,
                    "digitalDate": _isoDay(row["digital_release_date"]),
                    "physicalDate": _isoDay(row["physical_release_date"]),
                    "theatricalDate": _isoDay(row["theatrical_release_date"] or row["release_day"]),
                    "imageUrl": row["poster_path"],
                    "monitored": row["monitored"],
                    "hasFile": hasFile,
                    "status": entryState,
                    **searchFields("movie", row, entryState, row["next_eligible_at"]),
                }
            )

    for mediaType, sql in (("show", SHOW_SQL), ("anime", ANIME_SQL)):
        if mediaType not in selectedTypes:
            continue
        for row in await conn.fetch(sql, *queryArgs):
            day = row["calendar_date"]
            hasFile = bool(row["has_file"])
            entryState = entryStatus(day, today, hasFile, bool(row["downloading"]), row["monitored"])
            fields = searchFields(mediaType, row, entryState, None)
            entries.append(
                {
                    "key": f"{mediaType}-{row['series_id']}-{row['episode_id'] or 'series'}",
                    "mediaType": mediaType,
                    "mediaId": row["series_id"],
                    "episodeId": row["episode_id"],
                    "title": row["title"],
                    "subtitle": row["episode_title"],
                    "seasonNumber": row["season_number"],
                    "episodeNumber": row["episode_number"],
                    "date": day.isoformat(),
                    "dateKind": "airDate",
                    "digitalDate": None,
                    "physicalDate": None,
                    "theatricalDate": None,
                    "imageUrl": row["poster_path"],
                    "monitored": row["monitored"],
                    "hasFile": hasFile,
                    "status": entryState,
                    **fields,
                }
            )

    if "album" in selectedTypes:
        for row in await conn.fetch(ALBUM_SQL, *queryArgs):
            day = row["calendar_date"]
            hasFile = bool(row["has_file"])
            downloading = bool(row["downloading"]) or row["status"] in ("downloading", "processing")
            entryState = entryStatus(day, today, hasFile, downloading, row["monitored"])
            entries.append(
                {
                    "key": f"album-{row['id']}",
                    "mediaType": "album",
                    "mediaId": row["id"],
                    "episodeId": None,
                    "artistId": row["artist_id"],
                    "title": row["title"],
                    "subtitle": row["artist_name"],
                    "recordType": row["record_type"],
                    "seasonNumber": None,
                    "episodeNumber": None,
                    "date": day.isoformat(),
                    "dateKind": "release",
                    "digitalDate": None,
                    "physicalDate": None,
                    "theatricalDate": None,
                    "imageUrl": row["cover"],
                    "monitored": row["monitored"],
                    "hasFile": hasFile,
                    "status": entryState,
                    **searchFields("album", row, entryState, row["next_eligible_at"]),
                }
            )

    entries.sort(key=lambda e: (e["date"], e["title"] or "", e["seasonNumber"] or 0, e["episodeNumber"] or 0))
    return {
        "start": rangeStart.isoformat(),
        "end": rangeEnd.isoformat(),
        "today": today.isoformat(),
        "types": selectedTypes,
        "missingAfterDays": MISSING_AFTER_DAYS,
        "entries": entries,
    }
