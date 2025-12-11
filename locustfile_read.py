from locust import HttpUser, task, between
import random

# --- 配置区域 ---
# 必须和你刚才 Python 脚本生成的 ID 范围一致
# 我们刚才设定的是每分片 20000 条，假设你只连了一个分片或者 ID 是连续的
# 建议范围设置大一点，覆盖你的测试数据
MIN_USER_ID = 1
MAX_USER_ID = 20000 

class CouponQueryUser(HttpUser):
    # 模拟每个用户在请求之间思考 0.5 ~ 2 秒
    # 如果想测极限压力，可以把这个时间改小，比如 between(0.01, 0.1)
    wait_time = between(0.5, 2)

    @task
    def query_coupon_logic(self):
        user_id = random.randint(MIN_USER_ID, MAX_USER_ID)
        
        with self.client.get(f"/api/coupons/{user_id}", catch_response=True) as response:
            # 获取后端返回的 Header
            cache_status = response.headers.get("X-Cache", "UNKNOWN")
            
            # 动态修改 Locust 统计里的名字！
            # 这样你在 UI 上就会看到两行： "Coupon [HIT]" 和 "Coupon [MISS]"
            response.request_meta["name"] = f"Coupon [{cache_status}]"

# 如果你想直接运行 python locustfile.py (调试用)
if __name__ == "__main__":
    import os
    os.system("locust -f locustfile.py")