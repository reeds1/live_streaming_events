import redis
import json
import os
import sys
from typing import List, Dict, Optional, Union
from datetime import datetime
from dataclasses import asdict
from typing import List, Dict, Tuple

# ============================================================
# ✅ 1. Unified import path (consistent with Consumer)
# ============================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
strategies_dir = os.path.join(current_dir, 'hash_vs_range_comparison', 'strategies')
sys.path.append(strategies_dir)

try:
    # Import interface and specific strategies
    from sharding_interface import ShardingStrategy, CouponResult
    # Here we can decide to import AWS Hash or Range strategy based on configuration
    from hash_strategy_aws import HashShardingStrategyAWS
except ImportError as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)

# ============================================================
# ✅ 2. Cache service class (Service Layer)
# ============================================================
class CachedCouponService:
    """
    Coupon query service layer
    Responsibilities:
    1. Cache management (Redis Cache-Aside)
    2. Strategy routing (access DB through ShardingStrategy)
    3. Data adaptation (DTO <-> JSON)
    """

    def __init__(self, redis_host: str, strategy: ShardingStrategy):
        # Initialize Redis
        self.redis = redis.Redis(
            host=redis_host, 
            port=6379, 
            decode_responses=True
        )
        
        # Inject sharding strategy (Hash or Range)
        self.strategy = strategy
        
        # Cache expiration time (seconds)
        self.CACHE_TTL = 3600 

    def get_user_coupons(self, user_id: int) -> Tuple[List[Dict], bool]:
        redis_key = f"user:coupons:{user_id}"

        # 1. Check Redis (only GET)
        try:
            cached_json = self.redis.get(redis_key)
            if cached_json:
                # Even "[]" can be correctly parsed as an empty list
                return json.loads(cached_json), True
        except Exception as e:
            print(f"Redis Error: {e}")

        # 2. Check DB
        db_results = self.strategy.query_user_coupons(user_id)

        # 3. Write back
        return self._rebuild_cache(redis_key, db_results), False


    def save_coupon(self, coupon_result: CouponResult) -> bool:
        """
        [API usage] Directly save coupon and handle cache
        Note: Usually coupon grabbing is handled asynchronously via MQ, this method may be used for testing or order completion
        """
        # 1. Write to DB (through Strategy)
        success = self.strategy.save_coupon_result(coupon_result)
        
        if success:
            # 2. Delete cache (Cache Invalidation)
            # Force next query to go to DB, ensuring strong data consistency
            redis_key = f"user:coupons:{coupon_result.user_id}"
            try:
                self.redis.delete(redis_key)
                # print(f"🧹 Cache invalidated for User {coupon_result.user_id}")
            except redis.RedisError as e:
                print(f"⚠️ Redis Delete Error: {e}")
                
        return success

    def _rebuild_cache(self, redis_key: str, db_results: list) -> list:
        """
        Fixed version: Unified use of String JSON format to resolve type conflicts
        """
        import json
        import random
        from dataclasses import asdict
        from datetime import datetime

        # 1. Serialize data
        if not db_results:
            # No data, store empty list string "[]"
            # This way json.loads("[]") on the read side is still an empty list, perfect logic closure
            json_str = "[]"
            ttl = 60 # Prevent cache penetration, shorter time
        else:
            # Has data, convert to dict first then serialize
            formatted_list = []
            for result in db_results:
                # Compatible with both object and dict cases
                d = asdict(result) if hasattr(result, '__dataclass_fields__') else result
                
                # Handle datetime
                if isinstance(d.get('grab_time'), datetime):
                    d['grab_time'] = d['grab_time'].isoformat()
                # ... Handle other time fields ...
                
                formatted_list.append(d)
            
            json_str = json.dumps(formatted_list)
            ttl = 3600 + random.randint(0, 300) # Prevent cache avalanche

        # 2. Write to Redis (atomic overwrite)
        try:
            # Regardless of whether old data is List or String, directly overwrite, never error
            self.redis.setex(redis_key, ttl, json_str)
        except Exception as e:
            print(f"❌ Redis Write Error: {e}")

        return db_results

# ============================================================
# ✅ 3. Test/Usage example (simulate API call)
# ============================================================
if __name__ == "__main__":
    print("🚀 Initializing CachedCouponService...")
    
    # 1. Initialize strategy (connect to AWS RDS)
    # Note: Here we directly use AWS Hash strategy, you can switch to Range strategy
    aws_strategy = HashShardingStrategyAWS(num_shards=4)
    if not aws_strategy.initialize():
        print("❌ Failed to connect to AWS RDS")
        sys.exit(1)
        
    # 2. Initialize service
    service = CachedCouponService(
        redis_host=os.getenv('REDIS_HOST', 'localhost'),
        strategy=aws_strategy
    )
    
    # Simulate User ID (make sure this ID has data in your DB, or run Consumer script first)
    TEST_USER_ID = 10086
    
    print(f"\n🔎 Querying coupons for User {TEST_USER_ID}...")
    
    # First query (Cache Miss -> DB -> Redis)
    start_time = datetime.now()
    coupons = service.get_user_coupons(TEST_USER_ID)
    duration = (datetime.now() - start_time).total_seconds() * 1000
    
    print(f"Result Count: {len(coupons)}")
    print(f"Time Taken: {duration:.2f} ms")
    if coupons:
        print(f"First Coupon: {coupons[0]}")
        
    print("\n🔎 Querying again (Should hit Redis)...")
    
    # Second query (Cache Hit -> Redis)
    start_time = datetime.now()
    coupons_cache = service.get_user_coupons(TEST_USER_ID)
    duration = (datetime.now() - start_time).total_seconds() * 1000
    
    print(f"Result Count: {len(coupons_cache)}")
    print(f"Time Taken: {duration:.2f} ms")