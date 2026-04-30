from __future__ import annotations

import random
from datetime import datetime, timedelta

from models.alerts import Alert, AlertSeverity, AlertBatch
from models.topology import ServiceTopology
from simulation.scenarios.base_scenario import AlertStormProfile, BaseScenario


class AlertGenerator:
    def __init__(self, topology: ServiceTopology, scenario: BaseScenario):
        self.topology = topology
        self.scenario = scenario
        self._rng = random.Random(hash(scenario.scenario_id()))

    def generate_alert_storm(self) -> AlertBatch:
        profile = self.scenario.get_alert_profile()
        incident_ts = self.scenario.incident_timestamp()
        alerts: list[Alert] = []

        # Generate core alerts from the scenario
        for core in profile.core_alerts:
            ts = incident_ts + timedelta(seconds=core["delay_seconds"])
            alert = Alert(
                timestamp=ts,
                service_name=core["service"],
                alert_name=core["alert_name"],
                severity=AlertSeverity(core["severity"]),
                message=core["message"],
                labels={"env": "prod", "scenario": self.scenario.scenario_id()},
            )
            alerts.append(alert)

            # Add 3-6 duplicate/noise variants of each core alert
            for _ in range(self._rng.randint(3, 6)):
                dup_ts = ts + timedelta(seconds=self._rng.randint(-5, 30))
                dup = Alert(
                    timestamp=dup_ts,
                    service_name=core["service"],
                    alert_name=core["alert_name"],
                    severity=AlertSeverity(core["severity"]),
                    message=core["message"],
                    labels={"env": "prod", "scenario": self.scenario.scenario_id()},
                )
                alerts.append(dup)

        # Generate unrelated noise alerts from other services
        noise_names = [
            "CPUThreshold", "SlowQuery", "MemoryWarning",
            "DiskIORate", "PodRestarts", "HighThreadCount",
        ]
        for svc in profile.noise_services:
            for _ in range(self._rng.randint(1, 3)):
                ts = incident_ts + timedelta(seconds=self._rng.randint(0, 120))
                severity = self._rng.choice([AlertSeverity.LOW, AlertSeverity.INFO, AlertSeverity.MEDIUM])
                name = self._rng.choice(noise_names)
                alert = Alert(
                    timestamp=ts,
                    service_name=svc,
                    alert_name=name,
                    severity=severity,
                    message=f"{name} threshold triggered on {svc}",
                    labels={"env": "prod", "scenario": self.scenario.scenario_id()},
                )
                alerts.append(alert)

        # Sort by timestamp
        alerts.sort(key=lambda a: a.timestamp)

        window_start = min(a.timestamp for a in alerts)
        window_end = max(a.timestamp for a in alerts)

        return AlertBatch(alerts=alerts, window_start=window_start, window_end=window_end)
