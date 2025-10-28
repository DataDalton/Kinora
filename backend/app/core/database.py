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
                hashed_password VARCHAR(255) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE NOT NULL,
                is_superuser BOOLEAN DEFAULT FALSE NOT NULL,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
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

        # Media profiles table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS media_profiles (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                min_size INTEGER,
                max_size INTEGER,
                resolutions TEXT[] DEFAULT ARRAY[]::TEXT[],
                codecs TEXT[] DEFAULT ARRAY[]::TEXT[],
                sources TEXT[] DEFAULT ARRAY[]::TEXT[],
                audio_codecs TEXT[] DEFAULT ARRAY[]::TEXT[],
                audio_channels TEXT[] DEFAULT ARRAY[]::TEXT[],
                hdr_formats TEXT[] DEFAULT ARRAY[]::TEXT[],
                editions TEXT[] DEFAULT ARRAY[]::TEXT[],
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
                movie_naming_format TEXT,
                movie_folder_format TEXT,
                show_naming_format TEXT,
                show_folder_format TEXT,
                anime_naming_format TEXT,
                anime_folder_format TEXT,
                anime_subtitle_preference VARCHAR(20) DEFAULT 'softsub',
                anime_allow_hardsub BOOLEAN DEFAULT FALSE,
                anime_prefer_dual_audio BOOLEAN DEFAULT FALSE,
                anime_audio_language VARCHAR(10) DEFAULT 'ja',
                anime_subtitle_language VARCHAR(10) DEFAULT 'en',
                movie_indexers TEXT[] DEFAULT ARRAY[]::TEXT[],
                show_indexers TEXT[] DEFAULT ARRAY[]::TEXT[],
                anime_indexers TEXT[] DEFAULT ARRAY[]::TEXT[],
                media_server VARCHAR(20) DEFAULT 'jellyfin',
                use_hardlinks BOOLEAN DEFAULT TRUE,
                illegal_char_replacement VARCHAR(5) DEFAULT '_',
                colon_replacement VARCHAR(5) DEFAULT ' -',
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_media_profiles_name ON media_profiles(name);
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

        # Settings table for user-configurable options
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id SERIAL PRIMARY KEY,
                key VARCHAR(100) UNIQUE NOT NULL,
                value TEXT,
                value_type VARCHAR(20) DEFAULT 'string',
                category VARCHAR(50),
                description TEXT,
                is_sensitive BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW() NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key);
            CREATE INDEX IF NOT EXISTS idx_settings_category ON settings(category);
        """)

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
