import requests
import random
import time

# 假设刚才造了 20000 个用户 (ID 1 ~ 20000)
# 我们只预热前 20% (ID 1 ~ 4000) 模拟“活跃用户”

def warm_up_cache():
    print("🔥 开始预热 Redis (预加载前 20% 热点数据)...")
    
    # 遍历前 4000 个用户
    for user_id in range(1, 4001):
        # 调用 API，让后端逻辑自动把数据写入 Redis
        try:
            requests.get(f"http://localhost:8080/api/coupons/{user_id}")
        except:
            pass
        
        if user_id % 500 == 0:
            print(f"   已预热 {user_id} 条...")
            
    print("✅ 预热完成！前 4000 个用户现在是 Cache Hit，后面的用户是 Cache Miss。")

if __name__ == "__main__":
    warm_up_cache()