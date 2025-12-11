# event_producer_api_improved.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pika
import redis
import mysql.connector
import json
import time
import os
from contextlib import asynccontextmanager

# Configuration
ENABLE_FILTER = os.getenv('ENABLE_FILTER', 'false').lower() == 'true'
MYSQL_HOST = os.getenv('MYSQL_HOST', '127.0.0.1')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3307))
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'root123')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'event_system')

# Global variables
rabbitmq_connection = None
rabbitmq_channel = None
redis_client = None

# Pydantic models
class CouponGrabRequest(BaseModel):
    user_id: str

class LikeRequest(BaseModel):
    user_id: str

# Lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    global rabbitmq_connection, rabbitmq_channel, redis_client
    
    print("🚀 Initializing services...")
    
    # 1. Connect to Redis
    try:
        redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        redis_client.ping()
        print("✅ Redis connection successful!")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        raise
    
    # 2. Load stock from MySQL to Redis
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT remaining_stock FROM coupon_config WHERE coupon_type = 'default'")
        result = cursor.fetchone()
        
        if result:
            # 初始化 Redis 库存
            redis_client.set('coupon:stock', result['remaining_stock'])
            print(f"✅ 库存初始化: {result['remaining_stock']} (从 MySQL 加载)")
        else:
            # 如果数据库没有记录，设置默认值
            redis_client.set('coupon:stock', 90000)
            cursor.execute("""
                INSERT INTO coupon_config (coupon_type, total_stock, remaining_stock)
                VALUES ('default', 90000, 90000)
            """)
            conn.commit()
            print("✅ 库存初始化: 90000 (默认值)")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ MySQL 初始化警告: {e}")
        print("使用 Redis 中的现有值或默认值")
    
    # 3. Connect to RabbitMQ
    try:
        rabbitmq_connection = pika.BlockingConnection(
            pika.ConnectionParameters('localhost')
        )
        rabbitmq_channel = rabbitmq_connection.channel()
        rabbitmq_channel.queue_declare(queue='event_queue', durable=True)
        print("✅ RabbitMQ connection successful!")
    except Exception as e:
        print(f"❌ RabbitMQ connection failed: {e}")
        raise
    
    yield
    
    if rabbitmq_connection and not rabbitmq_connection.is_closed:
        rabbitmq_connection.close()
        print("🔌 RabbitMQ connection closed")

# Create FastAPI application
app = FastAPI(
    title="Event Producer API (Improved)",
    description="使用 Redis 原子操作的优惠券系统",
    version="2.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    try:
        current_stock = redis_client.get('coupon:stock')
        current_stock = int(current_stock) if current_stock else 0
    except:
        current_stock = 0
    
    return {
        "status": "running",
        "version": "2.0 (Redis Atomic)",
        "filter_enabled": ENABLE_FILTER,
        "remaining_stock": current_stock
    }

@app.post("/api/coupon/grab")
async def grab_coupon(request: CouponGrabRequest):
    """
    【实验三专用】慢速版 API：直接穿透到 MySQL
    没有 Redis，没有 MQ，只有数据库行锁。
    """
    start_time = time.time()
    
    # 建立数据库连接 (模拟每次请求建立连接的高开销)
    # 在高并发下，这很容易导致 "Too many connections"
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        conn.autocommit = False #以此开启事务
        cursor = conn.cursor(dictionary=True)
        
        # 1. 开启事务并加锁查询 (FOR UPDATE 是性能杀手)
        # 这行代码会让数据库锁住这一行，其他所有并发请求都在这里排队！
        cursor.execute("SELECT remaining_stock FROM coupon_config WHERE coupon_type = 'default' FOR UPDATE")
        result = cursor.fetchone()
        
        current_stock = result['remaining_stock'] if result else 0
        
        if current_stock > 0:
            # 2. 扣减库存
            cursor.execute("UPDATE coupon_config SET remaining_stock = remaining_stock - 1 WHERE coupon_type = 'default'")
            
            # 3. 记录日志 (直接写库)
            cursor.execute("""
                INSERT INTO coupon_events (user_id, event_type, success, reason, remaining_stock, timestamp)
                VALUES (%s, 'coupon_grab', 1, 'success', %s, %s)
            """, (request.user_id, current_stock - 1, time.time()))
            
            # 4. 提交事务
            conn.commit()
            success = True
            reason = 'success'
            remaining = current_stock - 1
        else:
            # 库存不足
            conn.rollback() # 释放锁
            success = False
            reason = 'out_of_stock'
            remaining = 0

    except mysql.connector.Error as e:
        if conn:
            conn.rollback()
        # 这里直接返回 500，模拟数据库撑不住的情况
        print(f"❌ DB Error: {e}")
        raise HTTPException(status_code=500, detail=f"Database overloaded: {str(e)}")
        
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # 关闭连接
        if cursor: cursor.close()
        if conn: conn.close()

    latency = (time.time() - start_time) * 1000
    
    return {
        'success': success,
        'reason': reason,
        'remaining_stock': remaining,
        'latency_ms': latency,
        'mode': 'direct_mysql_slow' # 标记这是慢速模式
    }

@app.post("/api/like")
async def like_action(request: LikeRequest):
    """点赞 API"""
    is_top_like = hash(request.user_id) % 10 == 0
    
    event = {
        'service': 'Like',
        'event_type': 'like',
        'user_id': request.user_id,
        'timestamp': time.time(),
        'is_top_like': is_top_like
    }
    
    if ENABLE_FILTER and not is_top_like:
        return {
            'success': True, 
            'filtered': True,
            'message': 'Normal like (not sent to queue)'
        }
    
    try:
        rabbitmq_channel.basic_publish(
            exchange='',
            routing_key='event_queue',
            body=json.dumps(event),
            properties=pika.BasicProperties(delivery_mode=2)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")
    
    return {
        'success': True, 
        'filtered': False,
        'is_top_like': is_top_like
    }

@app.post("/admin/reset")
async def reset_stock():
    """重置库存（从 MySQL 重新加载）"""
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        cursor = conn.cursor(dictionary=True)
        
        # 重置 MySQL
        cursor.execute("""
            UPDATE coupon_config 
            SET remaining_stock = total_stock 
            WHERE coupon_type = 'default'
        """)
        
        # 重新加载到 Redis
        cursor.execute("SELECT remaining_stock FROM coupon_config WHERE coupon_type = 'default'")
        result = cursor.fetchone()
        
        if result:
            redis_client.set('coupon:stock', result['remaining_stock'])
            stock = result['remaining_stock']
        else:
            stock = 0
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'message': 'Stock reset successfully',
            'stock': stock
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/stats")
async def get_stats():
    """获取统计信息"""
    try:
        # Redis 库存
        redis_stock = redis_client.get('coupon:stock')
        redis_stock = int(redis_stock) if redis_stock else 0
        
        # RabbitMQ 队列深度
        try:
            queue = rabbitmq_channel.queue_declare(queue='event_queue', passive=True)
            queue_depth = queue.method.message_count
        except:
            queue_depth = -1
        
        # MySQL 库存
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE
            )
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT remaining_stock FROM coupon_config WHERE coupon_type = 'default'")
            result = cursor.fetchone()
            mysql_stock = result['remaining_stock'] if result else 0
            cursor.close()
            conn.close()
        except:
            mysql_stock = -1
        
        return {
            'redis_stock': redis_stock,
            'mysql_stock': mysql_stock,
            'queue_depth': queue_depth,
            'filter_enabled': ENABLE_FILTER,
            'sync_needed': redis_stock != mysql_stock
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/sync-to-mysql")
async def sync_to_mysql():
    """手动同步 Redis 库存到 MySQL"""
    try:
        redis_stock = redis_client.get('coupon:stock')
        redis_stock = int(redis_stock) if redis_stock else 0
        
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE coupon_config 
            SET remaining_stock = %s 
            WHERE coupon_type = 'default'
        """, (redis_stock,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'message': 'Synced to MySQL',
            'stock': redis_stock
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    import uvicorn
    
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║     Event Producer API v2.0 (Redis Atomic)            ║
    ╠════════════════════════════════════════════════════════╣
    ║  特性:                                                 ║
    ║  ✅ Redis 原子操作（高并发安全）                        ║
    ║  ✅ MySQL 持久化（数据不丢失）                          ║
    ║  ✅ 多实例部署（共享 Redis）                            ║
    ║  ✅ 启动时从 MySQL 加载库存                             ║
    ╠════════════════════════════════════════════════════════╣
    ║  启动命令:                                             ║
    ║  uvicorn event_producer_api_improved:app               ║
    ║    --reload --port 8000                                ║
    ║                                                        ║
    ║  API 文档: http://localhost:8000/docs                  ║
    ╚════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run("event_producer_api_improved:app", host="0.0.0.0", port=8000, reload=True)