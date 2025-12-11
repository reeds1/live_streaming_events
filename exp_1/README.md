# Live Streaming Events System

A microservices-based event processing system for live streaming activities, supporting high-concurrency coupon grabbing and like functionality.

## 📋 Project Overview

This system is designed to handle real-time events during live streaming activities, including:
- **Coupon Grabbing**: High-concurrency coupon grabbing with Redis atomic operations to ensure inventory consistency
- **Like Functionality**: Records user like behaviors with support for top likes filtering
- **Event Processing**: Asynchronous event processing architecture based on message queues
- **Data Persistence**: Redis caching + MySQL persistent storage

## 🏗️ System Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Producer  │─────▶│  RabbitMQ    │─────▶│  Consumer   │
│     API     │      │ (Message Q)  │      │ (Processor) │
└─────────────┘      └──────────────┘      └──────┬──────┘
                                                   │
                              ┌────────────────────┼────────────────────┐
                              │                    │                    │
                         ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
                         │  Redis  │         │  MySQL  │         │ Query   │
                         │ (Cache) │         │(Storage)│         │   API   │
                         └─────────┘         └─────────┘         └─────────┘
```

### Core Components

1. **Event Producer API** (`event_producer_api.py`)
   - Handles coupon grab requests
   - Uses Redis atomic operations (DECR) to ensure inventory consistency
   - Supports optional event filtering
   - Publishes events to RabbitMQ queue

2. **Event Consumer** (`event_consumer.py`)
   - Consumes events from RabbitMQ
   - Updates Redis cache (fast response)
   - Persists to MySQL (data durability)
   - Supports connection pooling optimization

3. **Query API** (`query_api.py`)
   - Provides user statistics queries
   - Supports Redis cache-first queries
   - Falls back to MySQL as data source

4. **Event Producer SQL API** (`event_producer_sql_api.py`)
   - Direct MySQL version (slower performance)
   - Used for performance comparison experiments

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.8+
- MySQL 8.0
- Redis 7
- RabbitMQ 3

### Using Docker Compose

1. **Start all services**

```bash
cd exp_1
docker-compose up -d
```

This will start the following services:
- RabbitMQ (port 5672, management UI 15672)
- Redis (port 6379)
- MySQL (port 3306)
- Producer API (port 5000)
- Consumer service
- Query API (port 5001)

2. **Check service status**

```bash
docker-compose ps
```

3. **View logs**

```bash
# View all service logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f producer
docker-compose logs -f consumer
docker-compose logs -f query-api
```

### Local Development Environment

1. **Install dependencies**

```bash
pip install -r requirements.txt
```

2. **Start infrastructure services**

```bash
# Start only infrastructure services with Docker Compose
docker-compose up -d rabbitmq redis mysql
```

3. **Start application services**

```bash
# Terminal 1: Start Producer API
uvicorn event_producer_api:app --reload --port 5000

# Terminal 2: Start Consumer
python event_consumer.py

# Terminal 3: Start Query API
uvicorn query_api:app --reload --port 5001
```

## 📡 API Documentation

### Producer API (Port 5000)

#### 1. Grab Coupon

```bash
POST /api/coupon/grab
Content-Type: application/json

{
  "user_id": "user123"
}
```

**Response example:**
```json
{
  "success": true,
  "reason": "success",
  "remaining_stock": 89999,
  "latency_ms": 5.2
}
```

#### 2. Like Action

```bash
POST /api/like
Content-Type: application/json

{
  "user_id": "user123"
}
```

#### 3. Reset Stock

```bash
POST /admin/reset
```

#### 4. Get Statistics

```bash
GET /admin/stats
```

### Query API (Port 5001)

#### 1. Get User Statistics

```bash
GET /user/{user_id}/stats
```

**Response example:**
```json
{
  "user_id": "user123",
  "source": "redis",
  "coupon_stats": {
    "total_attempts": 10,
    "successful_grabs": 5,
    "failed_grabs": 5
  },
  "like_count": 3
}
```

#### 2. Get User Coupons

```bash
GET /user/{user_id}/coupons
```

#### 3. Get User History

```bash
GET /user/{user_id}/history?limit=50&event_type=coupon
```

#### 4. Get System Statistics

```bash
GET /system/stats
```

#### 5. Get Top Likes

```bash
GET /top-likes?limit=10
```

### Interactive API Documentation

After starting the services, visit the following URLs for interactive API documentation:

- Producer API: http://localhost:5000/docs
- Query API: http://localhost:5001/docs

## 🔧 Configuration

### Environment Variables

#### Producer API

- `RABBITMQ_HOST`: RabbitMQ host address (default: localhost)
- `ENABLE_FILTER`: Enable event filtering (default: false)
- `MYSQL_HOST`: MySQL host address (default: 127.0.0.1)
- `MYSQL_PORT`: MySQL port (default: 3307)
- `MYSQL_USER`: MySQL username (default: root)
- `MYSQL_PASSWORD`: MySQL password (default: root123)
- `MYSQL_DATABASE`: MySQL database name (default: event_system)

#### Consumer

- `RABBITMQ_HOST`: RabbitMQ host address (default: localhost)
- `REDIS_HOST`: Redis host address (default: localhost)
- `REDIS_PORT`: Redis port (default: 6379)
- `MYSQL_HOST`: MySQL host address (default: 127.0.0.1)
- `MYSQL_PORT`: MySQL port (default: 3307)
- `MYSQL_USER`: MySQL username (default: root)
- `MYSQL_PASSWORD`: MySQL password (default: root123)
- `MYSQL_DATABASE`: MySQL database name (default: event_system)

#### Query API

- `REDIS_HOST`: Redis host address (default: localhost)
- `MYSQL_HOST`: MySQL host address (default: 127.0.0.1)
- `MYSQL_PORT`: MySQL port (default: 3307)
- `MYSQL_USER`: MySQL username (default: root)
- `MYSQL_PASSWORD`: MySQL password (default: root123)
- `MYSQL_DATABASE`: MySQL database name (default: event_system)

### Docker Compose Configuration

In `docker-compose.yml`, you can modify:
- Service port mappings
- Database passwords
- RabbitMQ management UI credentials

## 🗄️ Database Schema

### Table Structure

1. **coupon_events**: Coupon grab event logs
   - `user_id`: User ID
   - `event_type`: Event type
   - `success`: Success status
   - `reason`: Reason
   - `remaining_stock`: Remaining stock
   - `timestamp`: Timestamp

2. **like_events**: Like event logs
   - `user_id`: User ID
   - `event_type`: Event type
   - `is_top_like`: Whether it's a top like
   - `timestamp`: Timestamp

3. **user_coupon_stats**: User coupon statistics
   - `user_id`: User ID (primary key)
   - `total_attempts`: Total attempts
   - `successful_grabs`: Successful grabs
   - `failed_grabs`: Failed attempts
   - `last_attempt_time`: Last attempt time

4. **coupon_config**: Coupon configuration
   - `coupon_type`: Coupon type (primary key)
   - `total_stock`: Total stock
   - `remaining_stock`: Remaining stock

## 🔍 Core Features

### 1. High-Concurrency Inventory Management

- Uses Redis `DECR` atomic operation to ensure inventory consistency
- Supports multi-instance deployment (shared Redis)
- Loads inventory from MySQL to Redis on startup

### 2. Asynchronous Event Processing

- Uses RabbitMQ to decouple producers and consumers
- Supports message persistence
- Consumer supports connection pooling optimization

### 3. Caching Strategy

- Redis as hot data cache
- MySQL as persistent storage
- Query API prioritizes Redis queries, falls back to MySQL

### 4. Event Filtering

- Optional filtering mechanism to reduce unnecessary messages
- Failed events can be optionally excluded from the queue

## 🧪 Testing

### Using curl

```bash
# Test coupon grab
curl -X POST http://localhost:5000/api/coupon/grab \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user_1"}'

# Test like
curl -X POST http://localhost:5000/api/like \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user_1"}'

# Query user statistics
curl http://localhost:5001/user/test_user_1/stats
```

### Load Testing

You can use Locust or other load testing tools for performance testing.

## 📊 Monitoring and Management

### RabbitMQ Management UI

Access http://localhost:15672
- Username: `admin`
- Password: `admin123`

You can view:
- Queue depth
- Message rate
- Connection status

### System Statistics

```bash
# Get system statistics
curl http://localhost:5000/admin/stats
curl http://localhost:5001/system/stats
```

## 🛠️ Troubleshooting

### Common Issues

1. **Connection Failures**
   - Check if services are running: `docker-compose ps`
   - Check if ports are occupied
   - View service logs: `docker-compose logs [service_name]`

2. **Inventory Desynchronization**
   - Use `/admin/sync-to-mysql` to manually sync
   - Check Redis and MySQL connections

3. **Message Queue Backlog**
   - Check if Consumer is running normally
   - Increase the number of Consumer instances
   - Check database performance

### Viewing Logs

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f producer
docker-compose logs -f consumer
```

## 📦 Dependencies

Main dependencies (see `requirements.txt`):

- `fastapi==0.109.0`: Web framework
- `uvicorn[standard]==0.27.0`: ASGI server
- `pydantic==2.5.3`: Data validation
- `pika==1.3.2`: RabbitMQ client
- `redis==5.0.1`: Redis client
- `mysql-connector-python==8.3.0`: MySQL connector

## 🔐 Security Considerations

⚠️ **Before deploying to production, please modify:**

- Database passwords
- RabbitMQ management UI passwords
- Service ports (if needed)
- Add authentication and authorization mechanisms
- Configure HTTPS
- Set up firewall rules

## 📝 Version History

- **v2.0.0**: Redis Atomic Operations Version
  - Uses Redis DECR to ensure inventory consistency
  - Supports multi-instance deployment
  - Optimized event processing flow

## 🤝 Contributing

Issues and Pull Requests are welcome!

## 📄 License

This project is for learning and research purposes.

---

**Note**: This is an experimental project for demonstrating high-concurrency event processing system design. Please conduct thorough security and performance testing before using in production.
