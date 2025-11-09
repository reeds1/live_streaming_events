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
COUPON_STOCK = 10
ENABLE_FILTER = os.getenv('ENABLE_FILTER', 'false').lower() == 'true'

# Global variables
current_stock = COUPON_STOCK
stock_lock = threading.Lock()
rabbitmq_connection = None
rabbitmq_channel = None

# Pydantic models (define request body format)
class CouponGrabRequest(BaseModel):
    user_id: str

class LikeRequest(BaseModel):
    user_id: str

# Lifecycle management: connect to RabbitMQ on startup, disconnect on shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Execute on startup
    global rabbitmq_connection, rabbitmq_channel
    
    print("🚀 Connecting to RabbitMQ...")
    try:
        rabbitmq_connection = pika.BlockingConnection(
            pika.ConnectionParameters('localhost')
        )
        rabbitmq_channel = rabbitmq_connection.channel()
        rabbitmq_channel.queue_declare(queue='event_queue')
        print("✅ RabbitMQ connection successful!")
    except Exception as e:
        print(f"❌ RabbitMQ connection failed: {e}")
        print("Please ensure RabbitMQ is running:")
        print("docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management")
        raise
    
    yield  # Application is running
    
    # Execute on shutdown
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

# ============================================================
# API Endpoints
# ============================================================

@app.get("/")
async def root():
    """Health check and status view"""
    return {
        "status": "running",
        "filter_enabled": ENABLE_FILTER,
        "remaining_stock": current_stock
    }

@app.post("/api/coupon/grab")
async def grab_coupon(request: CouponGrabRequest):
    """
    Coupon grab API
    
    - **user_id**: User ID
    """
    global current_stock
    
    start_time = time.time()
    
    # Simulate business logic: check inventory
    with stock_lock:
        if current_stock > 0:
            current_stock -= 1
            success = True
            reason = 'success'
        else:
            success = False
            reason = 'out_of_stock'
    
    # Create event
    event = {
        'service': 'Coupon',
        'event_type': 'coupon_grab',
        'user_id': request.user_id,
        'timestamp': time.time(),
        'success': success,
        'reason': reason,
        'remaining_stock': current_stock
    }
    
    # Key: filtering logic
    if ENABLE_FILTER and not success:
        # With filter: failed events are not sent to queue
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
            body=json.dumps(event)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to send message to queue: {str(e)}"
        )
    
    latency = (time.time() - start_time) * 1000  # ms
    
    return {
        'success': success,
        'reason': reason,
        'remaining_stock': current_stock,
        'latency_ms': latency
    }

@app.post("/api/like")
async def like_action(request: LikeRequest):
    """
    Like action API
    
    - **user_id**: User ID
    """
    # Simulate: only 1% of likes are "top likes"
    is_top_like = hash(request.user_id) % 100 == 0
    
    event = {
        'service': 'Like',
        'event_type': 'like',
        'user_id': request.user_id,
        'timestamp': time.time(),
        'is_top_like': is_top_like
    }
    
    # Filtering logic
    if ENABLE_FILTER and not is_top_like:
        return {
            'success': True, 
            'filtered': True,
            'message': 'Normal like (not sent to queue)'
        }
    
    # Send to message queue
    try:
        rabbitmq_channel.basic_publish(
            exchange='',
            routing_key='event_queue',
            body=json.dumps(event)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send message to queue: {str(e)}"
        )
    
    return {
        'success': True, 
        'filtered': False,
        'is_top_like': is_top_like
    }

@app.post("/admin/reset")
async def reset_stock():
    """Reset inventory (for testing)"""
    global current_stock
    current_stock = COUPON_STOCK
    return {
        'message': 'Stock reset successfully',
        'stock': current_stock
    }

@app.get("/admin/stats")
async def get_stats():
    """Get current statistics"""
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

# ============================================================
# Startup Instructions
# ============================================================
if __name__ == '__main__':
    import uvicorn
    
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║          Event Producer API (FastAPI)                  ║
    ╠════════════════════════════════════════════════════════╣
    ║  Start command:                                        ║
    ║  uvicorn event_producer_api:app --reload --port 5000   ║
    ║                                                        ║
    ║  Enable filtering:                                     ║
    ║  ENABLE_FILTER=true uvicorn event_producer_api:app    ║
    ║    --reload --port 5000                                ║
    ║                                                        ║
    ║  API Documentation:                                    ║
    ║  http://localhost:5000/docs                            ║
    ╚════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "event_producer_api:app",
        host="0.0.0.0",
        port=5000,
        reload=True
    )