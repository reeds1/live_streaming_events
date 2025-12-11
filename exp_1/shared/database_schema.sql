-- ============================================================
-- Database Schema Design - Live Stream Coupon Grabbing System
-- ============================================================
-- Use Case: High-concurrency live stream coupon grabbing
-- Supports: Both Hash Partitioning and Range Partitioning strategies
-- ============================================================

-- 1. Users Table
-- Purpose: Store user basic information
-- Sharding Strategy: Can be sharded by user_id using Hash partitioning
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(100),
    register_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    user_level INT DEFAULT 1 COMMENT 'User level: 1-Normal 2-VIP 3-SVIP',
    is_active BOOLEAN DEFAULT TRUE,
    INDEX idx_username (username),
    INDEX idx_phone (phone),
    INDEX idx_register_time (register_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Users table';

-- ============================================================
-- 2. Live Rooms Table
-- Purpose: Store live streaming room information
-- ============================================================
CREATE TABLE IF NOT EXISTS live_rooms (
    room_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    room_name VARCHAR(100) NOT NULL,
    anchor_id BIGINT NOT NULL COMMENT 'Anchor/Streamer ID',
    room_status TINYINT DEFAULT 0 COMMENT '0-Not started 1-Live 2-Ended',
    viewer_count INT DEFAULT 0 COMMENT 'Number of viewers',
    start_time TIMESTAMP NULL,
    end_time TIMESTAMP NULL,
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_hot BOOLEAN DEFAULT FALSE COMMENT 'Whether it is a hot room (for testing hotspot issues)',
    INDEX idx_anchor (anchor_id),
    INDEX idx_status (room_status),
    INDEX idx_start_time (start_time),
    INDEX idx_is_hot (is_hot)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Live rooms table';

-- ============================================================
-- 3. Coupons Main Table
-- Purpose: Store coupon basic information (excluding large fields)
-- Sharding Strategy: Can be sharded by room_id using Range partitioning
-- ============================================================
CREATE TABLE IF NOT EXISTS coupons (
    coupon_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    room_id BIGINT NOT NULL COMMENT 'Belongs to which live room',
    coupon_name VARCHAR(100) NOT NULL,
    coupon_type TINYINT NOT NULL COMMENT '1-Discount coupon 2-Percentage off 3-No threshold',
    discount_amount DECIMAL(10,2) COMMENT 'Discount amount',
    discount_rate DECIMAL(5,2) COMMENT 'Discount rate (e.g., 0.8 means 20% off)',
    min_purchase DECIMAL(10,2) DEFAULT 0 COMMENT 'Minimum purchase amount',
    total_stock INT NOT NULL COMMENT 'Total stock',
    remaining_stock INT NOT NULL COMMENT 'Remaining stock',
    start_time TIMESTAMP NOT NULL COMMENT 'Valid from',
    end_time TIMESTAMP NOT NULL COMMENT 'Valid until',
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status TINYINT DEFAULT 1 COMMENT '0-Disabled 1-Active',
    INDEX idx_room_id (room_id),
    INDEX idx_create_time (create_time),
    INDEX idx_start_time (start_time),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Coupons main table';

-- ============================================================
-- 4. Coupon Details Table
-- Purpose: Store large fields of coupons (Vertical Partitioning)
-- Note: This demonstrates vertical partitioning by splitting large fields
-- ============================================================
CREATE TABLE IF NOT EXISTS coupon_details (
    coupon_id BIGINT PRIMARY KEY,
    description TEXT COMMENT 'Detailed description of the coupon',
    usage_rules TEXT COMMENT 'Usage rules',
    product_range TEXT COMMENT 'Applicable product range (JSON format)',
    FOREIGN KEY (coupon_id) REFERENCES coupons(coupon_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Coupon details table (Vertical Partitioning)';

-- ============================================================
-- 5. Coupon Results Table (coupon_results / orders)
-- Purpose: Record coupon grabbing results
-- This is the MOST IMPORTANT table and needs optimization!
-- ============================================================
-- Strategy Description:
-- - Hash Sharding (Student A): Shard by user_id modulo, balanced write load
-- - Range Sharding (Student B): Shard by create_time or room_id, efficient queries
-- ============================================================
CREATE TABLE IF NOT EXISTS coupon_results (
    result_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL COMMENT 'User ID',
    coupon_id BIGINT NOT NULL COMMENT 'Coupon ID',
    room_id BIGINT NOT NULL COMMENT 'Live room ID (redundant field for Range sharding)',
    grab_status TINYINT NOT NULL COMMENT '0-Failed 1-Success',
    fail_reason VARCHAR(50) COMMENT 'Failure reason: out_of_stock, duplicate, invalid_time',
    grab_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Grab time',
    use_status TINYINT DEFAULT 0 COMMENT '0-Not used 1-Used 2-Expired',
    use_time TIMESTAMP NULL COMMENT 'Use time',
    order_amount DECIMAL(10,2) COMMENT 'Order amount (if used)',
    
    -- Index design (VERY IMPORTANT!)
    INDEX idx_user_id (user_id) COMMENT 'Needed for Hash sharding',
    INDEX idx_coupon_id (coupon_id),
    INDEX idx_room_id (room_id) COMMENT 'Needed for Range sharding',
    INDEX idx_grab_time (grab_time) COMMENT 'Needed for Range sharding',
    INDEX idx_status (grab_status, use_status),
    INDEX idx_user_coupon (user_id, coupon_id) COMMENT 'Prevent duplicate grabs',
    
    -- Composite indexes (for complex queries)
    INDEX idx_room_time (room_id, grab_time) COMMENT 'Core index for Range sharding',
    INDEX idx_user_time (user_id, grab_time) COMMENT 'Query optimization for Hash sharding'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Coupon results table';

-- ============================================================
-- 6. Stock Logs Table (Optional)
-- Purpose: Record stock change history for reconciliation and troubleshooting
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_logs (
    log_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    coupon_id BIGINT NOT NULL,
    operation_type TINYINT COMMENT '1-Initialize 2-Deduct 3-Rollback',
    stock_before INT,
    stock_after INT,
    operator VARCHAR(50),
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_coupon_id (coupon_id),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Stock operation logs';

-- ============================================================
-- 7. Sharding Table Examples (For Reference)
-- ============================================================

-- Range Sharding Example 1: Shard by time (Student B)
-- CREATE TABLE coupon_results_2025_12_01 LIKE coupon_results;
-- CREATE TABLE coupon_results_2025_12_02 LIKE coupon_results;
-- CREATE TABLE coupon_results_2025_12_03 LIKE coupon_results;

-- Range Sharding Example 2: Shard by room range (Student B)
-- CREATE TABLE coupon_results_room_1_1000 LIKE coupon_results;
-- CREATE TABLE coupon_results_room_1001_2000 LIKE coupon_results;
-- CREATE TABLE coupon_results_room_2001_3000 LIKE coupon_results;

-- Hash Sharding Example: Shard by user_id modulo (Student A)
-- CREATE DATABASE coupon_db_0;
-- CREATE DATABASE coupon_db_1;
-- CREATE DATABASE coupon_db_2;
-- CREATE DATABASE coupon_db_3;
-- Then create coupon_results table with the same structure in each database

-- ============================================================
-- 8. Initialize Test Data (Optional)
-- ============================================================

-- Insert test anchor accounts
INSERT INTO users (user_id, username, user_level, is_active) VALUES
(10001, 'anchor_alice', 3, TRUE),
(10002, 'anchor_bob', 3, TRUE),
(10003, 'anchor_test', 2, TRUE);

-- Insert test live rooms
INSERT INTO live_rooms (room_id, room_name, anchor_id, room_status, is_hot) VALUES
(1001, 'Alice Live Room', 10001, 1, TRUE),
(1002, 'Bob Live Room', 10002, 1, FALSE),
(1003, 'Test Live Room', 10003, 1, FALSE);

-- ============================================================
-- Schema Design Notes
-- ============================================================
/*
Core Design Principles:

1. **Users Table**
   - Can be sharded by user_id using Hash partitioning
   - Suitable for write-heavy, read-light scenarios

2. **Coupons Main Table + Details Table (coupons + coupon_details)**
   - Demonstrates Vertical Partitioning
   - Large fields split into details table, improving main table query performance

3. **Coupon Results Table (coupon_results) - CORE TABLE**
   - Rich indexes to support both sharding strategies:
     * Hash Sharding: idx_user_id, idx_user_coupon, idx_user_time
     * Range Sharding: idx_room_id, idx_grab_time, idx_room_time
   - room_id field is redundant (could be obtained via JOIN), but stored for performance

4. **Index Design Principles**
   - Frequent writes: Don't create too many indexes
   - Clear query patterns: Create composite indexes
   - Range queries: Index time fields

5. **Sharding Strategy Comparison**
   Hash Sharding Advantages:
   - Balanced write load, suitable for high-concurrency writes
   - Even data distribution
   
   Range Sharding Advantages:
   - Fast range queries (by time/by room)
   - Easy data archiving
   - Clear business logic
   
   Hash Sharding Disadvantages:
   - Complex cross-shard queries (e.g., query all orders for a room)
   - Data migration needed for scaling
   
   Range Sharding Disadvantages:
   - Potential hotspot issues (popular streamer rooms)
   - Unbalanced load

6. **Use Cases**
   - Write-heavy with random users: Hash Sharding is better
   - Data analysis or historical archiving: Range Sharding is better
   - Production environments may use hybrid strategies
*/

