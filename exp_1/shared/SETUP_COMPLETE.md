# Setup Complete - Shared Components

## ✅ All Files Created (English Version)

All project files have been created in English. Below is the complete list:

### 1. Database Design
- **`database_schema.sql`** - Complete database schema design
  - Tables: users, live_rooms, coupons, coupon_details, coupon_results, stock_logs
  - Indexes optimized for both Hash and Range sharding
  - Sample test data included

### 2. Data Generation
- **`data_seeder.py`** - Test data generator
  - Generates 100,000 users
  - Generates 100 live rooms (including 5 hot rooms)
  - Generates 500 coupons
  - Batch insertion for performance

### 3. Load Testing
- **`locustfile_advanced.py`** - Advanced Locust test script
  - 4 test scenarios: Normal users, Hot room users, Cross-shard queries, Admin
  - Weighted distribution
  - Detailed statistics output

### 4. Infrastructure
- **`docker-compose.yml`** - Complete Docker environment
  - MySQL main instance (port 3306)
  - MySQL shards 0-3 (ports 3307-3310)
  - Redis (port 6379)
  - RabbitMQ (ports 5672, 15672)
  - phpMyAdmin (port 8080)
  - RedisInsight (port 8081)

### 5. Interface Definition
- **`sharding_interface.py`** - Sharding strategy interface
  - Abstract base class: `ShardingStrategy`
  - Data models: `CouponResult`, `ShardingStats`
  - Manager class: `ShardingManager`
  - Usage examples included

### 6. Utilities
- **`quick_start.sh`** - One-click startup script
  - Checks dependencies
  - Installs Python packages
  - Starts Docker services
  - Initializes database
  - Optional: Generates test data

- **`requirements.txt`** - Python dependencies
  - pymysql, redis, pika
  - fastapi, uvicorn
  - locust

### 7. Documentation
- **`README.md`** - Shared components documentation
- **`HANDOVER_GUIDE.md`** - Handover guide for Student A
- **`PROJECT_OVERVIEW.md`** - Overall project overview

---

## 🚀 Quick Start

### Method 1: Automated (Recommended)
```bash
cd shared
chmod +x quick_start.sh
./quick_start.sh
```

### Method 2: Manual Steps
```bash
# 1. Start Docker services
docker-compose up -d

# 2. Wait for services
sleep 30

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Import database schema
docker exec -i coupon_mysql_main mysql -uroot -ppassword coupon_system < database_schema.sql

# 5. Generate test data
python data_seeder.py

# 6. Run load test
locust -f locustfile_advanced.py --host=http://localhost:8000
```

---

## 📊 Key Design Decisions

### Database Schema
The `coupon_results` table is the core table, designed to support both sharding strategies:

**For Hash Sharding (Student A):**
- Primary key: `user_id`
- Indexes: `idx_user_id`, `idx_user_coupon`, `idx_user_time`
- Shard by: `hash(user_id) % 4`

**For Range Sharding (Student B):**
- Primary keys: `room_id` or `grab_time`
- Indexes: `idx_room_id`, `idx_grab_time`, `idx_room_time`
- Shard by: time ranges or room ranges

### Test Data Distribution
- **Users**: 100,000 (evenly distributed)
- **Rooms**: 100 total, 5 are "hot" rooms (room_id 1-5)
- **Coupons**: 500 total
  - Hot rooms: 5,000-20,000 stock per coupon
  - Normal rooms: 500-5,000 stock per coupon

### Load Test Scenarios
1. **Normal Users (weight=5)**: Random coupon grabbing
2. **Hot Room Users (weight=3)**: Focus on hot rooms (tests hotspot issues)
3. **Cross-Shard Query Users (weight=1)**: Test aggregate queries
4. **Admin Users (weight=1)**: System management

---

## 🎯 API Endpoints to Implement

Both Student A and Student B need to implement these endpoints:

### Write Operations
```
POST /api/coupon/grab
Body: {"user_id": 123, "coupon_id": 456, "room_id": 1001}
```

### Read Operations
```
GET /api/user/:user_id/coupons          # Hash advantage
GET /api/room/:room_id/orders           # Range advantage (if sharded by room)
GET /api/orders/recent?hours=1          # Range advantage (if sharded by time)
GET /api/statistics/global              # Both need aggregation
```

### Admin Operations
```
GET /admin/stats                        # System statistics
GET /admin/shards/status                # Shard status
```

---

## 📈 Performance Metrics to Track

### Student A (Hash Sharding)
- ✅ Write QPS per shard (should be balanced)
- ✅ Data distribution (should be even)
- ⚠️ Cross-shard query time (may be slow)

### Student B (Range Sharding)
- ✅ Range query time (should be fast)
- ⚠️ Hot shard CPU/IO usage (may be high)
- ⚠️ Data distribution (may be unbalanced)

---

## 📦 Handover to Student A

You can now share the `shared/` folder with Student A. Everything is ready:

1. ✅ Database schema defined
2. ✅ Test data generator ready
3. ✅ Load testing environment configured
4. ✅ Docker environment ready to start
5. ✅ Interface clearly defined
6. ✅ Documentation complete

Student A just needs to:
1. Run `quick_start.sh`
2. Read `sharding_interface.py`
3. Implement `HashShardingStrategy`
4. Implement the API endpoints

---

## 🔧 Next Steps for You (Student B)

### 1. Choose Your Range Sharding Strategy

**Option 1: Shard by Time (Recommended)**
```python
# Table structure
coupon_results_2025_12_01
coupon_results_2025_12_02
coupon_results_2025_12_03
...

# Routing logic
def get_table_name(grab_time):
    return f"coupon_results_{grab_time.strftime('%Y_%m_%d')}"
```

**Option 2: Shard by Room**
```python
# Table structure
coupon_results_room_1_1000      # room_id: 1-1000
coupon_results_room_1001_2000   # room_id: 1001-2000
...

# Routing logic
def get_table_name(room_id):
    shard_id = (room_id - 1) // 1000
    return f"coupon_results_room_{shard_id*1000+1}_{(shard_id+1)*1000}"
```

### 2. Implement Your Strategy

Create `range_sharding_strategy.py`:
```python
from sharding_interface import ShardingStrategy, CouponResult

class RangeShardingStrategy(ShardingStrategy):
    def save_coupon_result(self, coupon_result: CouponResult) -> bool:
        # Your implementation here
        table_name = self._get_table_name(coupon_result.grab_time)
        # Insert into the appropriate table
        pass
    
    # Implement other methods...
```

### 3. Demonstrate Vertical Partitioning

The schema already includes `coupons` and `coupon_details` tables.
Show that querying the main `coupons` table is faster than joining with details.

### 4. Test and Optimize

- Run load tests
- Identify hotspot issues
- Implement optimizations (pre-sharding, caching, etc.)
- Compare with Student A's results

---

## 🎓 Learning Objectives

By completing this project, you will understand:

- ✅ How Hash and Range sharding work
- ✅ Trade-offs between different strategies
- ✅ When to use which strategy
- ✅ How to handle hotspots in Range sharding
- ✅ How to optimize cross-shard queries in Hash sharding
- ✅ Vertical partitioning benefits
- ✅ Load testing and performance analysis

---

## 📞 Support

If Student A has questions, they can refer to:
- `README.md` - Shared components guide
- `HANDOVER_GUIDE.md` - Detailed handover documentation
- `sharding_interface.py` - Interface examples

---

**All files are ready! Good luck with the project! 💪**

Date: 2025-12-04




