# event_consumer.py
import pika
import json
import redis
import mysql.connector
from mysql.connector import pooling
import time
import os
from datetime import datetime

# Configuration
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
MYSQL_HOST = os.getenv('MYSQL_HOST', '127.0.0.1')  # Use 127.0.0.1
MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3307))     # Port 3307
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'root123')  # Password
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'event_system')

# MySQL connection pool
mysql_pool = pooling.MySQLConnectionPool(
    pool_name="event_pool",
    pool_size=5,
    host=MYSQL_HOST,
    port=MYSQL_PORT,  # ✅ Ensure this line exists
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DATABASE
)

# Redis connection
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)

# Statistics
stats = {
    'processed': 0,
    'errors': 0,
    'start_time': time.time(),
    'last_sync_time': time.time()
}


def save_to_mysql(event):
    """Save event to MySQL"""
    conn = None
    cursor = None
    try:
        conn = mysql_pool.get_connection()
        cursor = conn.cursor()
        
        if event['event_type'] == 'coupon_grab':
            # 1. Save coupon event log
            sql = """
                INSERT INTO coupon_events 
                (user_id, event_type, success, reason, remaining_stock, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                event['user_id'],
                event['event_type'],
                event['success'],
                event.get('reason', ''),
                event.get('remaining_stock', 0),
                event['timestamp']
            ))
            
            # 2. Update user statistics table
            update_sql = """
                INSERT INTO user_coupon_stats 
                (user_id, total_attempts, successful_grabs, failed_grabs, last_attempt_time)
                VALUES (%s, 1, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    total_attempts = total_attempts + 1,
                    successful_grabs = successful_grabs + %s,
                    failed_grabs = failed_grabs + %s,
                    last_attempt_time = %s
            """
            success_count = 1 if event['success'] else 0
            fail_count = 0 if event['success'] else 1
            
            cursor.execute(update_sql, (
                event['user_id'],
                success_count,
                fail_count,
                event['timestamp'],
                success_count,
                fail_count,
                event['timestamp']
            ))

            # =========================================================
            # ✅ [New] 3. Actually decrement MySQL main stock table
            # Only when Redis determines grab success (success=True), deduct from database
            # =========================================================
            if event['success']:
                stock_sql = """
                    UPDATE coupon_config 
                    SET remaining_stock = remaining_stock - 1 
                    WHERE coupon_type = 'default' AND remaining_stock > 0
                """
                cursor.execute(stock_sql)
            # =========================================================
            
        elif event['event_type'] == 'like':
            # Save like event
            sql = """
                INSERT INTO like_events 
                (user_id, event_type, is_top_like, timestamp)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(sql, (
                event['user_id'],
                event['event_type'],
                event['is_top_like'],
                event['timestamp']
            ))
        
        # 4. Commit transaction
        # This will commit all at once: log insertion, user stats update, stock deduction
        conn.commit() 
        return True
        print(f"❌ MySQL Error: {err}")
    except mysql.connector.Error as err:
        stats['errors'] += 1
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return False
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        stats['errors'] += 1
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return False
    finally:
        # ✅ Critical: Close connection whether success or failure
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn:
            try:
                conn.close()
            except:
                pass
            

def update_redis_cache(event):
    """Update Redis cache"""
    try:
        user_id = event['user_id']
        
        if event['event_type'] == 'coupon_grab':
            # User coupon grab attempts
            redis_client.incr(f"user:attempts:{user_id}")
            
            if event['success']:
                # Successfully grabbed coupons
                redis_client.incr(f"user:success:{user_id}")
                redis_client.lpush(f"user:coupons:{user_id}", json.dumps({
                    'timestamp': event['timestamp'],
                    'grabbed_at': datetime.now().isoformat()
                }))
                # Set expiration time (7 days)
                redis_client.expire(f"user:coupons:{user_id}", 7 * 24 * 3600)
            else:
                # Failed attempts
                redis_client.incr(f"user:failed:{user_id}")
            
                        
        elif event['event_type'] == 'like':
            # Like count
            redis_client.incr(f"user:likes:{user_id}")
            
            if event.get('is_top_like'):
                # Top likes list
                redis_client.zadd(
                    "top_likes",
                    {user_id: event['timestamp']}
                )
        
        return True
        
    except redis.RedisError as e:
        print(f"❌ Redis Error: {e}")
        return False

def process_event(ch, method, properties, body):
    """Event processing callback function"""
    try:
        # Parse event
        event = json.loads(body)
        
        print(f"📥 Processing: {event['event_type']} from {event['user_id']}")
        
        # 1. Update Redis first (fast response)
        redis_success = update_redis_cache(event)
        
        # 2. Persist to MySQL
        mysql_success = save_to_mysql(event)
        
        if redis_success and mysql_success:
            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            stats['processed'] += 1
            
            
            if stats['processed'] % 100 == 0:
                elapsed = time.time() - stats['start_time']
                rate = stats['processed'] / elapsed if elapsed > 0 else 0
                print(f"📊 Processed: {stats['processed']}, "
                      f"Errors: {stats['errors']}, "
                      f"Rate: {rate:.2f} msg/s")
        else:
            # Processing failed, requeue (or send to dead letter queue)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            print(f"⚠️ Processing failed, message requeued")
            
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)  # Discard invalid message
        stats['errors'] += 1
    except Exception as e:
        print(f"❌ Processing error: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        stats['errors'] += 1

def main():
    """Main function"""
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║          Event Consumer Service                        ║
    ║          RabbitMQ → Redis → MySQL                      ║
    ╚════════════════════════════════════════════════════════╝
    """)
    
    # Test connections
    print("🔍 Testing connections...")
    
    try:
        # Test Redis
        redis_client.ping()
        print("✅ Redis connection OK")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return
    
    try:
        # Test MySQL
        conn = mysql_pool.get_connection()
        conn.close()
        print("✅ MySQL connection OK")
    except Exception as e:
        print(f"❌ MySQL connection failed: {e}")
        return
    
    # Connect to RabbitMQ
    print("🔍 Connecting to RabbitMQ...")
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST)
        )
        channel = connection.channel()
        
        # Declare queue
        channel.queue_declare(queue='event_queue', durable=True)
        
        # Set prefetch count (only fetch 1 message at a time)
        channel.basic_qos(prefetch_count=1)
        
        # Start consuming
        channel.basic_consume(
            queue='event_queue',
            on_message_callback=process_event
        )
        
        print("✅ RabbitMQ connection OK")
        print("🎧 Waiting for messages... (Press CTRL+C to exit)")
        
        channel.start_consuming()
        
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        elapsed = time.time() - stats['start_time']
        print(f"📊 Final stats: {stats['processed']} processed, "
              f"{stats['errors']} errors, "
              f"Runtime: {elapsed:.2f}s")
    except Exception as e:
        print(f"❌ RabbitMQ error: {e}")

if __name__ == '__main__':
    main()