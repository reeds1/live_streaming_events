"""
Comparison Experiment: Hash vs Range Sharding
Tests 5 key scenarios from the comparison table
"""

import sys
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import logging
import os

# Add parent directory to path to import from strategies
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'strategies'))

from hash_strategy import HashShardingStrategy
from range_strategy import RangeShardingStrategy
from sharding_interface import CouponResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ComparisonExperiment:
    """
    Comparison experiment runner for Hash vs Range sharding
    """
    
    def __init__(self):
        logger.info("Initializing comparison experiment...")
        self.hash_strategy = HashShardingStrategy(num_shards=4)
        self.range_strategy = RangeShardingStrategy(num_shards=4)
        
        # Initialize both strategies
        self.hash_strategy.initialize()
        self.range_strategy.initialize()
        
        logger.info("Both strategies initialized successfully")
    
    def generate_test_data(self, num_records: int = 1000, 
                          hot_room_id: int = 1001,
                          hot_room_ratio: float = 0.7) -> List[CouponResult]:
        """
        Generate test data with hotspot pattern
        
        Args:
            num_records: Number of records to generate
            hot_room_id: Hot room ID (for hotspot test)
            hot_room_ratio: Ratio of records for hot room
            
        Returns:
            List of CouponResult objects
        """
        results = []
        num_hot_records = int(num_records * hot_room_ratio)
        num_normal_records = num_records - num_hot_records
        
        # Generate hot room records
        for i in range(num_hot_records):
            results.append(CouponResult(
                user_id=random.randint(1, 10000),
                coupon_id=random.randint(1, 100),
                room_id=hot_room_id,
                grab_status=1,
                grab_time=datetime.now() - timedelta(minutes=random.randint(0, 60))
            ))
        
        # Generate normal records (distributed across rooms)
        for i in range(num_normal_records):
            results.append(CouponResult(
                user_id=random.randint(1, 10000),
                coupon_id=random.randint(1, 100),
                room_id=random.randint(1, 3500),  # Spread across all shard ranges
                grab_status=1,
                grab_time=datetime.now() - timedelta(minutes=random.randint(0, 120))
            ))
        
        random.shuffle(results)
        return results
    
    def measure_time(self, func, *args, **kwargs) -> Tuple[float, any]:
        """
        Measure execution time of a function
        
        Returns:
            Tuple of (execution_time_ms, result)
        """
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time_ms = (end_time - start_time) * 1000
        return execution_time_ms, result
    
    def test_scenario_1_write_performance(self, num_writes: int = 100) -> Dict:
        """
        Scenario 1: Write Performance
        
        Expected:
        - Hash: Balanced writes across all shards
        - Range: Unbalanced (hot rooms concentrate on one shard)
        """
        logger.info(f"\n{'='*60}")
        logger.info("Scenario 1: Write Performance Test")
        logger.info(f"{'='*60}")
        
        # Generate test data with hotspot (70% to room 1001)
        test_data = self.generate_test_data(num_writes, hot_room_id=1001, hot_room_ratio=0.7)
        
        # Test Hash strategy
        logger.info("\nTesting Hash strategy writes...")
        hash_times = []
        for result in test_data:
            exec_time, _ = self.measure_time(self.hash_strategy.save_coupon_result, result)
            hash_times.append(exec_time)
        
        hash_avg_time = sum(hash_times) / len(hash_times)
        hash_stats = self.hash_strategy.get_shard_stats()
        
        # Test Range strategy
        logger.info("Testing Range strategy writes...")
        range_times = []
        for result in test_data:
            exec_time, _ = self.measure_time(self.range_strategy.save_coupon_result, result)
            range_times.append(exec_time)
        
        range_avg_time = sum(range_times) / len(range_times)
        range_stats = self.range_strategy.get_shard_stats()
        
        # Calculate distribution balance
        hash_records = [s.total_records for s in hash_stats]
        range_records = [s.total_records for s in range_stats]
        
        hash_balance = self._calculate_balance_score(hash_records)
        range_balance = self._calculate_balance_score(range_records)
        
        results = {
            'scenario': 'Write Performance',
            'hash_avg_time_ms': round(hash_avg_time, 2),
            'range_avg_time_ms': round(range_avg_time, 2),
            'hash_shard_distribution': hash_records,
            'range_shard_distribution': range_records,
            'hash_balance_score': round(hash_balance, 2),
            'range_balance_score': round(range_balance, 2),
            'winner': 'Hash' if hash_balance > range_balance else 'Range'
        }
        
        self._print_scenario_results(results)
        return results
    
    def test_scenario_2_query_by_user(self, num_queries: int = 50) -> Dict:
        """
        Scenario 2: Query by User ID
        
        Expected:
        - Hash: Very fast (5ms) - only query 1 shard
        - Range: Slower (25ms) - query all shards
        """
        logger.info(f"\n{'='*60}")
        logger.info("Scenario 2: Query by User ID Test")
        logger.info(f"{'='*60}")
        
        # Test with random user IDs
        test_user_ids = [random.randint(1, 10000) for _ in range(num_queries)]
        
        # Test Hash strategy
        logger.info("\nTesting Hash strategy user queries...")
        hash_times = []
        for user_id in test_user_ids:
            exec_time, _ = self.measure_time(self.hash_strategy.query_user_coupons, user_id)
            hash_times.append(exec_time)
        
        hash_avg_time = sum(hash_times) / len(hash_times)
        
        # Test Range strategy
        logger.info("Testing Range strategy user queries...")
        range_times = []
        for user_id in test_user_ids:
            exec_time, _ = self.measure_time(self.range_strategy.query_user_coupons, user_id)
            range_times.append(exec_time)
        
        range_avg_time = sum(range_times) / len(range_times)
        
        results = {
            'scenario': 'Query by User',
            'hash_avg_time_ms': round(hash_avg_time, 2),
            'range_avg_time_ms': round(range_avg_time, 2),
            'speedup_factor': round(range_avg_time / hash_avg_time, 2) if hash_avg_time > 0 else 0,
            'winner': 'Hash'
        }
        
        self._print_scenario_results(results)
        return results
    
    def test_scenario_3_query_by_room(self, num_queries: int = 50) -> Dict:
        """
        Scenario 3: Query by Room ID
        
        Expected:
        - Hash: Slow (45ms) - query all 4 shards
        - Range: Fast (8ms) - query only 1 shard
        """
        logger.info(f"\n{'='*60}")
        logger.info("Scenario 3: Query by Room ID Test")
        logger.info(f"{'='*60}")
        
        # Test with various room IDs
        test_room_ids = [random.randint(1, 3500) for _ in range(num_queries)]
        
        # Test Hash strategy
        logger.info("\nTesting Hash strategy room queries...")
        hash_times = []
        for room_id in test_room_ids:
            exec_time, _ = self.measure_time(self.hash_strategy.query_room_orders, room_id, 100)
            hash_times.append(exec_time)
        
        hash_avg_time = sum(hash_times) / len(hash_times)
        
        # Test Range strategy
        logger.info("Testing Range strategy room queries...")
        range_times = []
        for room_id in test_room_ids:
            exec_time, _ = self.measure_time(self.range_strategy.query_room_orders, room_id, 100)
            range_times.append(exec_time)
        
        range_avg_time = sum(range_times) / len(range_times)
        
        results = {
            'scenario': 'Query by Room',
            'hash_avg_time_ms': round(hash_avg_time, 2),
            'range_avg_time_ms': round(range_avg_time, 2),
            'speedup_factor': round(hash_avg_time / range_avg_time, 2) if range_avg_time > 0 else 0,
            'winner': 'Range'
        }
        
        self._print_scenario_results(results)
        return results
    
    def test_scenario_4_query_by_time_range(self, num_queries: int = 30) -> Dict:
        """
        Scenario 4: Query by Time Range
        
        Expected:
        - Hash: Slow (52ms) - query all 4 shards
        - Range: Fast (6ms) - directly locate relevant partitions
        """
        logger.info(f"\n{'='*60}")
        logger.info("Scenario 4: Query by Time Range Test")
        logger.info(f"{'='*60}")
        
        # Generate time range queries (last few hours)
        time_ranges = []
        for _ in range(num_queries):
            start = datetime.now() - timedelta(hours=random.randint(1, 24))
            end = start + timedelta(hours=random.randint(1, 6))
            time_ranges.append((start, end))
        
        # Test Hash strategy
        logger.info("\nTesting Hash strategy time range queries...")
        hash_times = []
        for start_time, end_time in time_ranges:
            exec_time, _ = self.measure_time(
                self.hash_strategy.query_time_range_orders, 
                start_time, end_time, 1000
            )
            hash_times.append(exec_time)
        
        hash_avg_time = sum(hash_times) / len(hash_times)
        
        # Test Range strategy
        logger.info("Testing Range strategy time range queries...")
        range_times = []
        for start_time, end_time in time_ranges:
            exec_time, _ = self.measure_time(
                self.range_strategy.query_time_range_orders, 
                start_time, end_time, 1000
            )
            range_times.append(exec_time)
        
        range_avg_time = sum(range_times) / len(range_times)
        
        results = {
            'scenario': 'Query by Time Range',
            'hash_avg_time_ms': round(hash_avg_time, 2),
            'range_avg_time_ms': round(range_avg_time, 2),
            'speedup_factor': round(hash_avg_time / range_avg_time, 2) if range_avg_time > 0 else 0,
            'winner': 'Range'
        }
        
        self._print_scenario_results(results)
        return results
    
    def test_scenario_5_hotspot_issue(self) -> Dict:
        """
        Scenario 5: Hotspot Problem
        
        Expected:
        - Hash: No hotspot - balanced distribution
        - Range: Hotspot - hot rooms concentrate on one shard
        """
        logger.info(f"\n{'='*60}")
        logger.info("Scenario 5: Hotspot Problem Test")
        logger.info(f"{'='*60}")
        
        # Get shard statistics
        hash_stats = self.hash_strategy.get_shard_stats()
        range_stats = self.range_strategy.get_shard_stats()
        
        hash_records = [s.total_records for s in hash_stats]
        range_records = [s.total_records for s in range_stats]
        
        # Calculate balance scores
        hash_balance = self._calculate_balance_score(hash_records)
        range_balance = self._calculate_balance_score(range_records)
        
        # Calculate standard deviation (lower is better)
        hash_stddev = self._calculate_stddev(hash_records)
        range_stddev = self._calculate_stddev(range_records)
        
        results = {
            'scenario': 'Hotspot Problem',
            'hash_shard_distribution': hash_records,
            'range_shard_distribution': range_records,
            'hash_balance_score': round(hash_balance, 2),
            'range_balance_score': round(range_balance, 2),
            'hash_stddev': round(hash_stddev, 2),
            'range_stddev': round(range_stddev, 2),
            'winner': 'Hash'
        }
        
        self._print_scenario_results(results)
        return results
    
    def _calculate_balance_score(self, records: List[int]) -> float:
        """
        Calculate balance score (0-100, higher is better)
        100 means perfectly balanced
        """
        if not records or sum(records) == 0:
            return 100.0
        
        total = sum(records)
        expected_per_shard = total / len(records)
        
        # Calculate variance
        variance = sum((r - expected_per_shard) ** 2 for r in records) / len(records)
        stddev = variance ** 0.5
        
        # Convert to score (0-100)
        max_stddev = expected_per_shard  # Worst case: all data in one shard
        if max_stddev == 0:
            return 100.0
        
        balance_score = max(0, 100 - (stddev / max_stddev * 100))
        return balance_score
    
    def _calculate_stddev(self, records: List[int]) -> float:
        """Calculate standard deviation"""
        if not records:
            return 0.0
        
        mean = sum(records) / len(records)
        variance = sum((r - mean) ** 2 for r in records) / len(records)
        return variance ** 0.5
    
    def _print_scenario_results(self, results: Dict):
        """Print scenario results in a formatted way"""
        logger.info(f"\nResults for: {results['scenario']}")
        logger.info("-" * 60)
        
        for key, value in results.items():
            if key != 'scenario':
                logger.info(f"  {key}: {value}")
        
        logger.info(f"  Winner: {results['winner']} Partitioning")
    
    def run_all_tests(self) -> Dict:
        """
        Run all 5 scenario tests
        
        Returns:
            Dict with all test results
        """
        logger.info("\n" + "="*70)
        logger.info("Starting Comprehensive Comparison Experiment")
        logger.info("Hash Partitioning (Student A) vs Range Partitioning (Student B)")
        logger.info("="*70)
        
        all_results = {
            'timestamp': datetime.now().isoformat(),
            'scenarios': {}
        }
        
        # Run all scenarios
        all_results['scenarios']['scenario_1'] = self.test_scenario_1_write_performance(100)
        all_results['scenarios']['scenario_2'] = self.test_scenario_2_query_by_user(50)
        all_results['scenarios']['scenario_3'] = self.test_scenario_3_query_by_room(50)
        all_results['scenarios']['scenario_4'] = self.test_scenario_4_query_by_time_range(30)
        all_results['scenarios']['scenario_5'] = self.test_scenario_5_hotspot_issue()
        
        # Print summary
        self._print_summary(all_results)
        
        return all_results
    
    def _print_summary(self, results: Dict):
        """Print overall summary"""
        logger.info("\n" + "="*70)
        logger.info("EXPERIMENT SUMMARY")
        logger.info("="*70)
        
        scenarios = results['scenarios']
        
        logger.info("\n| Scenario | Hash | Range | Winner |")
        logger.info("|----------|------|-------|--------|")
        
        for key, data in scenarios.items():
            scenario_name = data['scenario']
            winner = data['winner']
            
            if 'hash_avg_time_ms' in data:
                hash_val = f"{data['hash_avg_time_ms']}ms"
                range_val = f"{data['range_avg_time_ms']}ms"
            else:
                hash_val = f"{data['hash_balance_score']}"
                range_val = f"{data['range_balance_score']}"
            
            logger.info(f"| {scenario_name:25s} | {hash_val:10s} | {range_val:10s} | {winner:6s} |")
        
        logger.info("\n" + "="*70)
        logger.info("Expected vs Actual Results Comparison")
        logger.info("="*70)
        
        expected = {
            'Write Performance': 'Hash (balanced)',
            'Query by User': 'Hash (fast, single shard)',
            'Query by Room': 'Range (fast, single shard)',
            'Query by Time Range': 'Range (fast, partition pruning)',
            'Hotspot Problem': 'Hash (no hotspot)'
        }
        
        for scenario, exp_winner in expected.items():
            actual_winner = scenarios[[k for k, v in scenarios.items() if v['scenario'] == scenario][0]]['winner']
            match = "✓" if exp_winner.startswith(actual_winner) else "✗"
            logger.info(f"{match} {scenario:25s}: Expected {exp_winner:30s}, Got {actual_winner}")
        
        logger.info("\n" + "="*70)

def main():
    """Main entry point"""
    try:
        experiment = ComparisonExperiment()
        results = experiment.run_all_tests()
        
        # Save results to file
        import json
        output_file = 'comparison_results.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"\nResults saved to: {output_file}")
        logger.info("\nExperiment completed successfully!")
        
    except Exception as e:
        logger.error(f"Experiment failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()

