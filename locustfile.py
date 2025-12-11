"""
Locust load testing file - Event-driven system
For testing high-concurrency performance of coupon grabbing and like functionality
"""

from locust import HttpUser, task, between, events
import random
import string
import time
import json

# Global statistics
stats = {
    'coupon_success': 0,
    'coupon_fail': 0,
    'like_success': 0,
    'like_fail': 0,
    'errors': 0
}

def generate_user_id():
    """Generate random user ID"""
    timestamp = int(time.time() * 1000)
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"user_{timestamp}_{random_str}"

class CouponGrabUser(HttpUser):
    """Coupon grab user behavior simulation"""
    
    # Wait time: Each user waits 1-3 seconds between requests
    wait_time = between(1, 3)
    
    # Producer API address
    host = "http://localhost:8000"
    
    @task(10)  # Weight 10: Coupon grabbing is the main behavior
    def grab_coupon(self):
        """Grab coupon"""
        user_id = generate_user_id()
        
        with self.client.post(
            "/api/coupon/grab",
            json={"user_id": user_id},
            catch_response=True
        ) as response:
            try:
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        stats['coupon_success'] += 1
                        response.success()
                    else:
                        stats['coupon_fail'] += 1
                        # Out of stock is not considered a failure
                        if data.get('reason') == 'out_of_stock':
                            response.success()
                        else:
                            response.failure(f"Coupon grab failed: {data.get('reason')}")
                else:
                    stats['errors'] += 1
                    response.failure(f"HTTP {response.status_code}")
            except Exception as e:
                stats['errors'] += 1
                response.failure(f"Exception: {str(e)}")
    
    @task(3)  # Weight 3: Like is secondary behavior
    def like_action(self):
        """Like action"""
        user_id = generate_user_id()
        
        with self.client.post(
            "/api/like",
            json={"user_id": user_id},
            catch_response=True
        ) as response:
            try:
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        stats['like_success'] += 1
                        response.success()
                    else:
                        stats['like_fail'] += 1
                        response.failure("Like failed")
                else:
                    stats['errors'] += 1
                    response.failure(f"HTTP {response.status_code}")
            except Exception as e:
                stats['errors'] += 1
                response.failure(f"Exception: {str(e)}")
    
    @task(1)  # Weight 1: Occasionally check system status
    def check_status(self):
        """Check system status"""
        with self.client.get("/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(1)  # Weight 1: Occasionally check admin statistics
    def check_admin_stats(self):
        """Check admin statistics"""
        with self.client.get("/admin/stats", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

class QueryUser(HttpUser):
    """Query user behavior simulation (access Query API)"""
    
    wait_time = between(2, 5)
    
    # Query API address
    host = "http://localhost:5001"
    
    @task(5)  # Query system statistics
    def get_system_stats(self):
        """Query system statistics"""
        with self.client.get("/system/stats", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(3)  # Query user statistics (random user)
    def get_user_stats(self):
        """Query user statistics"""
        # Generate a possibly existing user ID
        user_id = f"user_{random.randint(1000, 9999)}"
        
        with self.client.get(f"/user/{user_id}/stats", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                # User not found is not considered a failure
                response.success()
    
    @task(1)  # View top likes
    def get_top_likes(self):
        """Query top likes"""
        with self.client.get("/top-likes", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

# Extreme load test scenario: Pure coupon grabbing
class ExtremeCouponUser(HttpUser):
    """Extreme load test: Only grab coupons, no waiting"""
    
    wait_time = between(0.1, 0.5)  # Very short wait time
    host = "http://localhost:8000"
    
    @task
    def grab_coupon_fast(self):
        """Fast coupon grab"""
        user_id = generate_user_id()
        
        with self.client.post(
            "/api/coupon/grab",
            json={"user_id": user_id},
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

# Event hook: Test start
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Execute when test starts"""
    print("\n" + "="*60)
    print("🚀 Locust load test started")
    print("="*60)
    print(f"Target host: {environment.host}")
    print(f"Test scenario: Coupon grab + Like + Query")
    print("="*60 + "\n")

# Event hook: Test stop
@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Execute when test stops"""
    print("\n" + "="*60)
    print("📊 Test statistics report")
    print("="*60)
    print(f"✅ Coupon success: {stats['coupon_success']}")
    print(f"❌ Coupon failed: {stats['coupon_fail']}")
    print(f"👍 Like success: {stats['like_success']}")
    print(f"👎 Like failed: {stats['like_fail']}")
    print(f"⚠️  Total errors: {stats['errors']}")
    print("="*60 + "\n")

# Event hook: Periodic statistics printing
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Triggered when each request completes"""
    # Print every 100 requests
    if stats['coupon_success'] % 100 == 0 and stats['coupon_success'] > 0:
        print(f"⚡ Processed {stats['coupon_success']} coupon grab requests...")

if __name__ == "__main__":
    """
    Command line usage:
    
    Basic run:
    locust -f locustfile.py
    
    Specify user count and spawn rate:
    locust -f locustfile.py --users 100 --spawn-rate 10
    
    Headless mode (command line):
    locust -f locustfile.py --headless --users 100 --spawn-rate 10 --run-time 60s
    
    Specify test scenario:
    # Only test coupon grabbing
    locust -f locustfile.py --users 100 --spawn-rate 10 CouponGrabUser
    
    # Extreme load test
    locust -f locustfile.py --users 500 --spawn-rate 50 ExtremeCouponUser
    
    # Mixed test (coupon grab + query)
    locust -f locustfile.py --users 200 --spawn-rate 20 CouponGrabUser QueryUser
    """
    import os
    os.system("locust -f locustfile.py")