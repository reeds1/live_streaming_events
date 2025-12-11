"""
Locust 压力测试文件 - 事件驱动系统
用于测试抢券和点赞功能的高并发性能
"""

from locust import HttpUser, task, between, events
import random
import string
import time
import json

# 全局统计
stats = {
    'coupon_success': 0,
    'coupon_fail': 0,
    'like_success': 0,
    'like_fail': 0,
    'errors': 0
}

def generate_user_id():
    """生成随机用户 ID"""
    timestamp = int(time.time() * 1000)
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"user_{timestamp}_{random_str}"

class CouponGrabUser(HttpUser):
    """抢券用户行为模拟"""
    
    # 等待时间：每个用户在两次请求之间等待 1-3 秒
    wait_time = between(1, 3)
    
    # Producer API 地址
    host = "http://localhost:8000"
    
    @task(10)  # 权重 10：抢券是主要行为
    def grab_coupon(self):
        """抢优惠券"""
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
                        # 库存不足不算失败
                        if data.get('reason') == 'out_of_stock':
                            response.success()
                        else:
                            response.failure(f"抢券失败: {data.get('reason')}")
                else:
                    stats['errors'] += 1
                    response.failure(f"HTTP {response.status_code}")
            except Exception as e:
                stats['errors'] += 1
                response.failure(f"异常: {str(e)}")
    
    @task(3)  # 权重 3：点赞是次要行为
    def like_action(self):
        """点赞"""
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
                        response.failure("点赞失败")
                else:
                    stats['errors'] += 1
                    response.failure(f"HTTP {response.status_code}")
            except Exception as e:
                stats['errors'] += 1
                response.failure(f"异常: {str(e)}")
    
    @task(1)  # 权重 1：偶尔查看系统状态
    def check_status(self):
        """查看系统状态"""
        with self.client.get("/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(1)  # 权重 1：偶尔查看管理统计
    def check_admin_stats(self):
        """查看管理统计"""
        with self.client.get("/admin/stats", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

class QueryUser(HttpUser):
    """查询用户行为模拟（访问 Query API）"""
    
    wait_time = between(2, 5)
    
    # Query API 地址
    host = "http://localhost:5001"
    
    @task(5)  # 查询系统统计
    def get_system_stats(self):
        """查询系统统计"""
        with self.client.get("/system/stats", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(3)  # 查询用户统计（随机用户）
    def get_user_stats(self):
        """查询用户统计"""
        # 生成一个可能存在的用户 ID
        user_id = f"user_{random.randint(1000, 9999)}"
        
        with self.client.get(f"/user/{user_id}/stats", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                # 用户不存在不算失败
                response.success()
    
    @task(1)  # 查看热门点赞
    def get_top_likes(self):
        """查询热门点赞"""
        with self.client.get("/top-likes", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

# 极限压测场景：纯抢券
class ExtremeCouponUser(HttpUser):
    """极限压测：只抢券，无等待"""
    
    wait_time = between(0.1, 0.5)  # 极短等待时间
    host = "http://localhost:8000"
    
    @task
    def grab_coupon_fast(self):
        """快速抢券"""
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

# 事件钩子：测试开始
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """测试开始时执行"""
    print("\n" + "="*60)
    print("🚀 Locust 压力测试开始")
    print("="*60)
    print(f"目标主机: {environment.host}")
    print(f"测试场景: 抢券 + 点赞 + 查询")
    print("="*60 + "\n")

# 事件钩子：测试结束
@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """测试结束时执行"""
    print("\n" + "="*60)
    print("📊 测试统计报告")
    print("="*60)
    print(f"✅ 抢券成功: {stats['coupon_success']}")
    print(f"❌ 抢券失败: {stats['coupon_fail']}")
    print(f"👍 点赞成功: {stats['like_success']}")
    print(f"👎 点赞失败: {stats['like_fail']}")
    print(f"⚠️  错误总数: {stats['errors']}")
    print("="*60 + "\n")

# 事件钩子：定期打印统计
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """每个请求完成时触发"""
    # 每 100 个请求打印一次
    if stats['coupon_success'] % 100 == 0 and stats['coupon_success'] > 0:
        print(f"⚡ 已处理 {stats['coupon_success']} 个抢券请求...")

if __name__ == "__main__":
    """
    命令行运行说明：
    
    基础运行：
    locust -f locustfile.py
    
    指定用户数和增长率：
    locust -f locustfile.py --users 100 --spawn-rate 10
    
    无 Web UI 模式（命令行）：
    locust -f locustfile.py --headless --users 100 --spawn-rate 10 --run-time 60s
    
    指定测试场景：
    # 只测试抢券
    locust -f locustfile.py --users 100 --spawn-rate 10 CouponGrabUser
    
    # 极限压测
    locust -f locustfile.py --users 500 --spawn-rate 50 ExtremeCouponUser
    
    # 混合测试（抢券 + 查询）
    locust -f locustfile.py --users 200 --spawn-rate 20 CouponGrabUser QueryUser
    """
    import os
    os.system("locust -f locustfile.py")