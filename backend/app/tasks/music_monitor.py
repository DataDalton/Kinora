import asyncio
from datetime import datetime
from app.tasks.celery_app import celery_app
from app.core.database import get_pool
from app.services.automation.search_engine import search_engine
from app.services.media_profile import MediaProfile
from app.services.metadata.deezer import deezer_service


def parse_release_date(date_str: str | None):
    """Parse release date string from Deezer API into date object"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


@celery_app.task(name="app.tasks.music_monitor.search_wanted_music")
def search_wanted_music():
    """
    Search for all wanted/missing music albums across indexers
    Automatically selects and grabs best matches
    """
    return asyncio.run(async_search_wanted_music())


@celery_app.task(name="app.tasks.music_monitor.check_new_releases")
def check_new_releases():
    """
    Check for new releases from monitored artists
    Adds new albums to library and queues for download
    """
    return asyncio.run(async_check_new_releases())


async def async_search_wanted_music():
    """
    Async implementation of wanted music search
    Searches for all albums with status='wanted' and monitored=TRUE
    """
    try:
        grabbed_count = 0
        searched_count = 0

        pool = await get_pool()

        async with pool.acquire() as conn:
            # Get all wanted albums (monitored but not downloaded)
            wanted_albums = await conn.fetch(
                """
                SELECT a.*, ar.name as artist_name, ar.root_folder_path as artist_root_folder
                FROM albums a
                LEFT JOIN artists ar ON a.artist_id = ar.id
                WHERE a.monitored = TRUE
                AND a.status = 'wanted'
                ORDER BY a.release_date DESC NULLS LAST
                LIMIT 50
                """
            )

            for album_row in wanted_albums:
                album = dict(album_row)
                searched_count += 1

                # Build search query
                artist_name = album.get("artist_name") or ""
                album_title = album["title"]
                query = f"{artist_name} {album_title}"

                # Get quality profile
                profile = None
                if album["media_profile_id"]:
                    profile_row = await conn.fetchrow(
                        "SELECT * FROM quality_profiles WHERE id = $1",
                        album["media_profile_id"]
                    )
                    if profile_row:
                        profile = MediaProfile(**dict(profile_row))

                if not profile:
                    # Use default music profile settings
                    profile = MediaProfile(
                        id=0,
                        name="Default Music",
                        music_preferred_quality=["flac", "mp3_320", "mp3_256"],
                    )

                # Determine save path
                save_path = album.get("root_folder_path") or album.get("artist_root_folder")

                # Search and download
                try:
                    torrent_hash = await search_engine.search_music_and_download(
                        query=query,
                        profile=profile,
                        save_path=save_path,
                        tags=["nexarr", "music", f"album-{album['id']}"],
                    )

                    if torrent_hash:
                        # Record download
                        await conn.execute(
                            """
                            INSERT INTO download_history (
                                media_id, media_type, torrent_hash, torrent_title,
                                indexer, status, download_client
                            )
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                            """,
                            album["id"], "album", torrent_hash, query,
                            "1337x", "downloading", "qbittorrent"
                        )

                        # Update album status
                        await conn.execute(
                            """
                            UPDATE albums
                            SET status = 'downloading', updated_at = NOW()
                            WHERE id = $1
                            """,
                            album["id"]
                        )

                        grabbed_count += 1
                        print(f"Music: Grabbed {album_title} by {artist_name}")

                except Exception as e:
                    print(f"Error searching for music {query}: {e}")
                    continue

                # Small delay to avoid hammering indexers
                await asyncio.sleep(2)

        return {
            "status": "success",
            "items_searched": searched_count,
            "items_grabbed": grabbed_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        print(f"Wanted music search error: {e}")
        return {"status": "error", "message": str(e)}


async def async_check_new_releases():
    """
    Async implementation of new release checking
    Checks Deezer for new albums from monitored artists
    """
    try:
        new_albums_added = 0
        artists_checked = 0

        pool = await get_pool()

        async with pool.acquire() as conn:
            # Get all monitored artists with Deezer IDs
            monitored_artists = await conn.fetch(
                """
                SELECT * FROM artists
                WHERE monitored = TRUE
                AND deezer_id IS NOT NULL
                ORDER BY updated_at ASC
                LIMIT 20
                """
            )

            for artist_row in monitored_artists:
                artist = dict(artist_row)
                artists_checked += 1

                try:
                    # Fetch latest albums from Deezer
                    albums_data = await deezer_service.get_artist_albums(
                        artist["deezer_id"],
                        limit=10
                    )

                    for album_info in albums_data:
                        # Check if album already exists
                        existing = await conn.fetchrow(
                            "SELECT id FROM albums WHERE deezer_id = $1",
                            album_info["id"]
                        )

                        if existing:
                            continue

                        # Add new album to library
                        await conn.execute(
                            """
                            INSERT INTO albums (
                                title, cover, cover_medium, cover_big, cover_xl, release_date,
                                deezer_id, artist_id, monitored, root_folder_path,
                                nb_tracks, record_type, artist_name, status
                            )
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, TRUE, $9, $10, $11, $12, 'wanted')
                            """,
                            album_info.get("title"),
                            album_info.get("cover"),
                            album_info.get("cover_medium"),
                            album_info.get("cover_big"),
                            album_info.get("cover_xl"),
                            parse_release_date(album_info.get("release_date")),
                            album_info.get("id"),
                            artist["id"],
                            artist["root_folder_path"],
                            album_info.get("nb_tracks"),
                            album_info.get("record_type"),
                            artist["name"],
                        )

                        new_albums_added += 1
                        print(f"Music: New album found: {album_info.get('title')} by {artist['name']}")

                    # Update artist's last check time
                    await conn.execute(
                        "UPDATE artists SET updated_at = NOW() WHERE id = $1",
                        artist["id"]
                    )

                except Exception as e:
                    print(f"Error checking new releases for {artist['name']}: {e}")
                    continue

                # Small delay between artist checks
                await asyncio.sleep(1)

        return {
            "status": "success",
            "artists_checked": artists_checked,
            "new_albums_added": new_albums_added,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        print(f"New release check error: {e}")
        return {"status": "error", "message": str(e)}


@celery_app.task(name="app.tasks.music_monitor.search_discography")
def search_discography(artist_id: int):
    """
    Search and download full discography for an artist
    Called when user clicks "Download All" for an artist
    """
    return asyncio.run(async_search_discography(artist_id))


async def async_search_discography(artist_id: int):
    """
    Async implementation of discography search
    """
    try:
        grabbed_count = 0
        searched_count = 0

        pool = await get_pool()

        async with pool.acquire() as conn:
            # Get artist
            artist = await conn.fetchrow(
                "SELECT * FROM artists WHERE id = $1",
                artist_id
            )

            if not artist:
                return {"status": "error", "message": "Artist not found"}

            artist = dict(artist)

            # Get all wanted albums for this artist
            wanted_albums = await conn.fetch(
                """
                SELECT * FROM albums
                WHERE artist_id = $1
                AND status = 'wanted'
                AND monitored = TRUE
                ORDER BY release_date DESC
                """,
                artist_id
            )

            for album_row in wanted_albums:
                album = dict(album_row)
                searched_count += 1

                query = f"{artist['name']} {album['title']}"

                # Get or create default profile
                profile = MediaProfile(
                    id=0,
                    name="Default Music",
                    music_preferred_quality=["flac", "mp3_320", "mp3_256"],
                )

                if album["media_profile_id"]:
                    profile_row = await conn.fetchrow(
                        "SELECT * FROM quality_profiles WHERE id = $1",
                        album["media_profile_id"]
                    )
                    if profile_row:
                        profile = MediaProfile(**dict(profile_row))

                try:
                    torrent_hash = await search_engine.search_music_and_download(
                        query=query,
                        profile=profile,
                        save_path=album.get("root_folder_path") or artist.get("root_folder_path"),
                        tags=["nexarr", "music", "discography", f"album-{album['id']}"],
                    )

                    if torrent_hash:
                        await conn.execute(
                            """
                            UPDATE albums
                            SET status = 'downloading', updated_at = NOW()
                            WHERE id = $1
                            """,
                            album["id"]
                        )
                        grabbed_count += 1

                except Exception as e:
                    print(f"Error searching for {query}: {e}")
                    continue

                await asyncio.sleep(2)

        return {
            "status": "success",
            "artist": artist["name"],
            "items_searched": searched_count,
            "items_grabbed": grabbed_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        print(f"Discography search error: {e}")
        return {"status": "error", "message": str(e)}
