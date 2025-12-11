"""
Initialize coupon_results table in all 4 shards
Run: python -m init_shards
"""

import pymysql
from database import DatabaseConfig

def create_coupon_results_table(conn: pymysql.Connection):
    """Create coupon_results table"""
    sql = """
    CREATE TABLE IF NOT EXISTS coupon_results (
        result_id BIGINT PRIMARY KEY AUTO_INCREMENT,
        user_id BIGINT NOT NULL,
        coupon_id BIGINT NOT NULL,
        room_id BIGINT NOT NULL,
        grab_status TINYINT NOT NULL COMMENT '0-Failed 1-Success',
        fail_reason VARCHAR(50),
        grab_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        use_status TINYINT DEFAULT 0 COMMENT '0-Not used 1-Used 2-Expired',
        use_time TIMESTAMP NULL,
        order_amount DECIMAL(10,2),
        
        INDEX idx_user_id (user_id),
        INDEX idx_coupon_id (coupon_id),
        INDEX idx_user_coupon (user_id, coupon_id),
        INDEX idx_user_time (user_id, grab_time)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """
    
    with conn.cursor() as cursor:
        cursor.execute(sql)
        conn.commit()

def init_all_shards():
    """Initialize all shards"""
    print("🔧 Initializing shard tables...")
    
    for shard_id, config in DatabaseConfig.SHARD_DBS.items():
        try:
            conn = pymysql.connect(**config)
            create_coupon_results_table(conn)
            print(f" Shard {shard_id} initialized")
            conn.close()
        except Exception as e:
            print(f"Shard {shard_id} failed: {e}")

if __name__ == '__main__':
    init_all_shards()