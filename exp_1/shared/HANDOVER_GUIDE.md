# 📦 Shared Components Handover Guide

> **Delivered by**: Student B (you)  
> **Received by**: Student A  
> **Delivery Date**: 2025-12-04

---

## 📋 Delivery Contents

### ✅ Completed Files

| File Name | Purpose | Importance |
|-----------|---------|------------|
| `database_schema.sql` | Database table structure definition | ⭐⭐⭐⭐⭐ |
| `data_seeder.py` | Test data generator | ⭐⭐⭐⭐⭐ |
| `locustfile_advanced.py` | Advanced load testing script | ⭐⭐⭐⭐⭐ |
| `docker-compose.yml` | Docker environment configuration | ⭐⭐⭐⭐⭐ |
| `sharding_interface.py` | Sharding strategy interface definition | ⭐⭐⭐⭐⭐ |
| `requirements.txt` | Python dependency list | ⭐⭐⭐⭐ |
| `quick_start.sh` | One-click startup script | ⭐⭐⭐⭐ |
| `README.md` | Shared components documentation | ⭐⭐⭐⭐ |

---

## 🎯 Core Design Decisions

### 1. Database Schema

#### Core Table: `coupon_results`

This is the most important table in the system, specifically designed to **support both sharding strategies simultaneously**:

```sql
CREATE TABLE coupon_results (
    result_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,          -- 👈 Hash sharding key
    coupon_id BIGINT NOT NULL,
    room_id BIGINT NOT NULL,          -- 👈 Range sharding key (by live room)
    grab_status TINYINT NOT NULL,
    fail_reason VARCHAR(50),
    grab_time TIMESTAMP DEFAULT NOW,  -- 👈 Range sharding key (by time)
    use_status TINYINT DEFAULT 0,
    
    -- Indexes needed for Hash sharding
    INDEX idx_user_id (user_id),
    INDEX idx_user_coupon (user_id, coupon_id),
    INDEX idx_user_time (user_id, grab_time),
    
    -- Indexes needed for Range sharding
    INDEX idx_room_id (room_id),
    INDEX idx_grab_time (grab_time),
    INDEX idx_room_time (room_id, grab_time)
);
```

**Design Highlights**:
- ✅ Redundant `room_id` field (can be obtained via JOIN, but stored directly for performance)
- ✅ Indexes cover all query requirements for both strategies
- ✅ Reserved business fields like `fail_reason` and `use_status`

#### Other Tables

- `users`: User table (100k records)
- `live_rooms`: Live room table (100 rooms, including 5 hot rooms)
- `coupons` + `coupon_details`: Demonstrates **vertical sharding** (one of Student B's tasks)
- `stock_logs`: Stock logs (optional)

---

### 2. Data Generator

#### Generation Scale
- 👥 **100,000 users** (user_id: 1 - 100000)
- 🏠 **100 live rooms** (room_id: 1 - 100, first 5 are hot)
- 🎟️ **500 coupons** (coupon_id: 1 - 500)

#### Data Characteristics
- Hot live rooms (room_id 1-5) have more coupon stock (5000-20000)
- Normal live rooms have less coupon stock (500-5000)
- User level distribution: 70% normal users, 25% VIP, 5% SVIP

#### Usage
```bash
python data_seeder.py
```

**Note**: Will first clear all tables, then regenerate data (takes about 2-5 minutes).

---

### 3. Locust Load Testing Script

#### 4 Test Scenarios

| Scenario | Weight | Purpose |
|----------|--------|---------|
| **NormalCouponUser** | 5 | Normal users randomly grabbing coupons |
| **HotRoomUser** | 3 | Concentrated grabbing from hot live rooms (test hotspots) |
| **CrossShardQueryUser** | 1 | Cross-shard queries (test aggregation performance) |
| **AdminUser** | 1 | Admin queries |

#### Key API Endpoints

You need to implement these APIs:

```python
# Write operations
POST /api/coupon/grab              # Grab coupon
  body: {"user_id": 123, "coupon_id": 456, "room_id": 1001}

# Read operations (performance differences between strategies)
GET /api/user/{user_id}/coupons           # Query user coupons (Hash fast)
GET /api/room/{room_id}/orders            # Query live room orders (Range fast)
GET /api/orders/recent?hours=1            # Time range query (Range fast)
GET /api/statistics/global                # Global statistics (both slow, need aggregation)

# Admin interfaces
GET /admin/stats                          # System statistics
GET /admin/shards/status                  # Shard status
```

---

### 4. Docker Environment

#### Services Started

```yaml
Service list:
- mysql-main:       MySQL main database (port 3306)
- mysql-shard-0~3:  MySQL shards 0-3 (ports 3307-3310)  👈 For Student A
- redis:            Redis cache (port 6379)
- rabbitmq:         RabbitMQ message queue (port 5672, management UI 15672)
- phpmyadmin:       Database management tool (port 8080)
- redisinsight:    Redis management tool (port 8081)
```

#### One-Click Startup

```bash
cd shared
docker-compose up -d
```

---

### 5. Sharding Interface Definition

#### Core Interface: `ShardingStrategy`

```python
class ShardingStrategy(ABC):
    @abstractmethod
    def save_coupon_result(self, coupon_result: CouponResult) -> bool:
        """Save coupon grab result - core method!"""
        pass
    
    @abstractmethod
    def query_user_coupons(self, user_id: int) -> List[CouponResult]:
        """Query user coupons - Hash excels at this"""
        pass
    
    @abstractmethod
    def query_room_orders(self, room_id: int) -> List[CouponResult]:
        """Query live room orders - Range excels at this (if sharded by room_id)"""
        pass
    
    @abstractmethod
    def query_time_range_orders(self, start_time, end_time) -> List[CouponResult]:
        """Time range query - Range excels at this (if sharded by time)"""
        pass
```

#### Usage

```python
# Student A's implementation
class HashShardingStrategy(ShardingStrategy):
    def save_coupon_result(self, coupon_result: CouponResult) -> bool:
        shard_id = hash(coupon_result.user_id) % 4
        # Write to corresponding shard...

# Student B's implementation (you)
class RangeShardingStrategy(ShardingStrategy):
    def save_coupon_result(self, coupon_result: CouponResult) -> bool:
        table_name = f"coupon_results_{coupon_result.grab_time.date()}"
        # Write to corresponding shard table...
```

---

## 🚀 Quick Start Guide (for Student A)

### Step 1: Clone/Pull Code

```bash
cd "live_streaming_events/shared"
```

### Step 2: One-Click Environment Startup

```bash
chmod +x quick_start.sh
./quick_start.sh
```

This script will automatically:
1. ✅ Check dependencies (Docker, Python)
2. ✅ Install Python packages
3. ✅ Start Docker services (MySQL, Redis, RabbitMQ)
4. ✅ Import database schema
5. ✅ Generate test data (optional)

### Step 3: Verify Environment

```bash
# Check Docker service status
docker-compose ps

# Test MySQL connection
mysql -h 127.0.0.1 -P 3306 -uroot -ppassword coupon_system -e "SHOW TABLES;"

# Test Redis
redis-cli ping

# Test RabbitMQ
curl http://localhost:15672/
```

### Step 4: Start Development

1. Read `sharding_interface.py` to understand interface definition
2. Implement your `HashShardingStrategy` class
3. Refer to `locustfile_advanced.py` to understand APIs to implement

---

## 📊 Performance Test Metrics (for Student A reference)

### Metrics You Should Focus On

| Metric | Description | How to Get |
|--------|------------|------------|
| **Write QPS** | Writes per second | Locust report |
| **Data Distribution** | Data volume per shard | `SELECT COUNT(*) FROM coupon_results` |
| **Cross-Shard Query Time** | Aggregation query time | P95 of `/api/room/:id/orders` |
| **Shard CPU/IO** | Load per shard | `docker stats` or Prometheus |

### Expected Performance of Hash Sharding

✅ **Advantages**:
- Write QPS across 4 shards should be basically the same (error < 10%)
- Even data distribution
- Queries by `user_id` are very fast

⚠️ **Disadvantages**:
- Queries by `room_id` need to scan all shards (slow)
- Time range queries need to scan all shards (slow)

---

## 🎯 Your (Student B) Next Steps

### Range Sharding Implementation Options

#### Option 1: Shard by Time (Recommended)

```python
# Table structure
coupon_results_2025_12_01
coupon_results_2025_12_02
coupon_results_2025_12_03
...

# Routing logic
def get_table_name(grab_time: datetime) -> str:
    return f"coupon_results_{grab_time.strftime('%Y_%m_%d')}"
```

**Advantages**:
- ✅ Time range queries are extremely fast
- ✅ Data archiving is convenient (can directly delete old tables)

**Disadvantages**:
- ⚠️ Querying a user's coupons needs to scan multiple tables
- ⚠️ Today's table may become a hotspot

#### Option 2: Shard by Live Room

```python
# Table structure
coupon_results_room_1_1000      # room_id: 1-1000
coupon_results_room_1001_2000   # room_id: 1001-2000
...

# Routing logic
def get_table_name(room_id: int) -> str:
    shard_id = (room_id - 1) // 1000
    return f"coupon_results_room_{shard_id*1000+1}_{(shard_id+1)*1000}"
```

**Advantages**:
- ✅ Querying orders for a live room is extremely fast
- ✅ Clear business logic

**Disadvantages**:
- ⚠️ Hot live rooms (room_id 1-5) will become hotspots
- ⚠️ Time range queries need to scan multiple tables

#### Recommendation

I recommend you **shard by time**, because:
1. Better demonstrates Range sharding advantages (time range queries)
2. Hotspot issues are more obvious (convenient for optimization and comparison)
3. Matches actual business scenario of live streaming coupon grabbing (daily settlement)

---

## 🛠️ Vertical Sharding (Vertical Partitioning)

This is your (Student B) additional task, already implemented in the schema:

```sql
-- Main table: only core fields
CREATE TABLE coupons (
    coupon_id, room_id, coupon_name, 
    total_stock, remaining_stock, ...
);

-- Details table: large fields separated
CREATE TABLE coupon_details (
    coupon_id,
    description TEXT,      -- Large field
    usage_rules TEXT,      -- Large field
    product_range TEXT     -- Large field
);
```

**Demonstration Effect**:
- When querying coupon list, only query `coupons` table, fast
- When viewing coupon details, then JOIN `coupon_details` table

---

## 📞 Collaboration Method

### Interface Integration

Both of you need to implement **the same REST API**, so you can directly compare tests:

```
POST /api/coupon/grab
GET  /api/user/:id/coupons
GET  /api/room/:id/orders
GET  /api/orders/recent
GET  /admin/stats
GET  /admin/shards/status
```

### Code Structure Recommendation

```
live_streaming_events/
├── shared/              # Shared components (completed)
├── student_a_hash/      # Student A's code
│   ├── hash_strategy.py
│   ├── api_server.py
│   └── README.md
└── student_b_range/     # Your code
    ├── range_strategy.py
    ├── api_server.py
    └── README.md
```

### Testing Process

```bash
# Test Student A's implementation
locust -f shared/locustfile_advanced.py --host=http://localhost:8001

# Test Student B's implementation
locust -f shared/locustfile_advanced.py --host=http://localhost:8002

# Compare results
python benchmark/compare_results.py
```

---

## ✅ Checklist (for Student A)

After receiving this package, please check:

- [ ] All files exist (8 files)
- [ ] `quick_start.sh` is executable
- [ ] Docker services can start
- [ ] MySQL has 6 instances (1 main + 4 shards + phpMyAdmin can connect)
- [ ] Data generator can run
- [ ] Locust script can load
- [ ] Understand `ShardingStrategy` interface

---

## 📝 FAQ

### Q1: Why create 4 MySQL shards?
**A**: This is prepared for Student A's Hash sharding. You (Student B) don't necessarily need to use them, but keeping the environment consistent facilitates comparison.

### Q2: Why 100k users for data volume?
**A**: This is an appropriate test scale:
- Data volume is large enough to demonstrate sharding effects
- Data volume is not too large, generation is fast (2-5 minutes)
- If larger scale is needed, modify `NUM_USERS` in `data_seeder.py`

### Q3: How long should Locust load test run?
**A**: Recommendations:
- Baseline test: 100 concurrency, 5 minutes
- Stress test: 1000 concurrency, 10 minutes
- Extreme test: 5000 concurrency, until errors occur

### Q4: Can I modify these files?
**A**: Yes! These are just base versions, you can:
- Adjust data volume
- Add test scenarios
- Optimize database configuration
- Add more monitoring metrics

---

## 🎉 Summary

You have completed all the work for the shared components! This foundation is very solid, including:

✅ **Complete database design** (supports both sharding strategies)  
✅ **100k-level test data** (close to real scenarios)  
✅ **Professional load testing environment** (4 test scenarios)  
✅ **One-click startup script** (reduces environment setup difficulty)  
✅ **Clear interface definition** (facilitates collaboration)  

Now you can package the `shared/` folder and deliver it to Student A!

---

**Good luck! 💪**

Feel free to communicate if you have any questions.
