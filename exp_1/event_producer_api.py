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
            # Initialize Redis stock
            redis_client.set('coupon:stock', result['remaining_stock'])
            print(f"✅ Stock initialized: {result['remaining_stock']} (loaded from MySQL)")
        else:
            # If no record in database, set default value
            redis_client.set('coupon:stock', 90000)
            cursor.execute("""
                INSERT INTO coupon_config (coupon_type, total_stock, remaining_stock)
                VALUES ('default', 90000, 90000)
            """)
            conn.commit()
            print("✅ Stock initialized: 90000 (default value)")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ MySQL initialization warning: {e}")
        print("Using existing value in Redis or default value")
    
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
    description="Coupon system using Redis atomic operations",
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
    Coupon grab API (using Redis atomic operations)
    """
    start_time = time.time()
    
    try:
        # ✅ Use Redis DECR atomic operation to decrement stock
        remaining = redis_client.decr('coupon:stock')
        
        if remaining >= 0:
            # Coupon grab successful
            success = True
            reason = 'success'
            current_stock = remaining
        else:
            # Out of stock, rollback
            redis_client.incr('coupon:stock')
            success = False
            reason = 'out_of_stock'
            current_stock = 0
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis error: {str(e)}")
    
    # Construct event
    event = {
        'service': 'Coupon',
        'event_type': 'coupon_grab',
        'user_id': request.user_id,
        'timestamp': time.time(),
        'success': success,
        'reason': reason,
        'remaining_stock': current_stock
    }
    
    # Filter logic
    if ENABLE_FILTER and not success:
        return {
            'success': False,
            'reason': reason,
            'message': 'Event filtered (not sent to queue)',
            'remaining_stock': current_stock,
            'latency_ms': (time.time() - start_time) * 1000
        }
    
    # Send to message queue
    try:
        rabbitmq_channel.basic_publish(
            exchange='',
            routing_key='event_queue',
            body=json.dumps(event),
            properties=pika.BasicProperties(
                delivery_mode=2  # Persistent message
            )
        )
    except Exception as e:
        # Send failed, rollback stock
        if success:
            redis_client.incr('coupon:stock')
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")
    
    latency = (time.time() - start_time) * 1000
    
    return {
        'success': success,
        'reason': reason,
        'remaining_stock': current_stock,
        'latency_ms': latency
    }

@app.post("/api/like")
async def like_action(request: LikeRequest):
    """Like API"""
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
    """Reset stock (reload from MySQL)"""
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        cursor = conn.cursor(dictionary=True)
        
        # Reset MySQL
        cursor.execute("""
            UPDATE coupon_config 
            SET remaining_stock = total_stock 
            WHERE coupon_type = 'default'
        """)
        
        # Reload to Redis
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
    """Get statistics"""
    try:
        # Redis stock
        redis_stock = redis_client.get('coupon:stock')
        redis_stock = int(redis_stock) if redis_stock else 0
        
        # RabbitMQ queue depth
        try:
            queue = rabbitmq_channel.queue_declare(queue='event_queue', passive=True)
            queue_depth = queue.method.message_count
        except:
            queue_depth = -1
        
        # MySQL stock
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
    """Manually sync Redis stock to MySQL"""
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
    ║  Features:                                             ║
    ║  ✅ Redis atomic operations (high concurrency safe)   ║
    ║  ✅ MySQL persistence (data not lost)                 ║
    ║  ✅ Multi-instance deployment (shared Redis)           ║
    ║  ✅ Load stock from MySQL on startup                  ║
    ╠════════════════════════════════════════════════════════╣
    ║  Start command:                                        ║
    ║  uvicorn event_producer_api_improved:app              ║
    ║    --reload --port 8000                               ║
    ║                                                        ║
    ║  API docs: http://localhost:8000/docs                 ║
    ╚════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run("event_producer_api_improved:app", host="0.0.0.0", port=8000, reload=True)