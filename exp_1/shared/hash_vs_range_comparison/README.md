# Hash vs Range Sharding Comparison

A comprehensive comparison experiment between Hash Partitioning (Student A) and Range Partitioning (Student B) for a live streaming coupon system.

## Project Structure

```
hash_vs_range_comparison/
│
├── strategies/              # Sharding strategy implementations
│   ├── sharding_interface.py    # Common interface (abstract class)
│   ├── hash_strategy.py         # Student A: Hash partitioning
│   ├── range_strategy.py        # Student B: Range partitioning
│   ├── database.py              # Database connection pool
│   ├── init_hash_shards.py      # Initialize Hash shards
│   └── init_range_shards.py     # Initialize Range shards
│
├── tests/                   # Test and comparison scripts
│   ├── comparison_experiment.py # Main test (5 scenarios)
│   ├── verify_hotspot.py        # Hotspot verification
│   └── visualize_results.py     # Results visualization
│
├── config/                  # Configuration files
│   ├── docker-compose.yml       # MySQL infrastructure
│   ├── database_schema.sql      # Database schema
│   └── requirements.txt         # Python dependencies
│
├── results/                 # Test results
│   └── comparison_results.json  # Test output data
│
├── docs/                    # Documentation
│   ├── START_HERE.md           # Quick start guide
│   ├── FINAL_COMPARISON_REPORT.md
│   ├── EXPERIMENT_RESULTS_ANALYSIS.md
│   ├── QUICK_REFERENCE.md
│   └── 测试结果总结.md          # Chinese summary
│
└── README.md               # This file
```

## Quick Start

### 1. Start MySQL Containers
```bash
cd config
docker-compose up -d
sleep 30  # Wait for initialization
cd ..
```

### 2. Initialize Shards
```bash
cd strategies
python3 init_hash_shards.py
python3 init_range_shards.py
cd ..
```

### 3. Run Tests
```bash
cd tests
python3 comparison_experiment.py
python3 visualize_results.py
cd ..
```

## Test Results Summary

| Scenario | Hash (Student A) | Range (Student B) | Winner |
|----------|------------------|-------------------|--------|
| Write Performance | 95.47/100 | 40.06/100 | Hash ✓ |
| Query by User | 0.42ms | 1.48ms (3.5x slower) | Hash ✓ |
| Query by Room | 1.44ms | 0.37ms (3.93x faster) | Range ✓ |
| Query by Time | 1.91ms | 1.89ms | Range ✓ |
| Hotspot Problem | 26.7% max | 50.9% max | Hash ✓ |

**Score: Hash 3 wins, Range 2 wins**

## Key Files

### Strategy Implementations
- **`strategies/hash_strategy.py`** - Hash partitioning by user_id
- **`strategies/range_strategy.py`** - Range partitioning by room_id

### Test Scripts
- **`tests/comparison_experiment.py`** - Complete comparison test
- **`tests/verify_hotspot.py`** - Hotspot analysis

### Documentation
- **`docs/测试结果总结.md`** - Chinese summary (easiest to understand)
- **`docs/START_HERE.md`** - Quick start guide
- **`docs/FINAL_COMPARISON_REPORT.md`** - Complete report

## Dependencies

Install required packages:
```bash
pip install pymysql
```

Or use requirements file:
```bash
pip install -r config/requirements.txt
```

## Architecture

### Hash Partitioning (Student A)
```python
shard_id = hash(user_id) % 4
```
- Shard 0: user_id % 4 == 0
- Shard 1: user_id % 4 == 1
- Shard 2: user_id % 4 == 2
- Shard 3: user_id % 4 == 3

### Range Partitioning (Student B)
```python
Shard 0: room_id 1-1000
Shard 1: room_id 1001-2000
Shard 2: room_id 2001-3000
Shard 3: room_id 3001+
```

## Code Quality

✅ All Python files use English comments only (no Chinese)
✅ PEP 8 compliant
✅ No linter errors
✅ Comprehensive docstrings

## Database Infrastructure

- Main DB: `localhost:3306`
- Shard 0: `localhost:3307`
- Shard 1: `localhost:3308`
- Shard 2: `localhost:3309`
- Shard 3: `localhost:3310`

## When to Use Each Strategy

### Hash Partitioning
✅ User-centric queries
✅ Need load balancing
✅ Avoid hotspots
✅ High concurrent writes

### Range Partitioning
✅ Room/content queries
✅ Time-based analytics
✅ Data locality valuable
✅ Can tolerate imbalance

## Documentation

For detailed analysis, see `docs/` folder:
- Quick start → `START_HERE.md`
- Chinese summary → `测试结果总结.md`
- Full report → `FINAL_COMPARISON_REPORT.md`
- Performance data → `EXPERIMENT_RESULTS_ANALYSIS.md`

## License

Educational project for CS6650 course.

## Status

✅ All tests passed
✅ Results verified
✅ Documentation complete

