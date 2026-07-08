import os

from babelfish import Language
from subliminal import download_best_subtitles, save_subtitles, scan_video

from app.tasks.celery_app import celery_app, runAsync
from app.db import get_pool
from app.core.config import settings


@celery_app.task(name="app.tasks.subtitle_search.search_subtitles")
def search_subtitles(media_id: int, media_type: str, video_path: str):
    """
    Search and download subtitles for a single movie or show video file.
    """
    return runAsync(async_search_subtitles(media_id, media_type, video_path))


def _to_language(code: str):
    """Convert an ISO 639-1 (or 639-3) code to a babelfish Language, or None."""
    code = (code or "").strip()
    if not code:
        return None
    try:
        return Language.fromalpha2(code)
    except Exception:
        try:
            return Language(code)
        except Exception:
            return None


async def _resolve_languages(conn, media_profile_id):
    """
    Language order: profile subtitle_languages, else the global app setting, else English.
    """
    codes = []
    if media_profile_id:
        profile_langs = await conn.fetchval(
            "SELECT subtitle_languages FROM media_profiles WHERE id = $1", media_profile_id
        )
        if profile_langs:
            codes = list(profile_langs)
    if not codes:
        setting = await conn.fetchval("SELECT value FROM app_settings WHERE key = 'subtitle_languages'")
        codes = [c.strip() for c in (setting or "en").split(",") if c.strip()]

    languages = set()
    for code in codes:
        lang = _to_language(code)
        if lang is not None:
            languages.add(lang)
    return languages or {Language("eng")}


async def _opensubtitles_key(conn):
    """Read the OpenSubtitles API key from app_settings (decrypted) or the environment."""
    row = await conn.fetchrow("SELECT value, is_encrypted FROM app_settings WHERE key = 'opensubtitles_api_key'")
    if row and row["value"]:
        value = row["value"]
        if row["is_encrypted"]:
            try:
                from app.services.metadata.tmdb import decryptValue

                value = decryptValue(value)
            except Exception:
                value = ""
        if value:
            return value
    return settings.OPENSUBTITLES_API_KEY


def _existing_languages(video_path):
    """Return the set of ISO codes that already have a subtitle file next to the video."""
    directory = os.path.dirname(video_path)
    stem = os.path.splitext(os.path.basename(video_path))[0]
    existing = set()
    try:
        for name in os.listdir(directory):
            if name.startswith(stem) and name.lower().endswith((".srt", ".ass", ".sub")):
                parts = os.path.splitext(name)[0].split(".")
                if len(parts) >= 2:
                    existing.add(parts[-1].lower())
    except OSError:
        pass
    return existing


async def async_search_subtitles(media_id: int, media_type: str, video_path: str):
    """
    Download subtitles for one video file using Subliminal.
    Providers: Podnapisi (no auth) plus OpenSubtitles when an API key is configured.
    """
    if media_type == "anime":
        return {"status": "skipped", "reason": "Anime uses embedded subtitles", "subtitles_downloaded": 0}
    if media_type not in ("movie", "show"):
        return {"status": "error", "reason": f"Unknown media type: {media_type}", "subtitles_downloaded": 0}
    if not video_path or not os.path.exists(video_path):
        return {"status": "error", "reason": "Video file does not exist", "subtitles_downloaded": 0}

    pool = await get_pool()
    async with pool.acquire() as conn:
        table = "movies" if media_type == "movie" else "shows"
        media_profile_id = await conn.fetchval(f"SELECT media_profile_id FROM {table} WHERE id = $1", media_id)
        languages = await _resolve_languages(conn, media_profile_id)
        api_key = await _opensubtitles_key(conn)

    # Skip languages that already have a subtitle file next to the video.
    already = _existing_languages(video_path)

    def _alpha2(lang):
        try:
            return str(lang.alpha2)
        except Exception:
            return None

    languages = {lang for lang in languages if _alpha2(lang) not in already}
    if not languages:
        return {"status": "success", "subtitles_downloaded": 0, "reason": "All languages already present"}

    providers = ["podnapisi"]
    provider_configs = {}
    if api_key:
        providers.append("opensubtitlescom")
        provider_configs["opensubtitlescom"] = {"apikey": api_key}

    try:
        video = scan_video(video_path)
        subtitles = download_best_subtitles({video}, languages, providers=providers, provider_configs=provider_configs)
        if video in subtitles and subtitles[video]:
            saved = save_subtitles(video, subtitles[video])
            return {
                "status": "success",
                "subtitles_downloaded": len(saved),
                "languages": [str(sub.language) for sub in subtitles[video]],
            }
        return {"status": "success", "subtitles_downloaded": 0, "reason": "No subtitles found"}
    except Exception as e:
        return {"status": "error", "reason": str(e), "subtitles_downloaded": 0}
