# attacker.py
import aiohttp
import asyncio
import time
import random

# 配置
API_URL = "http://localhost:8000/api/coupon/grab"
TOTAL_REQUESTS = 5000    # 总请求数
CONCURRENCY = 1000        # 并发数 (模拟多少人同时点)

success_count = 0
fail_count = 0

async def attack(session, user_id):
    global success_count, fail_count
    try:
        async with session.post(API_URL, json={"user_id": f"user_{user_id}"}) as response:
            result = await response.json()
            if result.get('success'):
                success_count += 1
                # print(f"✅ User {user_id} got one!")
            else:
                fail_count += 1
    except Exception as e:
        print(f"❌ Request failed: {e}")
        fail_count += 1

async def main():
    print(f"🔥 Starting attack: {TOTAL_REQUESTS} requests with {CONCURRENCY} concurrency...")
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(TOTAL_REQUESTS):
            tasks.append(attack(session, i))
            # 控制并发节奏
            if len(tasks) >= CONCURRENCY:
                await asyncio.gather(*tasks)
                tasks = []
        
        if tasks:
            await asyncio.gather(*tasks)
            
    duration = time.time() - start_time
    print(f"\n╔════════════════════════════════════╗")
    print(f"║ 📊 Test Results                     ║")
    print(f"╠════════════════════════════════════╣")
    print(f"║ Total Time:    {duration:.2f}s             ║")
    print(f"║ QPS:           {TOTAL_REQUESTS/duration:.2f} req/s       ║")
    print(f"║ Success (Grab): {success_count}                 ║")
    print(f"║ Failed:        {fail_count}                 ║")
    print(f"╚════════════════════════════════════╝")

if __name__ == "__main__":
    asyncio.run(main())