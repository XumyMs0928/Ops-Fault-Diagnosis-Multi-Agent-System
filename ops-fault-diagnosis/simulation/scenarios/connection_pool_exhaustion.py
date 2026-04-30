from __future__ import annotations

from datetime import datetime, timedelta

from simulation.scenarios.base_scenario import (
    AlertStormProfile,
    LogFaultProfile,
    MetricsFaultProfile,
    ChangeProfile,
    BaseScenario,
)

_INCIDENT_TS = datetime(2026, 4, 29, 14, 30, 0)


class ConnectionPoolExhaustionScenario(BaseScenario):
    """
    Root cause: payment-svc v2.3.1 introduced a connection leak.
    Combined with db-primary max_connections reduced from 200 to 100.

    Failure cascade:
    1. db-primary connections exhausted (100/100 active)
    2. payment-svc cannot acquire DB connections -> request timeouts
    3. order-svc calls to payment-svc timeout -> order failures
    4. api-gateway returns 504/502 to web-frontend
    5. Users see "Order Failed" on the website
    """

    def scenario_id(self) -> str:
        return "conn-pool-exhaustion-001"

    def name(self) -> str:
        return "Database Connection Pool Exhaustion Cascade"

    def description(self) -> str:
        return (
            "payment-svc v2.3.1 introduced a connection leak, combined with "
            "db-primary max_connections reduced from 200 to 100, causing a "
            "cascading failure across the order processing chain."
        )

    def incident_timestamp(self) -> datetime:
        return _INCIDENT_TS

    def get_alert_profile(self) -> AlertStormProfile:
        return AlertStormProfile(
            root_service="db-primary",
            surface_services=["api-gateway", "order-svc"],
            affected_services=["db-primary", "payment-svc", "order-svc", "api-gateway"],
            core_alerts=[
                {"delay_seconds": 0, "service": "db-primary", "alert_name": "ActiveConnectionsExceeded", "severity": "critical", "message": "Active connections reached max_connections=100"},
                {"delay_seconds": 15, "service": "payment-svc", "alert_name": "HighLatencyP99", "severity": "high", "message": "P99 latency exceeded threshold: 5000ms"},
                {"delay_seconds": 20, "service": "payment-svc", "alert_name": "ErrorRateSpike", "severity": "critical", "message": "Error rate spiked to 35%"},
                {"delay_seconds": 30, "service": "order-svc", "alert_name": "UpstreamTimeout", "severity": "high", "message": "Upstream service payment-svc timeout rate 40%"},
                {"delay_seconds": 35, "service": "order-svc", "alert_name": "OrderFailureRate", "severity": "critical", "message": "Order creation failure rate 25%"},
                {"delay_seconds": 40, "service": "api-gateway", "alert_name": "ErrorRateSpike", "severity": "high", "message": "API error rate reached 20%"},
                {"delay_seconds": 45, "service": "api-gateway", "alert_name": "HighLatencyP99", "severity": "medium", "message": "Gateway P99 latency 6000ms"},
                {"delay_seconds": 50, "service": "web-frontend", "alert_name": "BackendUnavailable", "severity": "high", "message": "Backend API returning 504 errors"},
            ],
            noise_services=["product-svc", "user-svc", "inventory-svc", "notification-svc"],
        )

    def get_log_profile(self) -> LogFaultProfile:
        return LogFaultProfile(
            fault_logs=[
                {"delay_seconds": 0, "service": "db-primary", "level": "ERROR", "message": "Connection limit reached: max_connections=100, active=100", "exception_class": None},
                {"delay_seconds": 5, "service": "db-primary", "level": "WARN", "message": "Rejecting connection from 10.0.3.15: pool exhausted, waiting_timeout=30s", "exception_class": None},
                {"delay_seconds": 10, "service": "payment-svc", "level": "ERROR", "message": "HikariPool-1 - Connection is not available, request timed out after 30000ms", "exception_class": "java.sql.SQLTransientConnectionException"},
                {"delay_seconds": 12, "service": "payment-svc", "level": "ERROR", "message": "Unable to acquire JDBC connection from pool", "exception_class": "java.sql.SQLException"},
                {"delay_seconds": 18, "service": "payment-svc", "level": "WARN", "message": "Payment processing timeout for order ORD-88432 after 5000ms", "exception_class": None},
                {"delay_seconds": 25, "service": "payment-svc", "level": "ERROR", "message": "Stripe API call failed: connection pool exhausted", "exception_class": "com.stripe.exception.APIConnectionException"},
                {"delay_seconds": 30, "service": "order-svc", "level": "ERROR", "message": "feign.RetryableException: Read timed out executing POST http://payment-svc:8080/api/pay", "exception_class": "feign.RetryableException"},
                {"delay_seconds": 32, "service": "order-svc", "level": "WARN", "message": "Order ORD-88432 processing failed: upstream service unavailable", "exception_class": None},
                {"delay_seconds": 40, "service": "api-gateway", "level": "ERROR", "message": "upstream request timeout: POST /api/orders -> 504 Gateway Timeout", "exception_class": None},
                {"delay_seconds": 42, "service": "api-gateway", "level": "WARN", "message": "Circuit breaker OPEN for endpoint /api/orders/*", "exception_class": None},
            ],
            noise_ratio=0.3,
        )

    def get_metrics_profile(self) -> MetricsFaultProfile:
        return MetricsFaultProfile(
            anomalies=[
                {"service": "db-primary", "metric_type": "active_connections", "baseline": 45.0, "observed": 100.0, "deviation_percent": 122.2},
                {"service": "db-primary", "metric_type": "cpu_utilization_percent", "baseline": 30.0, "observed": 87.0, "deviation_percent": 190.0},
                {"service": "payment-svc", "metric_type": "latency_p99_ms", "baseline": 50.0, "observed": 15000.0, "deviation_percent": 29900.0},
                {"service": "payment-svc", "metric_type": "error_rate_percent", "baseline": 0.1, "observed": 35.0, "deviation_percent": 34900.0},
                {"service": "order-svc", "metric_type": "latency_p99_ms", "baseline": 80.0, "observed": 8000.0, "deviation_percent": 9900.0},
                {"service": "order-svc", "metric_type": "error_rate_percent", "baseline": 0.05, "observed": 25.0, "deviation_percent": 49900.0},
                {"service": "api-gateway", "metric_type": "latency_p99_ms", "baseline": 30.0, "observed": 6000.0, "deviation_percent": 19900.0},
                {"service": "api-gateway", "metric_type": "error_rate_percent", "baseline": 0.05, "observed": 20.0, "deviation_percent": 39900.0},
            ],
        )

    def get_change_profile(self) -> ChangeProfile:
        return ChangeProfile(
            root_cause_changes=[
                {"delay_hours": 2, "service": "payment-svc", "change_type": "deployment", "description": "payment-svc v2.3.1 deployed - added connection retry logic", "author": "zhang.wei"},
                {"delay_hours": 24, "service": "db-primary", "change_type": "config_change", "description": "max_connections changed from 200 to 100 for cost optimization", "author": "dba-team"},
            ],
            noise_changes=[
                {"delay_hours": 6, "service": "product-svc", "change_type": "deployment", "description": "product-svc v1.8.0 deployed - search ranking update", "author": "li.ming"},
                {"delay_hours": 12, "service": "user-svc", "change_type": "scaling", "description": "user-svc scaling event: 3->5 replicas", "author": "k8s-autoscaler"},
                {"delay_hours": 8, "service": "notification-svc", "change_type": "deployment", "description": "notification-svc v3.1.0 deployed - email template update", "author": "wang.fang"},
            ],
        )
