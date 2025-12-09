from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel, field_validator
import asyncpg

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user

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
    # Legacy global settings (kept for backward compatibility)
    min_size: Optional[int] = 0
    max_size: Optional[int] = 0
    resolutions: Optional[List[str]] = []
    codecs: Optional[List[str]] = []
    sources: Optional[List[str]] = []
    audio_codecs: Optional[List[str]] = []
    audio_channels: Optional[List[str]] = []
    hdr_formats: Optional[List[str]] = []
    editions: Optional[List[str]] = []
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
    upgradeuntil_quality: Optional[str] = None
    indexers: Optional[List[str]] = []
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

    @field_validator('languages', 'subtitle_languages')
    @classmethod
    def validate_languages(cls, v):
        """Validate all language codes in languages list"""
        if v:
            for code in v:
                if not validate_language_code(code):
                    raise ValueError(f"Invalid ISO 639-1 language code: {code}")
        return v

    @field_validator('anime_audio_language', 'anime_subtitle_language')
    @classmethod
    def validate_anime_languages(cls, v):
        """Validate anime language codes"""
        if v and not validate_language_code(v):
            raise ValueError(f"Invalid ISO 639-1 language code: {v}")
        return v


class MediaProfileUpdate(BaseModel):
    """Update media profile (all fields optional for partial updates)"""
    name: Optional[str] = None
    # Legacy global settings
    min_size: Optional[int] = None
    max_size: Optional[int] = None
    resolutions: Optional[List[str]] = None
    codecs: Optional[List[str]] = None
    sources: Optional[List[str]] = None
    audio_codecs: Optional[List[str]] = None
    audio_channels: Optional[List[str]] = None
    hdr_formats: Optional[List[str]] = None
    editions: Optional[List[str]] = None
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
    upgradeuntil_quality: Optional[str] = None
    indexers: Optional[List[str]] = None
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

    @field_validator('languages', 'subtitle_languages')
    @classmethod
    def validate_languages(cls, v):
        """Validate all language codes in languages list"""
        if v:
            for code in v:
                if not validate_language_code(code):
                    raise ValueError(f"Invalid ISO 639-1 language code: {code}")
        return v

    @field_validator('anime_audio_language', 'anime_subtitle_language')
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
    # Legacy global settings
    min_size: Optional[int]
    max_size: Optional[int]
    resolutions: Optional[List[str]]
    codecs: Optional[List[str]]
    sources: Optional[List[str]]
    audio_codecs: Optional[List[str]]
    audio_channels: Optional[List[str]]
    hdr_formats: Optional[List[str]]
    editions: Optional[List[str]]
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
    indexers: Optional[List[str]]
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


@router.get("/", response_model=List[MediaProfileResponse])
async def get_all_media_profiles(
    current_user = Depends(get_current_user),
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
    current_user = Depends(get_current_user),
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
    current_user = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Create a new media profile
    """
    existing = await conn.fetchrow(
        "SELECT id FROM media_profiles WHERE name = $1",
        profile.name
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Media profile with name '{profile.name}' already exists",
        )

    row = await conn.fetchrow(
        """
        INSERT INTO media_profiles (
            name, min_size, max_size,
            resolutions, codecs, sources, audio_codecs,
            audio_channels, hdr_formats, editions,
            movie_resolutions, movie_codecs, movie_sources, movie_audio_codecs,
            movie_audio_channels, movie_hdr_formats, movie_editions,
            movie_min_size, movie_max_size,
            show_resolutions, show_codecs, show_sources, show_audio_codecs,
            show_audio_channels, show_hdr_formats,
            show_min_size, show_max_size,
            anime_resolutions, anime_codecs, anime_sources, anime_audio_codecs,
            anime_audio_channels, anime_hdr_formats,
            anime_min_size, anime_max_size,
            languages, subtitle_languages, upgrade_allowed,
            indexers, uploaders, release_groups, regex_filters,
            seeder_weight, size_weight, recency_weight, search_sort_preference,
            season_pack_preference, search_timeout, max_retries, max_results,
            movie_naming_format, movie_folder_format, show_naming_format, show_folder_format,
            anime_naming_format, anime_folder_format,
            anime_subtitle_preference, anime_allow_hardsub, anime_prefer_dual_audio,
            anime_audio_language, anime_subtitle_language,
            movie_indexers, show_indexers, anime_indexers, music_indexers,
            music_artist_folder_format, music_album_folder_format,
            music_track_naming_format, music_multi_disc_format,
            music_preferred_quality, music_embed_lyrics, music_embed_artwork,
            media_server, use_hardlinks,
            illegal_char_replacement, colon_replacement
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
            $21, $22, $23, $24, $25, $26, $27, $28, $29, $30,
            $31, $32, $33, $34, $35, $36, $37, $38, $39, $40,
            $41, $42, $43, $44, $45, $46, $47, $48, $49, $50,
            $51, $52, $53, $54, $55, $56, $57, $58, $59, $60,
            $61, $62, $63, $64, $65, $66, $67, $68, $69, $70,
            $71, $72, $73, $74, $75, $76
        )
        RETURNING *
        """,
        profile.name,
        profile.min_size,
        profile.max_size,
        profile.resolutions,
        profile.codecs,
        profile.sources,
        profile.audio_codecs,
        profile.audio_channels,
        profile.hdr_formats,
        profile.editions,
        profile.movie_resolutions,
        profile.movie_codecs,
        profile.movie_sources,
        profile.movie_audio_codecs,
        profile.movie_audio_channels,
        profile.movie_hdr_formats,
        profile.movie_editions,
        profile.movie_min_size,
        profile.movie_max_size,
        profile.show_resolutions,
        profile.show_codecs,
        profile.show_sources,
        profile.show_audio_codecs,
        profile.show_audio_channels,
        profile.show_hdr_formats,
        profile.show_min_size,
        profile.show_max_size,
        profile.anime_resolutions,
        profile.anime_codecs,
        profile.anime_sources,
        profile.anime_audio_codecs,
        profile.anime_audio_channels,
        profile.anime_hdr_formats,
        profile.anime_min_size,
        profile.anime_max_size,
        profile.languages,
        profile.subtitle_languages,
        profile.upgrade_allowed,
        profile.indexers,
        profile.uploaders,
        profile.release_groups,
        profile.regex_filters,
        profile.seeder_weight,
        profile.size_weight,
        profile.recency_weight,
        profile.search_sort_preference,
        profile.season_pack_preference,
        profile.search_timeout,
        profile.max_retries,
        profile.max_results,
        profile.movie_naming_format,
        profile.movie_folder_format,
        profile.show_naming_format,
        profile.show_folder_format,
        profile.anime_naming_format,
        profile.anime_folder_format,
        profile.anime_subtitle_preference,
        profile.anime_allow_hardsub,
        profile.anime_prefer_dual_audio,
        profile.anime_audio_language,
        profile.anime_subtitle_language,
        profile.movie_indexers,
        profile.show_indexers,
        profile.anime_indexers,
        profile.music_indexers,
        profile.music_artist_folder_format,
        profile.music_album_folder_format,
        profile.music_track_naming_format,
        profile.music_multi_disc_format,
        profile.music_preferred_quality,
        profile.music_embed_lyrics,
        profile.music_embed_artwork,
        profile.media_server,
        profile.use_hardlinks,
        profile.illegal_char_replacement,
        profile.colon_replacement,
    )

    return dict(row)


@router.put("/{profile_id}", response_model=MediaProfileResponse)
async def update_media_profile(
    profile_id: int,
    profile: MediaProfileUpdate,
    current_user = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Update media profile
    """
    existing = await conn.fetchrow(
        "SELECT * FROM media_profiles WHERE id = $1",
        profile_id
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media profile with id {profile_id} not found",
        )

    update_fields = []
    update_values = []
    param_count = 1

    for field, value in profile.model_dump(exclude_unset=True).items():
        if value is not None:
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
    current_user = Depends(get_current_user),
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
        profile_id
    )

    if in_use > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete media profile. It is being used by {in_use} media item(s)",
        )

    result = await conn.execute(
        "DELETE FROM media_profiles WHERE id = $1",
        profile_id
    )

    if result == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media profile with id {profile_id} not found",
        )

    return {"message": "Media profile deleted successfully"}
