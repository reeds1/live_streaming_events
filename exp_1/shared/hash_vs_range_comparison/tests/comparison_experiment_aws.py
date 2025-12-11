"""
AWS Comparison Experiment: Hash vs Range on AWS RDS
Same tests as local, but running on AWS infrastructure
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'strategies'))

import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import logging

from hash_strategy_aws import HashShardingStrategyAWS
from range_strategy_aws import RangeShardingStrategyAWS
from sharding_interface import CouponResult

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AWSComparisonExperiment:
    """Comparison experiment on AWS RDS"""
    
    def __init__(self):
        logger.info("Initializing AWS comparison experiment...")
        self.hash_strategy = HashShardingStrategyAWS(num_shards=4)
        self.range_strategy = RangeShardingStrategyAWS(num_shards=4)
        
        self.hash_strategy.initialize()
        self.range_strategy.initialize()
        
        logger.info("✅ Both strategies connected to AWS RDS")
    
    def generate_test_data(self, num_records: int = 500, 
                          hot_room_id: int = 1001,
                          hot_room_ratio: float = 0.7) -> List[CouponResult]:
        """Generate test data"""
        results = []
        num_hot_records = int(num_records * hot_room_ratio)
        num_normal_records = num_records - num_hot_records
        
        for i in range(num_hot_records):
            results.append(CouponResult(
                user_id=random.randint(1, 10000),
                coupon_id=random.randint(1, 100),
                room_id=hot_room_id,
                grab_status=1,
                grab_time=datetime.now() - timedelta(minutes=random.randint(0, 60))
            ))
        
        for i in range(num_normal_records):
            results.append(CouponResult(
                user_id=random.randint(1, 10000),
                coupon_id=random.randint(1, 100),
                room_id=random.randint(1, 3500),
                grab_status=1,
                grab_time=datetime.now() - timedelta(minutes=random.randint(0, 120))
            ))
        
        random.shuffle(results)
        return results
    
    def measure_time(self, func, *args, **kwargs) -> Tuple[float, any]:
        """Measure execution time"""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time_ms = (end_time - start_time) * 1000
        return execution_time_ms, result
    
    def test_scenario_1_write_performance(self, num_writes: int = 500) -> Dict:
        """Scenario 1: Write Performance Test with Load Distribution Analysis"""
        logger.info(f"\n{'='*70}")
        logger.info("Scenario 1: Write Performance & Load Distribution (AWS RDS)")
        logger.info("Testing with 70% hotspot data (room_id=1001)")
        logger.info(f"{'='*70}")
        
        test_data = self.generate_test_data(num_writes, hot_room_id=1001, hot_room_ratio=0.7)
        
        import time
        
        logger.info(f"\nTesting Hash strategy: {num_writes} writes...")
        hash_start = time.time()
        hash_times = []
        for result in test_data:
            start = time.time()
            self.hash_strategy.save_coupon_result(result)
            hash_times.append((time.time() - start) * 1000)
        hash_total_time = (time.time() - hash_start) * 1000
        hash_stats = self.hash_strategy.get_shard_stats()
        
        logger.info(f"Testing Range strategy: {num_writes} writes...")
        range_start = time.time()
        range_times = []
        for result in test_data:
            start = time.time()
            self.range_strategy.save_coupon_result(result)
            range_times.append((time.time() - start) * 1000)
        range_total_time = (time.time() - range_start) * 1000
        range_stats = self.range_strategy.get_shard_stats()
        
        hash_records = [s.total_records for s in hash_stats]
        range_records = [s.total_records for s in range_stats]
        
        # Calculate load distribution metrics
        hash_max_load = max(hash_records)
        hash_total = sum(hash_records)
        hash_load_pct = (hash_max_load / hash_total * 100) if hash_total > 0 else 0
        
        range_max_load = max(range_records)
        range_total = sum(range_records)
        range_load_pct = (range_max_load / range_total * 100) if range_total > 0 else 0
        
        # Calculate balance score (higher is better)
        def calc_balance_score(records):
            if not records or sum(records) == 0:
                return 0
            total = sum(records)
            expected = total / len(records)
            variance = sum((r - expected) ** 2 for r in records) / len(records)
            stddev = variance ** 0.5
            return max(0, 100 - (stddev / expected * 100)) if expected > 0 else 0
        
        hash_balance = calc_balance_score(hash_records)
        range_balance = calc_balance_score(range_records)
        
        # Throughput
        hash_throughput = num_writes / (hash_total_time / 1000) if hash_total_time > 0 else 0
        range_throughput = num_writes / (range_total_time / 1000) if range_total_time > 0 else 0
        
        results = {
            'scenario': 'Write Performance & Load Distribution (AWS)',
            'hash_total_time_ms': round(hash_total_time, 2),
            'range_total_time_ms': round(range_total_time, 2),
            'hash_avg_time_ms': round(sum(hash_times)/len(hash_times), 2),
            'range_avg_time_ms': round(sum(range_times)/len(range_times), 2),
            'hash_throughput': round(hash_throughput, 2),
            'range_throughput': round(range_throughput, 2),
            'hash_distribution': hash_records,
            'range_distribution': range_records,
            'hash_max_load_pct': round(hash_load_pct, 2),
            'range_max_load_pct': round(range_load_pct, 2),
            'hash_balance_score': round(hash_balance, 2),
            'range_balance_score': round(range_balance, 2),
            'winner': 'Hash (Better load balance)' if hash_balance > range_balance else 'Range'
        }
        
        self._print_results(results)
        return results
    
    def test_scenario_2_user_query(self, num_queries: int = 30) -> Dict:
        """Scenario 2: Query by User (AWS)"""
        logger.info(f"\n{'='*70}")
        logger.info("Scenario 2: Query by User ID (AWS RDS)")
        logger.info(f"{'='*70}")
        
        test_user_ids = [random.randint(1, 10000) for _ in range(num_queries)]
        
        logger.info("\nTesting Hash strategy user queries on AWS...")
        hash_times = []
        for user_id in test_user_ids:
            exec_time, _ = self.measure_time(self.hash_strategy.query_user_coupons, user_id)
            hash_times.append(exec_time)
        
        hash_avg_time = sum(hash_times) / len(hash_times)
        
        logger.info("Testing Range strategy user queries on AWS...")
        range_times = []
        for user_id in test_user_ids:
            exec_time, _ = self.measure_time(self.range_strategy.query_user_coupons, user_id)
            range_times.append(exec_time)
        
        range_avg_time = sum(range_times) / len(range_times)
        
        results = {
            'scenario': 'Query by User (AWS)',
            'hash_avg_time_ms': round(hash_avg_time, 2),
            'range_avg_time_ms': round(range_avg_time, 2),
            'speedup': round(range_avg_time / hash_avg_time, 2) if hash_avg_time > 0 else 0,
            'winner': 'Hash'
        }
        
        self._print_results(results)
        return results
    
    def test_scenario_3_room_query(self, num_queries: int = 30) -> Dict:
        """Scenario 3: Query by Room (AWS)"""
        logger.info(f"\n{'='*70}")
        logger.info("Scenario 3: Query by Room ID (AWS RDS)")
        logger.info(f"{'='*70}")
        
        test_room_ids = [random.randint(1, 3500) for _ in range(num_queries)]
        
        logger.info("\nTesting Hash strategy room queries on AWS...")
        hash_times = []
        for room_id in test_room_ids:
            exec_time, _ = self.measure_time(self.hash_strategy.query_room_orders, room_id, 100)
            hash_times.append(exec_time)
        
        hash_avg_time = sum(hash_times) / len(hash_times)
        
        logger.info("Testing Range strategy room queries on AWS...")
        range_times = []
        for room_id in test_room_ids:
            exec_time, _ = self.measure_time(self.range_strategy.query_room_orders, room_id, 100)
            range_times.append(exec_time)
        
        range_avg_time = sum(range_times) / len(range_times)
        
        results = {
            'scenario': 'Query by Room (AWS)',
            'hash_avg_time_ms': round(hash_avg_time, 2),
            'range_avg_time_ms': round(range_avg_time, 2),
            'speedup': round(hash_avg_time / range_avg_time, 2) if range_avg_time > 0 else 0,
            'winner': 'Range'
        }
        
        self._print_results(results)
        return results
    
    def _print_results(self, results: Dict):
        """Print results"""
        logger.info(f"\nResults for: {results['scenario']}")
        logger.info("-" * 70)
        for key, value in results.items():
            if key != 'scenario':
                logger.info(f"  {key}: {value}")
    
    def test_scenario_4_time_query(self, num_queries: int = 30) -> Dict:
        """Scenario 4: Query by Time Range (AWS)"""
        logger.info(f"\n{'='*70}")
        logger.info("Scenario 4: Query by Time Range (AWS RDS)")
        logger.info(f"{'='*70}")
        
        time_ranges = []
        for _ in range(num_queries):
            start = datetime.now() - timedelta(hours=random.randint(1, 24))
            end = start + timedelta(hours=random.randint(1, 6))
            time_ranges.append((start, end))
        
        logger.info("\nTesting Hash strategy time range queries on AWS...")
        hash_times = []
        for start_time, end_time in time_ranges:
            exec_time, _ = self.measure_time(
                self.hash_strategy.query_time_range_orders, 
                start_time, end_time, 1000
            )
            hash_times.append(exec_time)
        
        hash_avg_time = sum(hash_times) / len(hash_times)
        
        logger.info("Testing Range strategy time range queries on AWS...")
        range_times = []
        for start_time, end_time in time_ranges:
            exec_time, _ = self.measure_time(
                self.range_strategy.query_time_range_orders, 
                start_time, end_time, 1000
            )
            range_times.append(exec_time)
        
        range_avg_time = sum(range_times) / len(range_times)
        
        results = {
            'scenario': 'Query by Time Range (AWS)',
            'hash_avg_time_ms': round(hash_avg_time, 2),
            'range_avg_time_ms': round(range_avg_time, 2),
            'speedup': round(hash_avg_time / range_avg_time, 2) if range_avg_time > 0 else 0,
            'winner': 'Range' if range_avg_time < hash_avg_time else 'Hash'
        }
        
        self._print_results(results)
        return results
    
    def test_scenario_5_hotspot(self) -> Dict:
        """Scenario 5: Hotspot Problem (AWS)"""
        logger.info(f"\n{'='*70}")
        logger.info("Scenario 5: Hotspot Problem (AWS RDS)")
        logger.info(f"{'='*70}")
        
        hash_stats = self.hash_strategy.get_shard_stats()
        range_stats = self.range_strategy.get_shard_stats()
        
        hash_records = [s.total_records for s in hash_stats]
        range_records = [s.total_records for s in range_stats]
        
        hash_total = sum(hash_records)
        range_total = sum(range_records)
        
        hash_max_pct = (max(hash_records) / hash_total * 100) if hash_total > 0 else 0
        range_max_pct = (max(range_records) / range_total * 100) if range_total > 0 else 0
        
        # Calculate balance scores
        def calc_balance(records):
            if not records or sum(records) == 0:
                return 100.0
            total = sum(records)
            expected = total / len(records)
            variance = sum((r - expected) ** 2 for r in records) / len(records)
            stddev = variance ** 0.5
            return max(0, 100 - (stddev / expected * 100)) if expected > 0 else 0
        
        hash_balance = calc_balance(hash_records)
        range_balance = calc_balance(range_records)
        
        results = {
            'scenario': 'Hotspot Problem (AWS)',
            'hash_distribution': hash_records,
            'range_distribution': range_records,
            'hash_balance_score': round(hash_balance, 2),
            'range_balance_score': round(range_balance, 2),
            'hash_max_pct': round(hash_max_pct, 2),
            'range_max_pct': round(range_max_pct, 2),
            'winner': 'Hash'
        }
        
        self._print_results(results)
        return results
    
    def run_all_tests(self) -> Dict:
        """Run all 5 tests on AWS"""
        logger.info("\n" + "="*70)
        logger.info("AWS COMPARISON EXPERIMENT - ALL 5 SCENARIOS")
        logger.info("Hash vs Range on AWS RDS")
        logger.info("="*70)
        
        all_results = {'timestamp': datetime.now().isoformat(), 'scenarios': {}}
        
        all_results['scenarios']['scenario_1'] = self.test_scenario_1_write_performance(500)
        all_results['scenarios']['scenario_2'] = self.test_scenario_2_user_query(30)
        all_results['scenarios']['scenario_3'] = self.test_scenario_3_room_query(30)
        all_results['scenarios']['scenario_4'] = self.test_scenario_4_time_query(30)
        all_results['scenarios']['scenario_5'] = self.test_scenario_5_hotspot()
        
        logger.info("\n" + "="*70)
        logger.info("AWS EXPERIMENT SUMMARY")
        logger.info("="*70)
        
        for key, data in all_results['scenarios'].items():
            logger.info(f"\n{data['scenario']}: Winner = {data['winner']}")
        
        logger.info("\n" + "="*70)
        
        # Save results
        import json
        with open('../results/aws_comparison_results.json', 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        
        logger.info("Results saved to: results/aws_comparison_results.json")
        
        return all_results

if __name__ == '__main__':
    try:
        experiment = AWSComparisonExperiment()
        results = experiment.run_all_tests()
        logger.info("\n✅ AWS experiment completed successfully!")
    except Exception as e:
        logger.error(f"❌ AWS experiment failed: {e}", exc_info=True)
        sys.exit(1)

