"""
Data Seeder
Purpose: Generate initial test data for load testing
- Generate 100,000 users
- Generate 100 live rooms
- Generate 500 coupons
- Support MySQL connection
"""

import pymysql
import random
from datetime import datetime, timedelta
import sys
from typing import List, Tuple
import time

# ============================================================
# Configuration
# ============================================================
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'password',  # Change to your actual password
    'database': 'coupon_system',
    'charset': 'utf8mb4'
}

# Generation count configuration
NUM_USERS = 100000      # 100K users
NUM_ROOMS = 100         # 100 live rooms
NUM_COUPONS = 500       # 500 coupons
BATCH_SIZE = 1000       # Batch insert size

# ============================================================
# Helper Functions
# ============================================================

def get_db_connection():
    """Get database connection"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        print(f"✅ Successfully connected to database: {DB_CONFIG['database']}")
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

def generate_phone():
    """Generate random phone number"""
    prefixes = ['130', '131', '132', '135', '136', '137', '138', '139', 
                '150', '151', '152', '155', '156', '157', '158', '159',
                '180', '181', '182', '185', '186', '187', '188', '189']
    return random.choice(prefixes) + ''.join([str(random.randint(0, 9)) for _ in range(8)])

def generate_email(username):
    """Generate email address"""
    domains = ['gmail.com', 'yahoo.com', '163.com', 'qq.com', 'outlook.com']
    return f"{username}@{random.choice(domains)}"

def batch_insert(cursor, sql, data_list, batch_size=BATCH_SIZE):
    """Batch insert data"""
    total = len(data_list)
    inserted = 0
    
    for i in range(0, total, batch_size):
        batch = data_list[i:i + batch_size]
        cursor.executemany(sql, batch)
        inserted += len(batch)
        print(f"  Inserted: {inserted}/{total} ({inserted*100//total}%)", end='\r')
    
    print(f"  Inserted: {inserted}/{total} (100%) ✅")

# ============================================================
# 1. Generate User Data
# ============================================================
def seed_users(cursor, num_users=NUM_USERS):
    """Generate user data"""
    print(f"\n📊 Generating {num_users} users...")
    
    users = []
    for i in range(1, num_users + 1):
        username = f"user_{i:06d}"
        phone = generate_phone()
        email = generate_email(username)
        user_level = random.choices([1, 2, 3], weights=[70, 25, 5])[0]  # 70% Normal, 25% VIP, 5% SVIP
        register_time = datetime.now() - timedelta(days=random.randint(1, 365))
        
        users.append((
            username,
            phone,
            email,
            register_time,
            user_level,
            True
        ))
    
    sql = """
        INSERT INTO users (username, phone, email, register_time, user_level, is_active)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    
    batch_insert(cursor, sql, users)
    return num_users

# ============================================================
# 2. Generate Live Room Data
# ============================================================
def seed_live_rooms(cursor, num_rooms=NUM_ROOMS):
    """Generate live room data"""
    print(f"\n📊 Generating {num_rooms} live rooms...")
    
    rooms = []
    room_names = [
        "Beauty Show", "Fashion Sale", "Snack Festival", "Digital Goods", "Home Living",
        "Health & Wellness", "Book Recommendations", "Sports Equipment", "Mother & Baby", "Pet Supplies"
    ]
    
    for i in range(1, num_rooms + 1):
        room_name = f"{random.choice(room_names)}_{i}"
        anchor_id = random.randint(1, min(10000, NUM_USERS))  # Random anchor from users
        room_status = 1  # All set to live
        viewer_count = random.randint(100, 50000)
        
        # 5% of rooms are hot rooms (for testing hotspot issues)
        is_hot = (i <= num_rooms * 0.05)
        if is_hot:
            viewer_count = random.randint(100000, 500000)  # Hot rooms have more viewers
        
        start_time = datetime.now() - timedelta(hours=random.randint(1, 10))
        
        rooms.append((
            room_name,
            anchor_id,
            room_status,
            viewer_count,
            start_time,
            is_hot
        ))
    
    sql = """
        INSERT INTO live_rooms (room_name, anchor_id, room_status, viewer_count, start_time, is_hot)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    
    batch_insert(cursor, sql, rooms)
    return num_rooms

# ============================================================
# 3. Generate Coupon Data
# ============================================================
def seed_coupons(cursor, num_coupons=NUM_COUPONS, num_rooms=NUM_ROOMS):
    """Generate coupon data"""
    print(f"\n📊 Generating {num_coupons} coupons...")
    
    coupons = []
    coupon_details = []
    
    coupon_names = [
        "New User Coupon", "Discount Coupon", "Percentage Off", "No Threshold Gift", 
        "Member Exclusive", "Flash Sale", "Category Coupon", "Store Coupon"
    ]
    
    for i in range(1, num_coupons + 1):
        room_id = random.randint(1, num_rooms)
        coupon_name = f"{random.choice(coupon_names)}_{i}"
        coupon_type = random.randint(1, 3)  # 1-Discount 2-Percentage 3-No threshold
        
        # Set different discounts based on type
        if coupon_type == 1:  # Discount coupon
            discount_amount = random.choice([5, 10, 20, 30, 50, 100])
            discount_rate = None
            min_purchase = discount_amount * 2
        elif coupon_type == 2:  # Percentage off
            discount_amount = None
            discount_rate = random.choice([0.95, 0.9, 0.85, 0.8, 0.75, 0.7])
            min_purchase = 50
        else:  # No threshold
            discount_amount = random.choice([3, 5, 8, 10])
            discount_rate = None
            min_purchase = 0
        
        # Stock: Hot rooms have more coupons
        if room_id <= num_rooms * 0.05:  # Hot rooms
            total_stock = random.randint(5000, 20000)
        else:
            total_stock = random.randint(500, 5000)
        
        remaining_stock = total_stock
        
        start_time = datetime.now()
        end_time = start_time + timedelta(days=random.randint(7, 30))
        
        coupons.append((
            room_id,
            coupon_name,
            coupon_type,
            discount_amount,
            discount_rate,
            min_purchase,
            total_stock,
            remaining_stock,
            start_time,
            end_time,
            1  # status
        ))
        
        # Generate coupon details (Vertical partitioning)
        description = f"This is the detailed description for {coupon_name}, including usage instructions and notes."
        usage_rules = "1. Limit 1 per user\n2. Cannot be combined with other offers\n3. Only for this live room"
        product_range = '{"categories": ["All categories"], "excluded": []}'
        
        coupon_details.append((
            i,  # coupon_id (assuming auto-increment from 1)
            description,
            usage_rules,
            product_range
        ))
    
    # Insert coupons main table
    sql_coupons = """
        INSERT INTO coupons (room_id, coupon_name, coupon_type, discount_amount, discount_rate,
                            min_purchase, total_stock, remaining_stock, start_time, end_time, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    batch_insert(cursor, sql_coupons, coupons)
    
    # Insert coupon details table
    print(f"\n📊 Generating {num_coupons} coupon details...")
    sql_details = """
        INSERT INTO coupon_details (coupon_id, description, usage_rules, product_range)
        VALUES (%s, %s, %s, %s)
    """
    batch_insert(cursor, sql_details, coupon_details)
    
    return num_coupons

# ============================================================
# 4. Truncate Tables
# ============================================================
def truncate_tables(cursor):
    """Truncate all tables"""
    print("\n🗑️  Truncating existing data...")
    
    tables = [
        'coupon_results',
        'stock_logs',
        'coupon_details',
        'coupons',
        'live_rooms',
        'users'
    ]
    
    cursor.execute('SET FOREIGN_KEY_CHECKS = 0')
    
    for table in tables:
        try:
            cursor.execute(f'TRUNCATE TABLE {table}')
            print(f"  ✅ Truncated table: {table}")
        except Exception as e:
            print(f"  ⚠️  Table {table} truncate failed or doesn't exist: {e}")
    
    cursor.execute('SET FOREIGN_KEY_CHECKS = 1')

# ============================================================
# 5. Main Function
# ============================================================
def main():
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║              Data Seeder                               ║
    ║      Live Stream Coupon Grabbing System                ║
    ╚════════════════════════════════════════════════════════╝
    """)
    
    print(f"Configuration:")
    print(f"  - Users: {NUM_USERS:,}")
    print(f"  - Live Rooms: {NUM_ROOMS}")
    print(f"  - Coupons: {NUM_COUPONS}")
    print(f"  - Database: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    
    confirm = input("\n⚠️  Warning: This will clear existing data! Continue? (yes/no): ")
    if confirm.lower() != 'yes':
        print("❌ Operation cancelled")
        return
    
    # Connect to database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    start_time = time.time()
    
    try:
        # 1. Truncate tables
        truncate_tables(cursor)
        conn.commit()
        
        # 2. Generate user data
        user_count = seed_users(cursor, NUM_USERS)
        conn.commit()
        
        # 3. Generate live room data
        room_count = seed_live_rooms(cursor, NUM_ROOMS)
        conn.commit()
        
        # 4. Generate coupon data
        coupon_count = seed_coupons(cursor, NUM_COUPONS, NUM_ROOMS)
        conn.commit()
        
        elapsed_time = time.time() - start_time
        
        print("\n" + "="*60)
        print("✅ Data generation complete!")
        print("="*60)
        print(f"📊 Statistics:")
        print(f"  - Users: {user_count:,}")
        print(f"  - Live Rooms: {room_count}")
        print(f"  - Coupons: {coupon_count}")
        print(f"  - Duration: {elapsed_time:.2f} seconds")
        print("="*60)
        
        # Display sample data
        print("\n📋 Sample data preview:")
        
        cursor.execute("SELECT * FROM users LIMIT 3")
        print("\nUsers sample:")
        for row in cursor.fetchall():
            print(f"  {row}")
        
        cursor.execute("SELECT * FROM live_rooms WHERE is_hot = TRUE LIMIT 3")
        print("\nHot rooms sample:")
        for row in cursor.fetchall():
            print(f"  {row}")
        
        cursor.execute("SELECT * FROM coupons LIMIT 3")
        print("\nCoupons sample:")
        for row in cursor.fetchall():
            print(f"  {row}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()
        print("\n🔌 Database connection closed")

if __name__ == '__main__':
    main()
