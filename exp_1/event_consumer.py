# event_consumer.py
import pika
import json
import redis
import mysql.connector
from mysql.connector import pooling
import time
import os
from datetime import datetime

# 配置
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
MYSQL_HOST = os.getenv('MYSQL_HOST', '127.0.0.1')  # 用 127.0.0.1
MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3307))     # 端口 3307
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'root123')  # 密码
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'event_system')

# MySQL 连接池
mysql_pool = pooling.MySQLConnectionPool(
    pool_name="event_pool",
    pool_size=5,
    host=MYSQL_HOST,
    port=MYSQL_PORT,  # ✅ 确保有这行
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DATABASE
)

# Redis 连接
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)

# 统计信息
stats = {
    'processed': 0,
    'errors': 0,
    'start_time': time.time(),
    'last_sync_time': time.time()
}


def save_to_mysql(event):
    """保存事件到 MySQL"""
    conn = None
    cursor = None
    try:
        conn = mysql_pool.get_connection()
        cursor = conn.cursor()
        
        if event['event_type'] == 'coupon_grab':
            # 1. 保存优惠券事件日志
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
            
            # 2. 更新用户统计表
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
            # ✅ [新增] 3. 真正扣减 MySQL 主库存表
            # 只有当 Redis 判定抢购成功 (success=True) 时，才去扣数据库
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
            # 保存点赞事件
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
        
        # 4. 提交事务
        # 这里会一次性提交：日志插入、用户统计更新、库存扣减
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
        # ✅ 关键：无论成功还是失败都要关闭连接
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
    """更新 Redis 缓存"""
    try:
        user_id = event['user_id']
        
        if event['event_type'] == 'coupon_grab':
            # 用户抢券次数
            redis_client.incr(f"user:attempts:{user_id}")
            
            if event['success']:
                # 成功抢到的优惠券
                redis_client.incr(f"user:success:{user_id}")
                redis_client.lpush(f"user:coupons:{user_id}", json.dumps({
                    'timestamp': event['timestamp'],
                    'grabbed_at': datetime.now().isoformat()
                }))
                # 设置过期时间（7天）
                redis_client.expire(f"user:coupons:{user_id}", 7 * 24 * 3600)
            else:
                # 失败次数
                redis_client.incr(f"user:failed:{user_id}")
            
                        
        elif event['event_type'] == 'like':
            # 点赞计数
            redis_client.incr(f"user:likes:{user_id}")
            
            if event.get('is_top_like'):
                # 热门点赞列表
                redis_client.zadd(
                    "top_likes",
                    {user_id: event['timestamp']}
                )
        
        return True
        
    except redis.RedisError as e:
        print(f"❌ Redis Error: {e}")
        return False

def process_event(ch, method, properties, body):
    """处理事件的回调函数"""
    try:
        # 解析事件
        event = json.loads(body)
        
        print(f"📥 Processing: {event['event_type']} from {event['user_id']}")
        
        # 1. 先更新 Redis（快速响应）
        redis_success = update_redis_cache(event)
        
        # 2. 持久化到 MySQL
        mysql_success = save_to_mysql(event)
        
        if redis_success and mysql_success:
            # 确认消息
            ch.basic_ack(delivery_tag=method.delivery_tag)
            stats['processed'] += 1
            
            
            if stats['processed'] % 100 == 0:
                elapsed = time.time() - stats['start_time']
                rate = stats['processed'] / elapsed if elapsed > 0 else 0
                print(f"📊 Processed: {stats['processed']}, "
                      f"Errors: {stats['errors']}, "
                      f"Rate: {rate:.2f} msg/s")
        else:
            # 处理失败，重新入队（或者发送到死信队列）
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            print(f"⚠️ Processing failed, message requeued")
            
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)  # 丢弃无效消息
        stats['errors'] += 1
    except Exception as e:
        print(f"❌ Processing error: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        stats['errors'] += 1

def main():
    """主函数"""
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║          Event Consumer Service                        ║
    ║          RabbitMQ → Redis → MySQL                      ║
    ╚════════════════════════════════════════════════════════╝
    """)
    
    # 测试连接
    print("🔍 Testing connections...")
    
    try:
        # 测试 Redis
        redis_client.ping()
        print("✅ Redis connection OK")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return
    
    try:
        # 测试 MySQL
        conn = mysql_pool.get_connection()
        conn.close()
        print("✅ MySQL connection OK")
    except Exception as e:
        print(f"❌ MySQL connection failed: {e}")
        return
    
    # 连接 RabbitMQ
    print("🔍 Connecting to RabbitMQ...")
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST)
        )
        channel = connection.channel()
        
        # 声明队列
        channel.queue_declare(queue='event_queue', durable=True)
        
        # 设置预取数量（每次只取1条消息）
        channel.basic_qos(prefetch_count=1)
        
        # 开始消费
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