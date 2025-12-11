import aiohttp
import asyncio
import time
import random

# ✅ Adapt to your AWS integrated API address
API_URL = "http://localhost:8002/api/coupon/grab"

# Configuration: 2000 people grabbing 10 coupons (Coupon 101)
TOTAL_REQUESTS = 2000 
CONCURRENCY = 1000

success_count = 0
fail_count = 0

async def attack(session):
    global success_count, fail_count
    user_id = random.randint(100000, 999999)
    
    # ✅ [Critical modification] Construct JSON matching new API definition
    payload = {
        "user_id": str(user_id),
        "coupon_id": 101,  # Must be the ID that exists in Redis
        "room_id": 1001    # Must correspond to Room ID in database
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
                print(f"🎉 User {user_id} grabbed it! Remaining stock: {result.get('remaining_stock')}")
            else:
                fail_count += 1
    except Exception as e:
        print(f"❌ Request Error: {e}")
        fail_count += 1

async def main():
    print(f"🏁 AWS architecture load test started: Target Coupon 101 (stock 10)...")
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