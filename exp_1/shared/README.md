# 共同部分 (Shared Components)

## 📋 概述

这是直播抢券系统的**共同部分**，包含了两位同学都需要使用的基础设施和工具。

### 包含内容

1. **数据库 Schema** (`database_schema.sql`)
2. **数据生成器** (`data_seeder.py`)
3. **Locust 高级压测脚本** (`locustfile_advanced.py`)
4. **Docker Compose 环境** (`docker-compose.yml`)

---

## 🗄️ 数据库设计

### 核心表结构

| 表名 | 用途 | 分片策略支持 |
|-----|------|------------|
| `users` | 用户信息 | Hash (按 user_id) |
| `live_rooms` | 直播间信息 | - |
| `coupons` | 优惠券主表 | Range (按 room_id) |
| `coupon_details` | 优惠券详情（垂直分表） | - |
| `coupon_results` | 抢券结果 **[核心]** | Hash / Range 都支持 |
| `stock_logs` | 库存操作日志 | - |

### 索引设计

为了支持两种分片策略，`coupon_results` 表设计了完善的索引：

```sql
-- Hash 分片需要的索引
INDEX idx_user_id (user_id)
INDEX idx_user_coupon (user_id, coupon_id)
INDEX idx_user_time (user_id, grab_time)

-- Range 分片需要的索引
INDEX idx_room_id (room_id)
INDEX idx_grab_time (grab_time)
INDEX idx_room_time (room_id, grab_time)
```

---

## 🚀 快速开始

### 1️⃣ 启动基础环境

```bash
cd shared
docker-compose up -d
```

启动的服务：
- MySQL 主库（端口 3306）
- MySQL 分片 0-3（端口 3307-3310）
- Redis（端口 6379）
- RabbitMQ（端口 5672, 管理界面 15672）
- phpMyAdmin（端口 8080）
- RedisInsight（端口 8081）

### 2️⃣ 初始化数据库

```bash
# 安装依赖
pip install pymysql

# 运行数据生成器
python data_seeder.py
```

生成的数据：
- 100,000 个用户
- 100 个直播间（包含 5 个热门直播间）
- 500 个优惠券

### 3️⃣ 运行压测

```bash
# 安装 Locust
pip install locust

# 启动 Locust（WebUI 模式）
locust -f locustfile_advanced.py --host=http://localhost:8000

# 访问 http://localhost:8089 进行配置和启动
```

或者直接命令行模式：

```bash
locust -f locustfile_advanced.py --host=http://localhost:8000 \
       --users 1000 --spawn-rate 50 --run-time 5m --headless
```

---

## 📊 压测场景说明

### 场景 1: 普通用户（权重 5）
- 随机抢券
- 查询自己的优惠券
- 查看优惠券库存

### 场景 2: 热点用户（权重 3）
- **专门抢热门直播间的券**
- 用于测试 Range 分片的热点问题

### 场景 3: 跨分片查询用户（权重 1）
- 查询某个直播间的所有订单
- 查询时间范围内的订单
- 全局统计
- **用于测试 Hash 分片的跨分片聚合性能**

### 场景 4: 管理员（权重 1）
- 查看系统统计
- 查看分片状态

---

## 🔧 配置说明

### 数据库连接配置

编辑 `data_seeder.py` 中的数据库配置：

```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'password',  # 修改为你的密码
    'database': 'coupon_system',
    'charset': 'utf8mb4'
}
```

### Locust 压测参数

编辑 `locustfile_advanced.py` 中的配置：

```python
USER_ID_MIN = 1
USER_ID_MAX = 100000    # 与数据生成器对应

ROOM_ID_MIN = 1
ROOM_ID_MAX = 100

COUPON_ID_MIN = 1
COUPON_ID_MAX = 500

HOT_ROOM_MIN = 1
HOT_ROOM_MAX = 5        # 热门直播间范围
```

---

## 📈 性能指标关注点

### 同学 A (Hash 分片) 应该关注：

1. **写入 QPS**
   - 4 个分片的写入 QPS 是否均衡
   - 总 QPS 是否线性提升

2. **数据分布**
   - 使用 `SELECT COUNT(*) FROM coupon_results` 检查每个分片的数据量
   - 是否存在数据倾斜（Data Skew）

3. **跨分片查询性能**
   - `/api/room/:id/orders [Cross Shard]` 的响应时间
   - 预期：会比较慢，因为需要聚合多个分片

### 同学 B (Range 分片) 应该关注：

1. **范围查询性能**
   - `/api/orders/recent [Time Range]` 的响应时间
   - 预期：应该很快，因为数据在同一个分片

2. **热点负载**
   - 热门直播间所在分片的 CPU/IO 负载
   - `/api/coupon/grab [Hot Room]` 的响应时间
   - 是否出现热点瓶颈

3. **数据分布**
   - 不同分片（按时间或直播间）的数据量差异
   - 热点分片 vs 冷分片的负载差异

---

## 🛠️ 工具使用

### phpMyAdmin
- URL: http://localhost:8080
- 服务器：mysql-main（或 mysql-shard-0~3）
- 用户名：root
- 密码：password

可以方便地查看表结构、执行 SQL、查看数据分布。

### RabbitMQ 管理界面
- URL: http://localhost:15672
- 用户名：admin
- 密码：admin123

可以监控消息队列的状态。

### RedisInsight
- URL: http://localhost:8081

可以监控 Redis 缓存的使用情况。

---

## 📝 数据库分片策略对比

| 维度 | Hash 分片（同学A） | Range 分片（同学B） |
|-----|------------------|-------------------|
| **写入性能** | ⭐⭐⭐⭐⭐ 均衡 | ⭐⭐⭐ 可能有热点 |
| **范围查询** | ⭐⭐ 需要聚合 | ⭐⭐⭐⭐⭐ 快速 |
| **数据分布** | ⭐⭐⭐⭐⭐ 均匀 | ⭐⭐⭐ 可能倾斜 |
| **扩容难度** | ⭐⭐ 需要迁移 | ⭐⭐⭐⭐ 容易 |
| **适用场景** | 写多读少、用户随机 | 时间查询、数据归档 |

---

## 🎯 测试建议

### 阶段 1：基准测试（Week 1）
- 用 100 并发测试 5 分钟
- 记录基准 QPS、响应时间、错误率

### 阶段 2：压力测试（Week 2）
- 逐步增加并发：500 → 1000 → 2000 → 5000
- 找到系统瓶颈点

### 阶段 3：对比测试（Week 3）
- 同时测试 Hash 和 Range 两种策略
- 对比不同场景下的性能表现
- 记录数据库负载（CPU、IO、连接数）

### 阶段 4：优化测试（Week 4）
- 根据瓶颈进行优化（索引、缓存、连接池）
- 重新测试验证效果

---

## 📦 依赖安装

```bash
# Python 依赖
pip install -r requirements.txt

# 或者手动安装
pip install pymysql locust redis pika fastapi uvicorn
```

创建 `requirements.txt`：

```
pymysql==1.1.0
locust==2.15.1
redis==5.0.1
pika==1.3.2
fastapi==0.104.1
uvicorn==0.24.0
```

---

## 🐛 常见问题

### 1. MySQL 连接失败
```bash
# 检查容器是否运行
docker-compose ps

# 查看 MySQL 日志
docker-compose logs mysql-main
```

### 2. 数据生成太慢
- 调整 `BATCH_SIZE` 参数（默认 1000）
- 减少生成数量（例如先生成 10,000 个用户测试）

### 3. Locust 压测连接失败
- 确保后端服务已启动
- 检查 `--host` 参数是否正确

---

## 📞 联系方式

如有问题，请联系：
- 同学 A: [邮箱/微信]
- 同学 B (你): [邮箱/微信]

---

## 📄 License

MIT




