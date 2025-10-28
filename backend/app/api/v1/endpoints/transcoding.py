from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Optional
import asyncpg
import json
from pathlib import Path

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.user import User
from app.schemas.transcoding import (
    TranscodingProfileCreate,
    TranscodingProfileUpdate,
    TranscodingProfileResponse,
    TranscodingJobCreate,
    TranscodingJobResponse,
    TranscodingRuleCreate,
    TranscodingRuleUpdate,
    TranscodingRuleResponse,
    HardwareAccelDevice,
    MediaFileInfo,
)
from app.services.transcoding import hardware_accel_service, ffmpeg_service

router = APIRouter()


# Hardware Acceleration Endpoints
@router.get("/hardware", response_model=List[HardwareAccelDevice])
async def get_hardware_devices(
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get available hardware acceleration devices"""
    rows = await conn.fetch(
        """
        SELECT * FROM hardware_accel_devices
        WHERE is_available = true
        ORDER BY device_type, device_index
        """
    )
    return [dict(row) for row in rows]


@router.post("/hardware/detect")
async def detect_hardware_devices(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Detect and save hardware acceleration devices"""

    async def detect_and_save():
        devices = await hardware_accel_service.detect_all_devices()
        await hardware_accel_service.save_devices_to_db(devices)

    background_tasks.add_task(detect_and_save)

    return {"message": "Hardware detection started"}


# Transcoding Profiles Endpoints
@router.get("/profiles", response_model=List[TranscodingProfileResponse])
async def get_transcoding_profiles(
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get all transcoding profiles"""
    rows = await conn.fetch("SELECT * FROM transcoding_profiles ORDER BY name")
    return [dict(row) for row in rows]


@router.get("/profiles/{profile_id}", response_model=TranscodingProfileResponse)
async def get_transcoding_profile(
    profile_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get transcoding profile by ID"""
    row = await conn.fetchrow(
        "SELECT * FROM transcoding_profiles WHERE id = $1", profile_id
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcoding profile with id {profile_id} not found",
        )

    return dict(row)


@router.post(
    "/profiles",
    response_model=TranscodingProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_transcoding_profile(
    profile: TranscodingProfileCreate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Create a new transcoding profile"""
    existing = await conn.fetchrow(
        "SELECT id FROM transcoding_profiles WHERE name = $1", profile.name
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transcoding profile with name '{profile.name}' already exists",
        )

    row = await conn.fetchrow(
        """
        INSERT INTO transcoding_profiles (
            name, description, container, video_codec, video_quality_mode,
            video_quality_value, video_preset, audio_codec, audio_bitrate,
            audio_channels, resolution, fps, hardware_accel_type,
            hardware_accel_device, tune, custom_ffmpeg_args
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
        RETURNING *
        """,
        profile.name,
        profile.description,
        profile.container,
        profile.video_codec,
        profile.video_quality_mode,
        profile.video_quality_value,
        profile.video_preset,
        profile.audio_codec,
        profile.audio_bitrate,
        profile.audio_channels,
        profile.resolution,
        profile.fps,
        profile.hardware_accel_type,
        profile.hardware_accel_device,
        profile.tune,
        json.dumps(profile.custom_ffmpeg_args) if profile.custom_ffmpeg_args else None,
    )

    return dict(row)


@router.put("/profiles/{profile_id}", response_model=TranscodingProfileResponse)
async def update_transcoding_profile(
    profile_id: int,
    profile: TranscodingProfileUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Update transcoding profile"""
    existing = await conn.fetchrow(
        "SELECT * FROM transcoding_profiles WHERE id = $1", profile_id
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcoding profile with id {profile_id} not found",
        )

    update_fields = []
    update_values = []
    param_count = 1

    for field, value in profile.dict(exclude_unset=True).items():
        if value is not None:
            if field == "custom_ffmpeg_args":
                value = json.dumps(value)
            update_fields.append(f"{field} = ${param_count}")
            update_values.append(value)
            param_count += 1

    if not update_fields:
        return dict(existing)

    update_fields.append("updated_at = NOW()")
    update_values.append(profile_id)

    query = f"""
        UPDATE transcoding_profiles
        SET {', '.join(update_fields)}
        WHERE id = ${param_count}
        RETURNING *
    """

    row = await conn.fetchrow(query, *update_values)
    return dict(row)


@router.delete("/profiles/{profile_id}")
async def delete_transcoding_profile(
    profile_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Delete transcoding profile"""
    in_use = await conn.fetchval(
        "SELECT COUNT(*) FROM transcoding_jobs WHERE profile_id = $1", profile_id
    )

    if in_use > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete profile. It is being used by {in_use} job(s)",
        )

    result = await conn.execute(
        "DELETE FROM transcoding_profiles WHERE id = $1", profile_id
    )

    if result == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcoding profile with id {profile_id} not found",
        )

    return {"message": "Transcoding profile deleted successfully"}


# Transcoding Jobs Endpoints
@router.get("/jobs", response_model=List[TranscodingJobResponse])
async def get_transcoding_jobs(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get transcoding jobs"""
    if status_filter:
        rows = await conn.fetch(
            """
            SELECT * FROM transcoding_jobs
            WHERE user_id = $1 AND status = $2
            ORDER BY created_at DESC
            """,
            current_user.id,
            status_filter,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT * FROM transcoding_jobs
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            current_user.id,
        )

    return [dict(row) for row in rows]


@router.get("/jobs/{job_id}", response_model=TranscodingJobResponse)
async def get_transcoding_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get transcoding job by ID"""
    row = await conn.fetchrow(
        """
        SELECT * FROM transcoding_jobs
        WHERE id = $1 AND user_id = $2
        """,
        job_id,
        current_user["id"],
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcoding job with id {job_id} not found",
        )

    return dict(row)


@router.post(
    "/jobs",
    response_model=TranscodingJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_transcoding_job(
    job: TranscodingJobCreate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Create a new transcoding job"""
    # Validate input file exists
    input_file = Path(job.input_path)
    if not input_file.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Input file not found: {job.input_path}",
        )

    # Get profile
    profile_row = await conn.fetchrow(
        "SELECT * FROM transcoding_profiles WHERE id = $1", job.profile_id
    )

    if not profile_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcoding profile with id {job.profile_id} not found",
        )

    profile_snapshot = dict(profile_row)

    # Get media info if media_id provided
    media_title = None
    if job.media_id and job.media_type:
        table_map = {"movie": "movies", "show": "shows", "anime": "anime"}
        table = table_map.get(job.media_type)
        if table:
            media_row = await conn.fetchrow(
                f"SELECT title FROM {table} WHERE id = $1", job.media_id
            )
            if media_row:
                media_title = media_row["title"]

    # Determine output path
    output_path = job.output_path
    if job.use_media_profile_naming and job.media_id and job.media_type:
        # Get media profile for naming format
        if job.media_type == "movie":
            media_profile_row = await conn.fetchrow(
                """
                SELECT mp.* FROM media_profiles mp
                JOIN movies m ON m.media_profile_id = mp.id
                WHERE m.id = $1
                """,
                job.media_id,
            )
            naming_field = "movie_naming_format"
        elif job.media_type == "show":
            media_profile_row = await conn.fetchrow(
                """
                SELECT mp.* FROM media_profiles mp
                JOIN shows s ON s.media_profile_id = mp.id
                WHERE s.id = $1
                """,
                job.media_id,
            )
            naming_field = "show_naming_format"
        else:
            media_profile_row = await conn.fetchrow(
                """
                SELECT mp.* FROM media_profiles mp
                JOIN anime a ON a.media_profile_id = mp.id
                WHERE a.id = $1
                """,
                job.media_id,
            )
            naming_field = "anime_naming_format"

        # Build output path from naming format (simplified for now)
        if media_profile_row and media_profile_row.get(naming_field):
            output_dir = input_file.parent
            output_filename = f"{media_title or input_file.stem}_transcoded{input_file.suffix}"
            output_path = str(output_dir / output_filename)

    if not output_path:
        # Default: add "_transcoded" suffix
        output_path = str(input_file.parent / f"{input_file.stem}_transcoded{input_file.suffix}")

    # Get file size
    file_size_input = input_file.stat().st_size

    # Create job
    row = await conn.fetchrow(
        """
        INSERT INTO transcoding_jobs (
            user_id, media_id, media_type, media_title, input_path, output_path,
            output_action, use_media_profile_naming, profile_id, profile_snapshot,
            hardware_accel_type, hardware_accel_device, status, file_size_input
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, 'pending', $13)
        RETURNING *
        """,
        current_user["id"],
        job.media_id,
        job.media_type,
        media_title,
        job.input_path,
        output_path,
        job.output_action,
        job.use_media_profile_naming,
        job.profile_id,
        json.dumps(profile_snapshot),
        job.hardware_accel_type,
        job.hardware_accel_device,
        file_size_input,
    )

    job_dict = dict(row)

    # Queue Celery task
    from app.tasks.transcoding import transcode_media_task

    task = transcode_media_task.delay(job_dict["id"])

    # Update job with Celery task ID
    await conn.execute(
        "UPDATE transcoding_jobs SET celery_task_id = $1, status = 'queued' WHERE id = $2",
        task.id,
        job_dict["id"],
    )

    job_dict["celery_task_id"] = task.id
    job_dict["status"] = "queued"

    return job_dict


@router.delete("/jobs/{job_id}")
async def cancel_transcoding_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Cancel a transcoding job"""
    job = await conn.fetchrow(
        """
        SELECT * FROM transcoding_jobs
        WHERE id = $1 AND user_id = $2
        """,
        job_id,
        current_user["id"],
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcoding job with id {job_id} not found",
        )

    if job["status"] not in ["pending", "queued", "processing"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status '{job['status']}'",
        )

    # Revoke Celery task if exists
    if job["celery_task_id"]:
        from app.tasks.celery_app import celery_app

        celery_app.control.revoke(job["celery_task_id"], terminate=True)

    # Update job status
    await conn.execute(
        """
        UPDATE transcoding_jobs
        SET status = 'cancelled', updated_at = NOW()
        WHERE id = $1
        """,
        job_id,
    )

    return {"message": "Transcoding job cancelled"}


# Transcoding Rules Endpoints
@router.get("/rules", response_model=List[TranscodingRuleResponse])
async def get_transcoding_rules(
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Get all transcoding rules"""
    rows = await conn.fetch("SELECT * FROM transcoding_rules ORDER BY priority DESC, name")
    return [dict(row) for row in rows]


@router.post(
    "/rules",
    response_model=TranscodingRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_transcoding_rule(
    rule: TranscodingRuleCreate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Create a new transcoding rule"""
    existing = await conn.fetchrow(
        "SELECT id FROM transcoding_rules WHERE name = $1", rule.name
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transcoding rule with name '{rule.name}' already exists",
        )

    row = await conn.fetchrow(
        """
        INSERT INTO transcoding_rules (
            name, enabled, priority, trigger_type, conditions, profile_id,
            output_action, use_media_profile_naming, media_types
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING *
        """,
        rule.name,
        rule.enabled,
        rule.priority,
        rule.trigger_type,
        json.dumps(rule.conditions),
        rule.profile_id,
        rule.output_action,
        rule.use_media_profile_naming,
        rule.media_types,
    )

    return dict(row)


@router.put("/rules/{rule_id}", response_model=TranscodingRuleResponse)
async def update_transcoding_rule(
    rule_id: int,
    rule: TranscodingRuleUpdate,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Update transcoding rule"""
    existing = await conn.fetchrow(
        "SELECT * FROM transcoding_rules WHERE id = $1", rule_id
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcoding rule with id {rule_id} not found",
        )

    update_fields = []
    update_values = []
    param_count = 1

    for field, value in rule.dict(exclude_unset=True).items():
        if value is not None:
            if field == "conditions":
                value = json.dumps(value)
            update_fields.append(f"{field} = ${param_count}")
            update_values.append(value)
            param_count += 1

    if not update_fields:
        return dict(existing)

    update_fields.append("updated_at = NOW()")
    update_values.append(rule_id)

    query = f"""
        UPDATE transcoding_rules
        SET {', '.join(update_fields)}
        WHERE id = ${param_count}
        RETURNING *
    """

    row = await conn.fetchrow(query, *update_values)
    return dict(row)


@router.delete("/rules/{rule_id}")
async def delete_transcoding_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Delete transcoding rule"""
    result = await conn.execute(
        "DELETE FROM transcoding_rules WHERE id = $1", rule_id
    )

    if result == "DELETE 0":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcoding rule with id {rule_id} not found",
        )

    return {"message": "Transcoding rule deleted successfully"}


# Media Info Endpoint
@router.get("/media-info")
async def get_media_info(
    file_path: str,
    current_user: User = Depends(get_current_user),
):
    """Get media file information using ffprobe"""
    file = Path(file_path)
    if not file.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File not found: {file_path}",
        )

    try:
        info = await ffmpeg_service.get_media_info(file_path)

        format_info = info.get("format", {})
        video_stream = next(
            (s for s in info.get("streams", []) if s.get("codec_type") == "video"),
            None,
        )
        audio_stream = next(
            (s for s in info.get("streams", []) if s.get("codec_type") == "audio"),
            None,
        )

        return {
            "format_name": format_info.get("format_name", ""),
            "duration": float(format_info.get("duration", 0)),
            "size": int(format_info.get("size", 0)),
            "bit_rate": int(format_info.get("bit_rate", 0)),
            "video_codec": video_stream.get("codec_name") if video_stream else None,
            "video_resolution": f"{video_stream.get('width')}x{video_stream.get('height')}"
            if video_stream
            else None,
            "video_fps": eval(video_stream.get("r_frame_rate", "0/1"))
            if video_stream
            else None,
            "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
            "audio_channels": audio_stream.get("channels") if audio_stream else None,
            "audio_bitrate": int(audio_stream.get("bit_rate", 0))
            if audio_stream
            else None,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting media info: {str(e)}",
        )
