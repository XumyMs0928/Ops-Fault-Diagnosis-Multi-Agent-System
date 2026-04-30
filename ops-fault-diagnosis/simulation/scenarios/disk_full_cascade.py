from __future__ import annotations

from datetime import datetime, timedelta

from simulation.scenarios.base_scenario import (
    AlertStormProfile,
    LogFaultProfile,
    MetricsFaultProfile,
    ChangeProfile,
    BaseScenario,
)

_INCIDENT_TS = datetime(2026, 4, 29, 22, 0, 0)


class DiskFullCascadeScenario(BaseScenario):
    """
    Root cause: Log rotation misconfigured on db-primary.
    Disk fills to 100%, causing:
    1. db-primary cannot write WAL -> replication lag -> read inconsistencies
    2. db-replica falls behind -> stale reads
    3. All services reading from replica get inconsistent data
    4. Notification-svc disk also filling (shared NFS mount)
    """

    def scenario_id(self) -> str:
        return "disk-full-cascade-001"

    def name(self) -> str:
        return "Disk Full Cascade"

    def description(self) -> str:
        return (
            "db-primary log rotation was misconfigured during the last config change, "
            "causing disk usage to reach 100%. WAL writes fail, replication breaks, "
            "causing stale reads and data inconsistency across the service mesh."
        )

    def incident_timestamp(self) -> datetime:
        return _INCIDENT_TS

    def get_alert_profile(self) -> AlertStormProfile:
        return AlertStormProfile(
            root_service="db-primary",
            surface_services=["api-gateway", "user-svc"],
            affected_services=["db-primary", "db-replica", "user-svc", "notification-svc", "api-gateway"],
            core_alerts=[
                {"delay_seconds": 0, "service": "db-primary", "alert_name": "DiskUsageCritical", "severity": "critical", "message": "Disk usage at 98% on /data volume"},
                {"delay_seconds": 30, "service": "db-primary", "alert_name": "WALWriteFailure", "severity": "critical", "message": "Failed to write WAL segment: No space left on device"},
                {"delay_seconds": 45, "service": "db-replica", "alert_name": "ReplicationLag", "severity": "high", "message": "Replication lag exceeded 300 seconds"},
                {"delay_seconds": 60, "service": "db-primary", "alert_name": "DiskFull", "severity": "critical", "message": "Disk usage at 100% on /data volume - writes failing"},
                {"delay_seconds": 90, "service": "user-svc", "alert_name": "StaleDataDetected", "severity": "high", "message": "User profile data from replica is 5+ minutes stale"},
                {"delay_seconds": 120, "service": "notification-svc", "alert_name": "DiskUsageWarning", "severity": "medium", "message": "NFS shared storage at 85% - log volume growing"},
                {"delay_seconds": 150, "service": "api-gateway", "alert_name": "ErrorRateSpike", "severity": "medium", "message": "API error rate at 8% - stale data causing 409 conflicts"},
                {"delay_seconds": 180, "service": "db-primary", "alert_name": "ServiceDegraded", "severity": "high", "message": "MySQL running in read-only mode due to disk full"},
            ],
            noise_services=["product-svc", "order-svc", "payment-svc", "inventory-svc"],
        )

    def get_log_profile(self) -> LogFaultProfile:
        return LogFaultProfile(
            fault_logs=[
                {"delay_seconds": 0, "service": "db-primary", "level": "ERROR", "message": "InnoDB: Error: write to log file failed. OS error: 28 (No space left on device)", "exception_class": None},
                {"delay_seconds": 15, "service": "db-primary", "level": "WARN", "message": "Disk usage on /data at 98% - log rotation may have failed", "exception_class": None},
                {"delay_seconds": 30, "service": "db-primary", "level": "ERROR", "message": "InnoDB: Cannot continue operation - log file write failed", "exception_class": None},
                {"delay_seconds": 45, "service": "db-replica", "level": "WARN", "message": "Replication SQL thread lag: 300s behind primary", "exception_class": None},
                {"delay_seconds": 60, "service": "db-primary", "level": "ERROR", "message": "PID file write failed: /var/run/mysqld/mysqld.pid (No space left on device)", "exception_class": None},
                {"delay_seconds": 90, "service": "user-svc", "level": "WARN", "message": "Stale data detected: user profile last_updated 5min behind expected", "exception_class": None},
                {"delay_seconds": 120, "service": "notification-svc", "level": "WARN", "message": "NFS mount /shared/logs at 85% capacity", "exception_class": None},
                {"delay_seconds": 150, "service": "api-gateway", "level": "ERROR", "message": "HTTP 409 Conflict: stale data version mismatch on user update", "exception_class": None},
                {"delay_seconds": 180, "service": "db-primary", "level": "ERROR", "message": "MySQL switching to read-only mode: SET GLOBAL read_only = ON", "exception_class": None},
            ],
            noise_ratio=0.3,
        )

    def get_metrics_profile(self) -> MetricsFaultProfile:
        return MetricsFaultProfile(
            anomalies=[
                {"service": "db-primary", "metric_type": "disk_utilization_percent", "baseline": 55.0, "observed": 100.0, "deviation_percent": 81.8},
                {"service": "db-primary", "metric_type": "error_rate_percent", "baseline": 0.01, "observed": 30.0, "deviation_percent": 2999900.0},
                {"service": "db-replica", "metric_type": "latency_p99_ms", "baseline": 10.0, "observed": 500.0, "deviation_percent": 4900.0},
                {"service": "user-svc", "metric_type": "error_rate_percent", "baseline": 0.1, "observed": 12.0, "deviation_percent": 11900.0},
                {"service": "notification-svc", "metric_type": "disk_utilization_percent", "baseline": 45.0, "observed": 85.0, "deviation_percent": 88.9},
                {"service": "api-gateway", "metric_type": "error_rate_percent", "baseline": 0.05, "observed": 8.0, "deviation_percent": 15900.0},
            ],
        )

    def get_change_profile(self) -> ChangeProfile:
        return ChangeProfile(
            root_cause_changes=[
                {"delay_hours": 72, "service": "db-primary", "change_type": "config_change", "description": "Logrotate config updated - removed compression and reduced retention from 30d to 7d by mistake", "author": "dba-intern"},
                {"delay_hours": 24, "service": "db-primary", "change_type": "config_change", "description": "MySQL slow_query_log enabled with file output instead of table", "author": "dba-team"},
            ],
            noise_changes=[
                {"delay_hours": 48, "service": "order-svc", "change_type": "deployment", "description": "order-svc v2.9.1 hotfix - null pointer fix", "author": "chen.hao"},
                {"delay_hours": 12, "service": "notification-svc", "change_type": "config_change", "description": "Email rate limit increased from 100/min to 500/min", "author": "wang.fang"},
            ],
        )
