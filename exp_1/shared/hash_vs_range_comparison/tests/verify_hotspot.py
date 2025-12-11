"""
Verify Hotspot Scenario with Clean Data
This script clears all data and runs a focused hotspot test
"""

import sys
import random
from datetime import datetime
import os
import logging

# Add parent directory to path to import from strategies
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'strategies'))

from hash_strategy import HashShardingStrategy
from range_strategy import RangeShardingStrategy
from sharding_interface import CouponResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clear_all_shards(strategy):
    """Clear all data from shards"""
    logger.info(f"Clearing data from {strategy.get_strategy_name()}...")
    for shard_id in range(strategy.num_shards):
        conn = strategy.pool.get_shard_connection(shard_id)
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM coupon_results")
                conn.commit()
                logger.info(f"  Cleared shard {shard_id}")
        except Exception as e:
            logger.error(f"  Failed to clear shard {shard_id}: {e}")

def test_hotspot(strategy, num_records=1000, hot_room_id=1001, hot_ratio=0.7):
    """
    Test hotspot scenario
    
    Args:
        strategy: Sharding strategy to test
        num_records: Total records to insert
        hot_room_id: Hot room ID
        hot_ratio: Ratio of records for hot room
    """
    logger.info(f"\nTesting {strategy.get_strategy_name()}")
    logger.info(f"  Total records: {num_records}")
    logger.info(f"  Hot room: {hot_room_id}")
    logger.info(f"  Hot ratio: {hot_ratio*100}%")
    
    # Generate hot records
    num_hot = int(num_records * hot_ratio)
    num_normal = num_records - num_hot
    
    logger.info(f"\nInserting {num_hot} hot records (room {hot_room_id})...")
    for i in range(num_hot):
        result = CouponResult(
            user_id=random.randint(1, 10000),
            coupon_id=random.randint(1, 100),
            room_id=hot_room_id,
            grab_status=1,
            grab_time=datetime.now()
        )
        strategy.save_coupon_result(result)
    
    logger.info(f"Inserting {num_normal} normal records (distributed rooms)...")
    for i in range(num_normal):
        result = CouponResult(
            user_id=random.randint(1, 10000),
            coupon_id=random.randint(1, 100),
            room_id=random.randint(1, 3500),
            grab_status=1,
            grab_time=datetime.now()
        )
        strategy.save_coupon_result(result)
    
    # Get distribution
    stats = strategy.get_shard_stats()
    records = [s.total_records for s in stats]
    
    logger.info(f"\nShard distribution:")
    for i, count in enumerate(records):
        percentage = (count / sum(records) * 100) if sum(records) > 0 else 0
        logger.info(f"  Shard {i}: {count:4d} records ({percentage:5.1f}%)")
    
    # Calculate balance metrics
    total = sum(records)
    mean = total / len(records)
    variance = sum((r - mean) ** 2 for r in records) / len(records)
    stddev = variance ** 0.5
    
    max_deviation = max(abs(r - mean) for r in records)
    balance_score = max(0, 100 - (stddev / mean * 100)) if mean > 0 else 0
    
    logger.info(f"\nBalance metrics:")
    logger.info(f"  Total records: {total}")
    logger.info(f"  Average per shard: {mean:.1f}")
    logger.info(f"  Standard deviation: {stddev:.2f}")
    logger.info(f"  Max deviation: {max_deviation:.1f}")
    logger.info(f"  Balance score: {balance_score:.2f}/100")
    
    return {
        'distribution': records,
        'stddev': stddev,
        'balance_score': balance_score,
        'max_percentage': max(records) / total * 100 if total > 0 else 0
    }

def main():
    logger.info("="*70)
    logger.info("Hotspot Verification Test")
    logger.info("Testing with CLEAN data")
    logger.info("="*70)
    
    # Initialize strategies
    hash_strategy = HashShardingStrategy(num_shards=4)
    range_strategy = RangeShardingStrategy(num_shards=4)
    
    hash_strategy.initialize()
    range_strategy.initialize()
    
    # Clear all existing data
    logger.info("\nStep 1: Clearing all existing data...")
    clear_all_shards(hash_strategy)
    clear_all_shards(range_strategy)
    
    # Test Hash strategy
    logger.info("\n" + "="*70)
    logger.info("Step 2: Testing Hash Partitioning")
    logger.info("="*70)
    hash_results = test_hotspot(hash_strategy, num_records=1000, hot_room_id=1001, hot_ratio=0.7)
    
    # Test Range strategy
    logger.info("\n" + "="*70)
    logger.info("Step 3: Testing Range Partitioning")
    logger.info("="*70)
    range_results = test_hotspot(range_strategy, num_records=1000, hot_room_id=1001, hot_ratio=0.7)
    
    # Comparison
    logger.info("\n" + "="*70)
    logger.info("COMPARISON RESULTS")
    logger.info("="*70)
    
    logger.info("\nDistribution Comparison:")
    logger.info(f"  Hash:  {hash_results['distribution']}")
    logger.info(f"  Range: {range_results['distribution']}")
    
    logger.info("\nBalance Score (higher is better):")
    logger.info(f"  Hash:  {hash_results['balance_score']:.2f}/100")
    logger.info(f"  Range: {range_results['balance_score']:.2f}/100")
    
    logger.info("\nStandard Deviation (lower is better):")
    logger.info(f"  Hash:  {hash_results['stddev']:.2f}")
    logger.info(f"  Range: {range_results['stddev']:.2f}")
    
    logger.info("\nMax Shard Percentage:")
    logger.info(f"  Hash:  {hash_results['max_percentage']:.1f}%")
    logger.info(f"  Range: {range_results['max_percentage']:.1f}%")
    
    logger.info("\n" + "="*70)
    logger.info("CONCLUSION")
    logger.info("="*70)
    
    if hash_results['balance_score'] > range_results['balance_score']:
        logger.info("✓ Hash partitioning shows better load balancing")
        logger.info("✓ Hash is more resistant to hotspot issues")
    else:
        logger.info("✗ Unexpected result - Range should have hotspot issue")
    
    if range_results['max_percentage'] > 60:
        logger.info(f"✓ Range partitioning shows hotspot: {range_results['max_percentage']:.1f}% in one shard")
    
    logger.info("\nExpected behavior:")
    logger.info("- Hash: Even distribution (~25% per shard)")
    logger.info("- Range: Hotspot in Shard 1 (room 1001 is in range 1001-2000)")
    logger.info("="*70)

if __name__ == '__main__':
    main()

