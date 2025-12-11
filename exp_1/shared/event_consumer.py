# event_consumer.py
import pika
import json
import redis
import time
import os
import sys
from datetime import datetime

# ============================================================
# ✅ 1. Import Strategy Pattern Dependencies
# ============================================================
# Adjust the import path if your directory structure is deep.
# Assuming structure: hash_vs_range_comparison/strategies/

# 1. Get absolute path of strategies folder
current_dir = os.path.dirname(os.path.abspath(__file__))
strategies_dir = os.path.join(current_dir, 'hash_vs_range_comparison', 'strategies')

# 2. Add this sub-directory to Python search path
sys.path.append(strategies_dir)

# 3. Import modules (Python can now find database_aws)
try:
    # Note: Import class names directly since the folder is in sys.path
    from hash_strategy_aws import HashShardingStrategyAWS
    from sharding_interface import CouponResult
except ImportError as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)

# Configuration
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))

# Benchmarking Globals
benchmark_start = 0
benchmark_count = 0
TARGET_REQUESTS = 2000

# Redis Connection (Used for updating user personal cache)
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)

# ✅ Initialize AWS Hash Sharding Strategy
# Set to 4 shards, corresponding to the 4 AWS RDS instances
sharding_strategy = HashShardingStrategyAWS(num_shards=4)

# Statistics
stats = {
    'processed': 0,
    'errors': 0,
    'start_time': time.time()
}

def update_redis_cache(event):
    """
    Update Redis Cache (User View)
    Note: This only updates user personal records, not global stock.
    """
    try:
        user_id = event['user_id']
        
        if event['event_type'] == 'coupon_grab':
            # Record attempt count
            redis_client.incr(f"user:attempts:{user_id}")
            
            if event['success']:
                # Record success count
                redis_client.incr(f"user:success:{user_id}")
                # Write to user's personal coupon list
                redis_client.lpush(f"user:coupons:{user_id}", json.dumps({
                    'coupon_id': event.get('coupon_id'),
                    'room_id': event.get('room_id'),
                    'timestamp': event['timestamp'],
                    'grabbed_at': datetime.now().isoformat()
                }))
                redis_client.expire(f"user:coupons:{user_id}", 7 * 24 * 3600)
            else:
                redis_client.incr(f"user:failed:{user_id}")
                
        elif event['event_type'] == 'like':
            redis_client.incr(f"user:likes:{user_id}")
            if event.get('is_top_like'):
                redis_client.zadd("top_likes", {user_id: event['timestamp']})
        
        return True
    except redis.RedisError as e:
        print(f"❌ Redis Error: {e}")
        return False # Redis failure should not block DB persistence

def process_event(ch, method, properties, body):
    """Callback function for processing events"""
    global benchmark_start, benchmark_count, stats
    try:
        # Parse event
        event = json.loads(body)
        print(f"📥 [MQ] Received message: {event['event_type']} | User: {event['user_id']}")
        
        # Start Timer on first message
        if benchmark_count == 0:
            benchmark_start = time.time()
            print(f"⏱️ [Timer Start] Received 1st message, processing at full speed...")
        
        # 1. Update Redis Cache (Non-critical path, for frontend display)
        update_redis_cache(event)
        
        # 2. Core Logic: Persist to AWS RDS (Using Strategy Pattern)
        if event['event_type'] == 'coupon_grab':
            if event['success']:
                # ✅ Data Adapter: Convert JSON to CouponResult Object
                # Critical step: Adapts data to the shared interface
                coupon_result = CouponResult(
                    user_id=int(event['user_id']),
                    coupon_id=int(event.get('coupon_id', 0)),
                    room_id=int(event.get('room_id', 0)),
                    grab_status=1,
                    fail_reason=None,
                    grab_time=datetime.fromtimestamp(event['timestamp']),
                    # Other fields can be defaults
                )
                
                # ✅ Strategy Call: Save using strategy
                # Consumer ignores sharding logic; Strategy handles routing
                save_success = sharding_strategy.save_coupon_result(coupon_result)
                
                if save_success:
                    print(f"✅ [AWS RDS] Save Success (Hash Sharding)")
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    stats['processed'] += 1
                else:
                    print(f"❌ [AWS RDS] Save Failed - Will Retry")
                    # Only Nack if DB write fails
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            else:
                # Failed grab (Out of Stock), log only, no DB write
                # Write-Behind Optimization: Reduce DB garbage data
                print(f"⚠️ Failed grab (Out of Stock), skipping DB write")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
        elif event['event_type'] == 'like':
            # Like Logic: Usually Redis only or async batch insert
            # Simplified here to just ACK
            ch.basic_ack(delivery_tag=method.delivery_tag)

        # 2. Increment counter
        benchmark_count += 1
        
        # 3. If target reached, stop timer and print stats
        if benchmark_count == TARGET_REQUESTS:
            duration = time.time() - benchmark_start
            tps = TARGET_REQUESTS / duration if duration > 0 else 0
            
            print("\n" + "="*50)
            print(f"🏁 [Benchmark Complete] Processed {TARGET_REQUESTS} requests")
            print(f"⏱️ Total Time: {duration:.4f} s")
            print(f"⚡ Throughput (TPS): {tps:.2f} msg/s")
            print("="*50 + "\n")
            
            # Reset counter for the next test run
            benchmark_count = 0

        # Print periodic statistics
        if stats['processed'] > 0 and stats['processed'] % 10 == 0:
            elapsed = time.time() - stats['start_time']
            rate = stats['processed'] / elapsed if elapsed > 0 else 0
            print(f"📊 Processed: {stats['processed']} | Rate: {rate:.2f} msg/s")

    except json.JSONDecodeError:
        print(f"❌ Invalid JSON")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"❌ Processing error: {e}")
        # Handle unknown errors, prevent infinite loops by not requeueing in this demo
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def main():
    """Main entry point"""
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║     Event Consumer Service (AWS Integrated)           ║
    ║     MQ → Strategy(AWS) → Sharded RDS                   ║
    ╚════════════════════════════════════════════════════════╝
    """)
    
    # 1. Initialize AWS Connection Pool (via Strategy)
    print("🔌 Connecting to AWS RDS...")
    if sharding_strategy.initialize():
        print("✅ AWS RDS Connection Pool Initialized")
    else:
        print("❌ Failed to connect to AWS RDS. Exiting...")
        return

    # 2. Connect to Redis
    try:
        redis_client.ping()
        print("✅ Redis connection OK")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return
    
    # 3. Connect to RabbitMQ
    print("🔍 Connecting to RabbitMQ...")
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST)
        )
        channel = connection.channel()
        channel.queue_declare(queue='event_queue', durable=True)
        
        # Increase concurrency prefetch
        channel.basic_qos(prefetch_count=20) 
        
        channel.basic_consume(
            queue='event_queue',
            on_message_callback=process_event
        )
        
        print("✅ RabbitMQ connection OK")
        print(f"🎧 Consumer Strategy: {sharding_strategy.get_strategy_name()}")
        print("Waiting for messages...")
        
        channel.start_consuming()
        
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        # Close connection pool
        from hash_vs_range_comparison.strategies.database_aws import connection_pool_aws
        connection_pool_aws.close_all()
        
    except Exception as e:
        print(f"❌ RabbitMQ error: {e}")

if __name__ == '__main__':
    main()