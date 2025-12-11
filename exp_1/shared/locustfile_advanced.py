"""
Locust Advanced Load Testing Script - Live Stream Coupon Grabbing System
Supports multiple test scenarios:
1. Normal coupon grabbing scenario
2. Hot room scenario (test Range sharding hotspot issues)
3. Cross-shard query scenario (test Hash sharding cross-shard queries)
4. Mixed read-write scenario
"""

from locust import HttpUser, task, between, events, LoadTestShape
import random
import time
from datetime import datetime

# ============================================================
# Configuration
# ============================================================

# Simulated user ID range (matches data seeder)
USER_ID_MIN = 1
USER_ID_MAX = 100000

# Simulated live room ID range
ROOM_ID_MIN = 1
ROOM_ID_MAX = 100

# Simulated coupon ID range
COUPON_ID_MIN = 1
COUPON_ID_MAX = 500

# Hot room ID range (top 5%)
HOT_ROOM_MIN = 1
HOT_ROOM_MAX = 5

# ============================================================
# Global Statistics
# ============================================================
successful_grabs = 0
failed_grabs = 0
out_of_stock_count = 0
duplicate_grab_count = 0

# ============================================================
# Scenario 1: Normal Coupon Users
# ============================================================
class NormalCouponUser(HttpUser):
    """Normal users: Random coupon grabbing"""
    weight = 5  # Weight: 5
    wait_time = between(0.1, 0.5)  # 100-500ms interval
    
    def on_start(self):
        """Initialize user"""
        self.user_id = random.randint(USER_ID_MIN, USER_ID_MAX)
        self.grabbed_coupons = set()  # Track grabbed coupons
        print(f"🟢 [Normal] User {self.user_id} online")
    
    @task(10)
    def grab_random_coupon(self):
        """Random coupon grab"""
        coupon_id = random.randint(COUPON_ID_MIN, COUPON_ID_MAX)
        
        with self.client.post(
            "/api/coupon/grab",
            json={
                "user_id": self.user_id,
                "coupon_id": coupon_id
            },
            catch_response=True,
            name="/api/coupon/grab [Random]"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get('grab_status') == 1:
                    self.grabbed_coupons.add(coupon_id)
                    response.success()
                else:
                    # Failure is also marked as success (normal business failure)
                    response.success()
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(3)
    def query_my_coupons(self):
        """Query my coupons"""
        self.client.get(
            f"/api/user/{self.user_id}/coupons",
            name="/api/user/:id/coupons [Query Own]"
        )
    
    @task(1)
    def check_coupon_stock(self):
        """Check coupon stock"""
        coupon_id = random.randint(COUPON_ID_MIN, COUPON_ID_MAX)
        self.client.get(
            f"/api/coupon/{coupon_id}/stock",
            name="/api/coupon/:id/stock [Check Stock]"
        )

# ============================================================
# Scenario 2: Hot Room Users (Test Range sharding hotspot issues)
# ============================================================
class HotRoomUser(HttpUser):
    """Hot users: Focus on hot room coupons"""
    weight = 3  # Weight: 3
    wait_time = between(0.05, 0.2)  # 50-200ms interval (faster)
    
    def on_start(self):
        self.user_id = random.randint(USER_ID_MIN, USER_ID_MAX)
        print(f"🔥 [Hot] User {self.user_id} online (hot user)")
    
    @task(10)
    def grab_hot_room_coupon(self):
        """Grab hot room coupons"""
        # Focus on hot rooms (first 5)
        room_id = random.randint(HOT_ROOM_MIN, HOT_ROOM_MAX)
        
        # Get coupons for this room (simplified: assume 5 coupons per room)
        coupon_id = (room_id - 1) * 5 + random.randint(1, 5)
        
        with self.client.post(
            "/api/coupon/grab",
            json={
                "user_id": self.user_id,
                "coupon_id": coupon_id,
                "room_id": room_id
            },
            catch_response=True,
            name="/api/coupon/grab [Hot Room]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(2)
    def query_hot_room_stats(self):
        """Query hot room statistics (Range sharding advantage)"""
        room_id = random.randint(HOT_ROOM_MIN, HOT_ROOM_MAX)
        self.client.get(
            f"/api/room/{room_id}/stats",
            name="/api/room/:id/stats [Hot Room Stats]"
        )

# ============================================================
# Scenario 3: Cross-Shard Query Users (Test Hash sharding cross-shard queries)
# ============================================================
class CrossShardQueryUser(HttpUser):
    """Cross-shard query users: Test Hash sharding aggregate query performance"""
    weight = 1  # Weight: 1 (less frequent)
    wait_time = between(1, 3)  # 1-3 seconds interval (query operations)
    
    def on_start(self):
        print(f"📊 [CrossShard] Query user online")
    
    @task(5)
    def query_room_all_orders(self):
        """Query all orders for a room (Hash sharding requires cross-shard aggregation)"""
        room_id = random.randint(ROOM_ID_MIN, ROOM_ID_MAX)
        self.client.get(
            f"/api/room/{room_id}/orders",
            name="/api/room/:id/orders [Cross Shard]"
        )
    
    @task(3)
    def query_time_range_orders(self):
        """Query orders within time range (Range sharding advantage)"""
        # Query last 1 hour of orders
        self.client.get(
            "/api/orders/recent?hours=1",
            name="/api/orders/recent [Time Range]"
        )
    
    @task(2)
    def global_statistics(self):
        """Global statistics (requires aggregation of all shards)"""
        self.client.get(
            "/api/statistics/global",
            name="/api/statistics/global [All Shards]"
        )

# ============================================================
# Scenario 4: Admin Users
# ============================================================
class AdminUser(HttpUser):
    """Admin: Management operations"""
    weight = 1  # Weight: 1 (least frequent)
    wait_time = between(5, 10)  # 5-10 seconds interval
    
    @task(1)
    def view_system_stats(self):
        """View system statistics"""
        self.client.get(
            "/admin/stats",
            name="/admin/stats [System Stats]"
        )
    
    @task(1)
    def view_db_shard_status(self):
        """View database shard status"""
        self.client.get(
            "/admin/shards/status",
            name="/admin/shards/status [Shard Status]"
        )

# ============================================================
# Custom Load Shape (Optional)
# ============================================================
class StepLoadShape(LoadTestShape):
    """
    Step load:
    - 0-60s: 100 users
    - 60-120s: 500 users
    - 120-180s: 1000 users
    - 180-240s: 2000 users
    """
    step_time = 60
    step_load = 100
    spawn_rate = 10
    time_limit = 240
    
    def tick(self):
        run_time = self.get_run_time()
        
        if run_time > self.time_limit:
            return None
        
        current_step = (run_time // self.step_time) + 1
        users = current_step * self.step_load
        
        return (users, self.spawn_rate)

# ============================================================
# Event Listeners
# ============================================================

@events.request.add_listener
def on_request_success(request_type, name, response_time, response_length, **kwargs):
    """Callback on successful request"""
    global successful_grabs
    
    if "coupon/grab" in name:
        successful_grabs += 1

@events.request.add_listener
def on_request_failure(request_type, name, response_time, response_length, exception, **kwargs):
    """Callback on failed request"""
    global failed_grabs
    
    if "coupon/grab" in name:
        failed_grabs += 1

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Test start"""
    print("\n" + "="*80)
    print("🚀 Locust load test started!")
    print("="*80)
    print(f"Target host: {environment.host}")
    print(f"Simulated user range: {USER_ID_MIN:,} - {USER_ID_MAX:,}")
    print(f"Room range: {ROOM_ID_MIN} - {ROOM_ID_MAX}")
    print(f"Coupon range: {COUPON_ID_MIN} - {COUPON_ID_MAX}")
    print(f"Hot rooms: {HOT_ROOM_MIN} - {HOT_ROOM_MAX}")
    print("="*80)
    print("\nScenario distribution:")
    print("  - Normal users (weight 5): Random coupon grabbing")
    print("  - Hot users (weight 3): Focus on hot room coupons")
    print("  - Cross-shard query users (weight 1): Test aggregate queries")
    print("  - Admin (weight 1): System management")
    print("="*80 + "\n")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Test stop"""
    print("\n" + "="*80)
    print("✅ Locust load test completed!")
    print("="*80)
    
    stats = environment.stats
    total = stats.total
    
    print(f"\n📊 Overall Statistics:")
    print(f"  - Total requests: {total.num_requests:,}")
    print(f"  - Failures: {total.num_failures:,}")
    print(f"  - Failure rate: {total.fail_ratio*100:.2f}%")
    print(f"  - Average response time: {total.avg_response_time:.2f} ms")
    print(f"  - Median response time: {total.median_response_time:.2f} ms")
    print(f"  - P95 response time: {total.get_response_time_percentile(0.95):.2f} ms")
    print(f"  - P99 response time: {total.get_response_time_percentile(0.99):.2f} ms")
    print(f"  - QPS: {total.total_rps:.2f}")
    print(f"  - Total throughput: {total.total_content_length/1024/1024:.2f} MB")
    
    print(f"\n🎯 Coupon Grab Statistics:")
    print(f"  - Successful grabs: {successful_grabs:,}")
    print(f"  - Failed grabs: {failed_grabs:,}")
    
    print("\n📋 Detailed Statistics by Endpoint:")
    for name, stat in sorted(stats.entries.items(), key=lambda x: x[1].num_requests, reverse=True):
        if stat.num_requests > 0:
            print(f"\n  {name}:")
            print(f"    Requests: {stat.num_requests:,}")
            print(f"    Failures: {stat.num_failures:,}")
            print(f"    Avg response: {stat.avg_response_time:.2f} ms")
            print(f"    P95: {stat.get_response_time_percentile(0.95):.2f} ms")
            print(f"    QPS: {stat.total_rps:.2f}")
    
    print("\n" + "="*80)
    print(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")

# ============================================================
# Usage Instructions
# ============================================================
"""
How to run:

1. WebUI mode (recommended):
   locust -f locustfile_advanced.py --host=http://localhost:8000
   Then visit: http://localhost:8089

2. Command line mode (headless):
   locust -f locustfile_advanced.py --host=http://localhost:8000 \\
          --users 1000 --spawn-rate 10 --run-time 5m --headless

3. Use custom load shape:
   locust -f locustfile_advanced.py --host=http://localhost:8000 \\
          --shape StepLoadShape --headless

4. Distributed mode (multi-machine testing):
   # Master
   locust -f locustfile_advanced.py --master --host=http://localhost:8000
   
   # Worker (can be started on multiple machines)
   locust -f locustfile_advanced.py --worker --master-host=<master-ip>

Test Scenario Recommendations:

【Test Hash Sharding】
- Focus on: /api/room/:id/orders [Cross Shard] response time
- Expected: Cross-shard aggregate queries will be slower

【Test Range Sharding】
- Focus on: /api/coupon/grab [Hot Room] distribution
- Expected: Hot room database load will be very high

【Comparison Test】
- Test write QPS for both sharding strategies simultaneously
- Compare /api/orders/recent [Time Range] performance under both strategies
"""
