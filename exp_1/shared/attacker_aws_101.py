import aiohttp
import asyncio
import time
import random

# ✅ 适配你的 AWS 集成版 API 地址
API_URL = "http://localhost:8002/api/coupon/grab"

# 配置：1000 人抢 10 张券 (Coupon 101)
TOTAL_REQUESTS = 2000 
CONCURRENCY = 1000

success_count = 0
fail_count = 0

async def attack(session):
    global success_count, fail_count
    user_id = random.randint(100000, 999999)
    
    # ✅ [关键修改] 构造符合新 API 定义的 JSON
    payload = {
        "user_id": str(user_id),
        "coupon_id": 101,  # 必须是 Redis 里有的那个 ID
        "room_id": 1001    # 必须对应数据库里的 Room ID
    }
    
    try:
        async with session.post(API_URL, json=payload) as response:
            if response.status != 200:
                print(f"❌ HTTP Error: {response.status}")
                fail_count += 1
                return

            result = await response.json()
            if result.get('success'):
                success_count += 1
                print(f"🎉 User {user_id} 抢到了! 剩余库存: {result.get('remaining_stock')}")
            else:
                fail_count += 1
    except Exception as e:
        print(f"❌ Request Error: {e}")
        fail_count += 1

async def main():
    print(f"🏁 AWS 架构压测开始: 目标 Coupon 101 (库存10)...")
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for _ in range(TOTAL_REQUESTS):
            tasks.append(attack(session))
            if len(tasks) >= CONCURRENCY:
                await asyncio.gather(*tasks)
                tasks = []
        if tasks:
            await asyncio.gather(*tasks)
            
    duration = time.time() - start_time
    print(f"\n╔════════════════════════════════════╗")
    print(f"║ 📊 AWS Architecture Test Result     ║")
    print(f"╠════════════════════════════════════╣")
    print(f"║ Total Time:    {duration:.4f}s            ║")
    print(f"║ Success:       {success_count} (Should be 2000)   ║")
    print(f"║ Failed:        {fail_count}                 ║")
    print(f"╚════════════════════════════════════╝")

if __name__ == "__main__":
    asyncio.run(main())