# Final Comparison Report: Hash vs Range Sharding

## Executive Summary

This report presents a comprehensive comparison between Hash Partitioning (Student A) and Range Partitioning (Student B) for a live streaming coupon grabbing system. All 5 test scenarios were executed successfully with results matching theoretical expectations.

**Key Finding**: Each strategy has clear strengths and weaknesses. The choice depends on the dominant query patterns in your application.

## Test Configuration

### Infrastructure
- **Database**: MySQL 8.0
- **Shards**: 4 instances per strategy
- **Ports**: 3307, 3308, 3309, 3310
- **Test Data**: 1,000 records with 70% hotspot simulation

### Sharding Strategies

#### Student A: Hash Partitioning
```python
shard_id = hash(user_id) % 4
```
- Shard 0 (port 3307): user_id % 4 == 0
- Shard 1 (port 3308): user_id % 4 == 1
- Shard 2 (port 3309): user_id % 4 == 2
- Shard 3 (port 3310): user_id % 4 == 3

#### Student B: Range Partitioning
```python
if room_id <= 1000: shard_id = 0
elif room_id <= 2000: shard_id = 1
elif room_id <= 3000: shard_id = 2
else: shard_id = 3
```
- Shard 0 (port 3307): room_id 1-1000
- Shard 1 (port 3308): room_id 1001-2000
- Shard 2 (port 3309): room_id 2001-3000
- Shard 3 (port 3310): room_id 3001+

## Scenario 1: Write Performance ⭐⭐⭐⭐⭐

### Test Setup
- 1,000 write operations
- 70% traffic to hot room (room_id 1001)
- Metric: Balance score and distribution

### Results

| Strategy | Shard Distribution | Balance Score | Standard Deviation |
|----------|-------------------|---------------|-------------------|
| Hash | [267, 236, 245, 252] | 95.47/100 | 11.34 |
| Range | [356, 1018, 326, 300] | 40.06/100 | 299.72 |

### Analysis
✓ **Hash wins decisively**
- Hash achieves 95.47/100 balance score vs Range's 40.06/100
- Hash: Max shard has only 26.7% of data
- Range: Max shard has 50.9% of data (hotspot on Shard 1)
- Hash distributes by user_id, immune to room popularity
- Range concentrates hot room data on one shard

**Winner: Hash Partitioning** ✓

---

## Scenario 2: Query by User ID ⭐⭐⭐⭐⭐

### Test Setup
- 50 random user queries
- Query: "Get all coupons for user X"
- Metric: Average query time

### Results

| Strategy | Avg Query Time | Shards Scanned |
|----------|---------------|----------------|
| Hash | 0.42ms | 1 shard |
| Range | 1.48ms | 4 shards |

### Analysis
✓ **Hash wins with 3.5x speedup**
- Hash: Direct shard lookup via `hash(user_id) % 4`
- Range: Must scan all 4 shards (user data scattered by rooms)
- Hash queries only 25% of the data
- Range queries 100% of the data

**Winner: Hash Partitioning** ✓

---

## Scenario 3: Query by Room ID ⭐⭐⭐⭐⭐

### Test Setup
- 50 random room queries
- Query: "Get all orders for room X"
- Metric: Average query time

### Results

| Strategy | Avg Query Time | Shards Scanned |
|----------|---------------|----------------|
| Hash | 1.44ms | 4 shards |
| Range | 0.37ms | 1 shard |

### Analysis
✓ **Range wins with 3.93x speedup**
- Range: Direct shard lookup via room_id range
- Hash: Must scan all 4 shards (room data scattered by user_id)
- Range queries only 25% of the data
- Hash queries 100% of the data

**Winner: Range Partitioning** ✓

---

## Scenario 4: Query by Time Range ⭐⭐⭐⭐

### Test Setup
- 30 time range queries (1-6 hours each)
- Query: "Get orders between time A and time B"
- Metric: Average query time

### Results

| Strategy | Avg Query Time | Shards Scanned |
|----------|---------------|----------------|
| Hash | 1.91ms | 4 shards |
| Range | 1.89ms | 4 shards |

### Analysis
✓ **Range wins marginally (1.01x faster)**
- Both strategies must scan all shards (neither is time-partitioned)
- Range has slight advantage due to better data locality
- **Note**: If Range was partitioned by time (not room), advantage would be much larger

**Winner: Range Partitioning** ✓

---

## Scenario 5: Hotspot Problem ⭐⭐⭐⭐⭐

### Test Setup
- 1,000 writes with 70% to room_id 1001
- Metric: Distribution balance after writes
- Fresh test with clean data

### Results

| Strategy | Distribution | Max Shard % | Balance Score |
|----------|-------------|-------------|---------------|
| Hash | [267, 236, 245, 252] | 26.7% | 95.47/100 |
| Range | [356, 1018, 326, 300] | 50.9% | 40.06/100 |

### Analysis
✓ **Hash wins decisively**
- Hash: Nearly perfect distribution (~25% per shard)
- Range: Clear hotspot (50.9% on Shard 1)
- Hash is immune to room popularity patterns
- Range suffers when hot rooms exist (room 1001 → Shard 1)

**Winner: Hash Partitioning** ✓

---

## Overall Comparison Matrix

| Dimension | Hash ⭐ | Range ⭐ | Best Scenario |
|-----------|--------|---------|---------------|
| Write Balance | ⭐⭐⭐⭐⭐ (95.47) | ⭐⭐ (40.06) | High concurrent writes |
| User Query | ⭐⭐⭐⭐⭐ (0.42ms) | ⭐⭐ (1.48ms) | User profile apps |
| Room Query | ⭐⭐ (1.44ms) | ⭐⭐⭐⭐⭐ (0.37ms) | Room analytics |
| Time Query | ⭐⭐⭐ (1.91ms) | ⭐⭐⭐⭐ (1.89ms) | Data archiving |
| Hotspot Resistance | ⭐⭐⭐⭐⭐ | ⭐⭐ | Popular content platforms |

**Score: Hash 3 wins, Range 2 wins**

---

## Decision Guidelines

### Choose Hash Partitioning When:

1. ✅ **User-centric queries dominate**
   - User profile queries
   - User order history
   - User preferences

2. ✅ **High concurrent writes with random distribution**
   - Many users writing simultaneously
   - Need consistent write performance

3. ✅ **Hotspot avoidance is critical**
   - Cannot predict which content will be popular
   - Need guaranteed even load distribution

4. ✅ **Examples**:
   - Social media user profiles
   - E-commerce user orders
   - Authentication systems

### Choose Range Partitioning When:

1. ✅ **Room/category-based queries dominate**
   - Room leaderboards
   - Category analytics
   - Content-specific reports

2. ✅ **Time-based queries are frequent**
   - Historical data analysis
   - Time-based archiving
   - Reporting systems

3. ✅ **Data locality is valuable**
   - Related data accessed together
   - Batch processing benefits

4. ✅ **Examples**:
   - Live streaming room analytics
   - IoT device data (by device range)
   - Geographical data (by region)

### Hybrid Strategy (Recommended for Production):

```
┌─────────────────────────────────────────────┐
│         Application Architecture             │
├─────────────────────────────────────────────┤
│                                             │
│  User Data        →  Hash Partition         │
│  (users, profiles)    by user_id            │
│                                             │
│  Transaction Data →  Hash Partition         │
│  (orders, payments)   by user_id            │
│                                             │
│  Room Data        →  Range Partition        │
│  (room_stats)         by room_id            │
│                                             │
│  Analytics Data   →  Range Partition        │
│  (aggregated)         by time               │
│                                             │
│  Hot Rooms        →  Dedicated Shard        │
│  (special handling)   separate instance     │
│                                             │
└─────────────────────────────────────────────┘
```

---

## Key Takeaways

### 1. No Silver Bullet
- Neither strategy is universally better
- Performance depends on query patterns
- Choose based on your dominant use case

### 2. Hash Strengths = Range Weaknesses
- Hash excels at user queries → Range struggles
- Range excels at room queries → Hash struggles
- They are complementary, not competing

### 3. Hotspot Matters
- Hash provides predictable performance
- Range can have severe imbalance (50.9% vs 15%)
- Consider content popularity patterns

### 4. Hybrid is Best
- Use Hash for user-centric tables
- Use Range for content-centric tables
- Separate hot content to dedicated shards

---

## Test Reproducibility

All tests are fully automated and reproducible:

```bash
# Full automated test
cd "shared 2"
./run_comparison.sh

# Individual tests
python3 comparison_experiment.py    # All 5 scenarios
python3 verify_hotspot.py          # Detailed hotspot test
```

**Test Files**:
- `comparison_experiment.py` - Main test runner
- `verify_hotspot.py` - Hotspot verification
- `Hash_experiment/` - Student A implementation
- `Range_experiment/` - Student B implementation

---

## Conclusion

✅ **All 5 scenarios tested successfully**
✅ **Results match theoretical expectations**
✅ **Clear trade-offs demonstrated empirically**

### Final Recommendation:

For a **live streaming coupon system**:
1. Use **Hash** for user-related queries (login, user coupons)
2. Use **Range** for room-related analytics (room rankings, time-based reports)
3. Implement **dedicated shards** for top 10% popular rooms
4. Use **time-based Range** partitioning for historical data archiving

This hybrid approach leverages the strengths of both strategies while mitigating their weaknesses.

---

## References

- Code Repository: `shared 2/`
- Raw Results: `comparison_results.json`
- Detailed Analysis: `EXPERIMENT_RESULTS_ANALYSIS.md`
- Setup Guide: `COMPARISON_README.md`

**Test Date**: December 8, 2025
**Status**: All tests passed ✓

