# Observability & Operations - Implementation Guide

This document describes the observability and operations features implemented for EPIC-9.

## Overview

The observability stack includes health checks, circuit breakers, structured logging, log shipping, APM integration, and custom metrics for monitoring the BB-PAXDATA application.

## TASK-9.1: Health Checks & Circuit Breaker

### 9.1.1 Health Check Endpoints

Three health check endpoints are available:

- **`/health`** - Basic health check
  - Checks database and Redis connectivity
  - Returns service status, version, and environment
  - Returns 503 if dependencies are unhealthy

- **`/ready`** - Readiness probe
  - Checks all dependencies (database, Redis, Meilisearch)
  - Returns detailed status of each dependency
  - Returns 503 if any dependency is not ready
  - Used by Kubernetes/Docker for readiness probes

- **`/live`** - Liveness probe
  - Checks if the process is running and responding
  - Lightweight check without dependency validation
  - Used by Kubernetes/Docker for liveness probes

### 9.1.2 Circuit Breaker Pattern

Circuit breaker implementation protects AI service calls from cascading failures.

**Features:**
- Configurable failure threshold (default: 5 consecutive failures)
- Automatic recovery with half-open state
- Configurable timeout before recovery attempts (default: 60 seconds)
- Fallback mechanism support
- State monitoring endpoint at `/health/circuit-breakers`

**States:**
- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Circuit open, requests fail fast
- **HALF_OPEN**: Testing if service has recovered

**Usage Example:**

```python
from bb_paxdata.infrastructure.ai.circuit_breaker import (
    with_circuit_breaker,
    CircuitBreakerConfig,
)

result = await with_circuit_breaker(
    service_name="anthropic",
    func=ai_service.complete,
    fallback_response=default_response,
    config=CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=2,
        open_timeout_seconds=60,
        timeout_seconds=120,
    ),
)
```

**Monitoring:**

```bash
curl http://localhost:8000/health/circuit-breakers
```

## TASK-9.2: Log Aggregation

### 9.2.1 Structured Logging

Enhanced structlog configuration with:

- **Correlation ID tracking**: Automatically injected from request headers
- **OpenTelemetry trace injection**: trace_id and span_id in logs
- **Performance markers**: Context manager for timing code blocks
- **Contextvars integration**: Request-scoped context binding

**Performance Logger Usage:**

```python
from bb_paxdata.config.logging import performance_logger

with performance_logger(logger, "ai_completion"):
    result = await ai_service.complete(prompt)
```

**Log Format:**

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "info",
  "logger": "bb_paxdata.infrastructure.ai",
  "correlation_id": "corr-abc123",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "event": "performance.end",
  "performance_stage": "ai_completion",
  "duration_ms": 1234.56
}
```

### 9.2.2 Log Shipping

Support for centralized log aggregation with ELK and Loki.

**Configuration (settings.py):**

```python
# Grafana Loki
loki_url: str = "http://localhost:3100"
loki_enabled: bool = False

# ELK Stack
elk_url: str = "http://localhost:9200"
elk_enabled: bool = False
elk_index: str = "bb-paxdata-logs"
```

**Usage:**

```python
from bb_paxdata.infrastructure.logging.log_shipping import setup_log_shipping

# Configure log shipping
shipper = setup_log_shipping(
    loki_url="http://loki:3100",
    loki_enabled=True,
    elk_url="http://elasticsearch:9200",
    elk_enabled=True,
)

# Add to structlog processors
structlog.configure(processors=[..., shipper, ...])
```

## TASK-9.3: Performance Monitoring

### 9.3.1 APM Integration

Support for New Relic and Datadog APM providers.

**Configuration (settings.py):**

```python
# APM Provider Selection
apm_provider: str = "none"  # "newrelic", "datadog", or "none"

# New Relic
newrelic_license_key: str = ""
newrelic_app_name: str = "bb-paxdata"
newrelic_enabled: bool = False

# Datadog
datadog_api_key: str = ""
datadog_service_name: str = "bb-paxdata"
datadog_enabled: bool = False
datadog_host: str = "localhost"
datadog_port: int = 8126
```

**Usage:**

```python
from bb_paxdata.infrastructure.observability.apm import get_apm

apm = get_apm()
apm.record_transaction("ai_completion", duration=1.23, backend="anthropic")
apm.record_error(error, context={"request_id": "123"})
```

### 9.3.2 Custom Metrics

Prometheus metrics for monitoring application performance.

**Available Metrics:**

- **Pipeline Metrics**
  - `pipeline_stage_duration_seconds`: Pipeline stage execution time
  - `pipeline_files_processed_total`: Total files processed

- **AI Model Metrics**
  - `ai_model_latency_seconds`: AI model response latency
  - `ai_request_duration_seconds`: AI request duration
  - `ai_tokens_total`: Token usage by type
  - `ai_tokens_per_second`: Token generation throughput

- **Cache Metrics**
  - `cache_hit_ratio`: Cache hit ratio (0.0 to 1.0)
  - `cache_hit_total`: Total cache hits
  - `cache_miss_total`: Total cache misses
  - `cache_operations_total`: Cache operations by type

- **Database Metrics**
  - `slow_query_total`: Slow database queries (>1s)

- **Circuit Breaker Metrics**
  - `circuit_breaker_state`: Circuit breaker state (0=closed, 1=open, 2=half_open)

**Usage:**

```python
from bb_paxdata.infrastructure.observability.metrics import get_metrics

metrics = get_metrics()

# Record pipeline stage duration
metrics.record_pipeline_stage_duration(
    stage_name="sentiment_analysis",
    duration_seconds=5.23,
    status="success"
)

# Record AI model latency
metrics.record_ai_model_latency(
    backend="anthropic",
    model="claude-3-5-sonnet",
    operation="complete",
    latency_seconds=1.45
)

# Record cache operations
metrics.record_cache_hit(cache_type="redis")
metrics.record_cache_miss(cache_type="redis")
metrics.update_cache_hit_ratio(cache_type="redis", ratio=0.85)

# Record slow query
metrics.record_slow_query(query_type="select")

# Set circuit breaker state
metrics.set_circuit_breaker_state(service_name="anthropic", state="open")
```

**Metrics Endpoint:**

```bash
curl http://localhost:8000/metrics
```

## Environment Variables

All observability features can be configured via environment variables:

```bash
# Health Checks
PAXDATA_METRICS_TOKEN=your-secret-token

# Circuit Breaker
PAXDATA_AI_TIMEOUT=120

# Log Shipping
PAXDATA_LOKI_URL=http://localhost:3100
PAXDATA_LOKI_ENABLED=true
PAXDATA_ELK_URL=http://localhost:9200
PAXDATA_ELK_ENABLED=true
PAXDATA_ELK_INDEX=bb-paxdata-logs

# APM
PAXDATA_APM_PROVIDER=datadog
PAXDATA_DATADOG_API_KEY=your-api-key
PAXDATA_DATADOG_SERVICE_NAME=bb-paxdata
PAXDATA_DATADOG_ENABLED=true
PAXDATA_NEWRELIC_LICENSE_KEY=your-license-key
PAXDATA_NEWRELIC_APP_NAME=bb-paxdata
PAXDATA_NEWRELIC_ENABLED=true

# OpenTelemetry
PAXDATA_OTEL_ENABLED=true
PAXDATA_OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
PAXDATA_OTEL_SERVICE_NAME=bb-paxdata

# Sentry
PAXDATA_SENTRY_DSN=https://your-sentry-dsn
PAXDATA_SENTRY_TRACES_SAMPLE_RATE=1.0
```

## Deployment

### Kubernetes Probes

```yaml
livenessProbe:
  httpGet:
    path: /live
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
```

### Prometheus Scrape Config

```yaml
scrape_configs:
  - job_name: 'bb-paxdata'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['bb-paxdata:8000']
    headers:
      X-Metrics-Token: 'your-secret-token'
```

### Grafana Dashboard

Import the provided Grafana dashboard configuration from `docs/runbooks/grafana_dashboard.json` for visualization of all metrics.

## Monitoring Best Practices

1. **Set up alerts** for:
   - Circuit breaker state changes
   - High error rates (>5%)
   - Slow AI model latency (>10s)
   - Low cache hit ratio (<70%)
   - Database slow queries

2. **Monitor key metrics**:
   - Pipeline stage durations
   - AI model latency and token usage
   - Cache hit/miss ratios
   - Circuit breaker states

3. **Use correlation IDs** for tracing requests across services

4. **Review logs** with centralized log aggregation (ELK/Loki)

5. **Track distributed traces** with OpenTelemetry/Jaeger

## Troubleshooting

### Circuit Breaker Open

If circuit breaker is open:
1. Check `/health/circuit-breakers` endpoint
2. Verify AI service availability
3. Check logs for failure reasons
4. Wait for timeout (default 60s) for automatic recovery

### High Latency

If AI model latency is high:
1. Check `ai_model_latency_seconds` metric
2. Verify network connectivity to AI provider
3. Check if rate limiting is applied
4. Consider switching to faster model

### Low Cache Hit Ratio

If cache hit ratio is low:
1. Check `cache_hit_ratio` metric
2. Review cache key generation logic
3. Increase cache TTL if appropriate
4. Check Redis memory usage

## References

- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
- [Grafana Loki](https://grafana.com/docs/loki/latest/)
- [New Relic Python Agent](https://docs.newrelic.com/docs/apm/agents/python-agent/)
- [Datadog APM](https://docs.datadoghq.com/tracing/)
