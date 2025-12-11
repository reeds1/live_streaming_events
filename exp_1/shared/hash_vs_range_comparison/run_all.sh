#!/bin/bash

echo "=========================================="
echo "Hash vs Range Sharding Comparison"
echo "=========================================="

# Navigate to project root
cd "$(dirname "$0")"

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Start MySQL containers if not running
echo ""
echo "Step 1: Checking MySQL containers..."
if ! docker ps | grep -q coupon_mysql; then
    echo "Starting MySQL containers..."
    cd config
    docker-compose up -d
    cd ..
    echo "Waiting 30 seconds for MySQL initialization..."
    sleep 30
else
    echo "✓ MySQL containers already running"
fi

# Initialize shards
echo ""
echo "Step 2: Initializing shards..."
cd strategies

echo "  Initializing Hash shards (Student A)..."
python3 init_hash_shards.py
if [ $? -ne 0 ]; then
    echo "❌ Hash shard initialization failed"
    exit 1
fi

echo "  Initializing Range shards (Student B)..."
python3 init_range_shards.py
if [ $? -ne 0 ]; then
    echo "❌ Range shard initialization failed"
    exit 1
fi

cd ..

# Run comparison tests
echo ""
echo "Step 3: Running comparison tests..."
cd tests
python3 comparison_experiment.py
if [ $? -ne 0 ]; then
    echo "❌ Comparison test failed"
    exit 1
fi

# Visualize results
echo ""
echo "Step 4: Visualizing results..."
python3 visualize_results.py

cd ..

# Success
echo ""
echo "=========================================="
echo "✅ All tests completed successfully!"
echo "=========================================="
echo ""
echo "Results saved to: results/comparison_results.json"
echo "Documentation in: docs/"
echo ""

