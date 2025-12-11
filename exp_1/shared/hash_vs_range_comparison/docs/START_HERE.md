# START HERE: Hash vs Range Sharding Comparison

## 🎯 Quick Start (3 Steps)

### Step 1: Start Databases
```bash
docker-compose up -d
sleep 30  # Wait for MySQL initialization
```

### Step 2: Run Comparison Test
```bash
./run_comparison.sh
```

### Step 3: View Results
```bash
python3 visualize_results.py
```

**That's it!** 🎉

---

## 📊 What You'll Get

After running the tests, you'll see:
- ✅ 5 scenario comparisons (Write, User Query, Room Query, Time Query, Hotspot)
- ✅ Performance metrics for both strategies
- ✅ Visual bar charts and tables
- ✅ Detailed analysis in JSON format

---

## 📁 Key Files to Read

### For Quick Understanding:
1. **测试结果总结.md** - Chinese summary (quickest to understand)
2. **QUICK_REFERENCE.md** - Performance numbers at a glance
3. **visualize_results.py output** - Visual comparison

### For Detailed Analysis:
1. **FINAL_COMPARISON_REPORT.md** - Comprehensive report
2. **EXPERIMENT_RESULTS_ANALYSIS.md** - Detailed analysis
3. **comparison_results.json** - Raw data

### For Implementation Details:
1. **Hash_experiment/hash_strategy.py** - Student A implementation
2. **Range_experiment/range_strategy.py** - Student B implementation
3. **comparison_experiment.py** - Test framework

---

## 🔍 Test Results Preview

```
┌─────────────────────────────┬───────────┬───────────┬──────────┐
│ Scenario                    │   Hash    │   Range   │  Winner  │
├─────────────────────────────┼───────────┼───────────┼──────────┤
│ Write Performance           │   95.47   │   40.06   │   Hash   │
│ Query by User               │  0.42ms   │  1.48ms   │   Hash   │
│ Query by Room               │  1.44ms   │  0.37ms   │   Range  │
│ Query by Time Range         │  1.91ms   │  1.89ms   │   Range  │
│ Hotspot Problem             │  26.7%    │  50.9%    │   Hash   │
└─────────────────────────────┴───────────┴───────────┴──────────┘
```

**Score: Hash 3 wins, Range 2 wins**

---

## 💡 Key Insights

### Hash Partitioning Wins:
- ⭐ **Write Balance**: 95.47/100 vs 40.06/100
- ⭐ **User Queries**: 3.5x faster than Range
- ⭐ **Hotspot Resistance**: Only 26.7% max vs 50.9%

### Range Partitioning Wins:
- ⭐ **Room Queries**: 3.93x faster than Hash
- ⭐ **Time Queries**: Marginally faster
- ⭐ **Data Locality**: Related data stored together

---

## 🎓 Understanding the Strategies

### Hash Partitioning (Student A)
```python
# Route by user_id
shard_id = hash(user_id) % 4

# Result: Users evenly distributed
Shard 0: 25% of users
Shard 1: 25% of users
Shard 2: 25% of users
Shard 3: 25% of users
```

**Best for**: User-centric applications, load balancing

### Range Partitioning (Student B)
```python
# Route by room_id
if room_id <= 1000: shard_id = 0
elif room_id <= 2000: shard_id = 1
elif room_id <= 3000: shard_id = 2
else: shard_id = 3

# Result: Rooms grouped by range
# Problem: Hot rooms create hotspots!
```

**Best for**: Room analytics, time-based queries

---

## 🚀 Advanced Usage

### Run Individual Tests

```bash
# Just the hotspot test
python3 verify_hotspot.py

# Just the comparison
python3 comparison_experiment.py

# Visualize existing results
python3 visualize_results.py
```

### Initialize Shards Separately

```bash
# Hash shards
cd Hash_experiment
python3 init_shards.py

# Range shards
cd Range_experiment
python3 init_shards.py
```

### Check Database Status

```bash
# Check containers
docker ps | grep coupon_mysql

# Check shard data
docker exec -it coupon_mysql_shard_0 mysql -uroot -ppassword -e "USE coupon_db_0; SELECT COUNT(*) FROM coupon_results;"
```

---

## 📖 Documentation Guide

### Quickest to Slowest Read Time:

1. **This File** (5 min) - You are here
2. **QUICK_REFERENCE.md** (10 min) - Commands and results
3. **测试结果总结.md** (15 min) - Chinese detailed summary
4. **EXPERIMENT_RESULTS_ANALYSIS.md** (20 min) - Technical analysis
5. **FINAL_COMPARISON_REPORT.md** (30 min) - Complete report
6. **COMPARISON_README.md** (15 min) - Setup guide
7. **PROJECT_SUMMARY.md** (20 min) - Project overview

---

## 🔧 Troubleshooting

### Problem: Docker not running
```bash
# Start Docker Desktop first, then:
docker-compose up -d
```

### Problem: Port already in use
```bash
# Check what's using the port
lsof -i :3307

# Stop and restart
docker-compose down
docker-compose up -d
```

### Problem: Connection refused
```bash
# Wait longer for MySQL to initialize
sleep 60

# Or check logs
docker logs coupon_mysql_shard_0
```

### Problem: Old test data interfering
```bash
# Clear all data
python3 verify_hotspot.py  # This clears before testing
```

---

## ✅ Verification Checklist

After running tests, verify:
- [ ] All 5 scenarios completed
- [ ] Hash wins Write Performance (balance ~95)
- [ ] Hash wins User Query (~0.4ms)
- [ ] Range wins Room Query (~0.4ms)
- [ ] Range wins Time Query (marginally)
- [ ] Hash wins Hotspot (max ~27%)
- [ ] Results saved to comparison_results.json
- [ ] All tests match expected outcomes ✓

---

## 🎯 Next Steps

1. **Read the Results**: Start with `测试结果总结.md` (Chinese)
2. **Understand Implementation**: Check `Hash_experiment/` and `Range_experiment/`
3. **Review Code**: All Python files have English comments only
4. **Run More Tests**: Modify parameters in `comparison_experiment.py`
5. **Apply to Your Project**: Use insights for your own sharding decisions

---

## 📊 Project Statistics

- **Total Files Created**: 15+
- **Lines of Code**: ~2000+
- **Documentation Pages**: 7
- **Test Scenarios**: 5
- **Strategies Compared**: 2
- **Database Shards**: 8 (4 per strategy)
- **Test Records**: 1000+

---

## 🎓 Learning Outcomes

After completing this experiment, you will understand:
- ✅ How Hash partitioning works
- ✅ How Range partitioning works
- ✅ Trade-offs between strategies
- ✅ When to use each approach
- ✅ How to implement sharding in Python
- ✅ How to design comparison experiments
- ✅ Real-world performance implications

---

## 🌟 Key Takeaway

**There is no "best" sharding strategy - only the best strategy for YOUR use case!**

- User-centric app? → Use Hash
- Content-centric app? → Use Range
- Both? → Use Hybrid approach

---

## 📞 Need Help?

1. Check `QUICK_REFERENCE.md` for commands
2. Check `FINAL_COMPARISON_REPORT.md` for details
3. Check `测试结果总结.md` for Chinese explanation
4. Check container logs: `docker logs coupon_mysql_shard_0`

---

## 🎉 Success Criteria

You'll know it worked when you see:
```
================================================================================
✅ All test results match expected theoretical outcomes
================================================================================

📈 Score: Hash wins 3 scenarios, Range wins 2 scenarios

💡 Key Takeaways:
   • Hash excels at: User queries, Write balance, Hotspot resistance
   • Range excels at: Room queries, Time queries
```

---

**Ready to begin? Run: `./run_comparison.sh`** 🚀

---

**Last Updated**: December 8, 2025
**Status**: Ready to Run ✅
**Code Quality**: No Chinese in code files ✅

