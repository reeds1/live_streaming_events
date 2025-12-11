import redis

try:
    # Establish connection
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    r.ping()
    
    # Get server information
    info = r.info()
    
    print("="*40)
    print("🕵️‍♂️ Detective Report: Current Redis Identity")
    print("="*40)
    
    # 1. Check OS kernel (strongest evidence)
    os_info = info['os']
    print(f"📍 Running OS: {os_info}")
    
    # 2. Check version
    print(f"🔢 Redis version:  {info['redis_version']}")
    
    # 3. Check process ID
    print(f"🆔 Process ID:     {info['process_id']}")

    print("-" * 40)
    
    # === Auto-detection logic (based on Mac usage) ===
    if "Darwin" in os_info:
        print("💡 Conclusion: 【Local Installation】 (Homebrew/direct install)")
        print("   Evidence: Darwin is the kernel name of macOS.")
    elif "Linux" in os_info:
        print("💡 Conclusion: 【Docker Container】")
        print("   Evidence: Docker Desktop on Mac runs in a Linux virtual machine.")
    else:
        print("💡 Conclusion: Unknown, please judge yourself.")

except Exception as e:
    print(f"❌ Cannot connect: {e}")