#!/bin/bash

# Automated Load Test Runner
# This script runs a series of load tests and collects metrics

echo "╔════════════════════════════════════════════════════════╗"
echo "║         Automated Load Test - Range Sharding          ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Test configuration
API_HOST="http://localhost:8002"
RESULTS_DIR="/Users/zact/Desktop/cs6650/final project/live_streaming_events/student_b_range/benchmark_results"

# Create results directory
mkdir -p "$RESULTS_DIR"

echo "Results will be saved to: $RESULTS_DIR"
echo ""

# Test 1: Warm-up test (100 users, 1 minute)
echo "═══════════════════════════════════════════════════════"
echo "Test 1: Warm-up (100 users, 1 minute)"
echo "═══════════════════════════════════════════════════════"
locust -f locustfile_advanced.py \
    --host=$API_HOST \
    --users 100 \
    --spawn-rate 10 \
    --run-time 1m \
    --headless \
    --html "$RESULTS_DIR/test1_warmup_100users.html" \
    --csv "$RESULTS_DIR/test1_warmup_100users"

echo "✅ Test 1 complete"
echo ""
sleep 5

# Test 2: Medium load (500 users, 3 minutes)
echo "═══════════════════════════════════════════════════════"
echo "Test 2: Medium Load (500 users, 3 minutes)"
echo "═══════════════════════════════════════════════════════"
locust -f locustfile_advanced.py \
    --host=$API_HOST \
    --users 500 \
    --spawn-rate 25 \
    --run-time 3m \
    --headless \
    --html "$RESULTS_DIR/test2_medium_500users.html" \
    --csv "$RESULTS_DIR/test2_medium_500users"

echo "✅ Test 2 complete"
echo ""
sleep 5

# Test 3: High load (1000 users, 5 minutes)
echo "═══════════════════════════════════════════════════════"
echo "Test 3: High Load (1000 users, 5 minutes)"
echo "═══════════════════════════════════════════════════════"
locust -f locustfile_advanced.py \
    --host=$API_HOST \
    --users 1000 \
    --spawn-rate 50 \
    --run-time 5m \
    --headless \
    --html "$RESULTS_DIR/test3_high_1000users.html" \
    --csv "$RESULTS_DIR/test3_high_1000users"

echo "✅ Test 3 complete"
echo ""
sleep 5

# Test 4: Stress test (2000 users, 3 minutes)
echo "═══════════════════════════════════════════════════════"
echo "Test 4: Stress Test (2000 users, 3 minutes)"
echo "═══════════════════════════════════════════════════════"
locust -f locustfile_advanced.py \
    --host=$API_HOST \
    --users 2000 \
    --spawn-rate 100 \
    --run-time 3m \
    --headless \
    --html "$RESULTS_DIR/test4_stress_2000users.html" \
    --csv "$RESULTS_DIR/test4_stress_2000users"

echo "✅ Test 4 complete"
echo ""

# Collect system stats
echo "═══════════════════════════════════════════════════════"
echo "Collecting System Statistics"
echo "═══════════════════════════════════════════════════════"

# Database stats
echo "Database partition statistics:" > "$RESULTS_DIR/system_stats.txt"
docker exec coupon_mysql_main mysql -uroot -ppassword coupon_system -e "
SELECT 
    table_name,
    table_rows,
    ROUND(((data_length + index_length) / 1024 / 1024), 2) AS size_mb
FROM information_schema.tables 
WHERE table_schema = 'coupon_system' 
AND table_name LIKE 'coupon_results_%'
ORDER BY table_name;
" 2>&1 | grep -v "Using a password" >> "$RESULTS_DIR/system_stats.txt"

# API stats
echo "" >> "$RESULTS_DIR/system_stats.txt"
echo "API Statistics:" >> "$RESULTS_DIR/system_stats.txt"
curl -s $API_HOST/admin/stats >> "$RESULTS_DIR/system_stats.txt"

echo "✅ System stats collected"
echo ""

# Summary
echo "╔════════════════════════════════════════════════════════╗"
echo "║              All Tests Complete!                       ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "Results saved in: $RESULTS_DIR"
echo ""
echo "Files created:"
ls -lh "$RESULTS_DIR" | tail -n +2
echo ""
echo "Open HTML reports in browser:"
echo "  open $RESULTS_DIR/test3_high_1000users.html"
echo ""

