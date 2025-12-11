# Quick Reference Guide

## Test Results at a Glance

### Performance Summary

| Scenario | Hash (Student A) | Range (Student B) | Winner |
|----------|-----------------|-------------------|---------|
| 📝 Write Balance | 95.47/100 | 40.06/100 | Hash ✓ |
| 👤 User Query | 0.42ms | 1.48ms (3.5x slower) | Hash ✓ |
| 🏠 Room Query | 1.44ms | 0.37ms (3.93x faster) | Range ✓ |
| ⏰ Time Query | 1.91ms | 1.89ms | Range ✓ |
| 🔥 Hotspot | 26.7% max | 50.9% max | Hash ✓ |

### Distribution Comparison (1000 records, 70% hot room)

```
Hash:  [267, 236, 245, 252]  ← Balanced ✓
Range: [356, 1018, 326, 300] ← Hotspot in Shard 1 ✗
```

## Quick Commands

### Run Full Comparison
```bash
cd "shared 2"
./run_comparison.sh
```

### Run Hotspot Test Only
```bash
cd "shared 2"
python3 verify_hotspot.py
```

### Initialize Shards
```bash
# Hash shards
cd Hash_experiment
python3 init_shards.py

# Range shards
cd Range_experiment
python3 init_shards.py
```

### Check Docker Status
```bash
docker ps | grep coupon_mysql
```

### View Results
```bash
cat comparison_results.json
```

## Architecture Overview

### Hash Partitioning (Student A)
```
┌─────────────────────────────────────┐
│  shard_id = hash(user_id) % 4       │
├─────────────────────────────────────┤
│  Shard 0: user_id % 4 == 0          │
│  Shard 1: user_id % 4 == 1          │
│  Shard 2: user_id % 4 == 2          │
│  Shard 3: user_id % 4 == 3          │
└─────────────────────────────────────┘
```

### Range Partitioning (Student B)
```
┌─────────────────────────────────────┐
│  Partition by room_id ranges        │
├─────────────────────────────────────┤
│  Shard 0: room_id 1-1000            │
│  Shard 1: room_id 1001-2000  ← Hot! │
│  Shard 2: room_id 2001-3000         │
│  Shard 3: room_id 3001+             │
└─────────────────────────────────────┘
```

## When to Use Each Strategy

### Use Hash When:
- 👤 User queries dominate
- ⚖️  Need load balancing
- 🔥 Hotspot prevention critical
- ✍️  High concurrent writes

### Use Range When:
- 🏠 Room queries dominate
- 📊 Analytics/reporting needed
- 📅 Time-based archiving
- 📍 Data locality valuable

## Key Files

```
shared 2/
├── comparison_experiment.py      ← Main test runner
├── verify_hotspot.py            ← Hotspot verification
├── run_comparison.sh            ← Automated script
├── comparison_results.json      ← Test results
│
├── Hash_experiment/             ← Student A
│   ├── hash_strategy.py
│   ├── database.py
│   └── init_shards.py
│
├── Range_experiment/            ← Student B
│   ├── range_strategy.py
│   ├── database.py
│   └── init_shards.py
│
└── Documentation/
    ├── COMPARISON_README.md
    ├── EXPERIMENT_RESULTS_ANALYSIS.md
    └── FINAL_COMPARISON_REPORT.md
```

## Troubleshooting

### MySQL Not Running
```bash
docker-compose up -d
sleep 30  # Wait for initialization
```

### Port Conflicts
```bash
# Check what's using the port
lsof -i :3307

# Stop and restart
docker-compose down
docker-compose up -d
```

### Clear All Data
```bash
python3 verify_hotspot.py  # This clears data first
```

### Connection Errors
```bash
# Check container logs
docker logs coupon_mysql_shard_0
docker logs coupon_mysql_shard_1
```

## Expected Results

All tests should show:
- ✓ Scenario 1: Hash wins (better balance)
- ✓ Scenario 2: Hash wins (faster user query)
- ✓ Scenario 3: Range wins (faster room query)
- ✓ Scenario 4: Range wins (faster time query)
- ✓ Scenario 5: Hash wins (no hotspot)

## Performance Benchmarks

### Hash Partitioning
- Write: ~1.3ms per record
- User query: ~0.4ms (single shard)
- Room query: ~1.4ms (all shards)
- Balance: 95.47/100

### Range Partitioning
- Write: ~1.3ms per record
- User query: ~1.5ms (all shards)
- Room query: ~0.4ms (single shard)
- Balance: 40.06/100 (with hotspot)

## Contact & Support

For issues or questions:
1. Check `FINAL_COMPARISON_REPORT.md` for detailed analysis
2. Review `EXPERIMENT_RESULTS_ANALYSIS.md` for insights
3. Check Docker logs for connection issues
4. Verify MySQL containers are running

---

**Last Updated**: December 8, 2025
**Test Status**: All Passed ✓

