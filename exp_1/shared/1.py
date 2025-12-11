import redis

try:
    # 建立连接
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    r.ping()
    
    # 获取服务器信息
    info = r.info()
    
    print("="*40)
    print("🕵️‍♂️ 侦探报告：当前连接的 Redis 身份")
    print("="*40)
    
    # 1. 看操作系统内核 (最铁的证据)
    os_info = info['os']
    print(f"📍 运行系统 (OS): {os_info}")
    
    # 2.看版本
    print(f"🔢 Redis 版本:  {info['redis_version']}")
    
    # 3.看进程ID
    print(f"🆔 进程 ID:     {info['process_id']}")

    print("-" * 40)
    
    # === 自动判断逻辑 (基于你用的是 Mac) ===
    if "Darwin" in os_info:
        print("💡 结论：【本地安装版】 (Homebrew/直接安装)")
        print("   证据：Darwin 是 macOS 的内核名称。")
    elif "Linux" in os_info:
        print("💡 结论：【Docker 容器版】")
        print("   证据：Docker Desktop 在 Mac 上是运行在一个 Linux 虚拟机里的。")
    else:
        print("💡 结论：未知，请自行判断。")

except Exception as e:
    print(f"❌ 根本连不上: {e}")