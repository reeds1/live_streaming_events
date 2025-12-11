import pymysql
import sys
import os

# Adjust import path to include current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    # Try importing configuration from different possible paths
    from hash_vs_range_comparison.strategies.database_aws import DatabaseConfigAWS
except ImportError:
    try:
        from strategies.database_aws import DatabaseConfigAWS
    except ImportError:
        from database_aws import DatabaseConfigAWS

def verify():
    print("🕵️‍♂️ Starting AWS data consistency check...")
    print("="*50)
    
    total_orders = 0
    # The coupon ID used in the attacker script
    correct_coupon_id = 101
    
    for shard_id, config in DatabaseConfigAWS.SHARD_DBS.items():
        conn = None
        try:
            # Establish connection
            conn = pymysql.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                database=config['database'],
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor, # Enforce returning dictionaries
                connect_timeout=10
            )
            
            with conn.cursor() as cursor:
                # Query the hash sharding table
                sql = "SELECT count(*) as cnt FROM coupon_results_hash WHERE coupon_id = %s"
                cursor.execute(sql, (correct_coupon_id,))
                
                # Fetch result
                result = cursor.fetchone()
                
                # Safely retrieve data
                if result and 'cnt' in result:
                    count = result['cnt']
                else:
                    count = 0
                
                print(f"📦 [Shard {shard_id}] Order count: {count}")
                total_orders += count
                
        except Exception as e:
            print(f"❌ [Shard {shard_id}] Query failed: {e}")
        finally:
            if conn:
                conn.close()

    print("="*50)
    print(f"📊 Final Verification Results:")
    print(f"   Expected Orders: 10 (Redis initial stock)")
    print(f"   Actual Orders:   {total_orders} (AWS total stored)")
    
    if total_orders == 2000:
        print("\n✅ Perfect! System is consistent. No overselling, no data loss!")
    elif total_orders > 2000:
        print("\n❌ CRITICAL: Overselling detected!")
    else:
        print(f"\n⚠️ WARNING: Only received {total_orders} orders (Expected 10).")
        print("   Possible causes: Consumer lag (still processing) or write errors.")

if __name__ == "__main__":
    verify()