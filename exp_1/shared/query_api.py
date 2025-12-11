# query_api.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis
import mysql.connector
from mysql.connector import pooling
from typing import List, Optional
import os

app = FastAPI(
    title="Event Query API",
    description="查询用户事件和统计信息",
    version="1.0.0"
)


REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
MYSQL_HOST = os.getenv('MYSQL_HOST', '127.0.0.1')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3307))
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'root123')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'event_system')

mysql_pool = pooling.MySQLConnectionPool(
    pool_name="query_pool",
    pool_size=5,
    host=MYSQL_HOST,
    port=MYSQL_PORT,  
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DATABASE
)


redis_client = redis.Redis(
    host=REDIS_HOST,
    port=6379,
    decode_responses=True
)

@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "Query API",
        "endpoints": [
            "/user/{user_id}/stats",
            "/user/{user_id}/coupons",
            "/user/{user_id}/history",
            "/system/stats"
        ]
    }

@app.get("/user/{user_id}/stats")
async def get_user_stats(user_id: str):
    try:
        attempts = redis_client.get(f"user:attempts:{user_id}")
        success = redis_client.get(f"user:success:{user_id}")
        failed = redis_client.get(f"user:failed:{user_id}")
        likes = redis_client.get(f"user:likes:{user_id}")
        
        if attempts is not None:
            return {
                "user_id": user_id,
                "source": "redis",
                "coupon_stats": {
                    "total_attempts": int(attempts) if attempts else 0,
                    "successful_grabs": int(success) if success else 0,
                    "failed_grabs": int(failed) if failed else 0
                },
                "like_count": int(likes) if likes else 0
            }
        
        conn = mysql_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT * FROM user_coupon_stats WHERE user_id = %s
        """, (user_id,))
        coupon_stats = cursor.fetchone()
        
        cursor.execute("""
            SELECT COUNT(*) as like_count 
            FROM like_events 
            WHERE user_id = %s
        """, (user_id,))
        like_result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not coupon_stats:
            return {
                "user_id": user_id,
                "source": "mysql",
                "message": "No data found"
            }
        
        return {
            "user_id": user_id,
            "source": "mysql",
            "coupon_stats": {
                "total_attempts": coupon_stats['total_attempts'],
                "successful_grabs": coupon_stats['successful_grabs'],
                "failed_grabs": coupon_stats['failed_grabs'],
                "last_attempt_time": coupon_stats['last_attempt_time']
            },
            "like_count": like_result['like_count'] if like_result else 0
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/user/{user_id}/coupons")
async def get_user_coupons(user_id: str):
    try:
        coupons = redis_client.lrange(f"user:coupons:{user_id}", 0, -1)
        
        if not coupons:
            conn = mysql_pool.get_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT id, timestamp, created_at 
                FROM coupon_events 
                WHERE user_id = %s AND success = TRUE
                ORDER BY created_at DESC
                LIMIT 50
            """, (user_id,))
            
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return {
                "user_id": user_id,
                "source": "mysql",
                "coupons": results,
                "count": len(results)
            }
        
        import json
        return {
            "user_id": user_id,
            "source": "redis",
            "coupons": [json.loads(c) for c in coupons],
            "count": len(coupons)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/user/{user_id}/history")
async def get_user_history(
    user_id: str,
    limit: int = 50,
    event_type: Optional[str] = None
):
    try:
        conn = mysql_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        if event_type == 'coupon':
            cursor.execute("""
                SELECT * FROM coupon_events 
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (user_id, limit))
        elif event_type == 'like':
            cursor.execute("""
                SELECT * FROM like_events 
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (user_id, limit))
        else:
            cursor.execute("""
                (SELECT id, user_id, event_type, timestamp, created_at, 
                        success as detail1, reason as detail2
                 FROM coupon_events WHERE user_id = %s)
                UNION ALL
                (SELECT id, user_id, event_type, timestamp, created_at,
                        is_top_like as detail1, NULL as detail2
                 FROM like_events WHERE user_id = %s)
                ORDER BY created_at DESC
                LIMIT %s
            """, (user_id, user_id, limit))
        
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return {
            "user_id": user_id,
            "events": results,
            "count": len(results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/system/stats")
async def get_system_stats():
    try:
        current_stock = redis_client.get("coupon:stock")
        
        conn = mysql_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT COUNT(*) as total FROM coupon_events")
        coupon_total = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) as total FROM coupon_events WHERE success = TRUE")
        coupon_success = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) as total FROM like_events")
        like_total = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(DISTINCT user_id) as total FROM user_coupon_stats")
        total_users = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return {
            "current_stock": int(current_stock) if current_stock else 0,
            "coupon_events": {
                "total": coupon_total['total'],
                "successful": coupon_success['total']
            },
            "like_events": {
                "total": like_total['total']
            },
            "total_users": total_users['total']
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/top-likes")
async def get_top_likes(limit: int = 10):
    try:
        top_users = redis_client.zrevrange("top_likes", 0, limit - 1, withscores=True)
        
        return {
            "top_likes": [
                {"user_id": user_id, "score": score}
                for user_id, score in top_users
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    import uvicorn
    
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║          Event Query API                               ║
    ║          Redis (Cache) + MySQL (Storage)               ║
    ╚════════════════════════════════════════════════════════╝
    
    Start: uvicorn query_api:app --reload --port 5001
    Docs:  http://localhost:5001/docs
    """)
    
    uvicorn.run("query_api:app", host="0.0.0.0", port=5001, reload=True)