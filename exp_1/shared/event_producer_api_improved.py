from fastapi import FastAPI, HTTPException, Response # 👈 确保引入了 Response
from pydantic import BaseModel
import pika
import redis
import json
import time
import os
import sys

# ============================================================
# 1. 基础配置与路径
# ============================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
strategies_dir = os.path.join(current_dir, 'hash_vs_range_comparison', 'strategies')
sys.path.append(strategies_dir)

# ============================================================
# ✅ 2. 【关键修正】全局直接初始化 Redis
# ============================================================
print("🚀 System Starting: Initializing Redis...")
try:
    # 直接在这里连接，不要放在函数里
    redis_client = redis.Redis(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        decode_responses=True
    )
    redis_client.ping()
    print("✅ Redis connection successful!")
except Exception as e:
    print(f"❌ Redis connection failed: {e}")
    redis_client = None  # 标记为 None，后续报错处理

# Global variables for others
rabbitmq_connection = None
rabbitmq_channel = None
coupon_service = None

# ============================================================
# 3. 导入业务模块 (AWS & Strategy)
# ============================================================
try:
    from hash_vs_range_comparison.strategies.database_aws import connection_pool_aws
    from hash_strategy_aws import HashShardingStrategyAWS
    from cached_coupon_service import CachedCouponService
except ImportError as e:
    print(f"⚠️ Import Error (AWS/Strategy modules not found): {e}")
    CachedCouponService = None

# Models
class CouponGrabRequest(BaseModel):
    user_id: str
    coupon_id: int
    room_id: int

class LikeRequest(BaseModel):
    user_id: str

# ============================================================
# 4. FastAPI App 定义
# ============================================================
app = FastAPI(title="Event Producer API", version="3.2.0")

# 使用 startup 事件钩子 (比 lifespan 兼容性更好)
@app.on_event("startup")
async def startup_event():
    global rabbitmq_connection, rabbitmq_channel, coupon_service
    
    print("🚀 App Startup: Connecting to dependencies...")
    
    # 1. 初始化 AWS RDS
    if connection_pool_aws.initialize():
        print("✅ AWS RDS connection pool initialized!")
        if CachedCouponService:
            aws_strategy = HashShardingStrategyAWS(num_shards=4)
            coupon_service = CachedCouponService('localhost', aws_strategy)
            print("✅ Query Service Ready")
    
    # 2. 连接 RabbitMQ
    try:
        rabbitmq_connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        rabbitmq_channel = rabbitmq_connection.channel()
        rabbitmq_channel.queue_declare(queue='event_queue', durable=True)
        print("✅ RabbitMQ connection successful!")
    except Exception as e:
        print(f"❌ RabbitMQ failed: {e}")
    
    coupon_service = CachedCouponService(
        redis_host=os.getenv('REDIS_HOST', 'localhost'),
        strategy=aws_strategy
    )
    print("✅ Service Ready!")

@app.on_event("shutdown")
async def shutdown_event():
    if rabbitmq_connection: rabbitmq_connection.close()
    connection_pool_aws.close_all()
    print("🛑 Services shut down")

# ============================================================
# 5. API 接口
# ============================================================

@app.get("/")
async def root():
    return {"status": "ok", "redis": "connected" if redis_client else "failed"}

@app.post("/api/coupon/grab")
async def grab_coupon(request: CouponGrabRequest):
    # ✅ 检查 Redis 是否就绪
    if not redis_client:
        raise HTTPException(status_code=500, detail="Redis client is not initialized")

    start_time = time.time()
    redis_key = f"coupon:{request.coupon_id}:stock"
    
    try:
        # 这里的 redis_client 一定有值了
        remaining = redis_client.decr(redis_key)
        
        if remaining >= 0:
            success = True
            reason = 'success'
            current_stock = remaining
        else:
            redis_client.incr(redis_key)
            success = False
            reason = 'out_of_stock'
            current_stock = 0
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis error: {str(e)}")
    
    # 构造事件
    event = {
        'service': 'Coupon',
        'event_type': 'coupon_grab',
        'user_id': request.user_id,
        'coupon_id': request.coupon_id,
        'room_id': request.room_id,
        'timestamp': time.time(),
        'success': success,
        'reason': reason,
        'remaining_stock': current_stock
    }
    
    # 发送 MQ
    try:
        if rabbitmq_channel:
            rabbitmq_channel.basic_publish(
                exchange='',
                routing_key='event_queue',
                body=json.dumps(event),
                properties=pika.BasicProperties(delivery_mode=2)
            )
        else:
            print("⚠️ MQ not connected, event lost")
    except Exception as e:
        if success: redis_client.incr(redis_key)
        raise HTTPException(status_code=500, detail=f"MQ Error: {str(e)}")
    
    return {
        'success': success,
        'reason': reason,
        'remaining_stock': current_stock,
        'latency_ms': (time.time() - start_time) * 1000
    }

@app.get("/api/coupons/{user_id}")
def get_user_coupons(user_id: int, response: Response):
    """
    Locust 压测专用接口
    """
    if not coupon_service:
        raise HTTPException(status_code=500, detail="Service not ready")
    
    try:
        # ✅ 正确处理元组返回值
        data, is_hit = coupon_service.get_user_coupons(user_id)
        
        # ✅ 设置 Header 给 Locust 看
        if is_hit:
            response.headers["X-Cache"] = "HIT"
        else:
            response.headers["X-Cache"] = "MISS"
            
        return {"code": 0, "data": data}
        
    except Exception as e:
        # 打印报错堆栈，方便你看 Locust log
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/reset")
async def reset_stock():
    # 简单的库存重置逻辑
    if not redis_client: return {"error": "No Redis"}
    # 假设重置 ID 101 的库存为 100
    redis_client.set("coupon:101:stock", 100)
    return {"msg": "Reset coupon 101 to 100"}

# ============================================================
# 6. 启动入口 (强制 8080)
# ============================================================
if __name__ == '__main__':
    import uvicorn
    # 这里指定了 8080
    uvicorn.run("event_producer_api_improved:app", host="0.0.0.0", port=8080, reload=True)