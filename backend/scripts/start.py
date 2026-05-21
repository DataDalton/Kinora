#!/usr/bin/env python3
"""
Startup script that waits for PostgreSQL and runs Alembic migrations before starting the server.
This ensures migrations run once before workers spawn, preventing race conditions.
"""
import asyncio
import os
import subprocess
import sys


async def waitForPostgres(maxRetries: int = 30, delay: float = 1.0) -> None:
    """Wait for PostgreSQL to be ready before running migrations."""
    import asyncpg

    dsn = os.environ.get(
        "DATABASE_URL",
        "postgresql://kinora:kinora_password@postgres:5432/kinora"
    )

    for i in range(maxRetries):
        try:
            conn = await asyncpg.connect(dsn)
            await conn.close()
            print("[INIT] PostgreSQL is ready")
            return
        except Exception:
            print(f"[INIT] Waiting for PostgreSQL... ({i + 1}/{maxRetries})")
            await asyncio.sleep(delay)

    raise RuntimeError("PostgreSQL not available after max retries")


def runMigrations() -> None:
    """Run Alembic migrations."""
    print("[INIT] Running database migrations...")
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )

    if result.returncode != 0:
        print(f"[ERROR] Migration failed: {result.stderr}")
        sys.exit(1)

    print("[INIT] Migrations complete")


def main():
    # Wait for PostgreSQL to be ready
    asyncio.run(waitForPostgres())

    # Run Alembic migrations
    runMigrations()

    # Start granian with the provided arguments
    # sys.argv[0] is this script, sys.argv[1:] are the granian args
    granianArgs = ["granian"] + sys.argv[1:]
    print(f"[INIT] Starting server: {' '.join(granianArgs)}")

    # Use os.execvp to replace the current process with granian
    # This ensures proper signal handling
    os.execvp("granian", granianArgs)


if __name__ == "__main__":
    main()
