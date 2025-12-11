# 📦 共同部分交付指南

> **交付人**：同学 B (你)  
> **接收人**：同学 A  
> **交付日期**：2025-12-04

---

## 📋 交付内容清单

### ✅ 已完成的文件

| 文件名 | 用途 | 重要程度 |
|--------|------|----------|
| `database_schema.sql` | 数据库表结构定义 | ⭐⭐⭐⭐⭐ |
| `data_seeder.py` | 测试数据生成器 | ⭐⭐⭐⭐⭐ |
| `locustfile_advanced.py` | 高级压测脚本 | ⭐⭐⭐⭐⭐ |
| `docker-compose.yml` | Docker 环境配置 | ⭐⭐⭐⭐⭐ |
| `sharding_interface.py` | 分片策略接口定义 | ⭐⭐⭐⭐⭐ |
| `requirements.txt` | Python 依赖列表 | ⭐⭐⭐⭐ |
| `quick_start.sh` | 一键启动脚本 | ⭐⭐⭐⭐ |
| `README.md` | 共同部分文档 | ⭐⭐⭐⭐ |

---

## 🎯 核心设计决策

### 1. 数据库 Schema

#### 核心表：`coupon_results`

这是系统最重要的表，专门设计为**同时支持两种分片策略**：

```sql
CREATE TABLE coupon_results (
    result_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,          -- 👈 Hash 分片的 key
    coupon_id BIGINT NOT NULL,
    room_id BIGINT NOT NULL,          -- 👈 Range 分片的 key (按直播间)
    grab_status TINYINT NOT NULL,
    fail_reason VARCHAR(50),
    grab_time TIMESTAMP DEFAULT NOW,  -- 👈 Range 分片的 key (按时间)
    use_status TINYINT DEFAULT 0,
    
    -- Hash 分片需要的索引
    INDEX idx_user_id (user_id),
    INDEX idx_user_coupon (user_id, coupon_id),
    INDEX idx_user_time (user_id, grab_time),
    
    -- Range 分片需要的索引
    INDEX idx_room_id (room_id),
    INDEX idx_grab_time (grab_time),
    INDEX idx_room_time (room_id, grab_time)
);
```

**设计亮点**：
- ✅ 冗余了 `room_id` 字段（虽然可以通过 JOIN 获取，但为了性能直接存储）
- ✅ 索引覆盖了两种策略的所有查询需求
- ✅ 预留了 `fail_reason` 和 `use_status` 等业务字段

#### 其他表

- `users`：用户表（10万条数据）
- `live_rooms`：直播间表（100个，含5个热门直播间）
- `coupons` + `coupon_details`：演示了**垂直分表**（同学 B 的任务之一）
- `stock_logs`：库存日志（可选）

---

### 2. 数据生成器

#### 生成规模
- 👥 **100,000 个用户**（user_id: 1 - 100000）
- 🏠 **100 个直播间**（room_id: 1 - 100，前5个是热门）
- 🎟️ **500 个优惠券**（coupon_id: 1 - 500）

#### 数据特点
- 热门直播间（room_id 1-5）的优惠券库存更多（5000-20000 张）
- 普通直播间的优惠券库存较少（500-5000 张）
- 用户等级分布：70% 普通用户，25% VIP，5% SVIP

#### 使用方法
```bash
python data_seeder.py
```

**注意**：会先清空所有表，然后重新生成数据（耗时约 2-5 分钟）。

---

### 3. Locust 压测脚本

#### 4 种测试场景

| 场景 | 权重 | 用途 |
|-----|------|------|
| **NormalCouponUser** | 5 | 普通用户随机抢券 |
| **HotRoomUser** | 3 | 集中抢热门直播间（测试热点） |
| **CrossShardQueryUser** | 1 | 跨分片查询（测试聚合性能） |
| **AdminUser** | 1 | 管理员查询 |

#### 关键 API 端点

你们需要实现这些 API：

```python
# 写操作
POST /api/coupon/grab              # 抢券
  body: {"user_id": 123, "coupon_id": 456, "room_id": 1001}

# 读操作（不同策略的性能差异）
GET /api/user/{user_id}/coupons           # 查询用户优惠券 (Hash 快)
GET /api/room/{room_id}/orders            # 查询直播间订单 (Range 快)
GET /api/orders/recent?hours=1            # 时间范围查询 (Range 快)
GET /api/statistics/global                # 全局统计 (都慢，需要聚合)

# 管理接口
GET /admin/stats                          # 系统统计
GET /admin/shards/status                  # 分片状态
```

---

### 4. Docker 环境

#### 启动的服务

```yaml
服务列表：
- mysql-main:       MySQL 主库 (端口 3306)
- mysql-shard-0~3:  MySQL 分片 0-3 (端口 3307-3310)  👈 给同学 A 用
- redis:            Redis 缓存 (端口 6379)
- rabbitmq:         RabbitMQ 消息队列 (端口 5672, 管理界面 15672)
- phpmyadmin:       数据库管理工具 (端口 8080)
- redisinsight:     Redis 管理工具 (端口 8081)
```

#### 一键启动

```bash
cd shared
docker-compose up -d
```

---

### 5. 分片接口定义

#### 核心接口：`ShardingStrategy`

```python
class ShardingStrategy(ABC):
    @abstractmethod
    def save_coupon_result(self, coupon_result: CouponResult) -> bool:
        """保存抢券结果 - 核心方法！"""
        pass
    
    @abstractmethod
    def query_user_coupons(self, user_id: int) -> List[CouponResult]:
        """查询用户优惠券 - Hash 擅长"""
        pass
    
    @abstractmethod
    def query_room_orders(self, room_id: int) -> List[CouponResult]:
        """查询直播间订单 - Range 擅长（如果按 room_id 分片）"""
        pass
    
    @abstractmethod
    def query_time_range_orders(self, start_time, end_time) -> List[CouponResult]:
        """时间范围查询 - Range 擅长（如果按时间分片）"""
        pass
```

#### 使用方式

```python
# 同学 A 的实现
class HashShardingStrategy(ShardingStrategy):
    def save_coupon_result(self, coupon_result: CouponResult) -> bool:
        shard_id = hash(coupon_result.user_id) % 4
        # 写入对应的分片...

# 同学 B 的实现（你）
class RangeShardingStrategy(ShardingStrategy):
    def save_coupon_result(self, coupon_result: CouponResult) -> bool:
        table_name = f"coupon_results_{coupon_result.grab_time.date()}"
        # 写入对应的分片表...
```

---

## 🚀 快速开始指南（给同学 A）

### Step 1: 克隆/拉取代码

```bash
cd "live_streaming_events/shared"
```

### Step 2: 一键启动环境

```bash
chmod +x quick_start.sh
./quick_start.sh
```

这个脚本会自动：
1. ✅ 检查依赖（Docker、Python）
2. ✅ 安装 Python 包
3. ✅ 启动 Docker 服务（MySQL、Redis、RabbitMQ）
4. ✅ 导入数据库 Schema
5. ✅ 生成测试数据（可选）

### Step 3: 验证环境

```bash
# 查看 Docker 服务状态
docker-compose ps

# 测试 MySQL 连接
mysql -h 127.0.0.1 -P 3306 -uroot -ppassword coupon_system -e "SHOW TABLES;"

# 测试 Redis
redis-cli ping

# 测试 RabbitMQ
curl http://localhost:15672/
```

### Step 4: 开始开发

1. 阅读 `sharding_interface.py` 了解接口定义
2. 实现你的 `HashShardingStrategy` 类
3. 参考 `locustfile_advanced.py` 了解需要实现的 API

---

## 📊 性能测试指标（给同学 A 参考）

### 你需要关注的指标

| 指标 | 说明 | 如何获取 |
|-----|------|---------|
| **Write QPS** | 每秒写入次数 | Locust 报告 |
| **数据分布** | 各分片数据量 | `SELECT COUNT(*) FROM coupon_results` |
| **跨分片查询时间** | 聚合查询耗时 | `/api/room/:id/orders` 的 P95 |
| **分片 CPU/IO** | 各分片负载 | `docker stats` 或 Prometheus |

### Hash 分片的预期表现

✅ **优势**：
- 4 个分片的写入 QPS 应该基本相同（误差 < 10%）
- 数据量分布均匀
- 按 `user_id` 查询非常快

⚠️ **劣势**：
- 按 `room_id` 查询需要扫描所有分片（慢）
- 按时间范围查询需要扫描所有分片（慢）

---

## 🎯 你（同学 B）的下一步

### Range 分片实现方案

#### 方案 1：按时间分片（推荐）

```python
# 分表结构
coupon_results_2025_12_01
coupon_results_2025_12_02
coupon_results_2025_12_03
...

# 路由逻辑
def get_table_name(grab_time: datetime) -> str:
    return f"coupon_results_{grab_time.strftime('%Y_%m_%d')}"
```

**优势**：
- ✅ 时间范围查询极快
- ✅ 数据归档方便（可以直接删除旧表）

**劣势**：
- ⚠️ 查询某个用户的优惠券需要扫描多张表
- ⚠️ 当天的表可能成为热点

#### 方案 2：按直播间分片

```python
# 分表结构
coupon_results_room_1_1000      # room_id: 1-1000
coupon_results_room_1001_2000   # room_id: 1001-2000
...

# 路由逻辑
def get_table_name(room_id: int) -> str:
    shard_id = (room_id - 1) // 1000
    return f"coupon_results_room_{shard_id*1000+1}_{(shard_id+1)*1000}"
```

**优势**：
- ✅ 查询某个直播间的订单极快
- ✅ 业务逻辑清晰

**劣势**：
- ⚠️ 热门直播间（room_id 1-5）会成为热点
- ⚠️ 时间范围查询需要扫描多张表

#### 建议

我建议你**按时间分片**，因为：
1. 更能展示 Range 分片的优势（时间范围查询）
2. 热点问题更明显（方便做优化和对比）
3. 符合直播抢券的实际业务场景（按日结算）

---

## 🛠️ 垂直分表（Vertical Partitioning）

这是你（同学 B）的额外任务，已经在 Schema 中实现了：

```sql
-- 主表：只保留核心字段
CREATE TABLE coupons (
    coupon_id, room_id, coupon_name, 
    total_stock, remaining_stock, ...
);

-- 详情表：大字段拆出去
CREATE TABLE coupon_details (
    coupon_id,
    description TEXT,      -- 大字段
    usage_rules TEXT,      -- 大字段
    product_range TEXT     -- 大字段
);
```

**演示效果**：
- 查询优惠券列表时，只查 `coupons` 表，速度快
- 查看优惠券详情时，才 JOIN `coupon_details` 表

---

## 📞 协作方式

### 接口对接

你们两人需要实现**相同的 REST API**，这样可以直接对比测试：

```
POST /api/coupon/grab
GET  /api/user/:id/coupons
GET  /api/room/:id/orders
GET  /api/orders/recent
GET  /admin/stats
GET  /admin/shards/status
```

### 代码结构建议

```
live_streaming_events/
├── shared/              # 共同部分（已完成）
├── student_a_hash/      # 同学 A 的代码
│   ├── hash_strategy.py
│   ├── api_server.py
│   └── README.md
└── student_b_range/     # 你的代码
    ├── range_strategy.py
    ├── api_server.py
    └── README.md
```

### 测试流程

```bash
# 测试同学 A 的实现
locust -f shared/locustfile_advanced.py --host=http://localhost:8001

# 测试同学 B 的实现
locust -f shared/locustfile_advanced.py --host=http://localhost:8002

# 对比结果
python benchmark/compare_results.py
```

---

## ✅ 检查清单（给同学 A）

在收到这个包后，请检查：

- [ ] 所有文件都存在（8 个文件）
- [ ] `quick_start.sh` 可以执行
- [ ] Docker 服务可以启动
- [ ] MySQL 有 6 个实例（1 个主库 + 4 个分片 + phpMyAdmin 可连接）
- [ ] 数据生成器可以运行
- [ ] Locust 脚本可以加载
- [ ] 理解了 `ShardingStrategy` 接口

---

## 📝 FAQ

### Q1: 为什么要创建 4 个 MySQL 分片？
**A**: 这是为同学 A 的 Hash 分片准备的。你（同学 B）不一定需要用，但保持环境一致方便对比。

### Q2: 数据量为什么是 10 万用户？
**A**: 这是一个合适的测试规模：
- 数据量足够大，能体现分片效果
- 数据量不太大，生成速度快（2-5 分钟）
- 如果需要更大规模，修改 `data_seeder.py` 中的 `NUM_USERS` 即可

### Q3: Locust 压测要跑多久？
**A**: 建议：
- 基准测试：100 并发，5 分钟
- 压力测试：1000 并发，10 分钟
- 极限测试：5000 并发，直到出现错误

### Q4: 我可以修改这些文件吗？
**A**: 可以！这些只是基础版本，你们可以：
- 调整数据量
- 增加测试场景
- 优化数据库配置
- 添加更多监控指标

---

## 🎉 总结

你已经完成了共同部分的所有工作！这个基础非常扎实，包括：

✅ **完整的数据库设计**（支持两种分片策略）  
✅ **10 万级别的测试数据**（贴近真实场景）  
✅ **专业的压测环境**（4 种测试场景）  
✅ **一键启动脚本**（降低环境搭建难度）  
✅ **清晰的接口定义**（方便两人协作）  

现在可以把 `shared/` 文件夹打包给同学 A 了！

---

**Good luck! 加油！💪**

有任何问题随时沟通。




