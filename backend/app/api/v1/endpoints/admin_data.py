"""
Admin database access and backup/restore.

Read-only browsing of the PostgreSQL tables, the current database connection details,
and full export/import of the database and app settings. Every endpoint requires the
system.admin permission. Table and column names are always validated against the live
schema before use, so there is no SQL injection surface in the browser.
"""

import io
import json
import os
import shutil
import tempfile
import zipfile
import asyncio
import datetime
import decimal
import uuid
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.db import get_db
from app.core.config import settings
from app.api.v1.endpoints.auth import require_admin
from app.schemas.user import UserWithPermissions

router = APIRouter()

# Categories included in the portable settings export. The full database dump carries
# everything; this is the human-portable subset of configuration.
_SETTINGS_TABLES = ["app_settings", "media_profiles", "root_folders"]


def _json_safe(value: Any) -> Any:
    """Convert a database value into something JSON serializable."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    return str(value)


async def _list_table_names(conn: asyncpg.Connection) -> List[str]:
    """All base table names in the public schema."""
    rows = await conn.fetch(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
        "ORDER BY table_name"
    )
    return [r["table_name"] for r in rows]


async def _column_names(conn: asyncpg.Connection, table: str) -> List[str]:
    """Ordered column names for a public-schema table."""
    rows = await conn.fetch(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = $1 ORDER BY ordinal_position",
        table,
    )
    return [r["column_name"] for r in rows]


def _pg_env() -> Dict[str, str]:
    """Environment for pg_dump/psql with the current password."""
    env = dict(os.environ)
    env["PGPASSWORD"] = settings.POSTGRES_PASSWORD
    return env


def _direct_conn_args() -> List[str]:
    """Shared pg_dump/psql connection flags for the direct PostgreSQL connection."""
    return [
        "-h",
        settings.POSTGRES_HOST,
        "-p",
        str(settings.POSTGRES_PORT),
        "-U",
        settings.POSTGRES_USER,
        "-d",
        settings.POSTGRES_DB,
    ]


@router.get("/database/info")
async def database_info(
    current_user: UserWithPermissions = Depends(require_admin),
):
    """
    Current database connection details, so an admin can connect with an external tool.
    The password is the live value (generated or default). Connect from this machine on
    the localhost-bound port, or from your server's address if you exposed it.
    """
    return {
        "host": settings.POSTGRES_HOST,
        "port": settings.POSTGRES_PORT,
        "database": settings.POSTGRES_DB,
        "user": settings.POSTGRES_USER,
        "password": settings.POSTGRES_PASSWORD,
        "connection_string": (
            f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
            f"@localhost:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        ),
    }


def _alembic_head_revision() -> Optional[str]:
    """The latest migration revision defined in the app, read from the alembic scripts."""
    try:
        import app as app_pkg
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        alembic_dir = os.path.join(os.path.dirname(app_pkg.__file__), "alembic")
        cfg = Config()
        cfg.set_main_option("script_location", alembic_dir)
        return ScriptDirectory.from_config(cfg).get_current_head()
    except Exception:
        return None


@router.get("/database/overview")
async def database_overview(
    current_user: UserWithPermissions = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    High level database facts: server version, on-disk size, table count, and the
    Alembic migration revision the schema is on versus the latest defined revision.
    """
    postgres_version = await conn.fetchval("SHOW server_version")
    size_bytes = await conn.fetchval("SELECT pg_database_size(current_database())")
    size_pretty = await conn.fetchval("SELECT pg_size_pretty(pg_database_size(current_database()))")
    table_count = await conn.fetchval(
        "SELECT count(*) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'r'"
    )

    current_revision = None
    try:
        current_revision = await conn.fetchval("SELECT version_num FROM alembic_version LIMIT 1")
    except Exception:
        current_revision = None

    head_revision = _alembic_head_revision()

    return {
        "postgres_version": postgres_version,
        "database_size": size_pretty,
        "database_size_bytes": size_bytes,
        "table_count": table_count,
        "alembic_current": current_revision,
        "alembic_head": head_revision,
        "up_to_date": bool(head_revision is not None and current_revision == head_revision),
    }


@router.get("/database/tables")
async def list_tables(
    current_user: UserWithPermissions = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db),
):
    """List all tables with their exact row count and on-disk size."""
    rows = await conn.fetch("""
        SELECT c.relname AS table_name,
               pg_total_relation_size(c.oid) AS size_bytes,
               pg_size_pretty(pg_total_relation_size(c.oid)) AS size_pretty
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        ORDER BY c.relname
        """)
    tables = []
    for r in rows:
        name = r["table_name"]
        # Table names come from the system catalog, quote them to build the count query.
        quoted = '"' + name.replace('"', '""') + '"'
        count = await conn.fetchval(f"SELECT COUNT(*) FROM {quoted}")
        tables.append(
            {
                "name": name,
                "row_count": count,
                "size_bytes": r["size_bytes"],
                "size_pretty": r["size_pretty"],
            }
        )
    return {"tables": tables}


@router.get("/database/tables/{table}")
async def table_rows(
    table: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    order_by: Optional[str] = None,
    order_dir: str = Query("asc", pattern="^(?i)(asc|desc)$"),
    current_user: UserWithPermissions = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Paginated rows of a single table (read-only). The table and order-by column are
    validated against the live schema and quoted, so the name cannot inject SQL.
    """
    valid_tables = await _list_table_names(conn)
    if table not in valid_tables:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")

    columns = await _column_names(conn, table)
    quoted_table = f'"{table}"'

    order_clause = ""
    if order_by:
        if order_by not in columns:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown order column")
        direction = "DESC" if order_dir.lower() == "desc" else "ASC"
        order_clause = f' ORDER BY "{order_by}" {direction}'

    total = await conn.fetchval(f"SELECT count(*) FROM {quoted_table}")
    rows = await conn.fetch(f"SELECT * FROM {quoted_table}{order_clause} LIMIT $1 OFFSET $2", limit, offset)

    return {
        "table": table,
        "columns": columns,
        "rows": [{k: _json_safe(v) for k, v in dict(r).items()} for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def _stream_process(program: str, args: List[str]):
    """Run a subprocess and yield its stdout in chunks. Raises if the program is missing."""
    try:
        process = await asyncio.create_subprocess_exec(
            program, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=_pg_env()
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"{program} is not available in this environment",
        )
    while True:
        chunk = await process.stdout.read(65536)
        if not chunk:
            break
        yield chunk
    await process.wait()


def _timestamp() -> str:
    return datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")


@router.get("/export/database")
async def export_database(
    current_user: UserWithPermissions = Depends(require_admin),
):
    """Stream a full pg_dump of the database as a downloadable .sql file."""
    args = _direct_conn_args() + ["--no-owner", "--no-acl", "--clean", "--if-exists"]
    filename = f"kinora-db-{_timestamp()}.sql"
    return StreamingResponse(
        _stream_process("pg_dump", args),
        media_type="application/sql",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _collect_settings(conn: asyncpg.Connection) -> Dict[str, Any]:
    """Read the portable settings tables into a plain dict."""
    data: Dict[str, Any] = {}
    valid = set(await _list_table_names(conn))
    for table in _SETTINGS_TABLES:
        if table not in valid:
            continue
        rows = await conn.fetch(f'SELECT * FROM "{table}"')
        data[table] = [{k: _json_safe(v) for k, v in dict(r).items()} for r in rows]
    return data


@router.get("/export/settings")
async def export_settings(
    current_user: UserWithPermissions = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Export profiles, root folders, and app settings as a downloadable JSON file."""
    payload = {
        "kind": "kinora-settings",
        "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
        "data": await _collect_settings(conn),
    }
    body = json.dumps(payload, indent=2).encode("utf-8")
    filename = f"kinora-settings-{_timestamp()}.json"
    return StreamingResponse(
        iter([body]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/full")
async def export_full(
    current_user: UserWithPermissions = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Full backup: a zip containing the database dump, the settings JSON, and a manifest.
    Built in a temp directory and streamed, then cleaned up.
    """
    settings_payload = {
        "kind": "kinora-settings",
        "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
        "data": await _collect_settings(conn),
    }
    manifest = {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
        "contents": ["database.sql", "settings.json", "manifest.json"],
    }

    tmp_dir = tempfile.mkdtemp(prefix="kinora-export-")
    dump_path = os.path.join(tmp_dir, "database.sql")
    zip_path = os.path.join(tmp_dir, "backup.zip")
    try:
        args = _direct_conn_args() + ["--no-owner", "--no-acl", "--clean", "--if-exists", "-f", dump_path]
        try:
            process = await asyncio.create_subprocess_exec(
                "pg_dump", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=_pg_env()
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="pg_dump is not available in this environment",
            )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"pg_dump failed: {stderr.decode('utf-8', 'replace')[:500]}",
            )

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(dump_path, "database.sql")
            zf.writestr("settings.json", json.dumps(settings_payload, indent=2))
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        with open(zip_path, "rb") as f:
            body = f.read()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    filename = f"kinora-backup-{_timestamp()}.zip"
    return StreamingResponse(
        iter([body]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import/database")
async def import_database(
    file: UploadFile = File(...),
    confirm: bool = Form(False),
    current_user: UserWithPermissions = Depends(require_admin),
):
    """
    Restore the database from a plain-SQL dump produced by the export. This overwrites
    live data, so confirm must be true. The dump is applied with psql.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Restore overwrites current data. Set confirm=true to proceed.",
        )

    content = await file.read()
    args = _direct_conn_args() + ["-v", "ON_ERROR_STOP=1"]
    try:
        process = await asyncio.create_subprocess_exec(
            "psql",
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_pg_env(),
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="psql is not available in this environment",
        )
    _, stderr = await process.communicate(input=content)
    if process.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restore failed: {stderr.decode('utf-8', 'replace')[:500]}",
        )
    return {"status": "restored", "bytes": len(content)}


class SettingsImportResult(BaseModel):
    imported: Dict[str, int]


@router.post("/import/settings", response_model=SettingsImportResult)
async def import_settings(
    file: UploadFile = File(...),
    confirm: bool = Form(False),
    current_user: UserWithPermissions = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Import a settings JSON produced by the export. Rows are upserted by primary key.
    Overwrites matching settings, so confirm must be true.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Import overwrites matching settings. Set confirm=true to proceed.",
        )

    try:
        payload = json.loads(await file.read())
    except json.JSONDecodeError, UnicodeDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON file")

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unrecognized settings file")

    valid_tables = set(await _list_table_names(conn))
    imported: Dict[str, int] = {}

    async with conn.transaction():
        for table, rows in data.items():
            if table not in _SETTINGS_TABLES or table not in valid_tables or not isinstance(rows, list):
                continue
            columns = await _column_names(conn, table)
            pkeys = await conn.fetch(
                """
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = $1::regclass AND i.indisprimary
                """,
                f'"{table}"',
            )
            pk_cols = [r["attname"] for r in pkeys]
            if not pk_cols:
                continue

            count = 0
            for row in rows:
                if not isinstance(row, dict):
                    continue
                cols = [c for c in columns if c in row]
                if not cols:
                    continue
                placeholders = ", ".join(f"${i + 1}" for i in range(len(cols)))
                col_list = ", ".join(f'"{c}"' for c in cols)
                updates = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c not in pk_cols)
                conflict = ", ".join(f'"{c}"' for c in pk_cols)
                set_clause = f" DO UPDATE SET {updates}" if updates else " DO NOTHING"
                sql = (
                    f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) '
                    f"ON CONFLICT ({conflict}){set_clause}"
                )
                await conn.execute(sql, *[row[c] for c in cols])
                count += 1
            imported[table] = count

    return SettingsImportResult(imported=imported)
