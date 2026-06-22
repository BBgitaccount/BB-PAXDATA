# Prometheus TSDB Corruption Recovery Runbook

## Problem Description

When Prometheus encounters TSDB (Time Series Database) corruption, you may see errors such as:

- `out of sequence m-mapped chunk`
- Corrupted mmap files that cannot be deleted
- Data integrity issues in the time series storage

## Root Cause

TSDB corruption can occur due to:

- Abrupt container shutdown or crash
- Disk I/O errors
- Insufficient disk space during writes
- File system corruption

## Recovery Procedures

### Option 1: Clean Chunks Directory (Minimal Data Loss)

This option attempts to preserve as much historical data as possible by only removing corrupted chunks.

```bash
# Stop the Prometheus container
docker-compose stop prometheus

# Access the Prometheus data volume
docker run --rm -v paxdata-prometheus_data:/prometheus busybox ls -la /prometheus

# Remove corrupted chunks (WARNING: This may cause gaps in metrics)
docker run --rm -v paxdata-prometheus_data:/prometheus busybox rm -rf /prometheus/chunks/*

# Restart Prometheus
docker-compose start prometheus
```

### Option 2: Reset Prometheus Volume (Complete Data Loss)

This option completely resets the Prometheus volume, resulting in permanent loss of all historical metric data.

```bash
# Stop the Prometheus container
docker-compose stop prometheus

# Remove the Prometheus volume
docker volume rm paxdata-prometheus_data

# Recreate the volume and restart Prometheus
docker-compose up -d prometheus
```

**Negative Impact Analysis:**

- All historical metric data will be permanently lost
- Grafana dashboards will show no historical data until new metrics are collected
- Alerting rules based on historical trends will be affected
- Time-based analysis and debugging will be limited to data collected after recovery

### Option 3: Backup and Selective Restore (Advanced)

If you have backups of the Prometheus data:

```bash
# Stop Prometheus
docker-compose stop prometheus

# Remove corrupted volume
docker volume rm paxdata-prometheus_data

# Restore from backup (if available)
docker run --rm -v paxdata-prometheus_data:/prometheus -v /path/to/backup:/backup busybox cp -a /backup/* /prometheus/

# Restart Prometheus
docker-compose start prometheus
```

## Prevention Strategies

### 1. Regular Volume Backups

```bash
# Backup Prometheus data
docker run --rm -v paxdata-prometheus_data:/prometheus -v $(pwd)/backups:/backup busybox tar czf /backup/prometheus-backup-$(date +%Y%m%d).tar.gz /prometheus
```

### 2. Monitor Disk Space

Ensure sufficient disk space is available for Prometheus operations:

- Monitor using Prometheus node-exporter metrics
- Set up alerts for disk usage > 80%
- Configure appropriate retention policies

### 3. Graceful Shutdowns

Always stop containers gracefully:

```bash
docker-compose stop prometheus  # Graceful shutdown
# Avoid: docker-compose kill prometheus
```

### 4. Health Checks

Prometheus includes built-in health checks. Monitor the container health status:

```bash
docker ps --filter name=paxdata-prometheus
```

## Verification

After recovery, verify Prometheus is functioning correctly:

```bash
# Check container status
docker ps --filter name=paxdata-prometheus

# Check Prometheus logs
docker logs paxdata-prometheus

# Access Prometheus UI
curl http://localhost:9090/-/healthy

# Verify data ingestion
curl http://localhost:9090/api/v1/query?query=up
```

## Related Documentation

- [Prometheus TSDB Documentation](https://prometheus.io/docs/prometheus/latest/storage/)
- [Docker Volume Management](https://docs.docker.com/storage/volumes/)
- [Grafana Dashboards](../guides/grafana-setup.md)
