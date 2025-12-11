"""
Range Sharding Strategy Implementation for Comparison
Shards data by room_id: shard_id = room_id range
"""

from sharding_interface import ShardingStrategy, CouponResult, ShardingStats
from database import connection_pool
from typing import List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class RangeShardingStrategy(ShardingStrategy):
    """
    Range-based sharding strategy
    Key: room_id
    Formula: Assign shards based on room_id ranges
    
    Shard 0: room_id 1-1000
    Shard 1: room_id 1001-2000
    Shard 2: room_id 2001-3000
    Shard 3: room_id 3001+
    """
    
    def __init__(self, num_shards: int = 4):
        self.num_shards = num_shards
        self.pool = connection_pool
        # Define room ranges for each shard
        self.shard_ranges = [
            (1, 1000),      # Shard 0
            (1001, 2000),   # Shard 1
            (2001, 3000),   # Shard 2
            (3001, 999999)  # Shard 3
        ]
    
    def initialize(self) -> bool:
        """Initialize database connections"""
        return self.pool.initialize()
    
    def _get_shard_id(self, room_id: int) -> int:
        """
        Core routing logic: Calculate shard ID from room_id
        
        Range partitioning:
        - Direct mapping based on room_id ranges
        - Efficient for room-based queries
        """
        for shard_id, (min_room, max_room) in enumerate(self.shard_ranges):
            if min_room <= room_id <= max_room:
                return shard_id
        # Default to last shard if out of range
        return self.num_shards - 1
    
    def save_coupon_result(self, coupon_result: CouponResult) -> bool:
        """
        Save coupon grab result to appropriate shard
        
        Range Sharding Challenge:
        - Hot rooms (e.g., room_id 1001) may concentrate on one shard
        - Uneven load distribution
        """
        shard_id = self._get_shard_id(coupon_result.room_id)
        conn = self.pool.get_shard_connection(shard_id)
        
        try:
            with conn.cursor() as cursor:
                sql = """
                INSERT INTO coupon_results 
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
                
                logger.debug(f"Saved to shard {shard_id}: room {coupon_result.room_id}")
                return True
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Save failed: {e}")
            return False
    
    def query_user_coupons(self, user_id: int) -> List[CouponResult]:
        """
        Query user's coupons - RANGE DISADVANTAGE!
        
        Why slow?
        - user_id doesn't determine shard
        - Must query ALL 4 shards
        - Aggregate results
        """
        all_results = []
        
        # Query all shards (expensive!)
        for shard_id in range(self.num_shards):
            conn = self.pool.get_shard_connection(shard_id)
            
            try:
                with conn.cursor() as cursor:
                    sql = """
                    SELECT * FROM coupon_results 
                    WHERE user_id = %s 
                    ORDER BY grab_time DESC
                    """
                    cursor.execute(sql, (user_id,))
                    rows = cursor.fetchall()
                    
                    all_results.extend([self._row_to_coupon_result(row) for row in rows])
                    
            except Exception as e:
                logger.error(f"Query shard {shard_id} failed: {e}")
        
        return all_results
    
    def query_room_orders(self, room_id: int, limit: int = 100) -> List[CouponResult]:
        """
        Query room orders - RANGE ADVANTAGE!
        
        Why fast?
        - room_id directly determines shard
        - Only need to query ONE shard
        - No cross-shard aggregation
        """
        shard_id = self._get_shard_id(room_id)
        conn = self.pool.get_shard_connection(shard_id)
        
        try:
            with conn.cursor() as cursor:
                sql = """
                SELECT * FROM coupon_results 
                WHERE room_id = %s 
                ORDER BY grab_time DESC 
                LIMIT %s
                """
                cursor.execute(sql, (room_id, limit))
                rows = cursor.fetchall()
                
                return [self._row_to_coupon_result(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []
    
    def query_time_range_orders(self, start_time: datetime, 
                               end_time: datetime,
                               limit: int = 1000) -> List[CouponResult]:
        """
        Query time range - RANGE ADVANTAGE (if partitioned by time)!
        
        Current implementation (by room_id):
        - Still need to query all shards
        - But typically fewer shards than hash (can optimize with metadata)
        """
        all_results = []
        
        for shard_id in range(self.num_shards):
            conn = self.pool.get_shard_connection(shard_id)
            
            try:
                with conn.cursor() as cursor:
                    sql = """
                    SELECT * FROM coupon_results 
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
                    cursor.execute("SELECT COUNT(*) as cnt FROM coupon_results")
                    result = cursor.fetchone()
                    total_records = result['cnt'] if result else 0
                    
                    stats.append(ShardingStats(
                        shard_id=f"shard_{shard_id}",
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
        return "Range Partitioning (by room_id)"
    
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

