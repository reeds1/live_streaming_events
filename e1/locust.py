# locustfile.py
from locust import HttpUser, task, between, events
import random
import time

class CouponGrabUser(HttpUser):
    """Simulate coupon grabbing users"""
    
    # User request interval time (seconds)
    wait_time = between(0.001, 0.01)  # Random between 1-10ms
    
    def on_start(self):
        """Execute once when each virtual user starts"""
        self.user_id = f"user_{random.randint(1, 10000)}"
        print(f"🟢 User {self.user_id} online")
    
    @task(5)  # Weight 5: coupon grab requests are more frequent
    def grab_coupon(self):
        """Coupon grab request"""
        with self.client.post(
            "/api/coupon/grab",
            json={"user_id": self.user_id},
            catch_response=True  # Catch response for custom success/failure
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    response.success()
                else:
                    # Out of stock is normal, not counted as failure
                    if data.get('reason') == 'out_of_stock':
                        response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(3)  # Weight 3: like requests are relatively less frequent
    def like_action(self):
        """Like action request"""
        self.client.post(
            "/api/like",
            json={"user_id": self.user_id}
        )
    
    @task(1)  # Weight 1: occasionally check statistics
    def check_stats(self):
        """Check statistics"""
        self.client.get("/admin/stats")


# ============================================================
# Custom Statistics and Event Listeners
# ============================================================

# Global counters
successful_grabs = 0
failed_grabs = 0

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):
    """Listen to each request"""
    global successful_grabs, failed_grabs
    
    # If it's a coupon grab request
    if name == "/api/coupon/grab" and not exception:
        # Can parse response here to track success/failure
        pass

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Execute when test starts"""
    print("\n" + "="*60)
    print("🔥 Load test started!")
    print("="*60)
    print(f"Target host: {environment.host}")
    print(f"User count: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'Not set'}")
    print("="*60 + "\n")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Execute when test stops"""
    print("\n" + "="*60)
    print("✅ Load test completed!")
    print("="*60)
    
    # Print statistics
    stats = environment.stats
    print(f"\nTotal requests: {stats.total.num_requests}")
    print(f"Failures: {stats.total.num_failures}")
    print(f"Average response time: {stats.total.avg_response_time:.2f} ms")
    print(f"P95 response time: {stats.total.get_response_time_percentile(0.95):.2f} ms")
    print(f"P99 response time: {stats.total.get_response_time_percentile(0.99):.2f} ms")
    print(f"RPS (requests per second): {stats.total.total_rps:.2f}")
    print("="*60 + "\n")