import pika
import json
import time
from datetime import datetime

# ✅ 1. Import standard interface and specific strategy
from sharding_interface import CouponResult
from sharding_strategy_hash_aws import HashShardingStrategyAWS

# ✅ 2. Initialize strategy (connect to AWS)
# This line is the only place coupled with "specific implementation", other places only use interface
strategy = HashShardingStrategyAWS(num_shards=4)
strategy.initialize()

print(f"🚀 Consumer started | Strategy: {strategy.get_strategy_name()}")

def process_event(ch, method, properties, body):
    try:
        event = json.loads(body)
        print(f"📥 [MQ] Received: {event['event_type']} | User: {event['user_id']}")
        
        if event['event_type'] == 'coupon_grab':
            if event['success']:
                # ✅ 3. Data conversion (Adapter Pattern)
                # Convert MQ's JSON to CouponResult object defined by interface
                coupon_result = CouponResult(
                    user_id=int(event['user_id']),
                    coupon_id=int(event.get('coupon_id', 0)),
                    room_id=int(event.get('room_id', 0)),
                    grab_status=1,
                    grab_time=datetime.fromtimestamp(event['timestamp']),
                    fail_reason=None
                )
                
                # ✅ 4. Call strategy to save (core decoupling)
                # You don't know if the underlying is Hash or Range, or AWS or local
                if strategy.save_coupon_result(coupon_result):
                    print(f"✅ [AWS] Database write successful")
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                else:
                    print(f"❌ [AWS] Database write failed")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            else:
                # Failed grabs don't write to database (Write-Behind optimization)
                ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"❌ Exception: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag) # Prevent infinite loop, ACK first

def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='event_queue', durable=True)
    channel.basic_qos(prefetch_count=50) # Increase concurrency
    channel.basic_consume(queue='event_queue', on_message_callback=process_event)
    print("🎧 Waiting for messages...")
    channel.start_consuming()

if __name__ == '__main__':
    main()