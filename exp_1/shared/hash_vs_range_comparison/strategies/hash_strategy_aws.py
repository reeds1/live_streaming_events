"""
Hash Sharding Strategy for AWS RDS
Identical logic to local version, but connects to AWS RDS
"""

from sharding_interface import ShardingStrategy, CouponResult, ShardingStats
from database_aws import connection_pool_aws
from typing import List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class HashShardingStrategyAWS(ShardingStrategy):
    """Hash-based sharding strategy on AWS RDS"""
    
    def __init__(self, num_shards: int = 4):
        self.num_shards = num_shards
        self.pool = connection_pool_aws
        self.table_name = "coupon_results_hash"  # Use dedicated table for Hash
    
    def initialize(self) -> bool:
        """Initialize database connections"""
        return self.pool.initialize()
    
    def _get_shard_id(self, user_id: int) -> int:
        """Calculate shard ID from user_id"""
        return hash(user_id) % self.num_shards
        #return 0
    
    def save_coupon_result(self, coupon_result: CouponResult) -> bool:
        """Save coupon grab result to appropriate shard"""
        shard_id = self._get_shard_id(coupon_result.user_id)
        conn = self.pool.get_shard_connection(shard_id)
        
        try:
            with conn.cursor() as cursor:
                sql = f"""
                INSERT INTO {self.table_name}
                (user_id, coupon_id, room_id, grab_status, fail_reason, grab_time)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (
                    coupon_result.user_id,
                    coupon_result.coupon_id,
                    coupon_result.room_id,
                    coupon_result.grab_status,
                    coupon_result.fail_reason,
                    coupon_result.grab_time or datetime.now()
                ))
                conn.commit()
                return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Save failed: {e}")
            return False
    
    def query_user_coupons(self, user_id: int) -> List[CouponResult]:
        """Query user's coupons - HASH ADVANTAGE on AWS!"""
        shard_id = self._get_shard_id(user_id)
        conn = self.pool.get_shard_connection(shard_id)
        
        try:
            with conn.cursor() as cursor:
                sql = f"""
                SELECT * FROM {self.table_name}
                WHERE user_id = %s 
                ORDER BY grab_time DESC
                """
                cursor.execute(sql, (user_id,))
                rows = cursor.fetchall()
                return [self._row_to_coupon_result(row) for row in rows]
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []
    
    def query_room_orders(self, room_id: int, limit: int = 100) -> List[CouponResult]:
        """Query room orders - slower, must query all shards"""
        all_results = []
        for shard_id in range(self.num_shards):
            conn = self.pool.get_shard_connection(shard_id)
            try:
                with conn.cursor() as cursor:
                    sql = f"""
                    SELECT * FROM {self.table_name}
                    WHERE room_id = %s 
                    ORDER BY grab_time DESC 
                    LIMIT %s
                    """
                    cursor.execute(sql, (room_id, limit))
                    rows = cursor.fetchall()
                    all_results.extend([self._row_to_coupon_result(row) for row in rows])
            except Exception as e:
                logger.error(f"Query shard {shard_id} failed: {e}")
        
        all_results.sort(key=lambda x: x.grab_time, reverse=True)
        return all_results[:limit]
    
    def query_time_range_orders(self, start_time: datetime, 
                               end_time: datetime,
                               limit: int = 1000) -> List[CouponResult]:
        """Query time range - slower, must query all shards"""
        all_results = []
        for shard_id in range(self.num_shards):
            conn = self.pool.get_shard_connection(shard_id)
            try:
                with conn.cursor() as cursor:
                    sql = f"""
                    SELECT * FROM {self.table_name}
                    WHERE grab_time BETWEEN %s AND %s 
                    ORDER BY grab_time DESC 
                    LIMIT %s
                    """
                    cursor.execute(sql, (start_time, end_time, limit))
                    rows = cursor.fetchall()
                    all_results.extend([self._row_to_coupon_result(row) for row in rows])
            except Exception as e:
                logger.error(f"Query shard {shard_id} failed: {e}")
        
        all_results.sort(key=lambda x: x.grab_time, reverse=True)
        return all_results[:limit]
    
    def get_shard_stats(self) -> List[ShardingStats]:
        """Get statistics for each shard"""
        stats = []
        for shard_id in range(self.num_shards):
            conn = self.pool.get_shard_connection(shard_id)
            try:
                with conn.cursor() as cursor:
                    cursor.execute(f"SELECT COUNT(*) as cnt FROM {self.table_name}")
                    result = cursor.fetchone()
                    total_records = result['cnt'] if result else 0
                    
                    stats.append(ShardingStats(
                        shard_id=f"aws_shard_{shard_id}",
                        total_records=total_records,
                        avg_response_time=0.0,
                        cpu_usage=0.0,
                        io_usage=0.0,
                        connection_count=0
                    ))
            except Exception as e:
                logger.error(f"Get stats failed for shard {shard_id}: {e}")
        
        return stats
    
    def get_strategy_name(self) -> str:
        return "Hash Partitioning (AWS RDS)"
    
    def _row_to_coupon_result(self, row: dict) -> CouponResult:
        """Convert database row to CouponResult object"""
        return CouponResult(
            result_id=row.get('result_id'),
            user_id=row.get('user_id'),
            coupon_id=row.get('coupon_id'),
            room_id=row.get('room_id'),
            grab_status=row.get('grab_status'),
            fail_reason=row.get('fail_reason'),
            grab_time=row.get('grab_time'),
            use_status=row.get('use_status'),
            use_time=row.get('use_time'),
            order_amount=row.get('order_amount')
        )

