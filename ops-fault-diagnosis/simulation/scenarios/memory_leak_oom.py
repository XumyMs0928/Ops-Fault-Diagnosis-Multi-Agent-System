from __future__ import annotations

from datetime import datetime, timedelta

from simulation.scenarios.base_scenario import (
    AlertStormProfile,
    LogFaultProfile,
    MetricsFaultProfile,
    ChangeProfile,
    BaseScenario,
)

_INCIDENT_TS = datetime(2026, 4, 29, 10, 15, 0)


class MemoryLeakOOMScenario(BaseScenario):
    """
    Root cause: order-svc has a memory leak in its new caching layer.

    Failure cascade:
    1. order-svc memory slowly climbs from 60% to 95% over 30 minutes
    2. JVM triggers aggressive GC, causing latency spikes
    3. OOM killer terminates order-svc container
    4. Kubernetes restarts order-svc (repeated crash loop)
    5. api-gateway sees intermittent 503 from order-svc
    6. payment-svc and inventory-svc see reduced upstream traffic
    7. Users experience intermittent failures and slow page loads
    """

    def scenario_id(self) -> str:
        return "memory-leak-oom-001"

    def name(self) -> str:
        return "Memory Leak OOM Kill Cascade"

    def description(self) -> str:
        return (
            "order-svc v3.0.0 introduced a memory leak in the new caching layer. "
            "Memory slowly climbs until the OOM killer terminates the container, "
            "causing a crash loop and intermittent failures across the order chain."
        )

    def incident_timestamp(self) -> datetime:
        return _INCIDENT_TS

    def get_alert_profile(self) -> AlertStormProfile:
        return AlertStormProfile(
            root_service="order-svc",
            surface_services=["api-gateway"],
            affected_services=["order-svc", "api-gateway", "payment-svc", "inventory-svc"],
            core_alerts=[
                {"delay_seconds": 0, "service": "order-svc", "alert_name": "HighMemoryUsage", "severity": "high", "message": "Memory usage exceeded 90% threshold"},
                {"delay_seconds": 120, "service": "order-svc", "alert_name": "HighLatencyP99", "severity": "high", "message": "GC pause causing P99 latency spike: 3000ms"},
                {"delay_seconds": 300, "service": "order-svc", "alert_name": "ProcessOOMKilled", "severity": "critical", "message": "Container order-svc-7d4f8b killed by OOM killer"},
                {"delay_seconds": 305, "service": "order-svc", "alert_name": "PodRestarting", "severity": "high", "message": "Pod order-svc-7d4f8b restarting (crash loop)"},
                {"delay_seconds": 310, "service": "api-gateway", "alert_name": "UpstreamUnavailable", "severity": "high", "message": "order-svc returning 503 - service unavailable"},
                {"delay_seconds": 315, "service": "api-gateway", "alert_name": "ErrorRateSpike", "severity": "medium", "message": "API error rate at 15% due to order-svc failures"},
                {"delay_seconds": 600, "service": "order-svc", "alert_name": "ProcessOOMKilled", "severity": "critical", "message": "Container order-svc-7d4f8b killed by OOM killer again"},
                {"delay_seconds": 605, "service": "order-svc", "alert_name": "CrashLoopBackOff", "severity": "critical", "message": "Pod in CrashLoopBackOff - failed 5 times in 30min"},
                {"delay_seconds": 610, "service": "payment-svc", "alert_name": "LowTraffic", "severity": "low", "message": "Payment processing traffic dropped 40%"},
                {"delay_seconds": 615, "service": "inventory-svc", "alert_name": "LowTraffic", "severity": "low", "message": "Inventory API traffic dropped 35%"},
            ],
            noise_services=["product-svc", "user-svc", "notification-svc", "db-primary"],
        )

    def get_log_profile(self) -> LogFaultProfile:
        return LogFaultProfile(
            fault_logs=[
                {"delay_seconds": 0, "service": "order-svc", "level": "WARN", "message": "Heap memory usage at 90%: used=1440MB, max=1600MB", "exception_class": None},
                {"delay_seconds": 60, "service": "order-svc", "level": "WARN", "message": "GC pause detected: 1200ms (G1 Young Generation)", "exception_class": None},
                {"delay_seconds": 120, "service": "order-svc", "level": "WARN", "message": "Full GC triggered: heap usage 95%, pause 3200ms", "exception_class": None},
                {"delay_seconds": 180, "service": "order-svc", "level": "ERROR", "message": "java.lang.OutOfMemoryError: Java heap space", "exception_class": "java.lang.OutOfMemoryError"},
                {"delay_seconds": 181, "service": "order-svc", "level": "ERROR", "message": "CacheStore.put() failed: unable to allocate new entry", "exception_class": None, "stack_trace": "at com.order.cache.CacheStore.put(CacheStore.java:142)\nat com.order.service.OrderService.processOrder(OrderService.java:89)\nat sun.reflect.NativeMethodAccessorImpl.invoke0(Native Method)"},
                {"delay_seconds": 300, "service": "order-svc", "level": "ERROR", "message": "JVM process terminated by SIGKILL (OOM killer)", "exception_class": None},
                {"delay_seconds": 310, "service": "api-gateway", "level": "ERROR", "message": "Connection refused: order-svc:8080 - service unavailable", "exception_class": None},
                {"delay_seconds": 315, "service": "api-gateway", "level": "WARN", "message": "Fallback triggered for /api/orders: returning HTTP 503", "exception_class": None},
                {"delay_seconds": 610, "service": "payment-svc", "level": "INFO", "message": "Payment request rate dropped to 60% of normal baseline", "exception_class": None},
            ],
            noise_ratio=0.3,
        )

    def get_metrics_profile(self) -> MetricsFaultProfile:
        return MetricsFaultProfile(
            anomalies=[
                {"service": "order-svc", "metric_type": "memory_utilization_percent", "baseline": 60.0, "observed": 97.0, "deviation_percent": 61.7},
                {"service": "order-svc", "metric_type": "latency_p99_ms", "baseline": 80.0, "observed": 3500.0, "deviation_percent": 4275.0},
                {"service": "order-svc", "metric_type": "error_rate_percent", "baseline": 0.05, "observed": 50.0, "deviation_percent": 99900.0},
                {"service": "api-gateway", "metric_type": "error_rate_percent", "baseline": 0.05, "observed": 15.0, "deviation_percent": 29900.0},
                {"service": "api-gateway", "metric_type": "latency_p99_ms", "baseline": 30.0, "observed": 2000.0, "deviation_percent": 6566.7},
                {"service": "payment-svc", "metric_type": "error_rate_percent", "baseline": 0.1, "observed": 5.0, "deviation_percent": 4900.0},
            ],
        )

    def get_change_profile(self) -> ChangeProfile:
        return ChangeProfile(
            root_cause_changes=[
                {"delay_hours": 3, "service": "order-svc", "change_type": "deployment", "description": "order-svc v3.0.0 deployed - new in-memory caching layer for order details", "author": "chen.hao"},
                {"delay_hours": 48, "service": "order-svc", "change_type": "config_change", "description": "JVM heap increased from 1GB to 1.6GB (-Xmx1600m)", "author": "chen.hao"},
            ],
            noise_changes=[
                {"delay_hours": 8, "service": "user-svc", "change_type": "deployment", "description": "user-svc v2.1.0 deployed - SSO integration update", "author": "liu.yang"},
                {"delay_hours": 24, "service": "db-primary", "change_type": "schema_migration", "description": "Added index on orders.created_at for reporting queries", "author": "dba-team"},
            ],
        )
