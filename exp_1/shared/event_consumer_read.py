import pika
import json
import redis
import time
import os
import sys
import traceback
from datetime import datetime

# ============================================================
# 1. 基础环境设置
# ============================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
strategies_dir = os.path.join(current_dir, 'hash_vs_range_comparison', 'strategies')
sys.path.append(strategies_dir)

try:
    # 导入原始的（可能有问题的）策略类
    from hash_strategy_aws import HashShardingStrategyAWS
    from sharding_interface import CouponResult
except ImportError as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)

# ============================================================
# ✅ 2. 【核心修复】创建修复版策略类 (Wrapper)
# ============================================================
class FixedHashStrategy(HashShardingStrategyAWS):
    """
    修复版策略类：继承自原始 AWS 策略，但在运行时动态修复 Bug。
    这样就不需要修改 hash_strategy_aws.py 原文件了。
    """
    
    def __init__(self, num_shards=4):
        super().__init__(num_shards)


    def _get_shard_id(self, user_id: int) -> int:
        """
        ✅ 修复 Bug 1: 移除 hash() 的随机性
        """
        return int(user_id) % self.num_shards

    def save_coupon_result(self, result: CouponResult) -> bool:
        """
        ✅ 修复 Bug 2: 解决 (0, '') 报错
        重写 save 方法，确保参数传递给 MySQL 驱动时是绝对安全的。
        """
        shard_id = self._get_shard_id(result.user_id)
        
        try:
            conn = self.pool.get_shard_connection(shard_id)
            if not conn:
                print(f"❌ [Shard {shard_id}] Connection is None!")
                return False

            # 不使用 context manager (with conn.cursor)，改用 try-finally 显式管理
            # 这能避免某些驱动版本在 __enter__ 时的异常被吞掉
            cursor = conn.cursor()
            try:
                sql = f"""
                INSERT INTO {self.table_name}
                (user_id, coupon_id, room_id, grab_status, fail_reason, grab_time)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                
                # 强转类型，防止 None 或奇怪的对象导致驱动崩溃
                params = (
                    int(result.user_id),
                    int(result.coupon_id),
                    int(result.room_id),
                    int(result.grab_status),
                    str(result.fail_reason) if result.fail_reason else None,
                    # 确保 grab_time 是 datetime 对象
                    result.grab_time if result.grab_time else datetime.now()
                )
                
                cursor.execute(sql, params)
                conn.commit()
                return True
                
            except Exception as inner_e:
                print(f"❌ [SQL Execute Error]: {inner_e}")
                print(f"   Params: {params}")
                # 尝试回滚，如果回滚失败也不要在意
                try: conn.rollback() 
                except: pass
                return False
            finally:
                # 显式关闭 cursor
                cursor.close()

        except Exception as e:
            print(f"❌ [Shard {shard_id}] Save Outer Error: {e}")
            return False

# ============================================================
# 3. 初始化配置
# ============================================================
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# ✅ 使用修复后的策略类
sharding_strategy = FixedHashStrategy(num_shards=4)

stats = {'processed': 0, 'errors': 0}

def update_redis_cache(event):
    """更新 Redis 缓存 (Cache Aside Invalidation)"""
    try:
        user_id = event['user_id']
        if event['event_type'] == 'coupon_grab':
            # 这里的逻辑是：写数据库后，删除缓存，让下一次查询走 DB
            # 为了简单演示，我们只在成功落库后删除 Key
            if event['success']:
                redis_client.delete(f"user:coupons:{user_id}")
        return True
    except Exception as e:
        print(f"Redis Error: {e}")
        return False

def process_event(ch, method, properties, body):
    """处理消息"""
    try:
        event = json.loads(body)
        print(f"📥 [MQ] Received: {event['event_type']} | User: {event['user_id']}")
        
        # 1. 核心业务：落库
        if event['event_type'] == 'coupon_grab':
            if event['success']:
                # 转换数据对象
                coupon_result = CouponResult(
                    user_id=int(event['user_id']),
                    coupon_id=int(event.get('coupon_id', 0)),
                    room_id=int(event.get('room_id', 0)),
                    grab_status=1,
                    fail_reason=None,
                    grab_time=datetime.fromtimestamp(event['timestamp'])
                )
                
                # ✅ 调用修复后的 save 方法
                save_success = sharding_strategy.save_coupon_result(coupon_result)
                
                if save_success:
                    print(f"✅ [AWS RDS] Save Success")
                    # 2. 落库成功后清理缓存
                    update_redis_cache(event)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    stats['processed'] += 1
                else:
                    print(f"❌ [AWS RDS] Save Failed - Logged & Skipped")
                    # 失败了暂时 ACK，防止死循环 (生产环境应该 NACK + 重试队列)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                # 抢券失败的消息，不需要落库，直接 ACK
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
        elif event['event_type'] == 'like':
            ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"❌ Processing error: {e}")
        traceback.print_exc()
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def main():
    print("🔌 Connecting to AWS RDS...")
    if sharding_strategy.initialize():
        print("✅ AWS RDS Connection Pool Initialized")
    else:
        print("❌ Failed to connect to AWS RDS")
        return

    print("🔍 Connecting to RabbitMQ...")
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue='event_queue', durable=True)
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue='event_queue', on_message_callback=process_event)
        
        print("✅ Consumer Ready! Using FixedHashStrategy.")
        channel.start_consuming()
    except KeyboardInterrupt:
        from hash_vs_range_comparison.strategies.database_aws import connection_pool_aws
        connection_pool_aws.close_all()
        print("\n👋 Shutdown")

if __name__ == '__main__':
    main()