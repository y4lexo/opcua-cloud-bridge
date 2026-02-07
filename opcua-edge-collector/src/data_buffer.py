"""Local data buffer for OPC UA Edge Gateway resilience layer"""

import asyncio
import logging
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import aiosqlite
from contextlib import asynccontextmanager

# Add parent directory to path for common models
import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "common"))

from data_models import TelemetryPoint

logger = logging.getLogger(__name__)


class DataBuffer:
    """SQLite-based local buffer for telemetry data and analytics results"""
    
    def __init__(self, db_path: str = "data_buffer.db", max_size_mb: int = 100):
        self.db_path = db_path
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.connection_pool = None
        self._lock = asyncio.Lock()
        
    async def initialize(self):
        """Initialize database schema and connection pool"""
        await self._create_schema()
        logger.info(f"Data buffer initialized: {self.db_path}")
    
    async def _create_schema(self):
        """Create database tables for telemetry and analytics data"""
        async with aiosqlite.connect(self.db_path) as db:
            # Telemetry data table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    enterprise TEXT NOT NULL,
                    site TEXT NOT NULL,
                    area TEXT NOT NULL,
                    line TEXT NOT NULL,
                    machine TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    value TEXT NOT NULL,
                    unit TEXT,
                    quality TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT FALSE,
                    batch_id TEXT
                )
            """)
            
            # Analytics results table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    asset_name TEXT NOT NULL,
                    analytics_type TEXT NOT NULL,
                    analytics_data TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT FALSE,
                    batch_id TEXT
                )
            """)
            
            # Buffer metadata table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS buffer_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for performance
            await db.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry(timestamp)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_processed ON telemetry(processed)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_batch ON telemetry(batch_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_analytics_timestamp ON analytics(timestamp)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_analytics_processed ON analytics(processed)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_analytics_batch ON analytics(batch_id)")
            
            # Initialize metadata
            await db.execute("""
                INSERT OR IGNORE INTO buffer_metadata (key, value) 
                VALUES ('total_telemetry_points', '0'), ('total_analytics_records', '0')
            """)
            
            await db.commit()
    
    async def save_telemetry_point(self, point: TelemetryPoint, batch_id: Optional[str] = None) -> bool:
        """Save a single telemetry point to the buffer"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO telemetry 
                    (timestamp, enterprise, site, area, line, machine, tag, value, unit, quality, batch_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    point.timestamp.isoformat(),
                    point.enterprise,
                    point.site,
                    point.area,
                    point.line,
                    point.machine,
                    point.tag,
                    json.dumps(point.value) if not isinstance(point.value, str) else point.value,
                    point.unit,
                    point.quality.value,
                    batch_id
                ))
                
                await db.execute("""
                    UPDATE buffer_metadata 
                    SET value = value + 1, updated_at = CURRENT_TIMESTAMP 
                    WHERE key = 'total_telemetry_points'
                """)
                
                await db.commit()
                
                # Check buffer size
                await self._check_buffer_size(db)
                
                return True
                
        except Exception as e:
            logger.error(f"Error saving telemetry point: {e}")
            return False
    
    async def save_analytics_result(self, analytics_data: Dict[str, Any], batch_id: Optional[str] = None) -> bool:
        """Save analytics results to the buffer"""
        try:
            asset_name = analytics_data.get('asset_name', 'unknown')
            timestamp = analytics_data.get('timestamp', datetime.utcnow().isoformat())
            analytics_json = json.dumps(analytics_data.get('analytics', {}))
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO analytics 
                    (timestamp, asset_name, analytics_type, analytics_data, batch_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    asset_name,
                    ','.join(analytics_data.get('analytics', {}).keys()),
                    analytics_json,
                    batch_id
                ))
                
                await db.execute("""
                    UPDATE buffer_metadata 
                    SET value = value + 1, updated_at = CURRENT_TIMESTAMP 
                    WHERE key = 'total_analytics_records'
                """)
                
                await db.commit()
                
                # Check buffer size
                await self._check_buffer_size(db)
                
                return True
                
        except Exception as e:
            logger.error(f"Error saving analytics result: {e}")
            return False
    
    async def save_batch(self, telemetry_points: List[TelemetryPoint], 
                        analytics_results: List[Dict[str, Any]], 
                        batch_id: str) -> bool:
        """Save a batch of telemetry points and analytics results"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Save telemetry points
                for point in telemetry_points:
                    await db.execute("""
                        INSERT INTO telemetry 
                        (timestamp, enterprise, site, area, line, machine, tag, value, unit, quality, batch_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        point.timestamp.isoformat(),
                        point.enterprise,
                        point.site,
                        point.area,
                        point.line,
                        point.machine,
                        point.tag,
                        json.dumps(point.value) if not isinstance(point.value, str) else point.value,
                        point.unit,
                        point.quality.value,
                        batch_id
                    ))
                
                # Save analytics results
                for analytics_data in analytics_results:
                    asset_name = analytics_data.get('asset_name', 'unknown')
                    timestamp = analytics_data.get('timestamp', datetime.utcnow().isoformat())
                    analytics_json = json.dumps(analytics_data.get('analytics', {}))
                    
                    await db.execute("""
                        INSERT INTO analytics 
                        (timestamp, asset_name, analytics_type, analytics_data, batch_id)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        timestamp,
                        asset_name,
                        ','.join(analytics_data.get('analytics', {}).keys()),
                        analytics_json,
                        batch_id
                    ))
                
                # Update metadata
                await db.execute("""
                    UPDATE buffer_metadata 
                    SET value = value + ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE key = 'total_telemetry_points'
                """, (len(telemetry_points),))
                
                await db.execute("""
                    UPDATE buffer_metadata 
                    SET value = value + ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE key = 'total_analytics_records'
                """, (len(analytics_results),))
                
                await db.commit()
                
                # Check buffer size
                await self._check_buffer_size(db)
                
                logger.info(f"Saved batch {batch_id}: {len(telemetry_points)} telemetry points, {len(analytics_results)} analytics results")
                return True
                
        except Exception as e:
            logger.error(f"Error saving batch {batch_id}: {e}")
            return False
    
    async def get_telemetry_batch(self, batch_size: int = 100, 
                                include_processed: bool = False) -> List[Dict[str, Any]]:
        """Get a batch of telemetry points from the buffer"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if include_processed:
                    query = """
                        SELECT * FROM telemetry 
                        ORDER BY created_at ASC 
                        LIMIT ?
                    """
                else:
                    query = """
                        SELECT * FROM telemetry 
                        WHERE processed = FALSE 
                        ORDER BY created_at ASC 
                        LIMIT ?
                    """
                
                cursor = await db.execute(query, (batch_size,))
                rows = await cursor.fetchall()
                
                # Convert rows to dictionaries
                columns = [description[0] for description in cursor.description]
                telemetry_batch = []
                
                for row in rows:
                    telemetry_dict = dict(zip(columns, row))
                    # Parse JSON value if needed
                    try:
                        telemetry_dict['value'] = json.loads(telemetry_dict['value'])
                    except (json.JSONDecodeError, TypeError):
                        pass  # Keep as string if not valid JSON
                    telemetry_batch.append(telemetry_dict)
                
                return telemetry_batch
                
        except Exception as e:
            logger.error(f"Error getting telemetry batch: {e}")
            return []
    
    async def get_analytics_batch(self, batch_size: int = 100, 
                                 include_processed: bool = False) -> List[Dict[str, Any]]:
        """Get a batch of analytics results from the buffer"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if include_processed:
                    query = """
                        SELECT * FROM analytics 
                        ORDER BY created_at ASC 
                        LIMIT ?
                    """
                else:
                    query = """
                        SELECT * FROM analytics 
                        WHERE processed = FALSE 
                        ORDER BY created_at ASC 
                        LIMIT ?
                    """
                
                cursor = await db.execute(query, (batch_size,))
                rows = await cursor.fetchall()
                
                # Convert rows to dictionaries
                columns = [description[0] for description in cursor.description]
                analytics_batch = []
                
                for row in rows:
                    analytics_dict = dict(zip(columns, row))
                    # Parse JSON analytics data
                    try:
                        analytics_dict['analytics_data'] = json.loads(analytics_dict['analytics_data'])
                    except (json.JSONDecodeError, TypeError):
                        pass  # Keep as string if not valid JSON
                    analytics_batch.append(analytics_dict)
                
                return analytics_batch
                
        except Exception as e:
            logger.error(f"Error getting analytics batch: {e}")
            return []
    
    async def get_batch_by_id(self, batch_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """Get telemetry and analytics data by batch ID"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Get telemetry data
                cursor = await db.execute("""
                    SELECT * FROM telemetry WHERE batch_id = ? ORDER BY created_at ASC
                """, (batch_id,))
                telemetry_rows = await cursor.fetchall()
                telemetry_columns = [description[0] for description in cursor.description]
                
                telemetry_data = []
                for row in telemetry_rows:
                    telemetry_dict = dict(zip(telemetry_columns, row))
                    try:
                        telemetry_dict['value'] = json.loads(telemetry_dict['value'])
                    except (json.JSONDecodeError, TypeError):
                        pass
                    telemetry_data.append(telemetry_dict)
                
                # Get analytics data
                cursor = await db.execute("""
                    SELECT * FROM analytics WHERE batch_id = ? ORDER BY created_at ASC
                """, (batch_id,))
                analytics_rows = await cursor.fetchall()
                analytics_columns = [description[0] for description in cursor.description]
                
                analytics_data = []
                for row in analytics_rows:
                    analytics_dict = dict(zip(analytics_columns, row))
                    try:
                        analytics_dict['analytics_data'] = json.loads(analytics_dict['analytics_data'])
                    except (json.JSONDecodeError, TypeError):
                        pass
                    analytics_data.append(analytics_dict)
                
                return {
                    'telemetry': telemetry_data,
                    'analytics': analytics_data
                }
                
        except Exception as e:
            logger.error(f"Error getting batch {batch_id}: {e}")
            return {'telemetry': [], 'analytics': []}
    
    async def mark_batch_processed(self, batch_id: str) -> bool:
        """Mark a batch as processed"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE telemetry SET processed = TRUE WHERE batch_id = ?
                """, (batch_id,))
                
                await db.execute("""
                    UPDATE analytics SET processed = TRUE WHERE batch_id = ?
                """, (batch_id,))
                
                await db.commit()
                logger.info(f"Marked batch {batch_id} as processed")
                return True
                
        except Exception as e:
            logger.error(f"Error marking batch {batch_id} as processed: {e}")
            return False
    
    async def delete_batch(self, batch_id: str) -> bool:
        """Delete a batch from the buffer"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Get counts before deletion
                cursor = await db.execute("SELECT COUNT(*) FROM telemetry WHERE batch_id = ?", (batch_id,))
                telemetry_count = (await cursor.fetchone())[0]
                
                cursor = await db.execute("SELECT COUNT(*) FROM analytics WHERE batch_id = ?", (batch_id,))
                analytics_count = (await cursor.fetchone())[0]
                
                # Delete telemetry data
                await db.execute("DELETE FROM telemetry WHERE batch_id = ?", (batch_id,))
                
                # Delete analytics data
                await db.execute("DELETE FROM analytics WHERE batch_id = ?", (batch_id,))
                
                # Update metadata
                await db.execute("""
                    UPDATE buffer_metadata 
                    SET value = value - ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE key = 'total_telemetry_points'
                """, (telemetry_count,))
                
                await db.execute("""
                    UPDATE buffer_metadata 
                    SET value = value - ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE key = 'total_analytics_records'
                """, (analytics_count,))
                
                await db.commit()
                logger.info(f"Deleted batch {batch_id}: {telemetry_count} telemetry points, {analytics_count} analytics records")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting batch {batch_id}: {e}")
            return False
    
    async def delete_processed_batches(self, older_than_hours: int = 24) -> int:
        """Delete processed batches older than specified hours"""
        try:
            cutoff_time = (datetime.utcnow() - timedelta(hours=older_than_hours)).isoformat()
            
            async with aiosqlite.connect(self.db_path) as db:
                # Get batch IDs to delete
                cursor = await db.execute("""
                    SELECT DISTINCT batch_id FROM telemetry 
                    WHERE processed = TRUE AND created_at < ? AND batch_id IS NOT NULL
                """, (cutoff_time,))
                
                batch_ids = [row[0] for row in await cursor.fetchall()]
                
                deleted_count = 0
                for batch_id in batch_ids:
                    if await self.delete_batch(batch_id):
                        deleted_count += 1
                
                logger.info(f"Deleted {deleted_count} processed batches older than {older_than_hours} hours")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Error deleting processed batches: {e}")
            return 0
    
    async def _check_buffer_size(self, db: aiosqlite.Connection):
        """Check buffer size and clean up if necessary"""
        try:
            # Get current database size
            db_size = Path(self.db_path).stat().st_size
            
            if db_size > self.max_size_bytes:
                logger.warning(f"Buffer size ({db_size} bytes) exceeds limit ({self.max_size_bytes} bytes)")
                
                # Delete oldest processed batches
                await self.delete_processed_batches(older_than_hours=1)
                
                # If still too large, delete oldest unprocessed telemetry
                new_size = Path(self.db_path).stat().st_size
                if new_size > self.max_size_bytes:
                    await db.execute("""
                        DELETE FROM telemetry 
                        WHERE processed = FALSE 
                        AND id IN (
                            SELECT id FROM telemetry 
                            WHERE processed = FALSE 
                            ORDER BY created_at ASC 
                            LIMIT 1000
                        )
                    """)
                    await db.commit()
                    logger.warning("Deleted oldest unprocessed telemetry to free space")
                
        except Exception as e:
            logger.error(f"Error checking buffer size: {e}")
    
    async def get_buffer_status(self) -> Dict[str, Any]:
        """Get current buffer status and statistics"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Get telemetry statistics
                cursor = await db.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN processed = FALSE THEN 1 ELSE 0 END) as unprocessed,
                        MIN(created_at) as oldest,
                        MAX(created_at) as newest
                    FROM telemetry
                """)
                telemetry_stats = dict(zip([desc[0] for desc in cursor.description], await cursor.fetchone()))
                
                # Get analytics statistics
                cursor = await db.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN processed = FALSE THEN 1 ELSE 0 END) as unprocessed,
                        MIN(created_at) as oldest,
                        MAX(created_at) as newest
                    FROM analytics
                """)
                analytics_stats = dict(zip([desc[0] for desc in cursor.description], await cursor.fetchone()))
                
                # Get database size
                db_size = Path(self.db_path).stat().st_size
                
                return {
                    'database_path': self.db_path,
                    'database_size_bytes': db_size,
                    'database_size_mb': round(db_size / (1024 * 1024), 2),
                    'max_size_mb': round(self.max_size_bytes / (1024 * 1024), 2),
                    'telemetry': telemetry_stats,
                    'analytics': analytics_stats
                }
                
        except Exception as e:
            logger.error(f"Error getting buffer status: {e}")
            return {}
    
    async def close(self):
        """Close database connections"""
        # aiosqlite manages connections automatically, but we can add cleanup here if needed
        logger.info("Data buffer closed")


@asynccontextmanager
async def get_data_buffer(db_path: str = "data_buffer.db", max_size_mb: int = 100):
    """Context manager for data buffer"""
    buffer = DataBuffer(db_path, max_size_mb)
    await buffer.initialize()
    try:
        yield buffer
    finally:
        await buffer.close()
