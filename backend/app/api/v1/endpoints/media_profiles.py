from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel, field_validator
import asyncpg

from app.db import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.services import naming_tokens

try:
    import iso639

    ISO639_AVAILABLE = True
except ImportError:
    ISO639_AVAILABLE = False


def validate_language_code(code: str) -> bool:
    """Validate ISO 639-1 language code"""
    if not ISO639_AVAILABLE:
        return len(code) == 2
    try:
        iso639.Language.match(code)
        return True
    except iso639.LanguageNotFoundError:
        return False


router = APIRouter()


class MediaProfileCreate(BaseModel):
    """
    Create media profile

    All list fields are ordered by preference (highest priority first):
    - If value is in list: allowed
    - Position in list: determines preference (index 0 = most preferred)
    - If value NOT in list: rejected
    """

    name: str
    # Per-media-type quality: Movies
    movie_resolutions: Optional[List[str]] = []
    movie_codecs: Optional[List[str]] = []
    movie_sources: Optional[List[str]] = []
    movie_audio_codecs: Optional[List[str]] = []
    movie_audio_channels: Optional[List[str]] = []
    movie_hdr_formats: Optional[List[str]] = []
    movie_editions: Optional[List[str]] = []
    movie_min_size: Optional[int] = None
    movie_max_size: Optional[int] = None
    # Per-media-type quality: TV Shows
    show_resolutions: Optional[List[str]] = []
    show_codecs: Optional[List[str]] = []
    show_sources: Optional[List[str]] = []
    show_audio_codecs: Optional[List[str]] = []
    show_audio_channels: Optional[List[str]] = []
    show_hdr_formats: Optional[List[str]] = []
    show_min_size: Optional[int] = None
    show_max_size: Optional[int] = None
    # Per-media-type quality: Anime
    anime_resolutions: Optional[List[str]] = []
    anime_codecs: Optional[List[str]] = []
    anime_sources: Optional[List[str]] = []
    anime_audio_codecs: Optional[List[str]] = []
    anime_audio_channels: Optional[List[str]] = []
    anime_hdr_formats: Optional[List[str]] = []
    anime_min_size: Optional[int] = None
    anime_max_size: Optional[int] = None
    # Common settings
    languages: Optional[List[str]] = []
    subtitle_languages: Optional[List[str]] = []
    upgrade_allowed: Optional[bool] = True
    uploaders: Optional[List[str]] = []
    release_groups: Optional[List[str]] = []
    regex_filters: Optional[List[str]] = []
    seeder_weight: Optional[int] = 34
    size_weight: Optional[int] = 33
    recency_weight: Optional[int] = 33
    search_sort_preference: Optional[str] = "weighted"
    season_pack_preference: Optional[str] = "prefer"
    search_timeout: Optional[int] = 30
    max_retries: Optional[int] = 3
    max_results: Optional[int] = 100
    min_seeds: Optional[int] = 1
    upgrade_replace_policy: Optional[str] = "keep_old"
    # Naming formats
    movie_naming_format: Optional[str] = None
    movie_folder_format: Optional[str] = None
    show_naming_format: Optional[str] = None
    show_folder_format: Optional[str] = None
    anime_naming_format: Optional[str] = None
    anime_folder_format: Optional[str] = None
    # Anime options
    anime_subtitle_preference: Optional[str] = "softsub"
    anime_allow_hardsub: Optional[bool] = False
    anime_prefer_dual_audio: Optional[bool] = False
    anime_audio_language: Optional[str] = "ja"
    anime_subtitle_language: Optional[str] = "en"
    # Indexers per media type
    movie_indexers: Optional[List[str]] = []
    show_indexers: Optional[List[str]] = []
    anime_indexers: Optional[List[str]] = []
    music_indexers: Optional[List[str]] = []
    # Music settings
    music_artist_folder_format: Optional[str] = "{artist}"
    music_album_folder_format: Optional[str] = "{album} ({year})"
    music_track_naming_format: Optional[str] = "{track:00} - {title}"
    music_multi_disc_format: Optional[str] = "{disc:00}-{track:00} - {title}"
    music_preferred_quality: Optional[List[str]] = ["flac", "mp3_320", "mp3_256", "aac"]
    music_embed_lyrics: Optional[bool] = True
    music_embed_artwork: Optional[bool] = True
    # File output settings
    media_server: Optional[str] = "jellyfin"
    use_hardlinks: Optional[bool] = True
    illegal_char_replacement: Optional[str] = "_"
    colon_replacement: Optional[str] = " -"
    # Torrent validation settings
    validation_enabled: Optional[bool] = True
    validation_mode: Optional[str] = "allowlist"
    forbidden_extensions: Optional[List[str]] = [
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
        ".jar",
    ]
    validation_failure_action: Optional[str] = "pause_notify"
    movie_allowed_extensions: Optional[List[str]] = [
        ".mkv",
        ".mp4",
        ".avi",
        ".m4v",
        ".mov",
        ".wmv",
        ".flv",
        ".webm",
        ".ts",
    ]
    show_allowed_extensions: Optional[List[str]] = [
        ".mkv",
        ".mp4",
        ".avi",
        ".m4v",
        ".mov",
        ".wmv",
        ".flv",
        ".webm",
        ".ts",
    ]
    anime_allowed_extensions: Optional[List[str]] = [".mkv", ".mp4", ".avi", ".m4v"]
    music_allowed_extensions: Optional[List[str]] = [".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".wma"]
    # Seeding overrides (None = inherit global download-client default)
    seed_ratio_limit: Optional[float] = None
    seed_time_limit: Optional[int] = None
    inactive_seed_time_limit: Optional[int] = None
    seed_then_cleanup: Optional[bool] = False
    auto_recovery: Optional[bool] = None

    @field_validator("languages", "subtitle_languages")
    @classmethod
    def validate_languages(cls, v):
        """Validate all language codes in languages list"""
        if v:
            for code in v:
                if not validate_language_code(code):
                    raise ValueError(f"Invalid ISO 639-1 language code: {code}")
        return v

    @field_validator("anime_audio_language", "anime_subtitle_language")
    @classmethod
    def validate_anime_languages(cls, v):
        """Validate anime language codes"""
        if v and not validate_language_code(v):
            raise ValueError(f"Invalid ISO 639-1 language code: {v}")
        return v


class MediaProfileUpdate(BaseModel):
    """Update media profile (all fields optional for partial updates)"""

    name: Optional[str] = None
    # Per-media-type quality: Movies
    movie_resolutions: Optional[List[str]] = None
    movie_codecs: Optional[List[str]] = None
    movie_sources: Optional[List[str]] = None
    movie_audio_codecs: Optional[List[str]] = None
    movie_audio_channels: Optional[List[str]] = None
    movie_hdr_formats: Optional[List[str]] = None
    movie_editions: Optional[List[str]] = None
    movie_min_size: Optional[int] = None
    movie_max_size: Optional[int] = None
    # Per-media-type quality: TV Shows
    show_resolutions: Optional[List[str]] = None
    show_codecs: Optional[List[str]] = None
    show_sources: Optional[List[str]] = None
    show_audio_codecs: Optional[List[str]] = None
    show_audio_channels: Optional[List[str]] = None
    show_hdr_formats: Optional[List[str]] = None
    show_min_size: Optional[int] = None
    show_max_size: Optional[int] = None
    # Per-media-type quality: Anime
    anime_resolutions: Optional[List[str]] = None
    anime_codecs: Optional[List[str]] = None
    anime_sources: Optional[List[str]] = None
    anime_audio_codecs: Optional[List[str]] = None
    anime_audio_channels: Optional[List[str]] = None
    anime_hdr_formats: Optional[List[str]] = None
    anime_min_size: Optional[int] = None
    anime_max_size: Optional[int] = None
    # Common settings
    languages: Optional[List[str]] = None
    subtitle_languages: Optional[List[str]] = None
    upgrade_allowed: Optional[bool] = None
    uploaders: Optional[List[str]] = None
    release_groups: Optional[List[str]] = None
    regex_filters: Optional[List[str]] = None
    seeder_weight: Optional[int] = None
    size_weight: Optional[int] = None
    recency_weight: Optional[int] = None
    search_sort_preference: Optional[str] = None
    season_pack_preference: Optional[str] = None
    search_timeout: Optional[int] = None
    max_retries: Optional[int] = None
    max_results: Optional[int] = None
    min_seeds: Optional[int] = None
    upgrade_replace_policy: Optional[str] = None
    # Naming formats
    movie_naming_format: Optional[str] = None
    movie_folder_format: Optional[str] = None
    show_naming_format: Optional[str] = None
    show_folder_format: Optional[str] = None
    anime_naming_format: Optional[str] = None
    anime_folder_format: Optional[str] = None
    # Anime options
    anime_subtitle_preference: Optional[str] = None
    anime_allow_hardsub: Optional[bool] = None
    anime_prefer_dual_audio: Optional[bool] = None
    anime_audio_language: Optional[str] = None
    anime_subtitle_language: Optional[str] = None
    # Indexers per media type
    movie_indexers: Optional[List[str]] = None
    show_indexers: Optional[List[str]] = None
    anime_indexers: Optional[List[str]] = None
    music_indexers: Optional[List[str]] = None
    # Music settings
    music_artist_folder_format: Optional[str] = None
    music_album_folder_format: Optional[str] = None
    music_track_naming_format: Optional[str] = None
    music_multi_disc_format: Optional[str] = None
    music_preferred_quality: Optional[List[str]] = None
    music_embed_lyrics: Optional[bool] = None
    music_embed_artwork: Optional[bool] = None
    # File output settings
    media_server: Optional[str] = None
    use_hardlinks: Optional[bool] = None
    illegal_char_replacement: Optional[str] = None
    colon_replacement: Optional[str] = None
    # Torrent validation settings
    validation_enabled: Optional[bool] = None
    validation_mode: Optional[str] = None
    forbidden_extensions: Optional[List[str]] = None
    validation_failure_action: Optional[str] = None
    movie_allowed_extensions: Optional[List[str]] = None
    show_allowed_extensions: Optional[List[str]] = None
    anime_allowed_extensions: Optional[List[str]] = None
    music_allowed_extensions: Optional[List[str]] = None
    # Seeding overrides (None = inherit global download-client default)
    seed_ratio_limit: Optional[float] = None
    seed_time_limit: Optional[int] = None
    inactive_seed_time_limit: Optional[int] = None
    seed_then_cleanup: Optional[bool] = None
    auto_recovery: Optional[bool] = None

    @field_validator("languages", "subtitle_languages")
    @classmethod
    def validate_languages(cls, v):
        """Validate all language codes in languages list"""
        if v:
            for code in v:
                if not validate_language_code(code):
                    raise ValueError(f"Invalid ISO 639-1 language code: {code}")
        return v

    @field_validator("anime_audio_language", "anime_subtitle_language")
    @classmethod
    def validate_anime_languages(cls, v):
        """Validate anime language codes"""
        if v and not validate_language_code(v):
            raise ValueError(f"Invalid ISO 639-1 language code: {v}")
        return v


class MediaProfileResponse(BaseModel):
    """Media profile response"""

    id: int
    name: str
    # Per-media-type quality: Movies
    movie_resolutions: Optional[List[str]]
    movie_codecs: Optional[List[str]]
    movie_sources: Optional[List[str]]
    movie_audio_codecs: Optional[List[str]]
    movie_audio_channels: Optional[List[str]]
    movie_hdr_formats: Optional[List[str]]
    movie_editions: Optional[List[str]]
    movie_min_size: Optional[int]
    movie_max_size: Optional[int]
    # Per-media-type quality: TV Shows
    show_resolutions: Optional[List[str]]
    show_codecs: Optional[List[str]]
    show_sources: Optional[List[str]]
    show_audio_codecs: Optional[List[str]]
    show_audio_channels: Optional[List[str]]
    show_hdr_formats: Optional[List[str]]
    show_min_size: Optional[int]
    show_max_size: Optional[int]
    # Per-media-type quality: Anime
    anime_resolutions: Optional[List[str]]
    anime_codecs: Optional[List[str]]
    anime_sources: Optional[List[str]]
    anime_audio_codecs: Optional[List[str]]
    anime_audio_channels: Optional[List[str]]
    anime_hdr_formats: Optional[List[str]]
    anime_min_size: Optional[int]
    anime_max_size: Optional[int]
    # Common settings
    languages: Optional[List[str]]
    subtitle_languages: Optional[List[str]]
    upgrade_allowed: bool
    uploaders: Optional[List[str]]
    release_groups: Optional[List[str]]
    regex_filters: Optional[List[str]]
    seeder_weight: Optional[int]
    size_weight: Optional[int]
    recency_weight: Optional[int]
    search_sort_preference: Optional[str]
    season_pack_preference: Optional[str]
    search_timeout: Optional[int]
    max_retries: Optional[int]
    max_results: Optional[int]
    min_seeds: Optional[int]
    upgrade_replace_policy: Optional[str]
    # Naming formats
    movie_naming_format: Optional[str]
    movie_folder_format: Optional[str]
    show_naming_format: Optional[str]
    show_folder_format: Optional[str]
    anime_naming_format: Optional[str]
    anime_folder_format: Optional[str]
    # Anime options
    anime_subtitle_preference: Optional[str]
    anime_allow_hardsub: Optional[bool]
    anime_prefer_dual_audio: Optional[bool]
    anime_audio_language: Optional[str]
    anime_subtitle_language: Optional[str]
    # Indexers per media type
    movie_indexers: Optional[List[str]]
    show_indexers: Optional[List[str]]
    anime_indexers: Optional[List[str]]
    music_indexers: Optional[List[str]]
    # Music settings
    music_artist_folder_format: Optional[str]
    music_album_folder_format: Optional[str]
    music_track_naming_format: Optional[str]
    music_multi_disc_format: Optional[str]
    music_preferred_quality: Optional[List[str]]
    music_embed_lyrics: Optional[bool]
    music_embed_artwork: Optional[bool]
    # File output settings
    media_server: Optional[str]
    use_hardlinks: Optional[bool]
    illegal_char_replacement: Optional[str]
    colon_replacement: Optional[str]
    # Torrent validation settings
    validation_enabled: Optional[bool]
    validation_mode: Optional[str]
    forbidden_extensions: Optional[List[str]]
    validation_failure_action: Optional[str]
    movie_allowed_extensions: Optional[List[str]]
    show_allowed_extensions: Optional[List[str]]
    anime_allowed_extensions: Optional[List[str]]
    music_allowed_extensions: Optional[List[str]]
    # Seeding overrides
    seed_ratio_limit: Optional[float] = None
    seed_time_limit: Optional[int] = None
    inactive_seed_time_limit: Optional[int] = None
    seed_then_cleanup: Optional[bool] = None
    auto_recovery: Optional[bool] = None


class NamingPreviewRequest(BaseModel):
    """Render a naming/folder format against a representative sample item."""

    media_type: str
    folder_format: Optional[str] = None
    naming_format: Optional[str] = None
    illegal_char_replacement: Optional[str] = "_"
    colon_replacement: Optional[str] = " -"


@router.post("/naming-preview")
async def naming_preview(
    request: NamingPreviewRequest,
    current_user=Depends(get_current_user),
):
    """Return a rendered example folder/file name plus any unrecognized tokens."""
    context = naming_tokens.sample_context(request.media_type)
    extension = ".flac" if request.media_type == "music" else ".mkv"
    illegal = request.illegal_char_replacement or "_"
    colon = request.colon_replacement or " -"

    folder = (
        naming_tokens.render(request.folder_format, context, illegal_replacement=illegal, colon_replacement=colon)
        if request.folder_format
        else ""
    )
    filename = (
        naming_tokens.render(
            request.naming_format, context, illegal_replacement=illegal, colon_replacement=colon, extension=extension
        )
        if request.naming_format
        else ""
    )
    unknown = sorted(
        set(
            naming_tokens.unknown_tokens(request.folder_format or "")
            + naming_tokens.unknown_tokens(request.naming_format or "")
        )
    )
    return {"folder": folder, "file": filename, "unknown_tokens": unknown}


@router.get("/", response_model=List[MediaProfileResponse])
async def get_all_media_profiles(
    current_user=Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get all media profiles
    """
    rows = await conn.fetch("SELECT * FROM media_profiles ORDER BY name")
    return [dict(row) for row in rows]


@router.get("/{profile_id}", response_model=MediaProfileResponse)
async def get_media_profile(
    profile_id: int,
    current_user=Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Get media profile by ID
    """
    row = await conn.fetchrow("SELECT * FROM media_profiles WHERE id = $1", profile_id)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media profile with id {profile_id} not found",
        )

    return dict(row)


@router.post("/", response_model=MediaProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_media_profile(
    profile: MediaProfileCreate,
    current_user=Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Create a new media profile
    """
    existing = await conn.fetchrow("SELECT id FROM media_profiles WHERE name = $1", profile.name)

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Media profile with name '{profile.name}' already exists",
        )

    # Build the INSERT from the model so column changes need no positional bookkeeping.
    data = profile.model_dump()
    columns = list(data.keys())
    placeholders = ", ".join(f"${i}" for i in range(1, len(columns) + 1))
    row = await conn.fetchrow(
        f"""
        INSERT INTO media_profiles ({", ".join(columns)})
        VALUES ({placeholders})
        RETURNING *
        """,
        *[data[col] for col in columns],
    )

    return dict(row)


@router.put("/{profile_id}", response_model=MediaProfileResponse)
async def update_media_profile(
    profile_id: int,
    profile: MediaProfileUpdate,
    current_user=Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Update media profile
    """
    existing = await conn.fetchrow("SELECT * FROM media_profiles WHERE id = $1", profile_id)

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media profile with id {profile_id} not found",
        )

    update_fields = []
    update_values = []
    param_count = 1

    # Fields where an explicit null means "inherit the global default", so null must
    # be persisted rather than skipped.
    nullable_fields = {
        "seed_ratio_limit",
        "seed_time_limit",
        "inactive_seed_time_limit",
        "auto_recovery",
    }

    for field, value in profile.model_dump(exclude_unset=True).items():
        if value is not None or field in nullable_fields:
            update_fields.append(f"{field} = ${param_count}")
            update_values.append(value)
            param_count += 1

    if not update_fields:
        return dict(existing)

    update_fields.append("updated_at = NOW()")
    update_values.append(profile_id)

    query = f"""
        UPDATE media_profiles
        SET {', '.join(update_fields)}
        WHERE id = ${param_count}
        RETURNING *
    """

    row = await conn.fetchrow(query, *update_values)
    return dict(row)


@router.delete("/{profile_id}")
async def delete_media_profile(
    profile_id: int,
    current_user=Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Delete media profile
    """
    in_use = await conn.fetchval(
        """
        SELECT COUNT(*) FROM (
            SELECT 1 FROM movies WHERE media_profile_id = $1
            UNION ALL
            SELECT 1 FROM shows WHERE media_profile_id = $1
            UNION ALL
            SELECT 1 FROM anime WHERE media_profile_id = $1
            UNION ALL
            SELECT 1 FROM albums WHERE media_profile_id = $1
        ) AS combined
        """,
        profile_id,
    )

    if in_use > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete media profile. It is being used by {in_use} media item(s)",
        )

    result = await conn.execute("DELETE FROM media_profiles WHERE id = $1", profile_id)

    if result == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media profile with id {profile_id} not found",
        )

    return {"message": "Media profile deleted successfully"}
