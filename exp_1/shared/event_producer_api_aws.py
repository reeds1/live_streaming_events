# event_producer_api_improved.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pika
import redis
import json
import time
import os
from contextlib import asynccontextmanager

from hash_vs_range_comparison.strategies.database_aws import connection_pool_aws

# Configuration
ENABLE_FILTER = os.getenv('ENABLE_FILTER', 'false').lower() == 'true'

# Global variables
rabbitmq_connection = None
rabbitmq_channel = None
redis_client = None

# ✅ [修改 1] 请求模型升级：需要知道抢的是哪个房间的哪张券
class CouponGrabRequest(BaseModel):
    user_id: str
    coupon_id: int  # 新增
    room_id: int    # 新增

class LikeRequest(BaseModel):
    user_id: str

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
    
    # 2. Load stock from MySQL (AWS) to Redis
    print("🔌 Connecting to AWS RDS (via shared module)...")
    if connection_pool_aws.initialize():
        print("✅ AWS RDS connection pool initialized!")
        
        # 预热缓存逻辑
        try:
            conn = connection_pool_aws.get_main_connection()
            conn.ping(reconnect=True) 
            
            with conn.cursor() as cursor:
                print("🔄 Loading coupons from AWS...")
                # ✅ 注意：这里改成了查 coupons 表
                cursor.execute("SELECT coupon_id, total_stock FROM coupons WHERE status = 1")
                rows = cursor.fetchall()
                
                if rows:
                    pipe = redis_client.pipeline()
                    for row in rows:
                        # ✅ Key 格式变更为: coupon:{id}:stock
                        key = f"coupon:{row['coupon_id']}:stock"
                        pipe.set(key, row['total_stock'])
                    pipe.execute()
                    print(f"✅ Pre-loaded {len(rows)} coupons into Redis (Batch Mode)")
                else:
                    print("⚠️ No active coupons found in DB")
                
        except Exception as e:
            print(f"⚠️ Failed to pre-load stock: {e}")
    else:
        print("❌ Failed to initialize AWS RDS pool")
    
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
    
    yield  # 🚀 服务运行中...
    
    # === Cleanup ===
    print("🛑 Shutting down services...")
    if rabbitmq_connection and not rabbitmq_connection.is_closed:
        rabbitmq_connection.close()
    
    connection_pool_aws.close_all()
    print("🔌 Connections closed")


app = FastAPI(
    title="Event Producer API (AWS Integrated)",
    description="集成 AWS RDS 分片架构的高并发秒杀系统",
    version="3.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    return {
        "status": "running",
        "version": "3.0 (AWS Sharding Ready)",
        "filter_enabled": ENABLE_FILTER
    }

# ✅ [修改 2] 抢购接口核心逻辑更新
@app.post("/api/coupon/grab")
async def grab_coupon(request: CouponGrabRequest):
    """
    优惠券抢购 API
    """
    start_time = time.time()
    
    # 1. 动态生成 Redis Key (不再是全局唯一的 coupon:stock)
    redis_key = f"coupon:{request.coupon_id}:stock"
    
    try:
        # Redis 原子扣减
        remaining = redis_client.decr(redis_key)
        
        if remaining >= 0:
            success = True
            reason = 'success'
            current_stock = remaining
        else:
            # 库存不足，回滚 (为了显示好看，其实不回滚也行)
            redis_client.incr(redis_key)
            success = False
            reason = 'out_of_stock'
            current_stock = 0
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis error: {str(e)}")
    
    # 构造事件 (必须包含 coupon_id 和 room_id 供 Consumer 落库使用)
    event = {
        'service': 'Coupon',
        'event_type': 'coupon_grab',
        'user_id': request.user_id,
        'coupon_id': request.coupon_id, # ✅ 传给消费者
        'room_id': request.room_id,     # ✅ 传给消费者
        'timestamp': time.time(),
        'success': success,
        'reason': reason,
        'remaining_stock': current_stock
    }
    
    # 过滤失败请求 (可选)
    if ENABLE_FILTER and not success:
        return {
            'success': False,
            'reason': reason,
            'remaining_stock': current_stock,
            'latency_ms': (time.time() - start_time) * 1000
        }
    
    # 发送 MQ
    try:
        rabbitmq_channel.basic_publish(
            exchange='',
            routing_key='event_queue',
            body=json.dumps(event),
            properties=pika.BasicProperties(delivery_mode=2)
        )
    except Exception as e:
        # 发送失败回滚 Redis
        if success:
            redis_client.incr(redis_key)
        raise HTTPException(status_code=500, detail=f"MQ Error: {str(e)}")
    
    return {
        'success': success,
        'reason': reason,
        'remaining_stock': current_stock,
        'latency_ms': (time.time() - start_time) * 1000
    }

@app.post("/api/like")
async def like_action(request: LikeRequest):
    """点赞 API (保持不变)"""
    is_top_like = hash(request.user_id) % 10 == 0
    event = {
        'service': 'Like',
        'event_type': 'like',
        'user_id': request.user_id,
        'timestamp': time.time(),
        'is_top_like': is_top_like
    }
    
    if ENABLE_FILTER and not is_top_like:
        return {'success': True, 'filtered': True}
    
    try:
        rabbitmq_channel.basic_publish(
            exchange='',
            routing_key='event_queue',
            body=json.dumps(event),
            properties=pika.BasicProperties(delivery_mode=2)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    return {'success': True, 'filtered': False}

# ✅ [修改 3] Reset 接口适配 coupons 表
@app.post("/admin/reset")
async def reset_stock():
    """重置所有优惠券库存（从 AWS coupons 表重新加载）"""
    try:
        # 使用 AWS 连接池
        conn = connection_pool_aws.get_main_connection()
        conn.ping(reconnect=True)
        
        loaded_count = 0
        
        with conn.cursor() as cursor:
            # 1. MySQL 重置
            cursor.execute("UPDATE coupons SET remaining_stock = total_stock WHERE status = 1")
            
            # 2. 读取数据
            cursor.execute("SELECT coupon_id, total_stock FROM coupons WHERE status = 1")
            all_coupons = cursor.fetchall()
            
            # 3. 批量写入 Redis
            pipe = redis_client.pipeline()
            for coupon in all_coupons:
                key = f"coupon:{coupon['coupon_id']}:stock"
                pipe.set(key, coupon['total_stock'])
                loaded_count += 1
            pipe.execute()
            
        conn.commit()
        
        return {
            'message': 'Stock reset successfully (AWS)',
            'loaded_coupons': loaded_count
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ✅ [修改 4] Stats 接口适配多优惠券查询
@app.get("/admin/stats")
async def get_stats(coupon_id: int = 101):
    """
    获取统计信息
    param coupon_id:查询特定优惠券的库存 (默认 101)
    """
    try:
        # 1. Redis 库存
        redis_key = f"coupon:{coupon_id}:stock"
        redis_stock = redis_client.get(redis_key)
        redis_stock = int(redis_stock) if redis_stock else -1
        
        # 2. RabbitMQ 深度
        try:
            queue = rabbitmq_channel.queue_declare(queue='event_queue', passive=True)
            queue_depth = queue.method.message_count
        except:
            queue_depth = -1
        
        # 3. MySQL 库存 (查 AWS)
        mysql_stock = -1
        try:
            conn = connection_pool_aws.get_main_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT remaining_stock FROM coupons WHERE coupon_id = %s", (coupon_id,))
                result = cursor.fetchone()
                if result:
                    mysql_stock = result['remaining_stock']
        except Exception as db_e:
            print(f"DB Error: {db_e}")
        
        return {
            'coupon_id': coupon_id,
            'redis_stock': redis_stock,
            'mysql_stock': mysql_stock,
            'queue_depth': queue_depth,
            'sync_needed': redis_stock != mysql_stock
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("event_producer_api_improved:app", host="0.0.0.0", port=8000, reload=True)