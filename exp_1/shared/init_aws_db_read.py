import pymysql
import logging
import random
import time
from datetime import datetime, timedelta

# 引入配置
try:
    from hash_vs_range_comparison.strategies.database_aws import DatabaseConfigAWS
except ImportError:
    # 兼容直接运行的情况
    class DatabaseConfigAWS:
        SHARD_DBS = {
            0: {"host": "localhost", "port": 3306, "user": "root", "password": "password", "database": "db_shard_0"},
            1: {"host": "localhost", "port": 3306, "user": "root", "password": "password", "database": "db_shard_1"}
        }

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_global_tables(conn):
    """
    🛠️ 在 Main DB 创建全局表
    包含: users, live_rooms, coupons, coupon_details, stock_logs
    """
    logger.info("  --> 正在创建全局表 (Users, Rooms, Coupons)...")
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

        # 4. Coupon Details (垂直分表)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS coupon_details (
            coupon_id BIGINT PRIMARY KEY,
            description TEXT,
            usage_rules TEXT,
            product_range TEXT,
            FOREIGN KEY (coupon_id) REFERENCES coupons(coupon_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        
        # 5. Stock Logs (库存日志)
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

        # --- 插入基础测试数据 ---
        logger.info("  --> 正在插入基础配置数据...")
        cursor.execute("""
            INSERT IGNORE INTO users (user_id, username, user_level) VALUES 
            (10001, 'anchor_alice', 3),
            (10002, 'anchor_bob', 3);
        """)
        
        cursor.execute("""
            INSERT IGNORE INTO live_rooms (room_id, room_name, anchor_id, is_hot) VALUES 
            (1001, 'Alice Live Room', 10001, 1);
        """)
        
        cursor.execute("""
            INSERT INTO coupons (coupon_id, room_id, coupon_name, coupon_type, total_stock, remaining_stock, status) 
            VALUES (101, 1001, 'AWS Speed Test Coupon', 1, 90000, 90000, 1)
            ON DUPLICATE KEY UPDATE total_stock=90000, remaining_stock=90000;
        """)
        
        conn.commit()

def create_sharded_tables(conn, shard_id):
    """
    🛠️ 在所有 Shard DB 创建订单表 并批量插入测试数据
    """
    table_name = "coupon_results_hash" 
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
        
        INDEX idx_user_id (user_id),
        INDEX idx_coupon_id (coupon_id),
        INDEX idx_room_id (room_id),
        INDEX idx_room_time (room_id, grab_time)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    
    with conn.cursor() as cursor:
        cursor.execute(sql)
        # 清空旧数据
        cursor.execute(f"TRUNCATE TABLE {table_name}")
        
        # ==========================================
        # 🚀 批量插入测试数据 (Batch Insert)
        # ==========================================
        TOTAL_ROWS_PER_SHARD = 20000  # 每个分片插 2万条，总量就是 2万 * 分片数
        BATCH_SIZE = 1000             # 每次 SQL 插 1000 条
        
        logger.info(f"  --> Shard {shard_id}: 正在生成 {TOTAL_ROWS_PER_SHARD} 条测试数据...")
        
        data_buffer = []
        base_user_id = shard_id * 1000000 # 简单的让不同分片 ID 错开一点
        
        for i in range(1, TOTAL_ROWS_PER_SHARD + 1):
            # 生成模拟数据
            uid = base_user_id + random.randint(1, 500000) # 随机 User ID
            cid = random.randint(100, 110)                 # Coupon ID
            rid = 1001                                     # Room ID
            status = 1                                     # Grab Success
            used = random.choice([0, 1])                   # Use Status
            
            # 随机时间 (最近30天)
            delta_seconds = random.randint(0, 30 * 24 * 3600)
            g_time = (datetime.now() - timedelta(seconds=delta_seconds)).strftime('%Y-%m-%d %H:%M:%S')
            
            # 加入 buffer
            data_buffer.append(f"({uid}, {cid}, {rid}, {status}, {used}, '{g_time}')")
            
            # 达到 BATCH_SIZE 或者是最后一条时，执行插入
            if len(data_buffer) >= BATCH_SIZE or i == TOTAL_ROWS_PER_SHARD:
                values_str = ",".join(data_buffer)
                insert_sql = f"""
                    INSERT INTO {table_name} 
                    (user_id, coupon_id, room_id, grab_status, use_status, grab_time) 
                    VALUES {values_str}
                """
                cursor.execute(insert_sql)
                conn.commit()
                data_buffer = [] # 清空 buffer
                
        logger.info(f"  --> Shard {shard_id}: ✅ 数据插入完成 ({TOTAL_ROWS_PER_SHARD} 条)")

def initialize_aws():
    print("🚀 开始按照最新设计图纸初始化 AWS...")
    
    for shard_id, config in DatabaseConfigAWS.SHARD_DBS.items():
        try:
            print(f"🔌 Connecting to Shard {shard_id} ({config['host']})...")
            conn = pymysql.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                database=config['database'],
                charset='utf8mb4',
                connect_timeout=10
            )
            
            # 1. 无论哪个分片，都创建订单表并塞数据
            create_sharded_tables(conn, shard_id)
            
            # 2. 如果是 Main DB (Shard 0)，额外创建全局表
            if shard_id == 0:
                create_global_tables(conn)
            
            conn.close()
            print(f"✅ Shard {shard_id} 初始化完成")
            
        except Exception as e:
            print(f"❌ Shard {shard_id} 失败: {e}")

if __name__ == "__main__":
    initialize_aws()