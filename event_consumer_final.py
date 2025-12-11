import pika
import json
import time
from datetime import datetime

# ✅ 1. 引入标准接口和具体策略
from sharding_interface import CouponResult
from sharding_strategy_hash_aws import HashShardingStrategyAWS

# ✅ 2. 初始化策略 (连接 AWS)
# 这一行是唯一和“具体实现”耦合的地方，其他地方都只用接口
strategy = HashShardingStrategyAWS(num_shards=4)
strategy.initialize()

print(f"🚀 消费者已启动 | 策略: {strategy.get_strategy_name()}")

def process_event(ch, method, properties, body):
    try:
        event = json.loads(body)
        print(f"📥 [MQ] 收到: {event['event_type']} | User: {event['user_id']}")
        
        if event['event_type'] == 'coupon_grab':
            if event['success']:
                # ✅ 3. 数据转换 (Adapter Pattern)
                # 把 MQ 的 JSON 转换成 接口定义的 CouponResult 对象
                coupon_result = CouponResult(
                    user_id=int(event['user_id']),
                    coupon_id=int(event.get('coupon_id', 0)),
                    room_id=int(event.get('room_id', 0)),
                    grab_status=1,
                    grab_time=datetime.fromtimestamp(event['timestamp']),
                    fail_reason=None
                )
                
                # ✅ 4. 调用策略保存 (核心解耦)
                # 你根本不知道底层是 Hash 还是 Range，也不知是 AWS 还是本地
                if strategy.save_coupon_result(coupon_result):
                    print(f"✅ [AWS] 落库成功")
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                else:
                    print(f"❌ [AWS] 落库失败")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            else:
                # 失败的抢购不落库 (Write-Behind 优化)
                ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"❌ 异常: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag) # 防止死循环，先ACK

def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='event_queue', durable=True)
    channel.basic_qos(prefetch_count=50) # 提高并发
    channel.basic_consume(queue='event_queue', on_message_callback=process_event)
    print("🎧 等待消息中...")
    channel.start_consuming()

if __name__ == '__main__':
    main()