import os
from typing import List, Optional
from pathlib import Path
import asyncpg
from babelfish import Language
from subliminal import download_best_subtitles, save_subtitles, scan_video
from subliminal.providers.podnapisi import PodnapisiProvider

from app.tasks.celery_app import celery_app
from app.core.database import get_pool


@celery_app.task(name="app.tasks.subtitle_search.search_subtitles")
async def search_subtitles(media_id: int, media_type: str):
    """
    Search and download subtitles using Subliminal with Podnapisi provider
    Only searches for movies and TV shows (anime uses embedded subs)
    """
    if media_type == "anime":
        return {"status": "skipped", "reason": "Anime uses embedded subtitles", "subtitles_downloaded": 0}

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get media item and settings
        if media_type == "movie":
            row = await conn.fetchrow("SELECT * FROM movies WHERE id = $1", media_id)
        elif media_type == "show":
            row = await conn.fetchrow("SELECT * FROM shows WHERE id = $1", media_id)
        else:
            return {"status": "error", "reason": f"Unknown media type: {media_type}", "subtitles_downloaded": 0}

        if not row:
            return {"status": "error", "reason": f"{media_type} not found", "subtitles_downloaded": 0}

        media = dict(row)

        # Check if file exists
        if not media.get("has_file") or not media.get("file_path"):
            return {"status": "skipped", "reason": "No video file found", "subtitles_downloaded": 0}

        video_path = media["file_path"]
        if not os.path.exists(video_path):
            return {"status": "error", "reason": "Video file does not exist", "subtitles_downloaded": 0}

        # Get subtitle language settings
        lang_setting = await conn.fetchval("SELECT value FROM settings WHERE key = 'subtitle_languages'")
        languages = [Language(lang.strip()) for lang in (lang_setting or "en").split(",")]

        try:
            # Scan video file to extract metadata
            video = scan_video(video_path)

            # Search for subtitles using Podnapisi provider only
            subtitles = download_best_subtitles(
                {video},
                languages,
                providers=["podnapisi"],
                provider_configs={}
            )

            # Save subtitles to disk
            if video in subtitles and subtitles[video]:
                saved_count = save_subtitles(video, subtitles[video])

                return {
                    "status": "success",
                    "subtitles_downloaded": len(saved_count),
                    "languages": [str(sub.language) for sub in subtitles[video]]
                }
            else:
                return {"status": "success", "subtitles_downloaded": 0, "reason": "No subtitles found"}

        except Exception as e:
            return {"status": "error", "reason": str(e), "subtitles_downloaded": 0}
