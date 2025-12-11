import pymysql
import logging
# Import configuration
try:
    from hash_vs_range_comparison.strategies.database_aws import DatabaseConfigAWS
except ImportError:
    from database_aws import DatabaseConfigAWS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_global_tables(conn):
    """
    🛠️ Create global tables in Main DB
    Includes: users, live_rooms, coupons, coupon_details, stock_logs
    """
    logger.info("  --> Creating global tables (Users, Rooms, Coupons)...")
    with conn.cursor() as cursor:
        # 1. Users Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY AUTO_INCREMENT,
            username VARCHAR(50) NOT NULL,
            phone VARCHAR(20),
            email VARCHAR(100),
            register_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_level INT DEFAULT 1,
            is_active BOOLEAN DEFAULT TRUE,
            INDEX idx_username (username)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # 2. Live Rooms Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS live_rooms (
            room_id BIGINT PRIMARY KEY AUTO_INCREMENT,
            room_name VARCHAR(100) NOT NULL,
            anchor_id BIGINT NOT NULL,
            room_status TINYINT DEFAULT 0,
            is_hot BOOLEAN DEFAULT FALSE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # 3. Coupons Main Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS coupons (
            coupon_id BIGINT PRIMARY KEY AUTO_INCREMENT,
            room_id BIGINT NOT NULL,
            coupon_name VARCHAR(100) NOT NULL,
            coupon_type TINYINT NOT NULL,
            total_stock INT NOT NULL,
            remaining_stock INT NOT NULL,
            status TINYINT DEFAULT 1,
            INDEX idx_room_id (room_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # 4. Coupon Details (vertical sharding)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS coupon_details (
            coupon_id BIGINT PRIMARY KEY,
            description TEXT,
            usage_rules TEXT,
            product_range TEXT,
            FOREIGN KEY (coupon_id) REFERENCES coupons(coupon_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        # 5. Stock Logs (inventory logs)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_logs (
            log_id BIGINT PRIMARY KEY AUTO_INCREMENT,
            coupon_id BIGINT NOT NULL,
            operation_type TINYINT,
            stock_before INT,
            stock_after INT,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # --- Insert test data ---
        logger.info("  --> Inserting test data...")
        
        # Insert anchors
        cursor.execute("""
            INSERT IGNORE INTO users (user_id, username, user_level) VALUES 
            (10001, 'anchor_alice', 3),
            (10002, 'anchor_bob', 3);
        """)
        
        # Insert live rooms
        cursor.execute("""
            INSERT IGNORE INTO live_rooms (room_id, room_name, anchor_id, is_hot) VALUES 
            (1001, 'Alice Live Room', 10001, 1);
        """)
        
        # Insert coupon (Coupon 101, Stock 10)
        # ⚠️ Note: total_stock is set to 10 here for speed testing
        cursor.execute("""
            INSERT INTO coupons (coupon_id, room_id, coupon_name, coupon_type, total_stock, remaining_stock, status) 
            VALUES (101, 1001, 'AWS Speed Test Coupon', 1, 10, 10, 1)
            ON DUPLICATE KEY UPDATE total_stock=90000, remaining_stock=90000;
        """)
        
        conn.commit()

def create_sharded_tables(conn, shard_id):
    """
    🛠️ Create order tables in all Shard DBs
    Includes: coupon_results_hash (corresponds to coupon_results in SQL)
    """
    table_name = "coupon_results_hash" # This is the name we use in our code
    logger.info(f"  --> Shard {shard_id}: Creating table {table_name}...")
    
    sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        result_id BIGINT PRIMARY KEY AUTO_INCREMENT,
        user_id BIGINT NOT NULL COMMENT 'User ID',
        coupon_id BIGINT NOT NULL COMMENT 'Coupon ID',
        room_id BIGINT NOT NULL COMMENT 'Live room ID',
        grab_status TINYINT NOT NULL COMMENT '0-Failed 1-Success',
        fail_reason VARCHAR(50),
        grab_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        use_status TINYINT DEFAULT 0,
        
        -- Core indexes (corresponding to teammate's design)
        INDEX idx_user_id (user_id),
        INDEX idx_coupon_id (coupon_id),
        INDEX idx_room_id (room_id),
        INDEX idx_room_time (room_id, grab_time)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    with conn.cursor() as cursor:
        cursor.execute(sql)
        # Clear old data for testing convenience
        cursor.execute(f"TRUNCATE TABLE {table_name}")
        conn.commit()

def initialize_aws():
    print("🚀 Starting AWS initialization according to latest design...")
    
    for shard_id, config in DatabaseConfigAWS.SHARD_DBS.items():
        try:
            conn = pymysql.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                database=config['database'],
                charset='utf8mb4',
                connect_timeout=10
            )
            
            # 1. Create order table for all shards
            create_sharded_tables(conn, shard_id)
            
            # 2. If it's Main DB (Shard 0), additionally create global tables
            if shard_id == 0:
                create_global_tables(conn)
            
            conn.close()
            print(f"✅ Shard {shard_id} initialization complete")
            
        except Exception as e:
            print(f"❌ Shard {shard_id} failed: {e}")

if __name__ == "__main__":
    initialize_aws()