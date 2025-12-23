"""
Base repository with common CRUD and batch operations.

All repositories inherit from this to get consistent, performant data access.
"""
from typing import TypeVar, Generic, List, Optional, Dict, Any, Type
from pydantic import BaseModel
import asyncpg

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    """Base repository providing common database operations.

    Uses raw asyncpg for maximum performance. All operations use parameterized
    queries to prevent SQL injection.
    """

    tableName: str
    modelClass: Type[T]
    primaryKey: str = "id"

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def getById(self, id: int) -> Optional[T]:
        """Fetch a single record by primary key."""
        row = await self.conn.fetchrow(
            f"SELECT * FROM {self.tableName} WHERE {self.primaryKey} = $1", id
        )
        return self.modelClass(**dict(row)) if row else None

    async def getByIds(self, ids: List[int]) -> List[T]:
        """Batch fetch multiple records by IDs. Prevents N+1 queries."""
        if not ids:
            return []
        rows = await self.conn.fetch(
            f"SELECT * FROM {self.tableName} WHERE {self.primaryKey} = ANY($1)", ids
        )
        return [self.modelClass(**dict(row)) for row in rows]

    async def getAll(self, limit: int = 100, offset: int = 0) -> List[T]:
        """Fetch all records with pagination."""
        rows = await self.conn.fetch(
            f"SELECT * FROM {self.tableName} ORDER BY {self.primaryKey} LIMIT $1 OFFSET $2",
            limit, offset
        )
        return [self.modelClass(**dict(row)) for row in rows]

    async def count(self) -> int:
        """Get total record count."""
        result = await self.conn.fetchval(f"SELECT COUNT(*) FROM {self.tableName}")
        return result or 0

    async def exists(self, id: int) -> bool:
        """Check if a record exists."""
        result = await self.conn.fetchval(
            f"SELECT EXISTS(SELECT 1 FROM {self.tableName} WHERE {self.primaryKey} = $1)", id
        )
        return result

    async def create(self, data: Dict[str, Any]) -> T:
        """Create a new record and return it."""
        if not data:
            raise ValueError("Cannot create record with empty data")

        columns = ", ".join(data.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(data)))
        row = await self.conn.fetchrow(
            f"INSERT INTO {self.tableName} ({columns}) VALUES ({placeholders}) RETURNING *",
            *data.values()
        )
        return self.modelClass(**dict(row))

    async def createMany(self, records: List[Dict[str, Any]]) -> List[T]:
        """Batch insert multiple records."""
        if not records:
            return []

        # All records must have the same columns
        columns = list(records[0].keys())
        columnStr = ", ".join(columns)

        # Build VALUES clause with proper parameter numbering
        valuesClauses = []
        allValues = []
        paramIdx = 1
        for record in records:
            placeholders = ", ".join(f"${paramIdx + i}" for i in range(len(columns)))
            valuesClauses.append(f"({placeholders})")
            allValues.extend(record[col] for col in columns)
            paramIdx += len(columns)

        query = f"INSERT INTO {self.tableName} ({columnStr}) VALUES {', '.join(valuesClauses)} RETURNING *"
        rows = await self.conn.fetch(query, *allValues)
        return [self.modelClass(**dict(row)) for row in rows]

    async def update(self, id: int, data: Dict[str, Any]) -> Optional[T]:
        """Update a single record by ID."""
        if not data:
            return await self.getById(id)

        setClause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(data.keys()))
        row = await self.conn.fetchrow(
            f"UPDATE {self.tableName} SET {setClause}, updated_at = NOW() "
            f"WHERE {self.primaryKey} = $1 RETURNING *",
            id, *data.values()
        )
        return self.modelClass(**dict(row)) if row else None

    async def updateBatch(self, ids: List[int], data: Dict[str, Any]) -> int:
        """Batch update multiple records. Returns number of updated rows."""
        if not ids or not data:
            return 0

        setClause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(data.keys()))
        result = await self.conn.execute(
            f"UPDATE {self.tableName} SET {setClause}, updated_at = NOW() "
            f"WHERE {self.primaryKey} = ANY($1)",
            ids, *data.values()
        )
        # Result is like "UPDATE 5"
        return int(result.split()[-1])

    async def delete(self, id: int) -> bool:
        """Delete a single record by ID. Returns True if deleted."""
        result = await self.conn.execute(
            f"DELETE FROM {self.tableName} WHERE {self.primaryKey} = $1", id
        )
        return result == "DELETE 1"

    async def deleteBatch(self, ids: List[int]) -> int:
        """Batch delete multiple records. Returns number of deleted rows."""
        if not ids:
            return 0

        result = await self.conn.execute(
            f"DELETE FROM {self.tableName} WHERE {self.primaryKey} = ANY($1)", ids
        )
        return int(result.split()[-1])

    async def findBy(self, column: str, value: Any) -> List[T]:
        """Find records by a specific column value."""
        rows = await self.conn.fetch(
            f"SELECT * FROM {self.tableName} WHERE {column} = $1", value
        )
        return [self.modelClass(**dict(row)) for row in rows]

    async def findOneBy(self, column: str, value: Any) -> Optional[T]:
        """Find a single record by a specific column value."""
        row = await self.conn.fetchrow(
            f"SELECT * FROM {self.tableName} WHERE {column} = $1 LIMIT 1", value
        )
        return self.modelClass(**dict(row)) if row else None

    async def rawQuery(self, query: str, *args) -> List[Dict[str, Any]]:
        """Execute a raw query and return results as dicts."""
        rows = await self.conn.fetch(query, *args)
        return [dict(row) for row in rows]

    async def rawExecute(self, query: str, *args) -> str:
        """Execute a raw command and return result string."""
        return await self.conn.execute(query, *args)
