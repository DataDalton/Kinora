"""
Torrent contents for import.

Imports read the torrent's own file list from the download client rather than scanning
the save folder, because every download shares one save folder and a scan would pick up
files that belong to other torrents. Files are then sorted into the main media, extras,
subtitles, images and companion files, and anything on the never-import list is skipped.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Dict, Iterable, List, Optional

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".flv", ".webm", ".ts"}
AUDIO_EXTENSIONS = {".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".wma"}
SUBTITLE_EXTENSIONS = {".srt", ".ass", ".ssa", ".sub", ".idx", ".sup", ".vtt"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
MUSIC_COMPANION_EXTENSIONS = {".lrc", ".cue", ".log", ".pdf", ".m3u", ".m3u8", ".accurip"}

# Executables, scripts and shortcuts. These are never imported and cannot be removed
# from the never-import list in a profile.
FIXED_NEVER_IMPORT = [
    ".exe",
    ".bat",
    ".cmd",
    ".sh",
    ".msi",
    ".dll",
    ".scr",
    ".com",
    ".ps1",
    ".vbs",
    ".vbe",
    ".js",
    ".jse",
    ".wsf",
    ".jar",
    ".pif",
    ".hta",
    ".lnk",
    ".url",
    ".reg",
    ".cpl",
    ".msc",
    ".appx",
    ".apk",
    ".app",
    ".dmg",
    ".pkg",
    ".deb",
    ".rpm",
]

# Skipped by default and editable per profile. .nfo is skipped because media servers
# read it as item metadata and a torrent's .nfo could replace the correct title and ids.
DEFAULT_NEVER_IMPORT = [
    ".rar",
    ".zip",
    ".7z",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".iso",
    ".img",
    ".bin",
    ".torrent",
    ".nfo",
    ".txt",
    ".sfv",
    ".md5",
    ".sha1",
    ".sha256",
    ".par2",
    ".html",
    ".htm",
]

# Folder names media servers treat as extras. A video inside one keeps the folder name.
EXTRAS_FOLDER_NAMES = {
    "extras": "Extras",
    "extra": "Extras",
    "featurettes": "Featurettes",
    "featurette": "Featurettes",
    "behind the scenes": "Behind The Scenes",
    "deleted scenes": "Deleted Scenes",
    "interviews": "Interviews",
    "scenes": "Scenes",
    "shorts": "Shorts",
    "trailers": "Trailers",
    "other": "Other",
    "bonus": "Extras",
    "special features": "Extras",
}

# Image names Kinora writes itself. A torrent image with one of these names is renamed so
# it never takes the place of, or gets written through by, Kinora's own artwork.
RESERVED_IMAGE_STEMS = {
    "poster",
    "folder",
    "cover",
    "fanart",
    "backdrop",
    "background",
    "banner",
    "logo",
    "clearart",
    "landscape",
    "thumb",
    "disc",
    "artist",
}

# Executable extensions that, placed before the real extension, disguise a program as
# media, such as movie.exe.mkv.
_DISGUISED_EXECUTABLES = {"exe", "scr", "bat", "cmd", "com", "pif", "msi", "vbs", "js", "jar", "lnk", "hta", "ps1"}

_splitArchivePattern = re.compile(r"\.(r\d{2}|\d{3}|part\d+\.rar)$", re.IGNORECASE)
_samplePattern = re.compile(r"(^|[\W_])sample([\W_]|$)", re.IGNORECASE)
# Advert files that sites add to torrents. Only checked for images and companion files,
# because real videos often carry a site name at the start of the file name.
_adNamePattern = re.compile(
    r"(www\.|https?[:_]|torrents?\s*downloaded|downloaded\s+from|\bvisit\s|\b[\w-]+\.(com|net|xyz|info)\b)",
    re.IGNORECASE,
)


@dataclass
class TorrentFile:
    """One file in a torrent, with its path inside the torrent and on disk."""

    relativePath: str
    absolutePath: str
    size: int

    @property
    def extension(self) -> str:
        return PurePosixPath(self.relativePath).suffix.lower()

    @property
    def stem(self) -> str:
        return PurePosixPath(self.relativePath).stem

    @property
    def parentNames(self) -> List[str]:
        return [part.lower() for part in PurePosixPath(self.relativePath).parts[:-1]]


@dataclass
class SortedContents:
    """A torrent's files sorted by role for import."""

    videos: List[TorrentFile] = field(default_factory=list)
    audio: List[TorrentFile] = field(default_factory=list)
    subtitles: List[TorrentFile] = field(default_factory=list)
    images: List[TorrentFile] = field(default_factory=list)
    companions: List[TorrentFile] = field(default_factory=list)
    skipped: List[TorrentFile] = field(default_factory=list)


def normalizeExtensions(extensions: Optional[Iterable[str]]) -> List[str]:
    """Lowercase extensions and give each a leading dot."""
    normalized = []
    for ext in extensions or []:
        ext = (ext or "").strip().lower()
        if not ext:
            continue
        normalized.append(ext if ext.startswith(".") else f".{ext}")
    return normalized


def neverImportList(profileList: Optional[Iterable[str]]) -> set:
    """The profile's never-import extensions, or the defaults, always joined with the fixed list."""
    chosen = normalizeExtensions(profileList) if profileList is not None else DEFAULT_NEVER_IMPORT
    return set(chosen) | set(FIXED_NEVER_IMPORT)


def isNeverImport(torrentFile: TorrentFile, neverImport: set) -> bool:
    """True for files that are skipped regardless of their media role."""
    name = PurePosixPath(torrentFile.relativePath).name
    if torrentFile.extension in neverImport or _splitArchivePattern.search(name):
        return True
    return hasDisguisedExecutable(name)


def isAdvert(torrentFile: TorrentFile) -> bool:
    """Image or text files whose names are site adverts."""
    return bool(_adNamePattern.search(torrentFile.stem))


def isSample(torrentFile: TorrentFile) -> bool:
    """Sample clips, by file name or by a folder named sample."""
    return bool(_samplePattern.search(torrentFile.stem)) or "sample" in torrentFile.parentNames


def hasDisguisedExecutable(name: str) -> bool:
    """Names such as movie.exe.mkv, where an executable extension sits just before the real one."""
    parts = name.lower().split(".")
    return len(parts) >= 3 and parts[-2] in _DISGUISED_EXECUTABLES


async def getTorrentFiles(client, torrent) -> List[TorrentFile]:
    """
    The torrent's own files that exist on disk. Paths come from the download client's
    file list joined to the torrent's save path. Files deselected in the client are left
    out. An empty list means the client returned nothing, and the import fails rather
    than falling back to scanning the shared save folder.
    """
    savePath = torrent.save_path or ""
    entries: List[Dict[str, Any]] = await client.get_torrent_files(torrent.hash)
    files = []
    for entry in entries or []:
        relativePath = (entry.get("name") or "").replace("\\", "/")
        if not relativePath or entry.get("priority", 1) == 0:
            continue
        absolutePath = os.path.normpath(os.path.join(savePath, relativePath))
        # A file list entry can never point outside the torrent's save path.
        if os.path.commonpath([os.path.normpath(savePath), absolutePath]) != os.path.normpath(savePath):
            continue
        if os.path.isfile(absolutePath):
            files.append(TorrentFile(relativePath, absolutePath, int(entry.get("size") or 0)))
    return files


def sortContents(files: List[TorrentFile], neverImport: set) -> SortedContents:
    """Sort files by role. Never-import files and samples go to skipped."""
    contents = SortedContents()
    for torrentFile in files:
        ext = torrentFile.extension
        if isNeverImport(torrentFile, neverImport):
            contents.skipped.append(torrentFile)
        elif ext in VIDEO_EXTENSIONS:
            (contents.skipped if isSample(torrentFile) else contents.videos).append(torrentFile)
        elif ext in AUDIO_EXTENSIONS:
            contents.audio.append(torrentFile)
        elif ext in SUBTITLE_EXTENSIONS:
            contents.subtitles.append(torrentFile)
        elif ext in IMAGE_EXTENSIONS:
            (contents.skipped if isAdvert(torrentFile) else contents.images).append(torrentFile)
        elif ext in MUSIC_COMPANION_EXTENSIONS:
            (contents.skipped if isAdvert(torrentFile) else contents.companions).append(torrentFile)
        else:
            contents.skipped.append(torrentFile)
    return contents


def extrasFolderFor(torrentFile: TorrentFile) -> Optional[str]:
    """The extras folder name a video sits in inside the torrent, or None."""
    for name in reversed(torrentFile.parentNames):
        if name in EXTRAS_FOLDER_NAMES:
            return EXTRAS_FOLDER_NAMES[name]
    return None


def subtitleTag(subtitle: TorrentFile, videoStem: str) -> str:
    """
    The language or label part of a subtitle name, used as the suffix after the renamed
    video. 'Movie.2024.en.forced.srt' for video 'Movie.2024' gives 'en.forced', and
    'Subs/2_English.srt' gives 'English'.
    """
    stem = subtitle.stem
    if stem.lower().startswith(videoStem.lower()):
        tag = stem[len(videoStem) :].strip(" ._-")
    else:
        tag = re.sub(r"^\d+[\s._-]*", "", stem).strip(" ._-")
    tag = re.sub(r"[^\w.\- ]", "", tag).replace(" ", ".")
    return tag


def subtitlesForVideo(video: TorrentFile, subtitles: List[TorrentFile], onlyVideo: bool) -> List[TorrentFile]:
    """
    Subtitles that belong to a video. A subtitle matches when its name starts with the
    video's name, or when it sits in a folder named after the video. When the torrent has
    a single video, every subtitle belongs to it.
    """
    if onlyVideo:
        return list(subtitles)
    videoStem = video.stem.lower()
    matched = []
    for subtitle in subtitles:
        if subtitle.stem.lower().startswith(videoStem) or videoStem in subtitle.parentNames:
            matched.append(subtitle)
    return matched


def safeImageName(image: TorrentFile) -> str:
    """The image's file name, renamed when it collides with an artwork name Kinora writes."""
    stem = image.stem
    if stem.lower() in RESERVED_IMAGE_STEMS:
        stem = f"{stem}-torrent"
    return f"{stem}{image.extension}"


def uniquePath(path: str) -> str:
    """A path that does not exist yet, adding a counter before the extension when needed."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 2
    while os.path.exists(f"{base}.{counter}{ext}"):
        counter += 1
    return f"{base}.{counter}{ext}"


def isUnderPath(path: str, parent: str) -> bool:
    """True when path is parent itself or inside it, comparing resolved real paths."""
    if not path or not parent:
        return False
    realPath = os.path.realpath(path)
    realParent = os.path.realpath(parent)
    try:
        return os.path.commonpath([realPath, realParent]) == realParent
    except ValueError:
        return False
