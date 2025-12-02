# event_producer_api.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pika
import json
import time
import threading
import os
from contextlib import asynccontextmanager

# Configuration
COUPON_STOCK = 90000
ENABLE_FILTER = os.getenv('ENABLE_FILTER', 'false').lower() == 'true'

# Global variables
current_stock = COUPON_STOCK
stock_lock = threading.Lock()
rabbitmq_connection = None
rabbitmq_channel = None

# Pydantic models
class CouponGrabRequest(BaseModel):
    user_id: str

class LikeRequest(BaseModel):
    user_id: str

# Lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    global rabbitmq_connection, rabbitmq_channel
    
    print("🚀 Connecting to RabbitMQ...")
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
    title="Event Producer API",
    description="Coupon grab and like event producer",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    return {
        "status": "running",
        "filter_enabled": ENABLE_FILTER,
        "remaining_stock": current_stock
    }

@app.post("/api/coupon/grab")
async def grab_coupon(request: CouponGrabRequest):
    global current_stock
    
    start_time = time.time()
    
    with stock_lock:
        if current_stock > 0:
            current_stock -= 1
            success = True
            reason = 'success'
        else:
            success = False
            reason = 'out_of_stock'
    
    event = {
        'service': 'Coupon',
        'event_type': 'coupon_grab',
        'user_id': request.user_id,
        'timestamp': time.time(),
        'success': success,
        'reason': reason,
        'remaining_stock': current_stock
    }
    
    if ENABLE_FILTER and not success:
        return {
            'success': False,
            'reason': reason,
            'message': 'Event filtered (not sent to queue)',
            'remaining_stock': current_stock,
            'latency_ms': (time.time() - start_time) * 1000
        }
    
    try:
        rabbitmq_channel.basic_publish(
            exchange='',
            routing_key='event_queue',
            body=json.dumps(event)
        )
    except Exception as e:
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
            body=json.dumps(event)
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
    global current_stock
    current_stock = COUPON_STOCK
    return {
        'message': 'Stock reset successfully',
        'stock': current_stock
    }

@app.get("/admin/stats")
async def get_stats():
    try:
        queue = rabbitmq_channel.queue_declare(queue='event_queue', passive=True)
        queue_depth = queue.method.message_count
    except:
        queue_depth = -1
    
    return {
        'remaining_stock': current_stock,
        'queue_depth': queue_depth,
        'filter_enabled': ENABLE_FILTER
    }

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("event_producer_api:app", host="0.0.0.0", port=5000, reload=True)