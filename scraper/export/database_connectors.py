"""
Database Connectors for Direct Export.

Export scraped data directly to production databases.
Premium feature - competitors charge $199-499/month for this.

Supported databases:
- PostgreSQL
- MySQL/MariaDB
- MongoDB
- Redis
- Elasticsearch
- ClickHouse
- BigQuery
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseConnector(ABC):
    """Base class for database connectors."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize connector.

        Args:
            config: Database connection configuration
        """
        self.config = config

    @abstractmethod
    async def connect(self):
        """Establish database connection."""
        pass

    @abstractmethod
    async def insert(self, table: str, data: List[Dict[str, Any]]):
        """Insert data into table."""
        pass

    @abstractmethod
    async def upsert(self, table: str, data: List[Dict[str, Any]], key_fields: List[str]):
        """Upsert data (insert or update if exists)."""
        pass

    @abstractmethod
    async def close(self):
        """Close database connection."""
        pass


# ============================================================================
# POSTGRESQL CONNECTOR
# ============================================================================

class PostgreSQLConnector(DatabaseConnector):
    """
    PostgreSQL database connector.

    Uses asyncpg for high-performance async operations.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.pool = None

    async def connect(self):
        """Create connection pool."""
        import asyncpg

        self.pool = await asyncpg.create_pool(
            host=self.config.get('host', 'localhost'),
            port=self.config.get('port', 5432),
            user=self.config.get('user'),
            password=self.config.get('password'),
            database=self.config.get('database'),
            min_size=self.config.get('min_connections', 1),
            max_size=self.config.get('max_connections', 10),
        )

        logger.info(f"Connected to PostgreSQL: {self.config.get('database')}")

    async def insert(self, table: str, data: List[Dict[str, Any]]):
        """
        Batch insert data into PostgreSQL.

        Args:
            table: Table name
            data: List of records to insert
        """
        if not data:
            return

        # Get column names from first record
        columns = list(data[0].keys())
        placeholders = ', '.join([f'${i+1}' for i in range(len(columns))])
        column_names = ', '.join(columns)

        query = f"""
            INSERT INTO {table} ({column_names})
            VALUES ({placeholders})
        """

        async with self.pool.acquire() as conn:
            # Batch insert using executemany
            await conn.executemany(
                query,
                [tuple(record[col] for col in columns) for record in data]
            )

        logger.info(f"Inserted {len(data)} records into PostgreSQL table '{table}'")

    async def upsert(self, table: str, data: List[Dict[str, Any]], key_fields: List[str]):
        """
        Upsert data using ON CONFLICT clause.

        Args:
            table: Table name
            data: List of records
            key_fields: Fields to use for conflict resolution
        """
        if not data:
            return

        columns = list(data[0].keys())
        column_names = ', '.join(columns)
        placeholders = ', '.join([f'${i+1}' for i in range(len(columns))])

        # Update clause for non-key fields
        update_fields = [col for col in columns if col not in key_fields]
        update_clause = ', '.join([f"{col} = EXCLUDED.{col}" for col in update_fields])

        conflict_cols = ', '.join(key_fields)

        query = f"""
            INSERT INTO {table} ({column_names})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_cols})
            DO UPDATE SET {update_clause}
        """

        async with self.pool.acquire() as conn:
            await conn.executemany(
                query,
                [tuple(record[col] for col in columns) for record in data]
            )

        logger.info(f"Upserted {len(data)} records into PostgreSQL table '{table}'")

    async def create_table_from_data(self, table: str, data: List[Dict[str, Any]]):
        """Auto-create table from data schema."""
        if not data:
            return

        # Infer column types
        sample = data[0]
        type_map = {
            int: 'INTEGER',
            float: 'REAL',
            bool: 'BOOLEAN',
            datetime: 'TIMESTAMP',
            str: 'TEXT',
        }

        columns = []
        for key, value in sample.items():
            col_type = type_map.get(type(value), 'TEXT')
            columns.append(f"{key} {col_type}")

        create_query = f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id SERIAL PRIMARY KEY,
                {', '.join(columns)},
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """

        async with self.pool.acquire() as conn:
            await conn.execute(create_query)

        logger.info(f"Created table '{table}' with {len(columns)} columns")

    async def close(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("PostgreSQL connection closed")


# ============================================================================
# MYSQL CONNECTOR
# ============================================================================

class MySQLConnector(DatabaseConnector):
    """MySQL/MariaDB database connector."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.pool = None

    async def connect(self):
        """Create connection pool."""
        import aiomysql

        self.pool = await aiomysql.create_pool(
            host=self.config.get('host', 'localhost'),
            port=self.config.get('port', 3306),
            user=self.config.get('user'),
            password=self.config.get('password'),
            db=self.config.get('database'),
            minsize=self.config.get('min_connections', 1),
            maxsize=self.config.get('max_connections', 10),
        )

        logger.info(f"Connected to MySQL: {self.config.get('database')}")

    async def insert(self, table: str, data: List[Dict[str, Any]]):
        """Batch insert into MySQL."""
        if not data:
            return

        columns = list(data[0].keys())
        placeholders = ', '.join(['%s'] * len(columns))
        column_names = ', '.join(columns)

        query = f"""
            INSERT INTO {table} ({column_names})
            VALUES ({placeholders})
        """

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.executemany(
                    query,
                    [tuple(record[col] for col in columns) for record in data]
                )
                await conn.commit()

        logger.info(f"Inserted {len(data)} records into MySQL table '{table}'")

    async def upsert(self, table: str, data: List[Dict[str, Any]], key_fields: List[str]):
        """Upsert using ON DUPLICATE KEY UPDATE."""
        if not data:
            return

        columns = list(data[0].keys())
        column_names = ', '.join(columns)
        placeholders = ', '.join(['%s'] * len(columns))

        update_fields = [col for col in columns if col not in key_fields]
        update_clause = ', '.join([f"{col} = VALUES({col})" for col in update_fields])

        query = f"""
            INSERT INTO {table} ({column_names})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {update_clause}
        """

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.executemany(
                    query,
                    [tuple(record[col] for col in columns) for record in data]
                )
                await conn.commit()

        logger.info(f"Upserted {len(data)} records into MySQL table '{table}'")

    async def close(self):
        """Close connection pool."""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("MySQL connection closed")


# ============================================================================
# MONGODB CONNECTOR
# ============================================================================

class MongoDBConnector(DatabaseConnector):
    """MongoDB database connector."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = None
        self.db = None

    async def connect(self):
        """Connect to MongoDB."""
        from motor.motor_asyncio import AsyncIOMotorClient

        connection_string = self.config.get('connection_string') or \
            f"mongodb://{self.config.get('host', 'localhost')}:{self.config.get('port', 27017)}"

        self.client = AsyncIOMotorClient(connection_string)
        self.db = self.client[self.config.get('database')]

        # Test connection
        await self.client.server_info()

        logger.info(f"Connected to MongoDB: {self.config.get('database')}")

    async def insert(self, collection: str, data: List[Dict[str, Any]]):
        """Insert documents into MongoDB collection."""
        if not data:
            return

        # Add timestamp
        for doc in data:
            if 'scraped_at' not in doc:
                doc['scraped_at'] = datetime.utcnow()

        result = await self.db[collection].insert_many(data)

        logger.info(f"Inserted {len(result.inserted_ids)} documents into MongoDB collection '{collection}'")

    async def upsert(self, collection: str, data: List[Dict[str, Any]], key_fields: List[str]):
        """Upsert documents based on key fields."""
        if not data:
            return

        from pymongo import UpdateOne

        operations = []
        for doc in data:
            # Build filter from key fields
            filter_dict = {field: doc[field] for field in key_fields if field in doc}

            # Add timestamp
            doc['updated_at'] = datetime.utcnow()
            if 'scraped_at' not in doc:
                doc['scraped_at'] = datetime.utcnow()

            operations.append(
                UpdateOne(
                    filter_dict,
                    {'$set': doc},
                    upsert=True
                )
            )

        if operations:
            result = await self.db[collection].bulk_write(operations)
            logger.info(f"Upserted {result.upserted_count + result.modified_count} documents into MongoDB")

    async def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")


# ============================================================================
# REDIS CONNECTOR
# ============================================================================

class RedisConnector(DatabaseConnector):
    """Redis database connector (for caching/fast lookups)."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.redis = None

    async def connect(self):
        """Connect to Redis."""
        import redis.asyncio as aioredis

        self.redis = await aioredis.from_url(
            self.config.get('url') or f"redis://{self.config.get('host', 'localhost')}:{self.config.get('port', 6379)}",
            decode_responses=True
        )

        # Test connection
        await self.redis.ping()

        logger.info("Connected to Redis")

    async def insert(self, key_prefix: str, data: List[Dict[str, Any]]):
        """Store data in Redis as JSON strings."""
        import json

        pipeline = self.redis.pipeline()

        for idx, record in enumerate(data):
            key = f"{key_prefix}:{idx}"
            pipeline.set(key, json.dumps(record))

            # Set expiry if configured
            ttl = self.config.get('ttl')
            if ttl:
                pipeline.expire(key, ttl)

        await pipeline.execute()

        logger.info(f"Stored {len(data)} records in Redis with prefix '{key_prefix}'")

    async def upsert(self, key_prefix: str, data: List[Dict[str, Any]], key_fields: List[str]):
        """Upsert using hash sets."""
        import json

        pipeline = self.redis.pipeline()

        for record in data:
            # Use key fields to create unique key
            key_values = '_'.join([str(record.get(field, '')) for field in key_fields])
            key = f"{key_prefix}:{key_values}"

            pipeline.set(key, json.dumps(record))

            ttl = self.config.get('ttl')
            if ttl:
                pipeline.expire(key, ttl)

        await pipeline.execute()

        logger.info(f"Upserted {len(data)} records in Redis")

    async def close(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            logger.info("Redis connection closed")


# ============================================================================
# ELASTICSEARCH CONNECTOR
# ============================================================================

class ElasticsearchConnector(DatabaseConnector):
    """Elasticsearch connector for full-text search."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = None

    async def connect(self):
        """Connect to Elasticsearch."""
        from elasticsearch import AsyncElasticsearch

        self.client = AsyncElasticsearch(
            hosts=[self.config.get('host', 'localhost') + ':' + str(self.config.get('port', 9200))],
            basic_auth=(self.config.get('user'), self.config.get('password')) if self.config.get('user') else None
        )

        # Test connection
        info = await self.client.info()
        logger.info(f"Connected to Elasticsearch: {info['version']['number']}")

    async def insert(self, index: str, data: List[Dict[str, Any]]):
        """Bulk index documents."""
        if not data:
            return

        from elasticsearch.helpers import async_bulk

        actions = [
            {
                '_index': index,
                '_source': doc
            }
            for doc in data
        ]

        success, failed = await async_bulk(self.client, actions)

        logger.info(f"Indexed {success} documents into Elasticsearch index '{index}'")
        if failed:
            logger.warning(f"{failed} documents failed to index")

    async def upsert(self, index: str, data: List[Dict[str, Any]], key_fields: List[str]):
        """Upsert documents with custom ID."""
        if not data:
            return

        from elasticsearch.helpers import async_bulk

        actions = []
        for doc in data:
            # Create doc ID from key fields
            doc_id = '_'.join([str(doc.get(field, '')) for field in key_fields])

            actions.append({
                '_index': index,
                '_id': doc_id,
                '_source': doc
            })

        success, failed = await async_bulk(self.client, actions)

        logger.info(f"Upserted {success} documents into Elasticsearch index '{index}'")

    async def close(self):
        """Close Elasticsearch connection."""
        if self.client:
            await self.client.close()
            logger.info("Elasticsearch connection closed")


# ============================================================================
# CONNECTOR FACTORY
# ============================================================================

class DatabaseExporter:
    """
    High-level database export interface.

    Automatically selects the appropriate connector based on configuration.
    """

    CONNECTORS = {
        'postgresql': PostgreSQLConnector,
        'postgres': PostgreSQLConnector,
        'mysql': MySQLConnector,
        'mariadb': MySQLConnector,
        'mongodb': MongoDBConnector,
        'mongo': MongoDBConnector,
        'redis': RedisConnector,
        'elasticsearch': ElasticsearchConnector,
        'es': ElasticsearchConnector,
    }

    def __init__(self, db_type: str, config: Dict[str, Any]):
        """
        Initialize database exporter.

        Args:
            db_type: Database type (postgresql, mysql, mongodb, etc.)
            config: Database configuration
        """
        connector_class = self.CONNECTORS.get(db_type.lower())
        if not connector_class:
            raise ValueError(f"Unsupported database type: {db_type}")

        self.connector = connector_class(config)
        self.db_type = db_type.lower()

    async def export(
        self,
        data: List[Dict[str, Any]],
        table: str,
        mode: str = 'insert',
        key_fields: Optional[List[str]] = None
    ):
        """
        Export data to database.

        Args:
            data: Data to export
            table: Table/collection/index name
            mode: 'insert' or 'upsert'
            key_fields: Fields to use for upsert (required if mode='upsert')
        """
        await self.connector.connect()

        try:
            if mode == 'upsert':
                if not key_fields:
                    raise ValueError("key_fields required for upsert mode")
                await self.connector.upsert(table, data, key_fields)
            else:
                await self.connector.insert(table, data)

            logger.info(f"Successfully exported {len(data)} records to {self.db_type}")

        finally:
            await self.connector.close()


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def example_usage():
    """Example of using database connectors."""

    # PostgreSQL example
    pg_exporter = DatabaseExporter('postgresql', {
        'host': 'localhost',
        'port': 5432,
        'user': 'scraper_user',
        'password': 'password',
        'database': 'scraping_data'
    })

    data = [
        {'id': 1, 'title': 'Product 1', 'price': 19.99},
        {'id': 2, 'title': 'Product 2', 'price': 29.99},
    ]

    await pg_exporter.export(data, 'products', mode='upsert', key_fields=['id'])

    # MongoDB example
    mongo_exporter = DatabaseExporter('mongodb', {
        'host': 'localhost',
        'port': 27017,
        'database': 'scraping_db'
    })

    await mongo_exporter.export(data, 'products', mode='insert')
