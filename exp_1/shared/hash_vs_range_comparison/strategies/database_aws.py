"""
Database Connection Pool Manager for AWS RDS
Connects to 4 RDS MySQL instances
"""

import pymysql
from pymysql.cursors import DictCursor
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class DatabaseConfigAWS:
    """AWS RDS Database configuration for all shards"""
    
    # Main database (not used in AWS, but kept for compatibility)
    MAIN_DB = {
        'host': 'hash-range-shard-0.ctxymzq4yvuj.us-east-1.rds.amazonaws.com',
        'port': 3306,
        'user': 'admin',
        'password': 'YourSecurePassword123!',
        'database': 'coupon_db_0',
        'charset': 'utf8mb4'
    }
    
    # 4 shard databases on AWS RDS
    SHARD_DBS = {
        0: {
            'host': 'hash-range-shard-0.ctxymzq4yvuj.us-east-1.rds.amazonaws.com',
            'port': 3306,
            'user': 'admin',
            'password': 'YourSecurePassword123!',
            'database': 'coupon_db_0',
            'charset': 'utf8mb4'
        },
        1: {
            'host': 'hash-range-shard-1.ctxymzq4yvuj.us-east-1.rds.amazonaws.com',
            'port': 3306,
            'user': 'admin',
            'password': 'YourSecurePassword123!',
            'database': 'coupon_db_1',
            'charset': 'utf8mb4'
        },
        2: {
            'host': 'hash-range-shard-2.ctxymzq4yvuj.us-east-1.rds.amazonaws.com',
            'port': 3306,
            'user': 'admin',
            'password': 'YourSecurePassword123!',
            'database': 'coupon_db_2',
            'charset': 'utf8mb4'
        },
        3: {
            'host': 'hash-range-shard-3.ctxymzq4yvuj.us-east-1.rds.amazonaws.com',
            'port': 3306,
            'user': 'admin',
            'password': 'YourSecurePassword123!',
            'database': 'coupon_db_3',
            'charset': 'utf8mb4'
        }
    }

class ConnectionPoolAWS:
    """Connection pool manager for AWS RDS"""
    
    def __init__(self):
        self.main_conn = None
        self.shard_conns: Dict[int, pymysql.Connection] = {}
    
    def initialize(self) -> bool:
        """Initialize all connections"""
        try:
            # Connect to main database
            self.main_conn = pymysql.connect(
                **DatabaseConfigAWS.MAIN_DB,
                cursorclass=DictCursor,
                autocommit=False,
                connect_timeout=10
            )
            logger.info("✅ Connected to AWS RDS main database")
            
            # Connect to all shards
            for shard_id, config in DatabaseConfigAWS.SHARD_DBS.items():
                self.shard_conns[shard_id] = pymysql.connect(
                    **config,
                    cursorclass=DictCursor,
                    autocommit=False,
                    connect_timeout=10
                )
                logger.info(f"✅ Connected to AWS RDS shard {shard_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ AWS RDS connection failed: {e}")
            return False
    
    def get_main_connection(self) -> pymysql.Connection:
        """Get main database connection"""
        if not self.main_conn or not self.main_conn.open:
            self.main_conn = pymysql.connect(
                **DatabaseConfigAWS.MAIN_DB,
                cursorclass=DictCursor,
                connect_timeout=10
            )
        return self.main_conn
    
    def get_shard_connection(self, shard_id: int) -> pymysql.Connection:
        """Get shard connection"""
        if shard_id not in self.shard_conns or not self.shard_conns[shard_id].open:
            self.shard_conns[shard_id] = pymysql.connect(
                **DatabaseConfigAWS.SHARD_DBS[shard_id],
                cursorclass=DictCursor,
                connect_timeout=10
            )
        return self.shard_conns[shard_id]
    
    def close_all(self):
        """Close all connections"""
        if self.main_conn:
            self.main_conn.close()
        for conn in self.shard_conns.values():
            if conn:
                conn.close()
        logger.info("🔌 All AWS RDS connections closed")

# Global connection pool instance for AWS
connection_pool_aws = ConnectionPoolAWS()

