"""
Heavy Load Test: 5-minute stress test with high concurrency
Tests both Hash and Range strategies under real load
"""

import sys
import os
import time
import random
import threading
from datetime import datetime, timedelta
from typing import List
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'strategies'))

from hash_strategy import HashShardingStrategy
from range_strategy import RangeShardingStrategy
from sharding_interface import CouponResult

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class LoadTester:
    def __init__(self):
        self.hash_strategy = HashShardingStrategy(num_shards=4)
        self.range_strategy = RangeShardingStrategy(num_shards=4)
        self.hash_strategy.initialize()
        self.range_strategy.initialize()
        
        self.hash_write_count = 0
        self.range_write_count = 0
        self.hash_query_count = 0
        self.range_query_count = 0
        
        self.hash_write_times = []
        self.range_write_times = []
        self.hash_query_times = []
        self.range_query_times = []
        
        self.lock = threading.Lock()
        self.running = True
    
    def write_worker(self, strategy, strategy_name, duration_seconds=300):
        """Worker thread for continuous writes"""
        start_time = time.time()
        
        while self.running and (time.time() - start_time) < duration_seconds:
            try:
                result = CouponResult(
                    user_id=random.randint(1, 50000),
                    coupon_id=random.randint(1, 100),
                    room_id=random.choice([1001] * 7 + list(range(1, 3500, 50))),  # 70% hotspot
                    grab_status=1,
                    grab_time=datetime.now()
                )
                
                write_start = time.time()
                success = strategy.save_coupon_result(result)
                write_time = (time.time() - write_start) * 1000
                
                with self.lock:
                    if strategy_name == 'Hash':
                        self.hash_write_count += 1
                        self.hash_write_times.append(write_time)
                    else:
                        self.range_write_count += 1
                        self.range_write_times.append(write_time)
                
                time.sleep(0.001)  # Small delay to simulate realistic load
                
            except Exception as e:
                logger.error(f"{strategy_name} write error: {e}")
    
    def query_worker(self, strategy, strategy_name, duration_seconds=300):
        """Worker thread for continuous queries"""
        start_time = time.time()
        
        while self.running and (time.time() - start_time) < duration_seconds:
            try:
                # Mix of query types
                query_type = random.choice(['user', 'room', 'time'])
                
                query_start = time.time()
                
                if query_type == 'user':
                    user_id = random.randint(1, 50000)
                    results = strategy.query_user_coupons(user_id)
                elif query_type == 'room':
                    room_id = random.randint(1, 3500)
                    results = strategy.query_room_orders(room_id, limit=100)
                else:
                    end_time = datetime.now()
                    start_time_query = end_time - timedelta(hours=1)
                    results = strategy.query_time_range_orders(start_time_query, end_time, limit=100)
                
                query_time = (time.time() - query_start) * 1000
                
                with self.lock:
                    if strategy_name == 'Hash':
                        self.hash_query_count += 1
                        self.hash_query_times.append(query_time)
                    else:
                        self.range_query_count += 1
                        self.range_query_times.append(query_time)
                
                time.sleep(0.005)  # Query delay
                
            except Exception as e:
                logger.error(f"{strategy_name} query error: {e}")
    
    def monitor_progress(self, duration_seconds=300):
        """Monitor and report progress every 30 seconds"""
        start_time = time.time()
        interval = 30
        
        while self.running and (time.time() - start_time) < duration_seconds:
            time.sleep(interval)
            elapsed = int(time.time() - start_time)
            remaining = duration_seconds - elapsed
            
            with self.lock:
                logger.info(f"--- Progress: {elapsed}s elapsed, {remaining}s remaining ---")
                logger.info(f"Hash:  {self.hash_write_count} writes, {self.hash_query_count} queries")
                logger.info(f"Range: {self.range_write_count} writes, {self.range_query_count} queries")
    
    def run_load_test(self, duration_seconds=300, num_write_threads=4, num_query_threads=4):
        """
        Run comprehensive load test
        
        Args:
            duration_seconds: Test duration (default 5 minutes)
            num_write_threads: Number of concurrent write threads per strategy
            num_query_threads: Number of concurrent query threads per strategy
        """
        logger.info("="*70)
        logger.info(f"STARTING {duration_seconds}-SECOND LOAD TEST")
        logger.info("="*70)
        logger.info(f"Write threads per strategy: {num_write_threads}")
        logger.info(f"Query threads per strategy: {num_query_threads}")
        logger.info(f"Total threads: {(num_write_threads + num_query_threads) * 2}")
        logger.info("="*70)
        
        threads = []
        
        # Start Hash write threads
        for i in range(num_write_threads):
            t = threading.Thread(
                target=self.write_worker,
                args=(self.hash_strategy, 'Hash', duration_seconds)
            )
            t.start()
            threads.append(t)
        
        # Start Range write threads
        for i in range(num_write_threads):
            t = threading.Thread(
                target=self.write_worker,
                args=(self.range_strategy, 'Range', duration_seconds)
            )
            t.start()
            threads.append(t)
        
        # Start Hash query threads
        for i in range(num_query_threads):
            t = threading.Thread(
                target=self.query_worker,
                args=(self.hash_strategy, 'Hash', duration_seconds)
            )
            t.start()
            threads.append(t)
        
        # Start Range query threads
        for i in range(num_query_threads):
            t = threading.Thread(
                target=self.query_worker,
                args=(self.range_strategy, 'Range', duration_seconds)
            )
            t.start()
            threads.append(t)
        
        # Start monitor thread
        monitor = threading.Thread(target=self.monitor_progress, args=(duration_seconds,))
        monitor.start()
        
        # Wait for all threads to complete
        logger.info("\nLoad test running... (this will take about 5 minutes)")
        
        for t in threads:
            t.join()
        
        self.running = False
        monitor.join()
        
        self.print_results()
    
    def print_results(self):
        """Print comprehensive test results"""
        logger.info("\n" + "="*70)
        logger.info("LOAD TEST RESULTS")
        logger.info("="*70)
        
        # Write statistics
        logger.info("\n📝 WRITE PERFORMANCE")
        logger.info("-"*70)
        logger.info(f"Hash Strategy:")
        logger.info(f"  Total writes: {self.hash_write_count}")
        logger.info(f"  Avg time: {sum(self.hash_write_times)/len(self.hash_write_times):.2f}ms")
        logger.info(f"  Min time: {min(self.hash_write_times):.2f}ms")
        logger.info(f"  Max time: {max(self.hash_write_times):.2f}ms")
        
        logger.info(f"\nRange Strategy:")
        logger.info(f"  Total writes: {self.range_write_count}")
        logger.info(f"  Avg time: {sum(self.range_write_times)/len(self.range_write_times):.2f}ms")
        logger.info(f"  Min time: {min(self.range_write_times):.2f}ms")
        logger.info(f"  Max time: {max(self.range_write_times):.2f}ms")
        
        # Query statistics
        logger.info("\n🔍 QUERY PERFORMANCE")
        logger.info("-"*70)
        logger.info(f"Hash Strategy:")
        logger.info(f"  Total queries: {self.hash_query_count}")
        logger.info(f"  Avg time: {sum(self.hash_query_times)/len(self.hash_query_times):.2f}ms")
        logger.info(f"  Min time: {min(self.hash_query_times):.2f}ms")
        logger.info(f"  Max time: {max(self.hash_query_times):.2f}ms")
        
        logger.info(f"\nRange Strategy:")
        logger.info(f"  Total queries: {self.range_query_count}")
        logger.info(f"  Avg time: {sum(self.range_query_times)/len(self.range_query_times):.2f}ms")
        logger.info(f"  Min time: {min(self.range_query_times):.2f}ms")
        logger.info(f"  Max time: {max(self.range_query_times):.2f}ms")
        
        # Shard distribution
        logger.info("\n📊 SHARD DISTRIBUTION")
        logger.info("-"*70)
        hash_stats = self.hash_strategy.get_shard_stats()
        range_stats = self.range_strategy.get_shard_stats()
        
        logger.info("Hash Strategy:")
        for stat in hash_stats:
            logger.info(f"  {stat.shard_id}: {stat.total_records} records")
        
        logger.info("\nRange Strategy:")
        for stat in range_stats:
            logger.info(f"  {stat.shard_id}: {stat.total_records} records")
        
        logger.info("\n" + "="*70)
        logger.info("✅ LOAD TEST COMPLETED")
        logger.info("="*70)

if __name__ == '__main__':
    try:
        tester = LoadTester()
        # Run 5-minute load test with 4 write threads and 4 query threads per strategy
        tester.run_load_test(duration_seconds=300, num_write_threads=4, num_query_threads=4)
    except KeyboardInterrupt:
        logger.info("\n\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)

