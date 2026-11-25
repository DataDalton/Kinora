"""
Rename planning shared by the rename preview and the rename apply.

Target paths come from planItemPaths, which takes an item row, its naming settings, its
base folder, and the media files found under it, and returns one entry per file. It
never writes to disk or the database. The only disk reads below it are the media info
probes behind the naming tokens. classifyEntries then marks each entry as a change, as
unchanged, or as a conflict.

The preview and the apply both reach planItemPaths through planRow, so the paths a
preview shows are the paths an apply recomputes. applyEntries moves only entries whose
recomputed paths match the previewed ones, and reports the rest as stale.
"""

import asyncio
import os
import shutil
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from app.services import naming_tokens

STATUS_CHANGE = "change"
STATUS_UNCHANGED = "unchanged"
STATUS_CONFLICT = "conflict"
STATUS_ERROR = "error"
STATUS_APPLIED = "applied"
STATUS_STALE = "stale"

TABLE_MAP = {
    "movie": "movies",
    "show": "shows",
    "anime": "anime",
    "album": "albums",
    "artist": "artists",
}

# Artists have no files of their own, so they are accepted and produce no entries.
RENAMEABLE_TYPES = ("movie", "show", "anime", "album")

NAMING_DEFAULTS = {
    "movie": ("{Movie CleanTitle} ({Release Year})", "{Movie CleanTitle} ({Release Year})"),
    "show": ("{Show Title} - S{Season:00}E{Episode:00}", "{Show Title}/Season {Season:00}"),
    "anime": ("{Anime Title} - {Episode:00}", "{Anime Title}"),
}
MUSIC_DEFAULTS = {
    "artist": "{artist}",
    "album": "{album} ({year})",
    "track": "{track:00} - {title}",
    "multiDisc": "{disc:00}-{track:00} - {title}",
}
VIDEO_EXT = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".m4v", ".mpg", ".mpeg", ".m2ts", ".ts", ".webm"}
AUDIO_EXT = {".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".wma"}

PROFILE_NAMING_COLUMNS = (
    "movie_naming_format, movie_folder_format, show_naming_format, show_folder_format, "
    "anime_naming_format, anime_folder_format, music_artist_folder_format, music_album_folder_format, "
    "music_track_naming_format, music_multi_disc_format, illegal_char_replacement, colon_replacement"
)


@dataclass
class NamingConfig:
    """Naming formats for one media type, with the profile values or the built in defaults."""

    fileFormat: str = ""
    folderFormat: str = ""
    illegalReplacement: str = ""
    colonReplacement: str = " -"
    artistFolderFormat: str = ""
    albumFolderFormat: str = ""
    trackFormat: str = ""
    multiDiscFormat: str = ""


@dataclass
class RenameEntry:
    """One file of one item, with where it is now and where the naming format puts it."""

    mediaType: str
    itemId: int
    itemTitle: Optional[str]
    oldPath: Optional[str]
    newPath: Optional[str]
    status: str = ""
    message: Optional[str] = None
    # Order of the file within its item. The first planned file sets the item's file_path.
    position: int = 0


@dataclass
class RowPlan:
    """Entries for one item plus the row they were planned from."""

    mediaType: str
    row: dict
    entries: List[RenameEntry] = field(default_factory=list)


def namingFromProfile(mediaType: str, profile: Optional[dict]) -> NamingConfig:
    """Resolve the naming formats for a media type from a profile row, or defaults when absent."""
    prof = profile or {}
    config = NamingConfig(
        illegalReplacement=prof.get("illegal_char_replacement") or "",
        colonReplacement=prof.get("colon_replacement") or " -",
    )
    if mediaType in NAMING_DEFAULTS:
        defaultFile, defaultFolder = NAMING_DEFAULTS[mediaType]
        config.fileFormat = prof.get(f"{mediaType}_naming_format") or defaultFile
        config.folderFormat = prof.get(f"{mediaType}_folder_format") or defaultFolder
    elif mediaType == "album":
        config.artistFolderFormat = prof.get("music_artist_folder_format") or MUSIC_DEFAULTS["artist"]
        config.albumFolderFormat = prof.get("music_album_folder_format") or MUSIC_DEFAULTS["album"]
        config.trackFormat = prof.get("music_track_naming_format") or MUSIC_DEFAULTS["track"]
        config.multiDiscFormat = prof.get("music_multi_disc_format") or MUSIC_DEFAULTS["multiDisc"]
    return config


def itemTopFolder(filePath: str, rootPath: Optional[str]) -> str:
    """Return the item's top level folder (root/<ItemFolder>) or the file's directory."""
    if not rootPath:
        return filePath if os.path.isdir(filePath) else os.path.dirname(filePath)
    try:
        rel = os.path.relpath(filePath, rootPath)
    except ValueError:
        return os.path.dirname(filePath)
    first = rel.split(os.sep)[0]
    if first in ("", ".", ".."):
        return os.path.dirname(filePath)
    return os.path.join(rootPath, first)


def walkMedia(folder: str, extensions: set) -> List[str]:
    """List media files under a folder in sorted order, or the path itself when it is a file."""
    if os.path.isfile(folder):
        return [folder]
    found = []
    for dirpath, _dirs, files in os.walk(folder):
        for name in files:
            if Path(name).suffix.lower() in extensions:
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def itemTitle(mediaType: str, row: dict) -> Optional[str]:
    return row.get("name") if mediaType == "artist" else row.get("title")


def _albumGenre(row: dict) -> Optional[str]:
    genres = row.get("genres") or []
    if not genres:
        return None
    first = genres[0]
    return first.get("name") if isinstance(first, dict) else first


def _parseEpisode(fileName: str) -> dict:
    # Imported here so the planner can load without the Celery task module.
    from app.tasks.download_monitor import parse_episode_info

    return parse_episode_info(fileName)


def planItemPaths(
    mediaType: str,
    row: dict,
    naming: NamingConfig,
    basePath: str,
    sourceFiles: List[str],
    trackRows: Optional[List[dict]] = None,
    episodeParser: Callable[[str], dict] = _parseEpisode,
) -> List[RenameEntry]:
    """
    Render the target path of every source file of one item. Returns entries with an
    empty status, or with the error status for files that cannot be named. Writes
    nothing, so the preview and the apply share it.
    """
    itemId = row["id"]
    title = itemTitle(mediaType, row)
    illegal = naming.illegalReplacement
    colon = naming.colonReplacement
    entries: List[RenameEntry] = []

    def entry(src: str, newPath: Optional[str], position: int, message: Optional[str] = None) -> RenameEntry:
        return RenameEntry(
            mediaType=mediaType,
            itemId=itemId,
            itemTitle=title,
            oldPath=src,
            newPath=newPath,
            status=STATUS_ERROR if message else "",
            message=message,
            position=position,
        )

    if mediaType == "movie":
        for position, src in enumerate(sourceFiles):
            ctx = naming_tokens.build_movie_context(dict(row), src, os.path.basename(src))
            folderName = naming_tokens.render(
                naming.folderFormat, ctx, illegal_replacement=illegal, colon_replacement=colon
            )
            fileName = naming_tokens.render(
                naming.fileFormat,
                ctx,
                illegal_replacement=illegal,
                colon_replacement=colon,
                extension=Path(src).suffix,
            )
            entries.append(entry(src, os.path.join(basePath, folderName, fileName), position))
        return entries

    if mediaType in ("show", "anime"):
        for position, src in enumerate(sourceFiles):
            ep = episodeParser(os.path.basename(src))
            if ep.get("episode_number") is None:
                entries.append(entry(src, None, position, "No episode number found in the file name"))
                continue
            episodeInfo = {
                "season_number": ep.get("season_number") or 1,
                "episode_number": ep["episode_number"],
                "episode_title": ep.get("episode_title") or "",
                "absolute_episode": ep.get("absolute_episode"),
            }
            if mediaType == "show":
                ctx = naming_tokens.build_show_context(dict(row), episodeInfo, src, os.path.basename(src))
            else:
                ctx = naming_tokens.build_anime_context(dict(row), episodeInfo, src, os.path.basename(src))
            folderName = naming_tokens.render(
                naming.folderFormat, ctx, illegal_replacement=illegal, colon_replacement=colon
            )
            fileName = naming_tokens.render(
                naming.fileFormat,
                ctx,
                illegal_replacement=illegal,
                colon_replacement=colon,
                extension=Path(src).suffix,
            )
            entries.append(entry(src, os.path.join(basePath, folderName, fileName), position))
        return entries

    if mediaType == "album":
        from app.services.file_manager import FileManager

        fm = FileManager()
        tracks = trackRows or []
        useMeta = len(tracks) == len(sourceFiles)
        isMultiDisc = any((t.get("disk_number") or 1) > 1 for t in tracks)
        releaseDate = row.get("release_date")
        year = releaseDate.year if releaseDate and hasattr(releaseDate, "year") else None
        genre = _albumGenre(row)
        for position, src in enumerate(sourceFiles):
            idx = position + 1
            if useMeta:
                meta = tracks[position]
                discNumber = meta.get("disk_number") or 1
                trackNumber = meta.get("track_position") or idx
                trackTitle = meta.get("title") or Path(src).stem
            else:
                discNumber, trackNumber, trackTitle = 1, idx, Path(src).stem
            trackData = {
                "artist": row.get("artist_name") or "Unknown Artist",
                "album": row.get("title"),
                "year": year,
                "track_number": trackNumber,
                "disc_number": discNumber,
                "title": trackTitle,
                "genre": genre,
                "extension": Path(src).suffix,
            }
            artistFolder = fm.format_music_filename(
                pattern=naming.artistFolderFormat,
                track_data=trackData,
                include_extension=False,
                illegal_replacement=illegal,
                colon_replacement=colon,
            )
            albumFolder = fm.format_music_filename(
                pattern=naming.albumFolderFormat,
                track_data=trackData,
                include_extension=False,
                illegal_replacement=illegal,
                colon_replacement=colon,
            )
            trackName = fm.format_music_filename(
                pattern=(naming.multiDiscFormat if isMultiDisc else naming.trackFormat),
                track_data=trackData,
                include_extension=True,
                illegal_replacement=illegal,
                colon_replacement=colon,
            )
            entries.append(entry(src, os.path.join(basePath, artistFolder, albumFolder, trackName), position))
        return entries

    return entries


def planManualRename(filePath: str, newName: str) -> str:
    """Target of a manual rename. The file keeps its folder and its extension."""
    return os.path.join(os.path.dirname(filePath), newName + os.path.splitext(filePath)[1])


def planRow(
    mediaType: str,
    row: dict,
    naming: NamingConfig,
    rootPath: Optional[str],
    trackRows: Optional[List[dict]] = None,
    episodeParser: Callable[[str], dict] = _parseEpisode,
) -> List[RenameEntry]:
    """
    Find an item's source files on disk and plan their targets with planItemPaths.
    Reads the disk and never writes to it.
    """
    title = itemTitle(mediaType, row)
    filePath = row.get("file_path")

    def errorEntry(message: str) -> List[RenameEntry]:
        return [
            RenameEntry(
                mediaType=mediaType,
                itemId=row["id"],
                itemTitle=title,
                oldPath=filePath,
                newPath=None,
                status=STATUS_ERROR,
                message=message,
            )
        ]

    if mediaType not in RENAMEABLE_TYPES:
        return []
    if not row.get("has_file") or not filePath:
        return errorEntry("No file recorded for this item")
    if not os.path.exists(filePath):
        return errorEntry("File not found on disk")

    if mediaType == "movie":
        basePath = rootPath or os.path.dirname(os.path.dirname(filePath))
        sourceFiles = [filePath]
    else:
        top = itemTopFolder(filePath, rootPath)
        basePath = rootPath or os.path.dirname(top)
        sourceFiles = walkMedia(top, VIDEO_EXT if mediaType in ("show", "anime") else AUDIO_EXT)
        if not sourceFiles:
            return errorEntry("No media files found in the item folder")

    try:
        return planItemPaths(mediaType, row, naming, basePath, sourceFiles, trackRows, episodeParser)
    except Exception as e:
        return errorEntry(f"Could not build the new name: {e}")


def pathKey(path: str) -> str:
    """Comparison key for a path, matching how the host filesystem treats case."""
    return os.path.normcase(os.path.normpath(path))


def isSameFile(first: str, second: str) -> bool:
    """True when both paths name the same file, as with a case-only rename on a case-insensitive filesystem."""
    try:
        return os.path.samefile(first, second)
    except OSError:
        return False


def classifyEntries(
    entries: Iterable[RenameEntry],
    pathExists: Callable[[str], bool] = os.path.exists,
    isSameFile: Callable[[str, str], bool] = isSameFile,
) -> None:
    """
    Set the status of every entry still unclassified. An entry is unchanged when its
    target equals its source. It is a conflict when another entry in the same batch
    has the same target, or when its target already exists on disk as a different
    file. A case-only rename on a case-insensitive filesystem points at the source
    itself and stays a change.
    """
    pending = [e for e in entries if not e.status]
    candidates = []
    for e in pending:
        if os.path.normpath(e.newPath) == os.path.normpath(e.oldPath):
            e.status = STATUS_UNCHANGED
        else:
            candidates.append(e)

    targetCounts = Counter(pathKey(e.newPath) for e in candidates)
    for e in candidates:
        if targetCounts[pathKey(e.newPath)] > 1:
            e.status = STATUS_CONFLICT
            e.message = "Another file in this batch maps to the same target"
        elif pathExists(e.newPath) and not isSameFile(e.oldPath, e.newPath):
            e.status = STATUS_CONFLICT
            e.message = "A file already exists at the target path"
        else:
            e.status = STATUS_CHANGE


def statusCounts(entries: Iterable[RenameEntry]) -> Dict[str, int]:
    counts = Counter(e.status for e in entries)
    return {
        status: counts.get(status, 0) for status in (STATUS_CHANGE, STATUS_UNCHANGED, STATUS_CONFLICT, STATUS_ERROR)
    }


class NamingCache:
    """Per request lookups of profile naming settings and root folder paths."""

    def __init__(self, conn):
        self.conn = conn
        self.profiles: Dict[int, Optional[dict]] = {}
        self.roots: Dict[int, Optional[str]] = {}

    async def naming(self, mediaType: str, profileId: Optional[int]) -> NamingConfig:
        profile = None
        if profileId:
            if profileId not in self.profiles:
                fetched = await self.conn.fetchrow(
                    f"SELECT {PROFILE_NAMING_COLUMNS} FROM media_profiles WHERE id = $1", profileId
                )
                self.profiles[profileId] = dict(fetched) if fetched else None
            profile = self.profiles[profileId]
        return namingFromProfile(mediaType, profile)

    async def rootPath(self, rootFolderId: Optional[int]) -> Optional[str]:
        if not rootFolderId:
            return None
        if rootFolderId not in self.roots:
            self.roots[rootFolderId] = await self.conn.fetchval(
                "SELECT root_path FROM root_folders WHERE id = $1", rootFolderId
            )
        return self.roots[rootFolderId]


async def planRows(conn, mediaType: str, rows: Iterable[dict], cache: Optional[NamingCache] = None) -> List[RowPlan]:
    """Plan every item in rows. Database reads happen here, disk reads run off the event loop."""
    cache = cache or NamingCache(conn)
    plans: List[RowPlan] = []
    for raw in rows:
        row = dict(raw)
        naming = await cache.naming(mediaType, row.get("media_profile_id"))
        rootPath = await cache.rootPath(row.get("root_folder_id"))
        trackRows = None
        if mediaType == "album":
            fetched = await conn.fetch(
                "SELECT disk_number, track_position, title FROM tracks WHERE album_id = $1 "
                "ORDER BY disk_number, track_position",
                row["id"],
            )
            trackRows = [dict(t) for t in fetched]
        entries = await asyncio.to_thread(planRow, mediaType, row, naming, rootPath, trackRows)
        plans.append(RowPlan(mediaType=mediaType, row=row, entries=entries))
    return plans


async def buildPreview(conn, rowsByType: Dict[str, Iterable[dict]]) -> List[RowPlan]:
    """Plan and classify a batch that may span several media types. Writes nothing."""
    cache = NamingCache(conn)
    plans: List[RowPlan] = []
    for mediaType, rows in rowsByType.items():
        plans.extend(await planRows(conn, mediaType, rows, cache))
    allEntries = [e for plan in plans for e in plan.entries]
    await asyncio.to_thread(classifyEntries, allEntries)
    return plans


def _entryKey(mediaType: str, itemId: int, oldPath: str) -> Tuple[str, int, str]:
    return (mediaType, itemId, pathKey(oldPath))


def _moveFile(src: str, dst: str) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(src, dst)


def _itemFilePathAfter(mediaType: str, entries: List[RenameEntry]) -> Optional[str]:
    """The item's file_path once its moves are done, taken from its first planned file."""
    planned = sorted((e for e in entries if e.newPath), key=lambda e: e.position)
    if not planned:
        return None
    first = planned[0]
    path = first.newPath if first.status in (STATUS_APPLIED, STATUS_UNCHANGED) else first.oldPath
    return os.path.dirname(path) if mediaType == "album" else path


async def applyEntries(conn, requested: Iterable[dict]) -> List[RenameEntry]:
    """
    Recompute the plan for every item named in requested and move each requested file
    whose recomputed source and target still match what was previewed. Anything that
    no longer matches is reported as stale, conflicts are never moved, and no file is
    ever deleted. Each requested dict holds mediaType, itemId, oldPath and newPath.
    """
    requestedList = list(requested)
    idsByType: Dict[str, set] = {}
    for ref in requestedList:
        idsByType.setdefault(ref["mediaType"], set()).add(ref["itemId"])

    rowsByType: Dict[str, List[dict]] = {}
    for mediaType, ids in idsByType.items():
        if mediaType not in RENAMEABLE_TYPES:
            continue
        fetched = await conn.fetch(f"SELECT * FROM {TABLE_MAP[mediaType]} WHERE id = ANY($1)", list(ids))
        rowsByType[mediaType] = [dict(r) for r in fetched]

    plans = await buildPreview(conn, rowsByType)
    recomputed: Dict[Tuple[str, int, str], RenameEntry] = {}
    for plan in plans:
        for e in plan.entries:
            if e.oldPath:
                recomputed[_entryKey(e.mediaType, e.itemId, e.oldPath)] = e

    results: List[RenameEntry] = []
    touchedItems = set()
    for ref in requestedList:
        current = recomputed.get(_entryKey(ref["mediaType"], ref["itemId"], ref["oldPath"]))
        result = RenameEntry(
            mediaType=ref["mediaType"],
            itemId=ref["itemId"],
            itemTitle=current.itemTitle if current else None,
            oldPath=ref["oldPath"],
            newPath=ref["newPath"],
        )
        results.append(result)
        if current is None:
            result.status = STATUS_STALE
            result.message = "The file is no longer at the previewed path"
            continue
        if not current.newPath or pathKey(current.newPath) != pathKey(ref["newPath"]):
            result.status = STATUS_STALE
            result.message = "The naming format now gives a different target than the preview"
            continue
        if current.status != STATUS_CHANGE:
            result.status = STATUS_STALE if current.status == STATUS_UNCHANGED else current.status
            result.message = current.message or "The file is already at the target path"
            continue
        # The target could have appeared since the batch was classified.
        if os.path.exists(current.newPath) and not isSameFile(current.oldPath, current.newPath):
            current.status = STATUS_CONFLICT
            result.status = STATUS_CONFLICT
            result.message = "A file already exists at the target path"
            continue
        try:
            await asyncio.to_thread(_moveFile, current.oldPath, current.newPath)
            current.status = STATUS_APPLIED
            result.status = STATUS_APPLIED
            touchedItems.add((current.mediaType, current.itemId))
        except Exception as e:
            result.status = STATUS_ERROR
            result.message = f"Move failed: {e}"

    movedEntries = [r for r in results if r.status == STATUS_APPLIED]
    if movedEntries:
        from app.services import jellyfin

        jellyfin.queueLibraryUpdate([r.oldPath for r in movedEntries], jellyfin.UPDATE_DELETED)
        jellyfin.queueLibraryUpdate([r.newPath for r in movedEntries], jellyfin.UPDATE_CREATED)

    # Point each item at its renamed primary file once all of its moves are done.
    for plan in plans:
        if (plan.mediaType, plan.row["id"]) not in touchedItems:
            continue
        newFilePath = _itemFilePathAfter(plan.mediaType, plan.entries)
        if newFilePath and newFilePath != plan.row.get("file_path"):
            await conn.execute(
                f"UPDATE {TABLE_MAP[plan.mediaType]} SET file_path = $1, updated_at = NOW() WHERE id = $2",
                newFilePath,
                plan.row["id"],
            )

    return results
