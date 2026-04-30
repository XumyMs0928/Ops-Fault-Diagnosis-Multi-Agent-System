from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

from models.metrics import MetricDataPoint, MetricAnomaly, MetricType
from models.topology import ServiceTopology
from simulation.scenarios.base_scenario import BaseScenario


class MetricsGenerator:
    def __init__(self, topology: ServiceTopology, scenario: BaseScenario):
        self.topology = topology
        self.scenario = scenario
        self._rng = random.Random(hash(scenario.scenario_id()) + 2)

    def generate_metrics(self, time_range: tuple[datetime, datetime] | None = None) -> list[MetricDataPoint]:
        profile = self.scenario.get_metrics_profile()
        incident_ts = self.scenario.incident_timestamp()

        if time_range is None:
            time_range = (incident_ts - timedelta(minutes=10), incident_ts + timedelta(minutes=2))

        points: list[MetricDataPoint] = []
        interval = timedelta(seconds=30)

        # Baseline metrics for all services
        baseline_map = {
            "cpu_utilization_percent": 25.0,
            "memory_utilization_percent": 55.0,
            "latency_p99_ms": 40.0,
            "error_rate_percent": 0.05,
            "disk_utilization_percent": 50.0,
            "active_connections": 40.0,
        }

        # Build anomaly lookup: (service, metric) -> anomaly info
        anomaly_lookup: dict[tuple[str, str], dict] = {}
        for a in profile.anomalies:
            anomaly_lookup[(a["service"], a["metric_type"])] = a

        # Generate time series for each service
        for svc in self.topology.get_all_service_names():
            for metric_type in MetricType:
                key = (svc, metric_type.value)
                baseline = baseline_map.get(metric_type.value, 50.0)

                ts = time_range[0]
                while ts <= time_range[1]:
                    # Check if this is an anomaly point
                    anomaly_info = anomaly_lookup.get(key)
                    if anomaly_info and ts >= incident_ts:
                        # Ramp from baseline to observed value
                        progress = min((ts - incident_ts).total_seconds() / 60.0, 1.0)
                        value = baseline + progress * (anomaly_info["observed"] - baseline)
                        # Add some noise
                        value += self._rng.gauss(0, abs(anomaly_info["observed"] * 0.02))
                    else:
                        # Normal baseline with noise
                        noise_std = baseline * 0.05
                        value = baseline + self._rng.gauss(0, noise_std)

                    value = max(0.0, value)
                    if metric_type.value.endswith("_percent"):
                        value = min(100.0, value)

                    points.append(MetricDataPoint(
                        timestamp=ts,
                        service_name=svc,
                        metric_type=metric_type,
                        value=round(value, 2),
                    ))
                    ts += interval

        points.sort(key=lambda p: (p.timestamp, p.service_name, p.metric_type.value))
        return points

    def detect_anomalies(self) -> list[MetricAnomaly]:
        profile = self.scenario.get_metrics_profile()
        anomalies: list[MetricAnomaly] = []
        incident_ts = self.scenario.incident_timestamp()

        for a in profile.anomalies:
            anomalies.append(MetricAnomaly(
                service_name=a["service"],
                metric_type=MetricType(a["metric_type"]),
                observed_value=a["observed"],
                baseline_value=a["baseline"],
                deviation_percent=a["deviation_percent"],
                start_time=incident_ts,
                is_anomaly=True,
            ))

        return anomalies
