import pika
import json
import redis
import time
import os
import sys
import traceback
from datetime import datetime

# ============================================================
# 1. Basic environment setup
# ============================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
strategies_dir = os.path.join(current_dir, 'hash_vs_range_comparison', 'strategies')
sys.path.append(strategies_dir)

try:
    # Import original (potentially problematic) strategy class
    from hash_strategy_aws import HashShardingStrategyAWS
    from sharding_interface import CouponResult
except ImportError as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)

# ============================================================
# ✅ 2. [Core fix] Create fixed version strategy class (Wrapper)
# ============================================================
class FixedHashStrategy(HashShardingStrategyAWS):
    """
    Fixed version strategy class: Inherits from original AWS strategy, but dynamically fixes bugs at runtime.
    This way we don't need to modify the original hash_strategy_aws.py file.
    """
    
    def __init__(self, num_shards=4):
        super().__init__(num_shards)


    def _get_shard_id(self, user_id: int) -> int:
        """
        ✅ Fix Bug 1: Remove randomness from hash()
        """
        return int(user_id) % self.num_shards

    def save_coupon_result(self, result: CouponResult) -> bool:
        """
        ✅ Fix Bug 2: Resolve (0, '') error
        Override save method to ensure parameters passed to MySQL driver are absolutely safe.
        """
        shard_id = self._get_shard_id(result.user_id)
        
        try:
            conn = self.pool.get_shard_connection(shard_id)
            if not conn:
                print(f"❌ [Shard {shard_id}] Connection is None!")
                return False

            # Don't use context manager (with conn.cursor), use try-finally for explicit management
            # This avoids exceptions being swallowed in __enter__ for certain driver versions
            cursor = conn.cursor()
            try:
                sql = f"""
                INSERT INTO {self.table_name}
                (user_id, coupon_id, room_id, grab_status, fail_reason, grab_time)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                
                # Force type conversion to prevent None or strange objects from causing driver crash
                params = (
                    int(result.user_id),
                    int(result.coupon_id),
                    int(result.room_id),
                    int(result.grab_status),
                    str(result.fail_reason) if result.fail_reason else None,
                    # Ensure grab_time is a datetime object
                    result.grab_time if result.grab_time else datetime.now()
                )
                
                cursor.execute(sql, params)
                conn.commit()
                return True
                
            except Exception as inner_e:
                print(f"❌ [SQL Execute Error]: {inner_e}")
                print(f"   Params: {params}")
                # Try to rollback, don't worry if rollback fails
                try: conn.rollback() 
                except: pass
                return False
            finally:
                # Explicitly close cursor
                cursor.close()

        except Exception as e:
            print(f"❌ [Shard {shard_id}] Save Outer Error: {e}")
            return False

# ============================================================
# 3. Initialize configuration
# ============================================================
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# ✅ Use fixed strategy class
sharding_strategy = FixedHashStrategy(num_shards=4)

stats = {'processed': 0, 'errors': 0}

def update_redis_cache(event):
    """Update Redis cache (Cache Aside Invalidation)"""
    try:
        user_id = event['user_id']
        if event['event_type'] == 'coupon_grab':
            # The logic here is: After writing to database, delete cache so next query goes to DB
            # For simple demonstration, we only delete key after successful database write
            if event['success']:
                redis_client.delete(f"user:coupons:{user_id}")
        return True
    except Exception as e:
        print(f"Redis Error: {e}")
        return False

def process_event(ch, method, properties, body):
    """Process message"""
    try:
        event = json.loads(body)
        print(f"📥 [MQ] Received: {event['event_type']} | User: {event['user_id']}")
        
        # 1. Core business: Write to database
        if event['event_type'] == 'coupon_grab':
            if event['success']:
                # Convert data object
                coupon_result = CouponResult(
                    user_id=int(event['user_id']),
                    coupon_id=int(event.get('coupon_id', 0)),
                    room_id=int(event.get('room_id', 0)),
                    grab_status=1,
                    fail_reason=None,
                    grab_time=datetime.fromtimestamp(event['timestamp'])
                )
                
                # ✅ Call fixed save method
                save_success = sharding_strategy.save_coupon_result(coupon_result)
                
                if save_success:
                    print(f"✅ [AWS RDS] Save Success")
                    # 2. Clear cache after successful database write
                    update_redis_cache(event)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    stats['processed'] += 1
                else:
                    print(f"❌ [AWS RDS] Save Failed - Logged & Skipped")
                    # On failure, temporarily ACK to prevent infinite loop (production should NACK + retry queue)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                # Failed coupon grab messages don't need database write, directly ACK
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