# Shared Components

## 📋 Overview

This is the **shared components** of the live streaming coupon grabbing system, containing infrastructure and tools that both students need to use.

### Contents

1. **Database Schema** (`database_schema.sql`)
2. **Data Generator** (`data_seeder.py`)
3. **Advanced Locust Load Testing Script** (`locustfile_advanced.py`)
4. **Docker Compose Environment** (`docker-compose.yml`)

---

## 🗄️ Database Design

### Core Table Structure

| Table Name | Purpose | Sharding Strategy Support |
|-----------|---------|-------------------------|
| `users` | User information | Hash (by user_id) |
| `live_rooms` | Live room information | - |
| `coupons` | Coupon main table | Range (by room_id) |
| `coupon_details` | Coupon details (vertical sharding) | - |
| `coupon_results` | Coupon grab results **[Core]** | Supports both Hash / Range |
| `stock_logs` | Stock operation logs | - |

### Index Design

To support both sharding strategies, the `coupon_results` table has comprehensive indexes:

```sql
-- Indexes needed for Hash sharding
INDEX idx_user_id (user_id)
INDEX idx_user_coupon (user_id, coupon_id)
INDEX idx_user_time (user_id, grab_time)

-- Indexes needed for Range sharding
INDEX idx_room_id (room_id)
INDEX idx_grab_time (grab_time)
INDEX idx_room_time (room_id, grab_time)
```

---

## 🚀 Quick Start

### 1️⃣ Start Base Environment

```bash
cd shared
docker-compose up -d
```

Services started:
- MySQL main database (port 3306)
- MySQL shards 0-3 (ports 3307-3310)
- Redis (port 6379)
- RabbitMQ (port 5672, management UI 15672)
- phpMyAdmin (port 8080)
- RedisInsight (port 8081)

### 2️⃣ Initialize Database

```bash
# Install dependencies
pip install pymysql

# Run data generator
python data_seeder.py
```

Generated data:
- 100,000 users
- 100 live rooms (including 5 hot rooms)
- 500 coupons

### 3️⃣ Run Load Test

```bash
# Install Locust
pip install locust

# Start Locust (WebUI mode)
locust -f locustfile_advanced.py --host=http://localhost:8000

# Visit http://localhost:8089 to configure and start
```

Or directly in command line mode:

```bash
locust -f locustfile_advanced.py --host=http://localhost:8000 \
       --users 1000 --spawn-rate 50 --run-time 5m --headless
```

---

## 📊 Load Test Scenarios

### Scenario 1: Normal Users (Weight 5)
- Random coupon grabbing
- Query own coupons
- View coupon stock

### Scenario 2: Hotspot Users (Weight 3)
- **Specifically grab coupons from hot live rooms**
- Used to test Range sharding hotspot issues

### Scenario 3: Cross-Shard Query Users (Weight 1)
- Query all orders for a live room
- Query orders within time range
- Global statistics
- **Used to test Hash sharding cross-shard aggregation performance**

### Scenario 4: Admin (Weight 1)
- View system statistics
- View shard status

---

## 🔧 Configuration

### Database Connection Configuration

Edit database configuration in `data_seeder.py`:

```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'password',  # Change to your password
    'database': 'coupon_system',
    'charset': 'utf8mb4'
}
```

### Locust Load Test Parameters

Edit configuration in `locustfile_advanced.py`:

```python
USER_ID_MIN = 1
USER_ID_MAX = 100000    # Corresponds to data generator

ROOM_ID_MIN = 1
ROOM_ID_MAX = 100

COUPON_ID_MIN = 1
COUPON_ID_MAX = 500

HOT_ROOM_MIN = 1
HOT_ROOM_MAX = 5        # Hot room range
```

---

## 📈 Performance Metrics to Focus On

### Student A (Hash Sharding) should focus on:

1. **Write QPS**
   - Whether write QPS across 4 shards is balanced
   - Whether total QPS scales linearly

2. **Data Distribution**
   - Use `SELECT COUNT(*) FROM coupon_results` to check data volume per shard
   - Check for data skew

3. **Cross-Shard Query Performance**
   - Response time of `/api/room/:id/orders [Cross Shard]`
   - Expected: Will be slower, as it needs to aggregate multiple shards

### Student B (Range Sharding) should focus on:

1. **Range Query Performance**
   - Response time of `/api/orders/recent [Time Range]`
   - Expected: Should be fast, as data is in the same shard

2. **Hotspot Load**
   - CPU/IO load of shard containing hot live rooms
   - Response time of `/api/coupon/grab [Hot Room]`
   - Whether hotspot bottlenecks occur

3. **Data Distribution**
   - Data volume differences across different shards (by time or room)
   - Load differences between hot shards vs cold shards

---

## 🛠️ Tool Usage

### phpMyAdmin
- URL: http://localhost:8080
- Server: mysql-main (or mysql-shard-0~3)
- Username: root
- Password: password

Can easily view table structure, execute SQL, view data distribution.

### RabbitMQ Management UI
- URL: http://localhost:15672
- Username: admin
- Password: admin123

Can monitor message queue status.

### RedisInsight
- URL: http://localhost:8081

Can monitor Redis cache usage.

---

## 📝 Database Sharding Strategy Comparison

| Dimension | Hash Sharding (Student A) | Range Sharding (Student B) |
|-----------|---------------------------|---------------------------|
| **Write Performance** | ⭐⭐⭐⭐⭐ Balanced | ⭐⭐⭐ May have hotspots |
| **Range Queries** | ⭐⭐ Needs aggregation | ⭐⭐⭐⭐⭐ Fast |
| **Data Distribution** | ⭐⭐⭐⭐⭐ Uniform | ⭐⭐⭐ May be skewed |
| **Scaling Difficulty** | ⭐⭐ Needs migration | ⭐⭐⭐⭐ Easy |
| **Use Cases** | Write-heavy, random users | Time queries, data archiving |

---

## 🎯 Testing Recommendations

### Phase 1: Baseline Test (Week 1)
- Test with 100 concurrency for 5 minutes
- Record baseline QPS, response time, error rate

### Phase 2: Stress Test (Week 2)
- Gradually increase concurrency: 500 → 1000 → 2000 → 5000
- Find system bottleneck points

### Phase 3: Comparison Test (Week 3)
- Test both Hash and Range strategies simultaneously
- Compare performance under different scenarios
- Record database load (CPU, IO, connection count)

### Phase 4: Optimization Test (Week 4)
- Optimize based on bottlenecks (indexes, cache, connection pool)
- Re-test to verify effectiveness

---

## 📦 Dependency Installation

```bash
# Python dependencies
pip install -r requirements.txt

# Or install manually
pip install pymysql locust redis pika fastapi uvicorn
```

Create `requirements.txt`:

```
pymysql==1.1.0
locust==2.15.1
redis==5.0.1
pika==1.3.2
fastapi==0.104.1
uvicorn==0.24.0
```

---

## 🐛 Common Issues

### 1. MySQL Connection Failed
```bash
# Check if containers are running
docker-compose ps

# View MySQL logs
docker-compose logs mysql-main
```

### 2. Data Generation Too Slow
- Adjust `BATCH_SIZE` parameter (default 1000)
- Reduce generation quantity (e.g., generate 10,000 users first for testing)

### 3. Locust Load Test Connection Failed
- Ensure backend service is started
- Check if `--host` parameter is correct

---

## 📞 Contact

If you have questions, please contact:
- Student A: [Email/WeChat]
- Student B (you): [Email/WeChat]

---

## 📄 License

MIT
