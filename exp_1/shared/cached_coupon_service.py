import redis
import json
import os
import sys
from typing import List, Dict, Optional, Union
from datetime import datetime
from dataclasses import asdict
from typing import List, Dict, Tuple

# ============================================================
# ✅ 1. 统一导入路径 (与 Consumer 保持一致)
# ============================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
strategies_dir = os.path.join(current_dir, 'hash_vs_range_comparison', 'strategies')
sys.path.append(strategies_dir)

try:
    # 导入接口和具体策略
    from sharding_interface import ShardingStrategy, CouponResult
    # 这里可以根据配置决定导入 AWS Hash 还是 Range 策略
    from hash_strategy_aws import HashShardingStrategyAWS
except ImportError as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)

# ============================================================
# ✅ 2. 缓存服务类 (Service Layer)
# ============================================================
class CachedCouponService:
    """
    优惠券查询服务层
    职责：
    1. 缓存管理 (Redis Cache-Aside)
    2. 策略路由 (通过 ShardingStrategy 访问 DB)
    3. 数据适配 (DTO <-> JSON)
    """

    def __init__(self, redis_host: str, strategy: ShardingStrategy):
        # 初始化 Redis
        self.redis = redis.Redis(
            host=redis_host, 
            port=6379, 
            decode_responses=True
        )
        
        # 注入分片策略 (Hash 或 Range)
        self.strategy = strategy
        
        # 缓存过期时间 (秒)
        self.CACHE_TTL = 3600 

    def get_user_coupons(self, user_id: int) -> Tuple[List[Dict], bool]:
        redis_key = f"user:coupons:{user_id}"

        # 1. 查 Redis (只用 GET)
        try:
            cached_json = self.redis.get(redis_key)
            if cached_json:
                # 即使是 "[]" 也能被正确解析为空列表
                return json.loads(cached_json), True
        except Exception as e:
            print(f"Redis Error: {e}")

        # 2. 查 DB
        db_results = self.strategy.query_user_coupons(user_id)

        # 3. 回写
        return self._rebuild_cache(redis_key, db_results), False


    def save_coupon(self, coupon_result: CouponResult) -> bool:
        """
        [API 使用] 直接保存优惠券并处理缓存
        注意：通常抢券是异步 MQ 处理，这个方法可能用于测试或补单
        """
        # 1. 写 DB (通过 Strategy)
        success = self.strategy.save_coupon_result(coupon_result)
        
        if success:
            # 2. 删缓存 (Cache Invalidation)
            # 强制下一次查询走 DB，保证数据强一致性
            redis_key = f"user:coupons:{coupon_result.user_id}"
            try:
                self.redis.delete(redis_key)
                # print(f"🧹 Cache invalidated for User {coupon_result.user_id}")
            except redis.RedisError as e:
                print(f"⚠️ Redis Delete Error: {e}")
                
        return success

    def _rebuild_cache(self, redis_key: str, db_results: list) -> list:
        """
        修正版：统一使用 String JSON 格式，解决类型冲突
        """
        import json
        import random
        from dataclasses import asdict
        from datetime import datetime

        # 1. 序列化数据
        if not db_results:
            # 没数据存空列表字符串 "[]"
            # 这样读取端 json.loads("[]") 还是一个空列表，逻辑完美闭环
            json_str = "[]"
            ttl = 60 # 防穿透，时间短点
        else:
            # 有数据，先转字典再序列化
            formatted_list = []
            for result in db_results:
                # 兼容 result 是对象还是字典的情况
                d = asdict(result) if hasattr(result, '__dataclass_fields__') else result
                
                # 处理 datetime
                if isinstance(d.get('grab_time'), datetime):
                    d['grab_time'] = d['grab_time'].isoformat()
                # ... 处理其他时间字段 ...
                
                formatted_list.append(d)
            
            json_str = json.dumps(formatted_list)
            ttl = 3600 + random.randint(0, 300) # 防雪崩

        # 2. 写入 Redis (原子覆盖)
        try:
            # 无论旧数据是 List 还是 String，直接覆盖，绝不报错
            self.redis.setex(redis_key, ttl, json_str)
        except Exception as e:
            print(f"❌ Redis Write Error: {e}")

        return db_results

# ============================================================
# ✅ 3. 测试/使用示例 (模拟 API 调用)
# ============================================================
if __name__ == "__main__":
    print("🚀 Initializing CachedCouponService...")
    
    # 1. 初始化策略 (连接 AWS RDS)
    # 注意：这里我们直接用 AWS Hash 策略，你可以换成 Range 策略
    aws_strategy = HashShardingStrategyAWS(num_shards=4)
    if not aws_strategy.initialize():
        print("❌ Failed to connect to AWS RDS")
        sys.exit(1)
        
    # 2. 初始化服务
    service = CachedCouponService(
        redis_host=os.getenv('REDIS_HOST', 'localhost'),
        strategy=aws_strategy
    )
    
    # 模拟 User ID (确保这个 ID 在你的 DB 里有数据，或者先跑 Consumer 脚本)
    TEST_USER_ID = 10086
    
    print(f"\n🔎 Querying coupons for User {TEST_USER_ID}...")
    
    # 第一次查询 (Cache Miss -> DB -> Redis)
    start_time = datetime.now()
    coupons = service.get_user_coupons(TEST_USER_ID)
    duration = (datetime.now() - start_time).total_seconds() * 1000
    
    print(f"Result Count: {len(coupons)}")
    print(f"Time Taken: {duration:.2f} ms")
    if coupons:
        print(f"First Coupon: {coupons[0]}")
        
    print("\n🔎 Querying again (Should hit Redis)...")
    
    # 第二次查询 (Cache Hit -> Redis)
    start_time = datetime.now()
    coupons_cache = service.get_user_coupons(TEST_USER_ID)
    duration = (datetime.now() - start_time).total_seconds() * 1000
    
    print(f"Result Count: {len(coupons_cache)}")
    print(f"Time Taken: {duration:.2f} ms")