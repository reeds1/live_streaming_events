"""
Sharding Strategy Interface Definition

This is the unified interface that both Student A and Student B need to implement
to ensure that both sharding strategies are interchangeable.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass

# ============================================================
# Data Models
# ============================================================

@dataclass
class CouponResult:
    """Coupon grab result data model"""
    result_id: Optional[int] = None
    user_id: int = 0
    coupon_id: int = 0
    room_id: int = 0
    grab_status: int = 0  # 0-Failed 1-Success
    fail_reason: Optional[str] = None
    grab_time: Optional[datetime] = None
    use_status: int = 0  # 0-Not used 1-Used 2-Expired
    use_time: Optional[datetime] = None
    order_amount: Optional[float] = None

@dataclass
class ShardingStats:
    """Sharding statistics information"""
    shard_id: str
    total_records: int
    avg_response_time: float  # ms
    cpu_usage: float  # %
    io_usage: float  # %
    connection_count: int

# ============================================================
# Sharding Strategy Interface
# ============================================================

class ShardingStrategy(ABC):
    """
    Sharding strategy abstract interface
    
    Student A implements: HashShardingStrategy
    Student B implements: RangeShardingStrategy
    """
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize sharding strategy
        
        Returns:
            bool: Whether initialization succeeded
        """
        pass
    
    @abstractmethod
    def save_coupon_result(self, coupon_result: CouponResult) -> bool:
        """
        Save coupon grab result
        
        Args:
            coupon_result: Coupon result object
            
        Returns:
            bool: Whether save succeeded
            
        Core method!
        - Hash strategy: Calculate shard by user_id
        - Range strategy: Calculate shard by grab_time or room_id
        """
        pass
    
    @abstractmethod
    def query_user_coupons(self, user_id: int) -> List[CouponResult]:
        """
        Query all coupons for a user
        
        Args:
            user_id: User ID
            
        Returns:
            List[CouponResult]: Coupon list
            
        Hash strategy advantage:
        - Direct locate to one shard, fast query
        
        Range strategy disadvantage:
        - May need to scan multiple shards (cross time periods)
        """
        pass
    
    @abstractmethod
    def query_room_orders(self, room_id: int, limit: int = 100) -> List[CouponResult]:
        """
        Query all orders for a live room
        
        Args:
            room_id: Live room ID
            limit: Result limit
            
        Returns:
            List[CouponResult]: Order list
            
        Hash strategy disadvantage:
        - Need to query all shards and aggregate (slow)
        
        Range strategy advantage:
        - If sharded by room_id, can directly locate
        """
        pass
    
    @abstractmethod
    def query_time_range_orders(self, start_time: datetime, 
                               end_time: datetime,
                               limit: int = 1000) -> List[CouponResult]:
        """
        Query orders within time range
        
        Args:
            start_time: Start time
            end_time: End time
            limit: Result limit
            
        Returns:
            List[CouponResult]: Order list
            
        Hash strategy disadvantage:
        - Need to query all shards and aggregate (slow)
        
        Range strategy advantage:
        - If sharded by time, can directly locate to a few shards
        """
        pass
    
    @abstractmethod
    def get_shard_stats(self) -> List[ShardingStats]:
        """
        Get statistics for each shard
        
        Returns:
            List[ShardingStats]: Shard statistics list
            
        Used to compare load balancing between two strategies
        """
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        """
        Get strategy name
        
        Returns:
            str: "Hash Partitioning" or "Range Partitioning"
        """
        pass
    
    # ============================================================
    # Optional: Advanced Features
    # ============================================================
    
    def bulk_save(self, coupon_results: List[CouponResult]) -> int:
        """
        Bulk save coupon results (optional implementation)
        
        Args:
            coupon_results: Coupon result list
            
        Returns:
            int: Number of successful saves
        """
        success_count = 0
        for result in coupon_results:
            if self.save_coupon_result(result):
                success_count += 1
        return success_count
    
    def health_check(self) -> bool:
        """
        Health check (optional implementation)
        
        Returns:
            bool: Whether all shards are healthy
        """
        return True
    
    def get_total_records(self) -> int:
        """
        Get total record count (optional implementation)
        
        Returns:
            int: Total record count
        """
        stats = self.get_shard_stats()
        return sum(s.total_records for s in stats)

# ============================================================
# Sharding Manager
# ============================================================

class ShardingManager:
    """
    Sharding Manager: Unified management of different sharding strategies
    
    Usage:
        manager = ShardingManager()
        manager.set_strategy(HashShardingStrategy())  # or RangeShardingStrategy()
        manager.save_coupon_result(result)
    """
    
    def __init__(self, strategy: Optional[ShardingStrategy] = None):
        self._strategy = strategy
    
    def set_strategy(self, strategy: ShardingStrategy):
        """Set sharding strategy"""
        self._strategy = strategy
        self._strategy.initialize()
    
    def get_strategy(self) -> ShardingStrategy:
        """Get current strategy"""
        if not self._strategy:
            raise ValueError("Strategy not set! Call set_strategy() first.")
        return self._strategy
    
    # Delegate all methods to strategy object
    
    def save_coupon_result(self, coupon_result: CouponResult) -> bool:
        return self.get_strategy().save_coupon_result(coupon_result)
    
    def query_user_coupons(self, user_id: int) -> List[CouponResult]:
        return self.get_strategy().query_user_coupons(user_id)
    
    def query_room_orders(self, room_id: int, limit: int = 100) -> List[CouponResult]:
        return self.get_strategy().query_room_orders(room_id, limit)
    
    def query_time_range_orders(self, start_time: datetime, 
                               end_time: datetime,
                               limit: int = 1000) -> List[CouponResult]:
        return self.get_strategy().query_time_range_orders(start_time, end_time, limit)
    
    def get_shard_stats(self) -> List[ShardingStats]:
        return self.get_strategy().get_shard_stats()
    
    def get_strategy_name(self) -> str:
        return self.get_strategy().get_strategy_name()

# ============================================================
# Usage Example
# ============================================================

if __name__ == '__main__':
    """
    Example: How to implement and use sharding strategies
    """
    
    # Example: Implement a simple Hash strategy (pseudo-code)
    class SimpleHashStrategy(ShardingStrategy):
        def __init__(self, num_shards: int = 4):
            self.num_shards = num_shards
            self.shards = {}
        
        def initialize(self) -> bool:
            # Initialize shard connections
            for i in range(self.num_shards):
                self.shards[i] = []  # Simplified: use list to simulate database
            return True
        
        def _get_shard_id(self, user_id: int) -> int:
            """Core: Calculate shard ID"""
            return hash(user_id) % self.num_shards
        
        def save_coupon_result(self, coupon_result: CouponResult) -> bool:
            shard_id = self._get_shard_id(coupon_result.user_id)
            self.shards[shard_id].append(coupon_result)
            print(f"✅ Saved to shard {shard_id}: user_id={coupon_result.user_id}")
            return True
        
        def query_user_coupons(self, user_id: int) -> List[CouponResult]:
            shard_id = self._get_shard_id(user_id)
            results = [r for r in self.shards[shard_id] if r.user_id == user_id]
            print(f"🔍 Query from shard {shard_id}: found {len(results)} records")
            return results
        
        def query_room_orders(self, room_id: int, limit: int = 100) -> List[CouponResult]:
            # Hash strategy pain point: need to query all shards
            all_results = []
            for shard_id, shard_data in self.shards.items():
                results = [r for r in shard_data if r.room_id == room_id]
                all_results.extend(results)
                print(f"🔍 Query shard {shard_id}: found {len(results)} records")
            return all_results[:limit]
        
        def query_time_range_orders(self, start_time: datetime, 
                                   end_time: datetime,
                                   limit: int = 1000) -> List[CouponResult]:
            # Hash strategy pain point: need to query all shards
            all_results = []
            for shard_data in self.shards.values():
                results = [r for r in shard_data 
                          if r.grab_time and start_time <= r.grab_time <= end_time]
                all_results.extend(results)
            return all_results[:limit]
        
        def get_shard_stats(self) -> List[ShardingStats]:
            stats = []
            for shard_id, shard_data in self.shards.items():
                stats.append(ShardingStats(
                    shard_id=f"shard_{shard_id}",
                    total_records=len(shard_data),
                    avg_response_time=10.5,
                    cpu_usage=45.0,
                    io_usage=30.0,
                    connection_count=50
                ))
            return stats
        
        def get_strategy_name(self) -> str:
            return "Hash Partitioning (Simple Demo)"
    
    # Usage example
    print("="*60)
    print("Sharding Strategy Interface Usage Example")
    print("="*60)
    
    # Create strategy
    strategy = SimpleHashStrategy(num_shards=4)
    strategy.initialize()
    
    # Create manager
    manager = ShardingManager(strategy)
    
    print(f"\nCurrent strategy: {manager.get_strategy_name()}\n")
    
    # Save some data
    for user_id in [101, 102, 103, 201, 202]:
        result = CouponResult(
            user_id=user_id,
            coupon_id=1,
            room_id=1001,
            grab_status=1,
            grab_time=datetime.now()
        )
        manager.save_coupon_result(result)
    
    print()
    
    # Query user coupons (Hash advantage)
    print("Query user 101's coupons:")
    user_coupons = manager.query_user_coupons(101)
    
    print()
    
    # Query room orders (Hash disadvantage)
    print("Query room 1001 orders (need to query all shards):")
    room_orders = manager.query_room_orders(1001)
    
    print()
    
    # View shard statistics
    print("Shard statistics:")
    for stat in manager.get_shard_stats():
        print(f"  {stat.shard_id}: {stat.total_records} records")
    
    print("\n" + "="*60)
    print("💡 Next steps:")
    print("  - Student A: Implement real HashShardingStrategy (connect to MySQL)")
    print("  - Student B: Implement real RangeShardingStrategy (by time or room)")
    print("="*60)
