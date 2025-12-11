"""
Initialize AWS RDS Shards - Create tables in all 4 RDS instances
"""

from database_aws import DatabaseConfigAWS
import pymysql
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_coupon_results_table(conn, table_name):
    """Create coupon results table"""
    sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
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
        logger.info(f"  Created {table_name} table")

def initialize_aws_shards():
    """Initialize all AWS RDS shards"""
    logger.info("="*70)
    logger.info("Initializing AWS RDS Shards (4 instances)")
    logger.info("="*70)
    
    for shard_id, config in DatabaseConfigAWS.SHARD_DBS.items():
        logger.info(f"\nInitializing AWS RDS Shard {shard_id}...")
        logger.info(f"  Host: {config['host']}")
        logger.info(f"  Database: {config['database']}")
        
        try:
            # Connect to RDS shard
            conn = pymysql.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                database=config['database'],
                charset=config['charset'],
                connect_timeout=30
            )
            
            # Create two separate tables for Hash and Range strategies
            create_coupon_results_table(conn, "coupon_results_hash")
            create_coupon_results_table(conn, "coupon_results_range")
            
            # Clear existing data if tables already exist
            with conn.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE coupon_results_hash")
                cursor.execute("TRUNCATE TABLE coupon_results_range")
                conn.commit()
                logger.info("  Cleared existing data")
            
            # Verify
            with conn.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                logger.info(f"  ✅ Shard {shard_id} initialized successfully")
                logger.info(f"  Tables: {len(tables)}")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"  ❌ Failed to initialize shard {shard_id}: {e}")
            return False
    
    logger.info("\n" + "="*70)
    logger.info("✅ All AWS RDS shards initialized successfully!")
    logger.info("="*70)
    logger.info("\nReady for testing on AWS!")
    logger.info("You can now run:")
    logger.info("  cd ../tests")
    logger.info("  python3 comparison_experiment_aws.py")
    logger.info("="*70)
    
    return True

if __name__ == '__main__':
    import sys
    if initialize_aws_shards():
        logger.info("\n✅ AWS RDS setup complete!")
        sys.exit(0)
    else:
        logger.error("\n❌ AWS RDS setup failed!")
        sys.exit(1)

