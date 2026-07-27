"""
Age-based backoff for the automated searches.

Every searchable media table carries last_search_at and search_attempts. An item
becomes eligible again after 2^attempts hours (capped at one week), so items that
keep coming up empty consume less and less indexer budget while never being
abandoned. Items released within the last 30 days stay on a fast 4-hour retry
because that is when a release is most likely to appear.

The RSS monitor matches every feed cycle with no backoff, so a release appearing
after any backoff window is still picked up within minutes of being uploaded.
"""

# Hard ceiling on the wait between attempts, in hours (one week).
MAX_BACKOFF_HOURS = 168

# Retry interval for recently released items, in hours.
RECENT_RELEASE_RETRY_HOURS = 4

# Attempt count where the exponential stops growing (2^8 = 256, above the ceiling).
MAX_COUNTED_ATTEMPTS = 8


def eligibilityClause(alias: str, release_date_column: str | None = None) -> str:
    """
    SQL condition selecting rows due for another search. release_date_column
    enables the fast retry window for recent releases and is skipped for tables
    without a date column (anime stores only a season year).
    """
    if release_date_column:
        hours = f"""
            CASE
                WHEN {alias}.{release_date_column} IS NOT NULL
                     AND {alias}.{release_date_column} > NOW() - INTERVAL '30 days'
                THEN {RECENT_RELEASE_RETRY_HOURS}
                ELSE LEAST(POWER(2, LEAST({alias}.search_attempts, {MAX_COUNTED_ATTEMPTS}))::int, {MAX_BACKOFF_HOURS})
            END
        """
    else:
        hours = f"LEAST(POWER(2, LEAST({alias}.search_attempts, {MAX_COUNTED_ATTEMPTS}))::int, {MAX_BACKOFF_HOURS})"

    return f"""(
        {alias}.last_search_at IS NULL
        OR {alias}.last_search_at < NOW() - (({hours}) * INTERVAL '1 hour')
    )"""


async def recordSearchAttempt(conn, table: str, media_id: int, found: bool) -> None:
    """
    Stamp an item after a search. A successful search resets the attempt counter,
    an empty one advances the backoff. Best effort, never raises.
    """
    try:
        await conn.execute(
            f"""
            UPDATE {table}
            SET last_search_at = NOW(),
                search_attempts = CASE WHEN $2 THEN 0 ELSE search_attempts + 1 END
            WHERE id = $1
            """,
            media_id,
            found,
        )
    except Exception as e:
        print(f"Failed to record search attempt for {table} {media_id}: {e}")
