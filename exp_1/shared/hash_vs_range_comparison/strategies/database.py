"""
Database Connection Pool Manager for Hash Sharding
Manages connections to 4 MySQL shard instances
"""

import pymysql
from pymysql.cursors import DictCursor
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class DatabaseConfig:
    """Database configuration for all shards"""
    
    # Main database (for users, rooms, coupons metadata)
    MAIN_DB = {
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': 'password',
        'database': 'coupon_system',
        'charset': 'utf8mb4'
    }
    
    # 4 shard databases (for coupon_results)
    SHARD_DBS = {
        0: {
            'host': 'localhost',
            'port': 3307,
            'user': 'root',
            'password': 'password',
            'database': 'coupon_db_0',
            'charset': 'utf8mb4'
        },
        1: {
            'host': 'localhost',
            'port': 3308,
            'user': 'root',
            'password': 'password',
            'database': 'coupon_db_1',
            'charset': 'utf8mb4'
        },
        2: {
            'host': 'localhost',
            'port': 3309,
            'user': 'root',
            'password': 'password',
            'database': 'coupon_db_2',
            'charset': 'utf8mb4'
        },
        3: {
            'host': 'localhost',
            'port': 3310,
            'user': 'root',
            'password': 'password',
            'database': 'coupon_db_3',
            'charset': 'utf8mb4'
        }
    }

class ConnectionPool:
    """Connection pool manager"""
    
    def __init__(self):
        self.main_conn = None
        self.shard_conns: Dict[int, pymysql.Connection] = {}
    
    def initialize(self) -> bool:
        """Initialize all connections"""
        try:
            # Connect to main database
            self.main_conn = pymysql.connect(
                **DatabaseConfig.MAIN_DB,
                cursorclass=DictCursor,
                autocommit=False
            )
            logger.info("Connected to main database")
            
            # Connect to all shards
            for shard_id, config in DatabaseConfig.SHARD_DBS.items():
                self.shard_conns[shard_id] = pymysql.connect(
                    **config,
                    cursorclass=DictCursor,
                    autocommit=False
                )
                logger.info(f"Connected to shard {shard_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def get_main_connection(self) -> pymysql.Connection:
        """Get main database connection"""
        if not self.main_conn or not self.main_conn.open:
            self.main_conn = pymysql.connect(
                **DatabaseConfig.MAIN_DB,
                cursorclass=DictCursor
            )
        return self.main_conn
    
    def get_shard_connection(self, shard_id: int) -> pymysql.Connection:
        """Get shard connection"""
        if shard_id not in self.shard_conns or not self.shard_conns[shard_id].open:
            self.shard_conns[shard_id] = pymysql.connect(
                **DatabaseConfig.SHARD_DBS[shard_id],
                cursorclass=DictCursor
            )
        return self.shard_conns[shard_id]
    
    def close_all(self):
        """Close all connections"""
        if self.main_conn:
            self.main_conn.close()
        for conn in self.shard_conns.values():
            if conn:
                conn.close()
        logger.info("🔌 All connections closed")

# Global connection pool instance
connection_pool = ConnectionPool()