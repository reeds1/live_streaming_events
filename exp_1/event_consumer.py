# event_consumer.py
import pika
import json
import redis
import mysql.connector
from mysql.connector import pooling
import time
import os
from datetime import datetime


RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')  # 添加这行
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))    # 添加这行

MYSQL_HOST = os.getenv('MYSQL_HOST', '127.0.0.1')  # 用 127.0.0.1
MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3307))    # 加端口
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'root123')  # 改密码
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'event_system')

mysql_pool = pooling.MySQLConnectionPool(
    pool_name="event_pool",
    pool_size=10,
    host=MYSQL_HOST,
    port=MYSQL_PORT,  # 添加这行
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DATABASE
)


redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)


stats = {
    'processed': 0,
    'errors': 0,
    'start_time': time.time()
}

def save_to_mysql(event):
    try:
        conn = mysql_pool.get_connection()
        cursor = conn.cursor()
        
        if event['event_type'] == 'coupon_grab':
            # 保存优惠券事件
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
            
            # 更新用户统计表
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
            
        elif event['event_type'] == 'like':
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
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except mysql.connector.Error as err:
        print(f"❌ MySQL Error: {err}")
        stats['errors'] += 1
        return False
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        stats['errors'] += 1
        return False

def update_redis_cache(event):
    try:
        user_id = event['user_id']
        
        if event['event_type'] == 'coupon_grab':

            redis_client.incr(f"user:attempts:{user_id}")
            
            if event['success']:
                redis_client.incr(f"user:success:{user_id}")
                redis_client.lpush(f"user:coupons:{user_id}", json.dumps({
                    'timestamp': event['timestamp'],
                    'grabbed_at': datetime.now().isoformat()
                }))
                redis_client.expire(f"user:coupons:{user_id}", 7 * 24 * 3600)
            else:
                redis_client.incr(f"user:failed:{user_id}")
            
            redis_client.set("coupon:stock", event.get('remaining_stock', 0))
            
        elif event['event_type'] == 'like':
            redis_client.incr(f"user:likes:{user_id}")
            
            if event.get('is_top_like'):
                redis_client.zadd(
                    "top_likes",
                    {user_id: event['timestamp']}
                )
        
        return True
        
    except redis.RedisError as e:
        print(f"❌ Redis Error: {e}")
        return False

def process_event(ch, method, properties, body):
    try:
        event = json.loads(body)
        
        print(f"📥 Processing: {event['event_type']} from {event['user_id']}")
        
        redis_success = update_redis_cache(event)
        
        mysql_success = save_to_mysql(event)
        
        if redis_success and mysql_success:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            stats['processed'] += 1
            
            if stats['processed'] % 100 == 0:
                elapsed = time.time() - stats['start_time']
                rate = stats['processed'] / elapsed if elapsed > 0 else 0
                print(f"📊 Processed: {stats['processed']}, "
                      f"Errors: {stats['errors']}, "
                      f"Rate: {rate:.2f} msg/s")
        else:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            print(f"⚠️ Processing failed, message requeued")
            
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)  
        stats['errors'] += 1
    except Exception as e:
        print(f"❌ Processing error: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        stats['errors'] += 1

def main():
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║          Event Consumer Service                        ║
    ║          RabbitMQ → Redis → MySQL                      ║
    ╚════════════════════════════════════════════════════════╝
    """)
    
    print("🔍 Testing connections...")
    
    try:
        redis_client.ping()
        print("✅ Redis connection OK")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return
    
    try:
        conn = mysql_pool.get_connection()
        conn.close()
        print("✅ MySQL connection OK")
    except Exception as e:
        print(f"❌ MySQL connection failed: {e}")
        return
    
    print("🔍 Connecting to RabbitMQ...")
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST)
        )
        channel = connection.channel()
        
        channel.queue_declare(queue='event_queue', durable=True)
        
        channel.basic_qos(prefetch_count=1)
        
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