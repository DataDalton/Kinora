import json
import time
from pathlib import Path
import shutil
from datetime import datetime

from app.tasks.celery_app import celery_app, runAsync
from app.core.cache import cacheSet
from app.db import get_pool
from app.core.webtransport import webtransport_manager
from app.services.transcoding import ffmpeg_service


async def get_db_connection():
    """Take a connection from the shared pool."""
    pool = await get_pool()
    return await pool.acquire()


async def release_db_connection(conn):
    """
    Hand a connection back to the pool.

    Calling close() on it instead drops the underlying connection and makes the pool
    open a replacement on the next acquire, so a season pack would rebuild one
    connection per episode.
    """
    pool = await get_pool()
    await pool.release(conn)


@celery_app.task(bind=True, max_retries=2)
def transcode_media_task(self, job_id: int):
    """
    Background task for media transcoding with progress tracking
    """

    async def run_transcoding():
        conn = await get_db_connection()

        try:
            # Get job details
            job = await conn.fetchrow("SELECT * FROM transcoding_jobs WHERE id = $1", job_id)

            if not job:
                raise ValueError(f"Job {job_id} not found")

            user_id = job["user_id"]
            input_path = job["input_path"]
            output_path = job["output_path"]
            output_action = job["output_action"]
            profile_snapshot = (
                json.loads(job["profile_snapshot"])
                if isinstance(job["profile_snapshot"], str)
                else job["profile_snapshot"]
            )
            hardware_accel_type = job["hardware_accel_type"]
            hardware_accel_device = job["hardware_accel_device"]

            # Validate input file exists
            if not Path(input_path).exists():
                raise FileNotFoundError(f"Input file not found: {input_path}")

            # Update status to processing
            await conn.execute(
                """
                UPDATE transcoding_jobs
                SET status = 'processing', started_at = NOW(), updated_at = NOW()
                WHERE id = $1
                """,
                job_id,
            )

            # Get total frames for progress calculation
            total_frames = await ffmpeg_service.count_frames(input_path)

            if total_frames:
                await conn.execute(
                    "UPDATE transcoding_jobs SET total_frames = $1 WHERE id = $2",
                    total_frames,
                    job_id,
                )

            # Progress callback to update database and send WebTransport updates
            async def update_progress(job_id: int, progress_data: dict):
                # Update progress table
                await conn.execute(
                    """
                    INSERT INTO transcoding_progress (
                        job_id, frame, fps, bitrate, size, time, speed, progress, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                    ON CONFLICT (job_id) DO UPDATE SET
                        frame = EXCLUDED.frame,
                        fps = EXCLUDED.fps,
                        bitrate = EXCLUDED.bitrate,
                        size = EXCLUDED.size,
                        time = EXCLUDED.time,
                        speed = EXCLUDED.speed,
                        progress = EXCLUDED.progress,
                        updated_at = NOW()
                    """,
                    job_id,
                    progress_data.get("frame"),
                    progress_data.get("fps"),
                    progress_data.get("bitrate"),
                    progress_data.get("size"),
                    progress_data.get("time"),
                    progress_data.get("speed"),
                    progress_data.get("progress"),
                )

                # Update job progress
                await conn.execute(
                    """
                    UPDATE transcoding_jobs
                    SET progress = $1, current_frame = $2, fps = $3, speed = $4, bitrate = $5, updated_at = NOW()
                    WHERE id = $6
                    """,
                    progress_data.get("progress"),
                    progress_data.get("frame"),
                    progress_data.get("fps"),
                    progress_data.get("speed"),
                    progress_data.get("bitrate"),
                    job_id,
                )

                # Send WebTransport update to user
                try:
                    await webtransport_manager.send_transcoding_progress(
                        user_id,
                        job_id,
                        progress_data.get("progress", 0),
                        progress_data.get("fps", 0),
                        progress_data.get("speed", "0x"),
                        progress_data.get("frame", 0),
                        progress_data.get("bitrate", "0kbits/s"),
                    )
                except Exception as e:
                    print(f"Error sending WebTransport update: {e}")

            # Run FFmpeg transcoding
            success = await ffmpeg_service.transcode(
                job_id,
                input_path,
                output_path,
                profile_snapshot,
                hardware_accel_type,
                hardware_accel_device,
                progress_callback=update_progress,
            )

            if success:
                # Get output file size
                output_file = Path(output_path)
                output_size = output_file.stat().st_size if output_file.exists() else 0

                # Handle file replacement or keep both
                if output_action == "replace":
                    # Backup original (optional)
                    # backup_path = Path(input_path).with_suffix(Path(input_path).suffix + ".backup")
                    # shutil.copy2(input_path, backup_path)

                    # Remove original
                    Path(input_path).unlink(missing_ok=True)

                    # Rename transcoded file to original name
                    output_file.rename(input_path)

                    final_path = input_path
                else:
                    # Keep both files
                    final_path = output_path

                # Update job to completed
                await conn.execute(
                    """
                    UPDATE transcoding_jobs
                    SET status = 'completed',
                        completed_at = NOW(),
                        file_size_output = $2,
                        progress = 100,
                        output_path = $3,
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    job_id,
                    output_size,
                    final_path,
                )

                # Update media file info if media_id exists
                if job["media_id"] and job["media_type"]:
                    table_map = {"movie": "movies", "show": "shows", "anime": "anime"}
                    table = table_map.get(job["media_type"])
                    if table:
                        await conn.execute(
                            f"""
                            UPDATE {table}
                            SET file_path = $1,
                                file_size = $2,
                                updated_at = NOW()
                            WHERE id = $3
                            """,
                            final_path,
                            output_size,
                            job["media_id"],
                        )

                # Send completion notification via WebTransport
                try:
                    await webtransport_manager.send_transcoding_complete(
                        user_id,
                        job_id,
                        job["media_title"] or Path(input_path).name,
                        True,
                    )
                except Exception as e:
                    print(f"Error sending completion notification: {e}")

            else:
                raise Exception("FFmpeg transcoding failed")

        except Exception as e:
            error_message = str(e)
            print(f"Transcoding job {job_id} failed: {error_message}")

            # Update job to failed
            await conn.execute(
                """
                UPDATE transcoding_jobs
                SET status = 'failed', error_message = $2, updated_at = NOW()
                WHERE id = $1
                """,
                job_id,
                error_message,
            )

            # Send failure notification via WebTransport
            try:
                await webtransport_manager.send_transcoding_complete(
                    user_id,
                    job_id,
                    job.get("media_title") or Path(input_path).name,
                    False,
                    error_message,
                )
            except Exception as wt_error:
                print(f"Error sending failure notification: {wt_error}")

            raise

        finally:
            await release_db_connection(conn)

    # Runs on the loop shared by every Celery task. The connection pool is bound to that
    # loop, so a task that opened its own loop could not use a pooled connection.
    return runAsync(run_transcoding())


@celery_app.task
def check_and_apply_transcoding_rules(
    media_id: int, media_type: str, file_path: str, trigger_type: str = "on_download"
):
    """
    Evaluate the transcoding rules for one file and queue an encode for the first match.

    trigger_type selects which rules apply: on_download for a file that arrived from the
    download client, on_import for one adopted from disk by a library import, and
    scheduled for the periodic sweep over files already in the library.
    """

    async def check_rules():
        conn = await get_db_connection()

        try:
            # Get active rules for this media type and the event that fired the check
            rules = await conn.fetch(
                """
                SELECT * FROM transcoding_rules
                WHERE enabled = true
                  AND trigger_type = $2
                  AND $1 = ANY(media_types)
                ORDER BY priority DESC
                """,
                media_type,
                trigger_type,
            )

            if not rules:
                return

            # Get file info
            try:
                media_info = await ffmpeg_service.get_media_info(file_path)
            except Exception as e:
                print(f"Error getting media info for {file_path}: {e}")
                return

            file_size = Path(file_path).stat().st_size
            format_info = media_info.get("format", {})
            video_stream = next(
                (s for s in media_info.get("streams", []) if s.get("codec_type") == "video"),
                None,
            )

            # Check each rule
            for rule in rules:
                conditions = (
                    json.loads(rule["conditions"]) if isinstance(rule["conditions"], str) else rule["conditions"]
                )

                # Evaluate conditions
                matches = True

                if "file_size_gt" in conditions:
                    if file_size <= conditions["file_size_gt"]:
                        matches = False

                if "file_size_lt" in conditions:
                    if file_size >= conditions["file_size_lt"]:
                        matches = False

                if "codec" in conditions and video_stream:
                    if video_stream.get("codec_name") != conditions["codec"]:
                        matches = False

                if "resolution_gt" in conditions and video_stream:
                    height = video_stream.get("height", 0)
                    if height <= conditions["resolution_gt"]:
                        matches = False

                if matches:
                    # Get profile
                    profile_row = await conn.fetchrow(
                        "SELECT * FROM transcoding_profiles WHERE id = $1",
                        rule["profile_id"],
                    )

                    if not profile_row:
                        continue

                    # Freeze the encoding settings onto the job so editing the profile
                    # later does not change an encode that is already queued. Row
                    # timestamps are not settings and do not survive JSON, so they are
                    # dropped rather than carried along.
                    profile_snapshot = {
                        key: value
                        for key, value in dict(profile_row).items()
                        if key not in ("created_at", "updated_at")
                    }

                    # Get media title
                    table_map = {"movie": "movies", "show": "shows", "anime": "anime"}
                    table = table_map.get(media_type)
                    media_title = None

                    if table:
                        media_row = await conn.fetchrow(f"SELECT title FROM {table} WHERE id = $1", media_id)
                        if media_row:
                            media_title = media_row["title"]

                    # Determine output path
                    output_path = None
                    if rule["use_media_profile_naming"]:
                        # Use media profile naming
                        output_dir = Path(file_path).parent
                        output_filename = f"{media_title or Path(file_path).stem}_transcoded{Path(file_path).suffix}"
                        output_path = str(output_dir / output_filename)
                    else:
                        output_path = str(
                            Path(file_path).parent / f"{Path(file_path).stem}_transcoded{Path(file_path).suffix}"
                        )

                    # Skip a file that already has a job queued, running, or finished. The
                    # same file reaches this task more than once: an import that a restart
                    # left mid-flight is recovered and reprocessed, and scheduled rules
                    # rescan the library on every cycle. Without this a second encode would
                    # start on a file the first one is still writing, and under the replace
                    # action both would target the same path.
                    existing_job = await conn.fetchval(
                        """
                        SELECT id FROM transcoding_jobs
                        WHERE input_path = $1
                          AND status IN ('pending', 'queued', 'processing', 'completed')
                        LIMIT 1
                        """,
                        file_path,
                    )
                    if existing_job:
                        print(
                            f"Transcoding job {existing_job} already covers {file_path}, skipping rule '{rule['name']}'"
                        )
                        break

                    # Create transcoding job
                    job_row = await conn.fetchrow(
                        """
                        INSERT INTO transcoding_jobs (
                            user_id, media_id, media_type, media_title, input_path, output_path,
                            output_action, use_media_profile_naming, profile_id, profile_snapshot,
                            hardware_accel_type, hardware_accel_device, status, file_size_input
                        )
                        VALUES (1, $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'pending', $12)
                        RETURNING *
                        """,
                        media_id,
                        media_type,
                        media_title,
                        file_path,
                        output_path,
                        rule["output_action"],
                        rule["use_media_profile_naming"],
                        rule["profile_id"],
                        # default=str keeps a column type JSON cannot represent from
                        # failing the whole rule check.
                        json.dumps(profile_snapshot, default=str),
                        profile_row["hardware_accel_type"],
                        profile_row["hardware_accel_device"],
                        file_size,
                    )

                    # Queue transcoding task
                    task = transcode_media_task.delay(job_row["id"])

                    # Update job with Celery task ID
                    await conn.execute(
                        "UPDATE transcoding_jobs SET celery_task_id = $1, status = 'queued' WHERE id = $2",
                        task.id,
                        job_row["id"],
                    )

                    print(
                        f"Created automatic transcoding job {job_row['id']} for {file_path} using rule '{rule['name']}'"
                    )

                    # Only apply first matching rule
                    break

        except Exception as e:
            print(f"Error checking transcoding rules: {e}")

        finally:
            await release_db_connection(conn)

    return runAsync(check_rules())


# Files examined per scheduled sweep. A large library is worked through across successive
# runs rather than queueing an encode for every file at once.
SCAN_BATCH_LIMIT = 200


@celery_app.task(name="app.tasks.transcoding.scan_library_for_transcoding")
def scan_library_for_transcoding():
    """
    Apply rules whose trigger is 'scheduled' to files already in the library.

    on_download and on_import only ever see files as they arrive, so this is what
    reaches a back catalogue that predates the rule.
    """
    return runAsync(async_scan_library_for_transcoding())


async def async_scan_library_for_transcoding():
    taskName = "transcoding_scan"
    startTime = time.time()
    status = "success"
    queued = 0

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            typeRows = await conn.fetch("""
                SELECT DISTINCT unnest(media_types) AS media_type
                FROM transcoding_rules
                WHERE enabled = true AND trigger_type = 'scheduled'
                """)
            mediaTypes = [row["media_type"] for row in typeRows]
            if not mediaTypes:
                return {"status": "skipped", "reason": "No scheduled transcoding rules", "queued": 0}

            # Files already carrying a job are excluded here rather than left for the rule
            # check to reject, so each sweep advances through the library instead of
            # re-dispatching the same files every cycle.
            rows = await conn.fetch(
                """
                SELECT mf.media_type, mf.media_id, mf.file_path
                FROM media_files mf
                LEFT JOIN transcoding_jobs tj
                       ON tj.input_path = mf.file_path
                      AND tj.status IN ('pending', 'queued', 'processing', 'completed')
                WHERE mf.media_type = ANY($1)
                  AND tj.id IS NULL
                ORDER BY mf.id
                LIMIT $2
                """,
                mediaTypes,
                SCAN_BATCH_LIMIT,
            )

        for row in rows:
            check_and_apply_transcoding_rules.delay(row["media_id"], row["media_type"], row["file_path"], "scheduled")
            queued += 1

        print(f"Transcoding sweep queued {queued} rule checks")
        return {"status": "success", "queued": queued}

    except Exception as e:
        status = "failed"
        print(f"Transcoding sweep error: {e}")
        return {"status": "error", "message": str(e), "queued": queued}

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
