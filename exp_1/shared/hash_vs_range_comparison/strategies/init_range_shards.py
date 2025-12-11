"""
Initialize Range Sharding - Create tables in all 4 shards
"""

from database import DatabaseConfig
import pymysql
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_coupon_results_table(conn):
    """Create coupon_results table"""
    sql = """
    CREATE TABLE IF NOT EXISTS coupon_results (
        result_id BIGINT PRIMARY KEY AUTO_INCREMENT,
        user_id BIGINT NOT NULL COMMENT 'User ID',
        coupon_id BIGINT NOT NULL COMMENT 'Coupon ID',
        room_id BIGINT NOT NULL COMMENT 'Live room ID',
        grab_status TINYINT NOT NULL COMMENT '0-Failed 1-Success',
        fail_reason VARCHAR(50) COMMENT 'Failure reason',
        grab_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Grab time',
        use_status TINYINT DEFAULT 0 COMMENT '0-Not used 1-Used 2-Expired',
        use_time TIMESTAMP NULL COMMENT 'Use time',
        order_amount DECIMAL(10,2) COMMENT 'Order amount',
        
        INDEX idx_user_id (user_id),
        INDEX idx_coupon_id (coupon_id),
        INDEX idx_room_id (room_id),
        INDEX idx_grab_time (grab_time),
        INDEX idx_status (grab_status, use_status),
        INDEX idx_room_time (room_id, grab_time)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Coupon results table';
    """
    
    with conn.cursor() as cursor:
        cursor.execute(sql)
        conn.commit()
        logger.info("Created coupon_results table")

def initialize_range_shards():
    """Initialize all shards for Range partitioning"""
    logger.info("="*60)
    logger.info("Initializing Range Sharding - 4 Shards")
    logger.info("="*60)
    
    for shard_id, config in DatabaseConfig.SHARD_DBS.items():
        logger.info(f"\nInitializing Shard {shard_id}...")
        logger.info(f"  Host: {config['host']}:{config['port']}")
        logger.info(f"  Database: {config['database']}")
        
        try:
            # Connect to shard
            conn = pymysql.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                database=config['database'],
                charset=config['charset']
            )
            
            # Create table
            create_coupon_results_table(conn)
            
            # Verify
            with conn.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                logger.info(f"  Tables in shard {shard_id}: {tables}")
            
            conn.close()
            logger.info(f"Shard {shard_id} initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize shard {shard_id}: {e}")
            return False
    
    logger.info("\n" + "="*60)
    logger.info("All Range shards initialized successfully!")
    logger.info("="*60)
    logger.info("\nRange Partitioning Strategy:")
    logger.info("  Shard 0: room_id 1-1000")
    logger.info("  Shard 1: room_id 1001-2000")
    logger.info("  Shard 2: room_id 2001-3000")
    logger.info("  Shard 3: room_id 3001+")
    logger.info("="*60)
    
    return True

if __name__ == '__main__':
    if initialize_range_shards():
        logger.info("\nRange sharding setup complete!")
        sys.exit(0)
    else:
        logger.error("\nRange sharding setup failed!")
        sys.exit(1)

