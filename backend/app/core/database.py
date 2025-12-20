import asyncpg
from typing import Optional

from app.core.config import settings

# Global connection pool
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """
    Get or create database connection pool with maximum performance settings
    """
    global _pool

    if _pool is None:
        _pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=10,
            max_size=50,
            max_queries=100000,
            max_inactive_connection_lifetime=300,
            command_timeout=60,
        )

    return _pool


async def close_pool():
    """
    Close database connection pool
    """
    global _pool

    if _pool:
        await _pool.close()
        _pool = None


async def get_db():
    """
    Get database connection from pool (dependency injection)
    """
    pool = await get_pool()
    async with pool.acquire() as connection:
        yield connection


async def init_db():
    """
    Initialize database schema with all tables and indexes
    """
    pool = await get_pool()

    async with pool.acquire() as conn:
        # Users table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                hashed_password VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE NOT NULL,
                role VARCHAR(50) DEFAULT 'user' NOT NULL,
                last_login_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
        """)

        # User auth providers table - tracks linked authentication methods
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_auth_providers (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE NOT NULL,
                provider_type VARCHAR(50) NOT NULL,
                provider_name VARCHAR(100),
                provider_subject VARCHAR(255) NOT NULL,
                provider_username VARCHAR(255),
                provider_metadata JSONB,
                linked_at TIMESTAMP DEFAULT NOW() NOT NULL,
                last_used_at TIMESTAMP DEFAULT NOW() NOT NULL,
                UNIQUE(provider_type, provider_name, provider_subject)
            );

            CREATE INDEX IF NOT EXISTS idx_user_auth_providers_user ON user_auth_providers(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_auth_providers_subject ON user_auth_providers(provider_subject);
            CREATE INDEX IF NOT EXISTS idx_user_auth_providers_type ON user_auth_providers(provider_type);
        """)

        # TOTP 2FA table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_totp (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE NOT NULL UNIQUE,
                secret VARCHAR(255) NOT NULL,
                enabled BOOLEAN DEFAULT FALSE NOT NULL,
                backup_codes JSONB,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                verified_at TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_user_totp_user ON user_totp(user_id);
        """)

        # WebAuthn credentials table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_webauthn_credentials (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE NOT NULL,
                credential_id TEXT NOT NULL UNIQUE,
                public_key TEXT NOT NULL,
                sign_count INTEGER DEFAULT 0 NOT NULL,
                name VARCHAR(100),
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                last_used_at TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_user_webauthn_user ON user_webauthn_credentials(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_webauthn_credential ON user_webauthn_credentials(credential_id);
        """)

        # Movies table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                original_title VARCHAR(255),
                overview TEXT,
                poster_path VARCHAR(500),
                backdrop_path VARCHAR(500),
                release_date TIMESTAMP,
                genres JSONB,
                rating FLOAT,
                vote_count INTEGER,
                popularity FLOAT,
                status VARCHAR(50) DEFAULT 'wanted' NOT NULL,
                tmdb_id INTEGER UNIQUE,
                imdb_id VARCHAR(20),
                monitored BOOLEAN DEFAULT TRUE NOT NULL,
                media_profile_id INTEGER,
                root_folder_path VARCHAR(500),
                runtime INTEGER,
                budget BIGINT,
                revenue BIGINT,
                tagline VARCHAR(500),
                production_companies JSONB,
                production_countries JSONB,
                spoken_languages JSONB,
                collection_id INTEGER,
                collection_name VARCHAR(255),
                has_file BOOLEAN DEFAULT FALSE NOT NULL,
                file_path VARCHAR(1000),
                file_size BIGINT,
                quality_detected VARCHAR(50),
                codec VARCHAR(50),
                resolution VARCHAR(50),
                metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_movies_title ON movies USING GIN (to_tsvector('english', title));
            CREATE INDEX IF NOT EXISTS idx_movies_tmdb_id ON movies(tmdb_id);
            CREATE INDEX IF NOT EXISTS idx_movies_imdb_id ON movies(imdb_id);
            CREATE INDEX IF NOT EXISTS idx_movies_status ON movies(status);
            CREATE INDEX IF NOT EXISTS idx_movies_monitored ON movies(monitored);
            CREATE INDEX IF NOT EXISTS idx_movies_collection ON movies(collection_id);
        """)

        # Shows table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS shows (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                original_title VARCHAR(255),
                overview TEXT,
                poster_path VARCHAR(500),
                backdrop_path VARCHAR(500),
                release_date TIMESTAMP,
                genres JSONB,
                rating FLOAT,
                vote_count INTEGER,
                popularity FLOAT,
                status VARCHAR(50) DEFAULT 'wanted' NOT NULL,
                tmdb_id INTEGER UNIQUE,
                imdb_id VARCHAR(20),
                tvdb_id INTEGER,
                tvrage_id INTEGER,
                monitored BOOLEAN DEFAULT TRUE NOT NULL,
                media_profile_id INTEGER,
                root_folder_path VARCHAR(500),
                number_of_seasons INTEGER,
                number_of_episodes INTEGER,
                episode_run_time JSONB,
                networks JSONB,
                production_companies JSONB,
                first_air_date TIMESTAMP,
                last_air_date TIMESTAMP,
                in_production BOOLEAN DEFAULT FALSE,
                season_monitoring VARCHAR(50) DEFAULT 'all',
                metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_shows_title ON shows USING GIN (to_tsvector('english', title));
            CREATE INDEX IF NOT EXISTS idx_shows_tmdb_id ON shows(tmdb_id);
            CREATE INDEX IF NOT EXISTS idx_shows_imdb_id ON shows(imdb_id);
            CREATE INDEX IF NOT EXISTS idx_shows_tvdb_id ON shows(tvdb_id);
            CREATE INDEX IF NOT EXISTS idx_shows_status ON shows(status);
        """)

        # Anime table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS anime (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                original_title VARCHAR(255),
                overview TEXT,
                poster_path VARCHAR(500),
                backdrop_path VARCHAR(500),
                release_date TIMESTAMP,
                genres JSONB,
                rating FLOAT,
                vote_count INTEGER,
                popularity FLOAT,
                status VARCHAR(50) DEFAULT 'wanted' NOT NULL,
                tmdb_id INTEGER,
                imdb_id VARCHAR(20),
                anilist_id INTEGER UNIQUE,
                mal_id INTEGER,
                monitored BOOLEAN DEFAULT TRUE NOT NULL,
                media_profile_id INTEGER,
                root_folder_path VARCHAR(500),
                episodes INTEGER,
                duration INTEGER,
                season_year INTEGER,
                season_period VARCHAR(50),
                format VARCHAR(50),
                source VARCHAR(50),
                studios JSONB,
                is_adult BOOLEAN DEFAULT FALSE,
                absolute_numbering BOOLEAN DEFAULT TRUE,
                has_file BOOLEAN DEFAULT FALSE NOT NULL,
                episode_monitoring VARCHAR(50) DEFAULT 'all',
                metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_anime_title ON anime USING GIN (to_tsvector('english', title));
            CREATE INDEX IF NOT EXISTS idx_anime_anilist_id ON anime(anilist_id);
            CREATE INDEX IF NOT EXISTS idx_anime_mal_id ON anime(mal_id);
            CREATE INDEX IF NOT EXISTS idx_anime_status ON anime(status);
        """)

        # Artists table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS artists (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                picture VARCHAR(500),
                picture_medium VARCHAR(500),
                picture_big VARCHAR(500),
                picture_xl VARCHAR(500),
                deezer_id BIGINT UNIQUE,
                monitored BOOLEAN DEFAULT TRUE NOT NULL,
                root_folder_path VARCHAR(500),
                genres JSONB,
                nb_album INTEGER,
                nb_fan INTEGER,
                has_files BOOLEAN DEFAULT FALSE NOT NULL,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_artists_name ON artists USING GIN (to_tsvector('english', name));
            CREATE INDEX IF NOT EXISTS idx_artists_deezer_id ON artists(deezer_id);
            CREATE INDEX IF NOT EXISTS idx_artists_monitored ON artists(monitored);
        """)

        # Albums table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS albums (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                cover VARCHAR(500),
                cover_medium VARCHAR(500),
                cover_big VARCHAR(500),
                cover_xl VARCHAR(500),
                release_date TIMESTAMP,
                deezer_id BIGINT UNIQUE,
                artist_id INTEGER REFERENCES artists(id) ON DELETE CASCADE,
                upc VARCHAR(50),
                monitored BOOLEAN DEFAULT TRUE NOT NULL,
                media_profile_id INTEGER,
                root_folder_path VARCHAR(500),
                status VARCHAR(50) DEFAULT 'wanted' NOT NULL,
                genres JSONB,
                nb_tracks INTEGER,
                duration INTEGER,
                label VARCHAR(255),
                explicit_lyrics BOOLEAN DEFAULT FALSE,
                record_type VARCHAR(50),
                artist_name VARCHAR(255),
                has_file BOOLEAN DEFAULT FALSE NOT NULL,
                file_path VARCHAR(1000),
                file_size BIGINT,
                quality_detected VARCHAR(50),
                codec VARCHAR(50),
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_albums_title ON albums USING GIN (to_tsvector('english', title));
            CREATE INDEX IF NOT EXISTS idx_albums_deezer_id ON albums(deezer_id);
            CREATE INDEX IF NOT EXISTS idx_albums_artist_id ON albums(artist_id);
            CREATE INDEX IF NOT EXISTS idx_albums_status ON albums(status);
            CREATE INDEX IF NOT EXISTS idx_albums_monitored ON albums(monitored);
        """)

        # Tracks table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tracks (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                duration INTEGER,
                track_position INTEGER,
                disk_number INTEGER,
                deezer_id BIGINT UNIQUE,
                album_id INTEGER REFERENCES albums(id) ON DELETE CASCADE,
                isrc VARCHAR(50),
                explicit_lyrics BOOLEAN DEFAULT FALSE,
                preview VARCHAR(500),
                artist_name VARCHAR(255),
                album_title VARCHAR(255),
                has_file BOOLEAN DEFAULT FALSE NOT NULL,
                file_path VARCHAR(1000),
                file_size BIGINT,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks USING GIN (to_tsvector('english', title));
            CREATE INDEX IF NOT EXISTS idx_tracks_deezer_id ON tracks(deezer_id);
            CREATE INDEX IF NOT EXISTS idx_tracks_album_id ON tracks(album_id);
            CREATE INDEX IF NOT EXISTS idx_tracks_isrc ON tracks(isrc);
        """)

        # Media profiles table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS media_profiles (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                min_size INTEGER,
                max_size INTEGER,
                -- Legacy global quality fields (kept for backward compatibility)
                resolutions TEXT[] DEFAULT ARRAY[]::TEXT[],
                codecs TEXT[] DEFAULT ARRAY[]::TEXT[],
                sources TEXT[] DEFAULT ARRAY[]::TEXT[],
                audio_codecs TEXT[] DEFAULT ARRAY[]::TEXT[],
                audio_channels TEXT[] DEFAULT ARRAY[]::TEXT[],
                hdr_formats TEXT[] DEFAULT ARRAY[]::TEXT[],
                editions TEXT[] DEFAULT ARRAY[]::TEXT[],
                -- Per-media-type quality: Movies
                movie_resolutions TEXT[] DEFAULT ARRAY[]::TEXT[],
                movie_codecs TEXT[] DEFAULT ARRAY[]::TEXT[],
                movie_sources TEXT[] DEFAULT ARRAY[]::TEXT[],
                movie_audio_codecs TEXT[] DEFAULT ARRAY[]::TEXT[],
                movie_audio_channels TEXT[] DEFAULT ARRAY[]::TEXT[],
                movie_hdr_formats TEXT[] DEFAULT ARRAY[]::TEXT[],
                movie_editions TEXT[] DEFAULT ARRAY[]::TEXT[],
                movie_min_size INTEGER,
                movie_max_size INTEGER,
                -- Per-media-type quality: TV Shows
                show_resolutions TEXT[] DEFAULT ARRAY[]::TEXT[],
                show_codecs TEXT[] DEFAULT ARRAY[]::TEXT[],
                show_sources TEXT[] DEFAULT ARRAY[]::TEXT[],
                show_audio_codecs TEXT[] DEFAULT ARRAY[]::TEXT[],
                show_audio_channels TEXT[] DEFAULT ARRAY[]::TEXT[],
                show_hdr_formats TEXT[] DEFAULT ARRAY[]::TEXT[],
                show_min_size INTEGER,
                show_max_size INTEGER,
                -- Per-media-type quality: Anime
                anime_resolutions TEXT[] DEFAULT ARRAY[]::TEXT[],
                anime_codecs TEXT[] DEFAULT ARRAY[]::TEXT[],
                anime_sources TEXT[] DEFAULT ARRAY[]::TEXT[],
                anime_audio_codecs TEXT[] DEFAULT ARRAY[]::TEXT[],
                anime_audio_channels TEXT[] DEFAULT ARRAY[]::TEXT[],
                anime_hdr_formats TEXT[] DEFAULT ARRAY[]::TEXT[],
                anime_min_size INTEGER,
                anime_max_size INTEGER,
                -- Common settings
                languages TEXT[] DEFAULT ARRAY[]::TEXT[],
                subtitle_languages TEXT[] DEFAULT ARRAY[]::TEXT[],
                upgrade_allowed BOOLEAN DEFAULT TRUE,
                indexers TEXT[] DEFAULT ARRAY[]::TEXT[],
                uploaders TEXT[] DEFAULT ARRAY[]::TEXT[],
                release_groups TEXT[] DEFAULT ARRAY[]::TEXT[],
                regex_filters TEXT[] DEFAULT ARRAY[]::TEXT[],
                seeder_weight INTEGER DEFAULT 34,
                size_weight INTEGER DEFAULT 33,
                recency_weight INTEGER DEFAULT 33,
                search_sort_preference VARCHAR(20) DEFAULT 'weighted',
                season_pack_preference VARCHAR(20) DEFAULT 'prefer',
                search_timeout INTEGER DEFAULT 30,
                max_retries INTEGER DEFAULT 3,
                max_results INTEGER DEFAULT 100,
                -- Naming formats
                movie_naming_format TEXT,
                movie_folder_format TEXT,
                show_naming_format TEXT,
                show_folder_format TEXT,
                anime_naming_format TEXT,
                anime_folder_format TEXT,
                -- Anime options
                anime_subtitle_preference VARCHAR(20) DEFAULT 'softsub',
                anime_allow_hardsub BOOLEAN DEFAULT FALSE,
                anime_prefer_dual_audio BOOLEAN DEFAULT FALSE,
                anime_audio_language VARCHAR(10) DEFAULT 'ja',
                anime_subtitle_language VARCHAR(10) DEFAULT 'en',
                -- Indexers per media type
                movie_indexers TEXT[] DEFAULT ARRAY[]::TEXT[],
                show_indexers TEXT[] DEFAULT ARRAY[]::TEXT[],
                anime_indexers TEXT[] DEFAULT ARRAY[]::TEXT[],
                music_indexers TEXT[] DEFAULT ARRAY[]::TEXT[],
                -- Music settings
                music_artist_folder_format TEXT DEFAULT '{artist}',
                music_album_folder_format TEXT DEFAULT '{album} ({year})',
                music_track_naming_format TEXT DEFAULT '{track:00} - {title}',
                music_multi_disc_format TEXT DEFAULT '{disc:00}-{track:00} - {title}',
                music_preferred_quality TEXT[] DEFAULT ARRAY['flac', 'mp3_320', 'mp3_256', 'aac']::TEXT[],
                music_embed_lyrics BOOLEAN DEFAULT TRUE,
                music_embed_artwork BOOLEAN DEFAULT TRUE,
                -- File output settings
                media_server VARCHAR(20) DEFAULT 'jellyfin',
                use_hardlinks BOOLEAN DEFAULT TRUE,
                illegal_char_replacement VARCHAR(5) DEFAULT '_',
                colon_replacement VARCHAR(5) DEFAULT ' -',
                -- Torrent validation settings
                validation_enabled BOOLEAN DEFAULT TRUE,
                allowed_extensions TEXT[],
                forbidden_extensions TEXT[] DEFAULT ARRAY['.exe', '.bat', '.cmd', '.sh', '.msi', '.dll', '.scr', '.com', '.ps1', '.vbs', '.jar']::TEXT[],
                validation_failure_action VARCHAR(20) DEFAULT 'pause_notify',
                movie_allowed_extensions TEXT[] DEFAULT ARRAY['.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.webm', '.ts']::TEXT[],
                show_allowed_extensions TEXT[] DEFAULT ARRAY['.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.webm', '.ts']::TEXT[],
                anime_allowed_extensions TEXT[] DEFAULT ARRAY['.mkv', '.mp4', '.avi', '.m4v']::TEXT[],
                music_allowed_extensions TEXT[] DEFAULT ARRAY['.flac', '.mp3', '.m4a', '.aac', '.ogg', '.opus', '.wav', '.wma']::TEXT[],
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_media_profiles_name ON media_profiles(name);
        """)

        # Add new columns if they don't exist (migration for existing databases)
        await conn.execute("""
            DO $$
            BEGIN
                -- Movie quality columns
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'movie_resolutions') THEN
                    ALTER TABLE media_profiles ADD COLUMN movie_resolutions TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'movie_codecs') THEN
                    ALTER TABLE media_profiles ADD COLUMN movie_codecs TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'movie_sources') THEN
                    ALTER TABLE media_profiles ADD COLUMN movie_sources TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'movie_audio_codecs') THEN
                    ALTER TABLE media_profiles ADD COLUMN movie_audio_codecs TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'movie_audio_channels') THEN
                    ALTER TABLE media_profiles ADD COLUMN movie_audio_channels TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'movie_hdr_formats') THEN
                    ALTER TABLE media_profiles ADD COLUMN movie_hdr_formats TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'movie_editions') THEN
                    ALTER TABLE media_profiles ADD COLUMN movie_editions TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'movie_min_size') THEN
                    ALTER TABLE media_profiles ADD COLUMN movie_min_size INTEGER;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'movie_max_size') THEN
                    ALTER TABLE media_profiles ADD COLUMN movie_max_size INTEGER;
                END IF;
                -- Show quality columns
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'show_resolutions') THEN
                    ALTER TABLE media_profiles ADD COLUMN show_resolutions TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'show_codecs') THEN
                    ALTER TABLE media_profiles ADD COLUMN show_codecs TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'show_sources') THEN
                    ALTER TABLE media_profiles ADD COLUMN show_sources TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'show_audio_codecs') THEN
                    ALTER TABLE media_profiles ADD COLUMN show_audio_codecs TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'show_audio_channels') THEN
                    ALTER TABLE media_profiles ADD COLUMN show_audio_channels TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'show_hdr_formats') THEN
                    ALTER TABLE media_profiles ADD COLUMN show_hdr_formats TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'show_min_size') THEN
                    ALTER TABLE media_profiles ADD COLUMN show_min_size INTEGER;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'show_max_size') THEN
                    ALTER TABLE media_profiles ADD COLUMN show_max_size INTEGER;
                END IF;
                -- Anime quality columns
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'anime_resolutions') THEN
                    ALTER TABLE media_profiles ADD COLUMN anime_resolutions TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'anime_codecs') THEN
                    ALTER TABLE media_profiles ADD COLUMN anime_codecs TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'anime_sources') THEN
                    ALTER TABLE media_profiles ADD COLUMN anime_sources TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'anime_audio_codecs') THEN
                    ALTER TABLE media_profiles ADD COLUMN anime_audio_codecs TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'anime_audio_channels') THEN
                    ALTER TABLE media_profiles ADD COLUMN anime_audio_channels TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'anime_hdr_formats') THEN
                    ALTER TABLE media_profiles ADD COLUMN anime_hdr_formats TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'anime_min_size') THEN
                    ALTER TABLE media_profiles ADD COLUMN anime_min_size INTEGER;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'anime_max_size') THEN
                    ALTER TABLE media_profiles ADD COLUMN anime_max_size INTEGER;
                END IF;
                -- Music columns
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'music_indexers') THEN
                    ALTER TABLE media_profiles ADD COLUMN music_indexers TEXT[] DEFAULT ARRAY[]::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'music_artist_folder_format') THEN
                    ALTER TABLE media_profiles ADD COLUMN music_artist_folder_format TEXT DEFAULT '{artist}';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'music_album_folder_format') THEN
                    ALTER TABLE media_profiles ADD COLUMN music_album_folder_format TEXT DEFAULT '{album} ({year})';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'music_track_naming_format') THEN
                    ALTER TABLE media_profiles ADD COLUMN music_track_naming_format TEXT DEFAULT '{track:00} - {title}';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'music_multi_disc_format') THEN
                    ALTER TABLE media_profiles ADD COLUMN music_multi_disc_format TEXT DEFAULT '{disc:00}-{track:00} - {title}';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'music_preferred_quality') THEN
                    ALTER TABLE media_profiles ADD COLUMN music_preferred_quality TEXT[] DEFAULT ARRAY['flac', 'mp3_320', 'mp3_256', 'aac']::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'music_embed_lyrics') THEN
                    ALTER TABLE media_profiles ADD COLUMN music_embed_lyrics BOOLEAN DEFAULT TRUE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'music_embed_artwork') THEN
                    ALTER TABLE media_profiles ADD COLUMN music_embed_artwork BOOLEAN DEFAULT TRUE;
                END IF;
                -- Torrent validation columns
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'validation_enabled') THEN
                    ALTER TABLE media_profiles ADD COLUMN validation_enabled BOOLEAN DEFAULT TRUE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'allowed_extensions') THEN
                    ALTER TABLE media_profiles ADD COLUMN allowed_extensions TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'forbidden_extensions') THEN
                    ALTER TABLE media_profiles ADD COLUMN forbidden_extensions TEXT[] DEFAULT ARRAY['.exe', '.bat', '.cmd', '.sh', '.msi', '.dll', '.scr', '.com', '.ps1', '.vbs', '.jar']::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'validation_failure_action') THEN
                    ALTER TABLE media_profiles ADD COLUMN validation_failure_action VARCHAR(20) DEFAULT 'pause_notify';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'movie_allowed_extensions') THEN
                    ALTER TABLE media_profiles ADD COLUMN movie_allowed_extensions TEXT[] DEFAULT ARRAY['.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.webm', '.ts']::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'show_allowed_extensions') THEN
                    ALTER TABLE media_profiles ADD COLUMN show_allowed_extensions TEXT[] DEFAULT ARRAY['.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.webm', '.ts']::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'anime_allowed_extensions') THEN
                    ALTER TABLE media_profiles ADD COLUMN anime_allowed_extensions TEXT[] DEFAULT ARRAY['.mkv', '.mp4', '.avi', '.m4v']::TEXT[];
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'media_profiles' AND column_name = 'music_allowed_extensions') THEN
                    ALTER TABLE media_profiles ADD COLUMN music_allowed_extensions TEXT[] DEFAULT ARRAY['.flac', '.mp3', '.m4a', '.aac', '.ogg', '.opus', '.wav', '.wma']::TEXT[];
                END IF;
            END $$;
        """)

        # Download history table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS download_history (
                id SERIAL PRIMARY KEY,
                media_id INTEGER NOT NULL,
                media_type VARCHAR(20) NOT NULL,
                torrent_hash VARCHAR(100) NOT NULL,
                torrent_title TEXT NOT NULL,
                indexer VARCHAR(50) NOT NULL,
                quality VARCHAR(50),
                size BIGINT,
                status VARCHAR(50) DEFAULT 'pending',
                progress FLOAT DEFAULT 0.0,
                download_client VARCHAR(50),
                save_path TEXT,
                error_message TEXT,
                started_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_download_history_media ON download_history(media_id, media_type);
            CREATE INDEX IF NOT EXISTS idx_download_history_hash ON download_history(torrent_hash);
            CREATE INDEX IF NOT EXISTS idx_download_history_status ON download_history(status);
        """)

        # Collections table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS collections (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                description TEXT,
                collection_type VARCHAR(50),
                tmdb_collection_id INTEGER,
                poster_path VARCHAR(500),
                backdrop_path VARCHAR(500),
                monitored BOOLEAN DEFAULT TRUE,
                media_profile_id INTEGER,
                search_on_add BOOLEAN DEFAULT TRUE,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_collections_name ON collections(name);
            CREATE INDEX IF NOT EXISTS idx_collections_tmdb ON collections(tmdb_collection_id);
        """)

        # Collection items (many-to-many relationship)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS collection_items (
                id SERIAL PRIMARY KEY,
                collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE,
                media_id INTEGER NOT NULL,
                media_type VARCHAR(20) NOT NULL,
                sort_order INTEGER,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_collection_items_collection ON collection_items(collection_id);
            CREATE INDEX IF NOT EXISTS idx_collection_items_media ON collection_items(media_id, media_type);
        """)

        # Removed settings table - now using app_settings table for all configuration

        # Transcoding profiles table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS transcoding_profiles (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                description TEXT,
                container VARCHAR(20),
                video_codec VARCHAR(50),
                video_quality_mode VARCHAR(20),
                video_quality_value INTEGER,
                video_preset VARCHAR(50),
                audio_codec VARCHAR(50),
                audio_bitrate INTEGER,
                audio_channels VARCHAR(20),
                resolution VARCHAR(20),
                fps VARCHAR(20),
                hardware_accel_type VARCHAR(20),
                hardware_accel_device INTEGER,
                tune VARCHAR(50),
                custom_ffmpeg_args JSONB,
                is_system BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_transcoding_profiles_name ON transcoding_profiles(name);
        """)

        # Transcoding rules table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS transcoding_rules (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                enabled BOOLEAN DEFAULT TRUE,
                priority INTEGER DEFAULT 0,
                trigger_type VARCHAR(50) NOT NULL,
                conditions JSONB,
                profile_id INTEGER REFERENCES transcoding_profiles(id) ON DELETE CASCADE,
                output_action VARCHAR(50) DEFAULT 'replace',
                use_media_profile_naming BOOLEAN DEFAULT TRUE,
                media_types TEXT[] DEFAULT ARRAY['movie', 'show', 'anime']::TEXT[],
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_transcoding_rules_enabled ON transcoding_rules(enabled);
            CREATE INDEX IF NOT EXISTS idx_transcoding_rules_priority ON transcoding_rules(priority);
        """)

        # Transcoding jobs table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS transcoding_jobs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                media_id INTEGER,
                media_type VARCHAR(20),
                media_title VARCHAR(500),
                input_path TEXT NOT NULL,
                output_path TEXT,
                output_action VARCHAR(50) DEFAULT 'replace',
                use_media_profile_naming BOOLEAN DEFAULT TRUE,
                profile_id INTEGER REFERENCES transcoding_profiles(id) ON DELETE SET NULL,
                profile_snapshot JSONB NOT NULL,
                hardware_accel_type VARCHAR(20),
                hardware_accel_device INTEGER,
                status VARCHAR(20) DEFAULT 'pending',
                progress NUMERIC(5, 2) DEFAULT 0,
                current_frame INTEGER,
                total_frames INTEGER,
                fps NUMERIC(10, 2),
                speed VARCHAR(20),
                bitrate VARCHAR(50),
                file_size_input BIGINT,
                file_size_output BIGINT,
                eta_seconds INTEGER,
                celery_task_id VARCHAR(255),
                error_message TEXT,
                log_file TEXT,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_transcoding_jobs_status ON transcoding_jobs(status);
            CREATE INDEX IF NOT EXISTS idx_transcoding_jobs_user ON transcoding_jobs(user_id);
            CREATE INDEX IF NOT EXISTS idx_transcoding_jobs_media ON transcoding_jobs(media_id, media_type);
            CREATE INDEX IF NOT EXISTS idx_transcoding_jobs_created ON transcoding_jobs(created_at);
        """)

        # Transcoding progress table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS transcoding_progress (
                job_id INTEGER PRIMARY KEY REFERENCES transcoding_jobs(id) ON DELETE CASCADE,
                frame INTEGER,
                fps NUMERIC(10, 2),
                bitrate VARCHAR(50),
                size BIGINT,
                time VARCHAR(50),
                speed VARCHAR(20),
                progress NUMERIC(5, 2),
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );
        """)

        # Hardware acceleration devices table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS hardware_accel_devices (
                id SERIAL PRIMARY KEY,
                device_type VARCHAR(20) NOT NULL,
                device_index INTEGER NOT NULL,
                device_name VARCHAR(255),
                device_uuid VARCHAR(100),
                pci_bus_id VARCHAR(50),
                compute_capability VARCHAR(20),
                memory_total BIGINT,
                driver_version VARCHAR(50),
                is_available BOOLEAN DEFAULT TRUE,
                last_detected TIMESTAMP DEFAULT NOW() NOT NULL,
                UNIQUE(device_type, device_index)
            );

            CREATE INDEX IF NOT EXISTS idx_hardware_accel_type ON hardware_accel_devices(device_type);
            CREATE INDEX IF NOT EXISTS idx_hardware_accel_available ON hardware_accel_devices(is_available);
        """)

        # Application settings table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                id SERIAL PRIMARY KEY,
                key VARCHAR(100) UNIQUE NOT NULL,
                value TEXT,
                value_type VARCHAR(20) DEFAULT 'string' NOT NULL,
                is_encrypted BOOLEAN DEFAULT FALSE NOT NULL,
                category VARCHAR(50) NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_app_settings_key ON app_settings(key);
            CREATE INDEX IF NOT EXISTS idx_app_settings_category ON app_settings(category);
        """)

        # Download clients table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS download_clients (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                client_type VARCHAR(50) NOT NULL,
                host VARCHAR(255) NOT NULL,
                port INTEGER NOT NULL,
                username VARCHAR(100),
                encrypted_password TEXT,
                use_ssl BOOLEAN DEFAULT FALSE NOT NULL,
                is_enabled BOOLEAN DEFAULT TRUE NOT NULL,
                is_default BOOLEAN DEFAULT FALSE NOT NULL,
                test_status VARCHAR(20) DEFAULT 'untested' NOT NULL,
                last_tested TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_download_clients_enabled ON download_clients(is_enabled);
            CREATE INDEX IF NOT EXISTS idx_download_clients_default ON download_clients(is_default);
        """)

        # Seasons table for TV shows
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS seasons (
                id SERIAL PRIMARY KEY,
                show_id INTEGER REFERENCES shows(id) ON DELETE CASCADE NOT NULL,
                season_number INTEGER NOT NULL,
                title VARCHAR(500),
                overview TEXT,
                poster_path VARCHAR(500),
                air_date DATE,
                episode_count INTEGER,
                monitored BOOLEAN DEFAULT TRUE NOT NULL,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
                UNIQUE(show_id, season_number)
            );

            CREATE INDEX IF NOT EXISTS idx_seasons_show ON seasons(show_id);
            CREATE INDEX IF NOT EXISTS idx_seasons_monitored ON seasons(monitored);
        """)

        # Episodes table for TV shows
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id SERIAL PRIMARY KEY,
                show_id INTEGER REFERENCES shows(id) ON DELETE CASCADE NOT NULL,
                season_id INTEGER REFERENCES seasons(id) ON DELETE CASCADE,
                season_number INTEGER NOT NULL,
                episode_number INTEGER NOT NULL,
                title VARCHAR(500),
                overview TEXT,
                still_path VARCHAR(500),
                air_date DATE,
                runtime INTEGER,
                monitored BOOLEAN DEFAULT TRUE NOT NULL,
                has_file BOOLEAN DEFAULT FALSE NOT NULL,
                file_path VARCHAR(1000),
                file_size BIGINT,
                quality_detected VARCHAR(50),
                codec VARCHAR(50),
                resolution VARCHAR(50),
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
                UNIQUE(show_id, season_number, episode_number)
            );

            CREATE INDEX IF NOT EXISTS idx_episodes_show ON episodes(show_id);
            CREATE INDEX IF NOT EXISTS idx_episodes_season ON episodes(season_id);
            CREATE INDEX IF NOT EXISTS idx_episodes_monitored ON episodes(monitored);
            CREATE INDEX IF NOT EXISTS idx_episodes_has_file ON episodes(has_file);
        """)

        # Anime episodes table with absolute and season-based numbering support
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS anime_episodes (
                id SERIAL PRIMARY KEY,
                anime_id INTEGER REFERENCES anime(id) ON DELETE CASCADE NOT NULL,
                episode_number INTEGER NOT NULL,
                season_number INTEGER,
                season_episode INTEGER,
                title VARCHAR(500),
                air_date DATE,
                monitored BOOLEAN DEFAULT TRUE NOT NULL,
                has_file BOOLEAN DEFAULT FALSE NOT NULL,
                file_path VARCHAR(1000),
                file_size BIGINT,
                quality_detected VARCHAR(50),
                codec VARCHAR(50),
                resolution VARCHAR(50),
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
                UNIQUE(anime_id, episode_number)
            );

            CREATE INDEX IF NOT EXISTS idx_anime_episodes_anime ON anime_episodes(anime_id);
            CREATE INDEX IF NOT EXISTS idx_anime_episodes_monitored ON anime_episodes(monitored);
            CREATE INDEX IF NOT EXISTS idx_anime_episodes_has_file ON anime_episodes(has_file);
        """)

        # Blocklist table for rejected releases
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS blocklist (
                id SERIAL PRIMARY KEY,
                media_type VARCHAR(50) NOT NULL,
                media_id INTEGER NOT NULL,
                release_title VARCHAR(1000) NOT NULL,
                reason VARCHAR(500),
                blocked_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_blocklist_media ON blocklist(media_type, media_id);
            CREATE INDEX IF NOT EXISTS idx_blocklist_title ON blocklist(release_title);
        """)

        # Tags table for organizing media
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                color VARCHAR(20) DEFAULT '#6366f1',
                created_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);
        """)

        # Media tags junction table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS media_tags (
                id SERIAL PRIMARY KEY,
                tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE NOT NULL,
                media_type VARCHAR(50) NOT NULL,
                media_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                UNIQUE(tag_id, media_type, media_id)
            );

            CREATE INDEX IF NOT EXISTS idx_media_tags_tag ON media_tags(tag_id);
            CREATE INDEX IF NOT EXISTS idx_media_tags_media ON media_tags(media_type, media_id);
        """)

        # Add upgrade_allowed column and other new columns to existing tables
        await conn.execute("""
            DO $$
            BEGIN
                -- Movies: upgrade_allowed
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'movies' AND column_name = 'upgrade_allowed') THEN
                    ALTER TABLE movies ADD COLUMN upgrade_allowed BOOLEAN DEFAULT NULL;
                END IF;

                -- Shows: upgrade_allowed
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'shows' AND column_name = 'upgrade_allowed') THEN
                    ALTER TABLE shows ADD COLUMN upgrade_allowed BOOLEAN DEFAULT NULL;
                END IF;

                -- Anime: upgrade_allowed
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'anime' AND column_name = 'upgrade_allowed') THEN
                    ALTER TABLE anime ADD COLUMN upgrade_allowed BOOLEAN DEFAULT NULL;
                END IF;

                -- Albums: upgrade_allowed
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'albums' AND column_name = 'upgrade_allowed') THEN
                    ALTER TABLE albums ADD COLUMN upgrade_allowed BOOLEAN DEFAULT NULL;
                END IF;

                -- Download history: add new columns for detailed tracking
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'download_history' AND column_name = 'episode_id') THEN
                    ALTER TABLE download_history ADD COLUMN episode_id INTEGER;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'download_history' AND column_name = 'indexer_page_url') THEN
                    ALTER TABLE download_history ADD COLUMN indexer_page_url VARCHAR(2000);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'download_history' AND column_name = 'torrent_url') THEN
                    ALTER TABLE download_history ADD COLUMN torrent_url VARCHAR(2000);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'download_history' AND column_name = 'magnet_link') THEN
                    ALTER TABLE download_history ADD COLUMN magnet_link TEXT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'download_history' AND column_name = 'info_hash') THEN
                    ALTER TABLE download_history ADD COLUMN info_hash VARCHAR(64);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'download_history' AND column_name = 'source') THEN
                    ALTER TABLE download_history ADD COLUMN source VARCHAR(50);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'download_history' AND column_name = 'seeders') THEN
                    ALTER TABLE download_history ADD COLUMN seeders INTEGER;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'download_history' AND column_name = 'was_upgrade') THEN
                    ALTER TABLE download_history ADD COLUMN was_upgrade BOOLEAN DEFAULT FALSE;
                END IF;
            END $$;
        """)
