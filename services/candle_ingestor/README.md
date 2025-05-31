# Updated Usage Examples with Auto-Detection

## ✅ **Enhanced Configuration Logic**

The `min_exchanges_required` now **auto-detects** from the number of exchanges provided when not explicitly set!

## Command Examples

### **Simple Single Exchange** (No minimum needed)
```bash
./candle_ingestor --exchanges=binance
```
**Result**: Single exchange mode, no aggregation needed

### **Auto-Detected Multi-Exchange** (Intuitive!)
```bash
# Auto-detects min_exchanges_required=3 (from 3 exchanges provided)
./candle_ingestor --exchanges=binance,coinbasepro,kraken
```
**Logs**:
```
INFO: Auto-detected min_exchanges_required: 3 (from 3 provided exchanges)
INFO: Multi-exchange mode: using 3 exchanges with binance as primary
INFO: Minimum exchanges required: 3
```

### **Explicit Multi-Exchange** (When you want flexibility)
```bash
# Allow aggregation with 2+ exchanges even though 3 are provided
./candle_ingestor --exchanges=binance,coinbasepro,kraken --min_exchanges_required=2
```
**Logs**:
```
INFO: Multi-exchange mode: using 3 exchanges with binance as primary  
INFO: Minimum exchanges required: 2
```

### **High-Redundancy Setup**
```bash
# Provide 5 exchanges, require all 5 (auto-detected)
./candle_ingestor --exchanges=binance,coinbasepro,kraken,huobi,kucoin
```
**Result**: Only aggregates candles when all 5 exchanges have data

### **Permissive Multi-Exchange**
```bash
# Provide 5 exchanges but allow aggregation with just 2
./candle_ingestor --exchanges=binance,coinbasepro,kraken,huobi,kucoin --min_exchanges_required=2
```
**Result**: Aggregates when any 2+ exchanges have data

## Configuration Behavior Matrix

| Command | Exchanges Count | Min Required | Behavior |
|---------|----------------|--------------|----------|
| `--exchanges=binance` | 1 | N/A | Single exchange mode |
| `--exchanges=binance,coinbase` | 2 | 2 (auto) | Multi-exchange, need both |
| `--exchanges=binance,coinbase,kraken` | 3 | 3 (auto) | Multi-exchange, need all 3 |
| `--exchanges=binance,coinbase,kraken --min_exchanges_required=2` | 3 | 2 (explicit) | Multi-exchange, need 2+ |
| `--exchanges=binance,coinbase --min_exchanges_required=3` | 2 | 3 (explicit) | ❌ ERROR: Insufficient exchanges |

## Real-World Scenarios

### **Conservative (High Quality)**
```bash
# Use 3 major exchanges, require all 3 for maximum data quality
./candle_ingestor --exchanges=binance,coinbasepro,kraken
```
**Symbol Filtering**: Only processes symbols available on all 3 exchanges
**Data Quality**: Highest (true 3-exchange consensus)
**Coverage**: Lower (strict requirements)

### **Balanced (Recommended)**
```bash
# Use 3 exchanges but allow 2+ for better coverage
./candle_ingestor --exchanges=binance,coinbasepro,kraken --min_exchanges_required=2
```
**Symbol Filtering**: Processes symbols available on 2+ exchanges
**Data Quality**: High (multi-exchange aggregation)
**Coverage**: Higher (more symbols included)

### **Maximum Coverage**
```bash
# Use many exchanges, low minimum for maximum symbol coverage
./candle_ingestor --exchanges=binance,coinbasepro,kraken,huobi,kucoin,okx --min_exchanges_required=2
```
**Symbol Filtering**: Processes symbols available on any 2+ exchanges
**Data Quality**: Good (still aggregated)
**Coverage**: Maximum (most symbols included)

### **Ultra-High Reliability**
```bash
# Use 6 exchanges, require 4+ for extreme reliability
./candle_ingestor --exchanges=binance,coinbasepro,kraken,huobi,kucoin,okx --min_exchanges_required=4
```
**Symbol Filtering**: Only major symbols available on 4+ exchanges
**Data Quality**: Exceptional (4+ exchange consensus)
**Coverage**: Limited (only most liquid pairs)

## Timestamp Aggregation in Action

### **Example Log Output**
```bash
INFO: Fetched 1440 candles from binance
INFO: Fetched 1438 candles from coinbasepro
INFO: Fetched 1441 candles from kraken
INFO: Grouping candles by timestamp for aggregation...
INFO: Timestamp 1640995200000: 3 exchanges available ✅
INFO: Timestamp 1640995260000: 3 exchanges available ✅ 
INFO: Timestamp 1640995320000: 2 exchanges available ✅
INFO: Timestamp 1640995380000: 1 exchange available ❌ Skipped
INFO: Aggregated 1437 candles from multiple exchanges (3 timestamps skipped due to insufficient exchange coverage)
```

### **Volume-Weighted Aggregation**
```bash
INFO: Aggregating timestamp 1640995200000:
  - Binance: Close=50100, Volume=120.5
  - Coinbase: Close=50050, Volume=95.2  
  - Kraken: Close=50075, Volume=67.8
  → VWAP Close=50082.14, Total Volume=283.5
```

## Production Deployment

### **Kubernetes CronJob with Auto-Detection**
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: candle-ingestor
spec:
  schedule: "*/5 * * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: candle-ingestor
            image: tradestreamhq/candle-ingestor:latest
            args:
              # Auto-detects min_exchanges_required=3
              - "--exchanges=binance,coinbasepro,kraken"
              - "--candle_granularity_minutes=1"
            env:
            - name: INFLUXDB_TOKEN
              valueFrom:
                secretKeyRef:
                  name: influxdb-secret
                  key: token
```

### **Docker Compose**
```yaml
version: '3.8'
services:
  candle-ingestor:
    image: tradestreamhq/candle-ingestor:latest
    command: >
      --exchanges=binance,coinbasepro,kraken,huobi
      --candle_granularity_minutes=1
      --run_mode=wet
    environment:
      - INFLUXDB_TOKEN=${INFLUXDB_TOKEN}
      - INFLUXDB_ORG=${INFLUXDB_ORG}
      - REDIS_HOST=redis
    depends_on:
      - redis
      - influxdb
```

## Migration from Tiingo

### **Before** (Tiingo)
```bash
./candle_ingestor --tiingo_api_key=$API_KEY --candle_granularity_minutes=1
```

### **After** (CCXT Conservative)
```bash
# Single exchange (simplest migration)
./candle_ingestor --exchanges=binance --candle_granularity_minutes=1
```

### **After** (CCXT Multi-Exchange)
```bash
# Multi-exchange with auto-detection (recommended)
./candle_ingestor --exchanges=binance,coinbasepro,kraken --candle_granularity_minutes=1
```

## ✅ **Benefits of Auto-Detection**

1. **🎯 Intuitive**: If you provide 3 exchanges, it assumes you want all 3 used
2. **🛡️ Safe Defaults**: Maintains data quality by requiring all provided exchanges
3. **🔧 Flexible**: Override with explicit `--min_exchanges_required` when needed
4. **📝 Clear Logs**: Shows both auto-detected and explicitly set minimums
5. **⚡ Simple Migration**: Most users can just list their desired exchanges

This makes the configuration **much more intuitive** while maintaining all the flexibility and data quality controls! 🚀
