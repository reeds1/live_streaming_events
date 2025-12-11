import requests
import random
import time

# Assume we created 20000 users (ID 1 ~ 20000)
# We only warm up the first 20% (ID 1 ~ 4000) to simulate "active users"

def warm_up_cache():
    print("🔥 Starting Redis warmup (preload first 20% hot data)...")
    
    # Iterate through first 4000 users
    for user_id in range(1, 4001):
        # Call API, let backend logic automatically write data to Redis
        try:
            requests.get(f"http://localhost:8080/api/coupons/{user_id}")
        except:
            pass
        
        if user_id % 500 == 0:
            print(f"   Warmed up {user_id} entries...")
            
    print("✅ Warmup complete! First 4000 users are now Cache Hit, later users are Cache Miss.")

if __name__ == "__main__":
    warm_up_cache()