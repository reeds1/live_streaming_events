# locustfile.py
from locust import HttpUser, task, between, events
import random

class CouponGrabUser(HttpUser):
    """Simulate coupon grabbing users"""
    
    wait_time = between(0.001, 0.01)
    
    def on_start(self):
        """Execute once when each virtual user starts"""
        self.user_id = f"user_{random.randint(1, 10000)}"
        print(f"🟢 User {self.user_id} online")
    
    @task(5)
    def grab_coupon(self):
        """Coupon grab request"""
        with self.client.post(
            "/api/coupon/grab",
            json={"user_id": self.user_id},
            catch_response=True
        ) as response:
            # All HTTP 200 responses are successful
            # (including business-level failures like out_of_stock)
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(3)
    def like_action(self):
        """Like action request"""
        with self.client.post(
            "/api/like",
            json={"user_id": self.user_id},
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(1)
    def check_stats(self):
        """Check statistics"""
        self.client.get("/admin/stats")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Execute when test starts"""
    print("\n" + "="*60)
    print("🔥 Load test started!")
    print("="*60)
    print(f"Target host: {environment.host}")
    user_count = getattr(environment.runner, 'target_user_count', 'Not set')
    print(f"User count: {user_count}")
    print("="*60 + "\n")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Execute when test stops"""
    print("\n" + "="*60)
    print("✅ Load test completed!")
    print("="*60)
    
    stats = environment.stats
    print(f"\nTotal requests: {stats.total.num_requests}")
    print(f"Failures: {stats.total.num_failures}")
    if stats.total.num_requests > 0:
        failure_rate = (stats.total.num_failures / stats.total.num_requests) * 100
        print(f"Failure rate: {failure_rate:.2f}%")
    print(f"Average response time: {stats.total.avg_response_time:.2f} ms")
    print(f"P95 response time: {stats.total.get_response_time_percentile(0.95):.2f} ms")
    print(f"P99 response time: {stats.total.get_response_time_percentile(0.99):.2f} ms")
    print(f"RPS (requests per second): {stats.total.total_rps:.2f}")
    print("="*60 + "\n")