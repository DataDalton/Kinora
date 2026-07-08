"""
Music tagging service.

Writes standard tags and optionally embeds album artwork and lyrics into audio files
using mutagen. Lyrics are fetched from lrclib.net. Handles FLAC, MP3, MP4/M4A, and
OGG/Opus. All operations are best-effort and never raise to the caller.
"""

import base64
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover
from mutagen.id3 import ID3, ID3NoHeaderError, APIC, USLT, TIT2, TPE1, TPE2, TALB, TDRC, TRCK, TPOS, TCON
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus

from app.core.http_client import http_get

_FLAC = {".flac"}
_MP3 = {".mp3"}
_MP4 = {".m4a", ".mp4", ".aac"}
_OGG = {".ogg", ".opus"}


def _picture(image_bytes: bytes) -> Picture:
    pic = Picture()
    pic.type = 3  # front cover
    pic.mime = "image/jpeg"
    pic.desc = "Cover"
    pic.data = image_bytes
    return pic


def _ogg_file(path: str):
    return OggOpus(path) if Path(path).suffix.lower() == ".opus" else OggVorbis(path)


def write_tags(path: str, tags: Dict[str, Any]) -> bool:
    """Write title/artist/album/albumartist/date/track/disc/genre tags."""
    ext = Path(path).suffix.lower()
    try:
        title = tags.get("title")
        artist = tags.get("artist")
        album = tags.get("album")
        albumartist = tags.get("albumartist") or artist
        date = str(tags.get("date")) if tags.get("date") else None
        track = str(tags.get("track")) if tags.get("track") else None
        disc = str(tags.get("disc")) if tags.get("disc") else None
        genre = tags.get("genre")

        if ext in _FLAC or ext in _OGG:
            audio = FLAC(path) if ext in _FLAC else _ogg_file(path)
            if title:
                audio["title"] = title
            if artist:
                audio["artist"] = artist
            if album:
                audio["album"] = album
            if albumartist:
                audio["albumartist"] = albumartist
            if date:
                audio["date"] = date
            if track:
                audio["tracknumber"] = track
            if disc:
                audio["discnumber"] = disc
            if genre:
                audio["genre"] = genre
            audio.save()
            return True

        if ext in _MP3:
            try:
                audio = ID3(path)
            except ID3NoHeaderError:
                audio = ID3()
            if title:
                audio.setall("TIT2", [TIT2(encoding=3, text=title)])
            if artist:
                audio.setall("TPE1", [TPE1(encoding=3, text=artist)])
            if albumartist:
                audio.setall("TPE2", [TPE2(encoding=3, text=albumartist)])
            if album:
                audio.setall("TALB", [TALB(encoding=3, text=album)])
            if date:
                audio.setall("TDRC", [TDRC(encoding=3, text=date)])
            if track:
                audio.setall("TRCK", [TRCK(encoding=3, text=track)])
            if disc:
                audio.setall("TPOS", [TPOS(encoding=3, text=disc)])
            if genre:
                audio.setall("TCON", [TCON(encoding=3, text=genre)])
            audio.save(path)
            return True

        if ext in _MP4:
            audio = MP4(path)
            if title:
                audio["\xa9nam"] = title
            if artist:
                audio["\xa9ART"] = artist
            if albumartist:
                audio["aART"] = albumartist
            if album:
                audio["\xa9alb"] = album
            if date:
                audio["\xa9day"] = date
            if genre:
                audio["\xa9gen"] = genre
            if track:
                audio["trkn"] = [(int(track), 0)]
            if disc:
                audio["disk"] = [(int(disc), 0)]
            audio.save()
            return True
    except Exception:
        return False
    return False


def embed_artwork(path: str, image_bytes: bytes) -> bool:
    """Embed cover art (JPEG bytes) into the audio file's metadata."""
    if not image_bytes:
        return False
    ext = Path(path).suffix.lower()
    try:
        if ext in _FLAC:
            audio = FLAC(path)
            audio.clear_pictures()
            audio.add_picture(_picture(image_bytes))
            audio.save()
            return True
        if ext in _OGG:
            audio = _ogg_file(path)
            audio["metadata_block_picture"] = [base64.b64encode(_picture(image_bytes).write()).decode("ascii")]
            audio.save()
            return True
        if ext in _MP3:
            try:
                audio = ID3(path)
            except ID3NoHeaderError:
                audio = ID3()
            audio.delall("APIC")
            audio.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=image_bytes))
            audio.save(path)
            return True
        if ext in _MP4:
            audio = MP4(path)
            audio["covr"] = [MP4Cover(image_bytes, imageformat=MP4Cover.FORMAT_JPEG)]
            audio.save()
            return True
    except Exception:
        return False
    return False


def embed_lyrics(path: str, lyrics: str) -> bool:
    """Embed plain lyrics into the audio file's metadata."""
    if not lyrics:
        return False
    ext = Path(path).suffix.lower()
    try:
        if ext in _FLAC or ext in _OGG:
            audio = FLAC(path) if ext in _FLAC else _ogg_file(path)
            audio["lyrics"] = lyrics
            audio.save()
            return True
        if ext in _MP3:
            try:
                audio = ID3(path)
            except ID3NoHeaderError:
                audio = ID3()
            audio.delall("USLT")
            audio.add(USLT(encoding=3, lang="eng", desc="", text=lyrics))
            audio.save(path)
            return True
        if ext in _MP4:
            audio = MP4(path)
            audio["\xa9lyr"] = lyrics
            audio.save()
            return True
    except Exception:
        return False
    return False


async def fetch_lyrics(
    artist: str, title: str, album: Optional[str] = None, duration: Optional[int] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetch lyrics from lrclib.net. Returns (plain_lyrics, synced_lyrics), either may be None.
    """
    if not artist or not title:
        return None, None
    params = {"artist_name": artist, "track_name": title}
    if album:
        params["album_name"] = album
    if duration:
        params["duration"] = int(duration)
    try:
        response = await http_get("https://lrclib.net/api/get", params=params)
        if response.status_code == 200:
            data = response.json()
            return data.get("plainLyrics"), data.get("syncedLyrics")
    except Exception:
        pass
    return None, None
