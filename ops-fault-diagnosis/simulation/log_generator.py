from __future__ import annotations

import random
from datetime import datetime, timedelta

from models.logs import LogEntry, LogLevel
from models.topology import ServiceTopology
from simulation.scenarios.base_scenario import BaseScenario


class LogGenerator:
    def __init__(self, topology: ServiceTopology, scenario: BaseScenario):
        self.topology = topology
        self.scenario = scenario
        self._rng = random.Random(hash(scenario.scenario_id()) + 1)

    def generate_logs(self, time_range: tuple[datetime, datetime] | None = None) -> list[LogEntry]:
        profile = self.scenario.get_log_profile()
        incident_ts = self.scenario.incident_timestamp()
        entries: list[LogEntry] = []

        if time_range is None:
            time_range = (incident_ts - timedelta(minutes=5), incident_ts + timedelta(minutes=5))

        # Generate fault-specific logs
        for fault in profile.fault_logs:
            ts = incident_ts + timedelta(seconds=fault["delay_seconds"])
            entry = LogEntry(
                timestamp=ts,
                service_name=fault["service"],
                level=LogLevel[fault["level"]],
                message=fault["message"],
                trace_id=f"trace-{self._rng.randint(10000, 99999)}",
                span_id=f"span-{self._rng.randint(1000, 9999)}",
                exception_class=fault.get("exception_class"),
                stack_trace=fault.get("stack_trace"),
            )
            entries.append(entry)

        # Generate normal noise logs
        noise_messages = [
            ("INFO", "Request processed successfully in {ms}ms"),
            ("INFO", "Health check passed"),
            ("INFO", "Cache hit ratio: {pct}%"),
            ("DEBUG", "Processing batch item {n}"),
            ("INFO", "Connection pool stats: active={a}, idle={i}"),
            ("INFO", "Scheduled task completed: {task}"),
            ("WARN", "Slow query detected: {ms}ms"),
            ("INFO", "GC pause: {ms}ms"),
        ]
        all_services = self.topology.get_all_service_names()
        total_noise = int(len(profile.fault_logs) * profile.noise_ratio * 3)

        for _ in range(total_noise):
            ts = self._rng.uniform(time_range[0].timestamp(), time_range[1].timestamp())
            ts = datetime.fromtimestamp(ts)
            svc = self._rng.choice(all_services)
            tmpl_level, tmpl_msg = self._rng.choice(noise_messages)
            msg = tmpl_msg.format(
                ms=self._rng.randint(5, 200),
                pct=self._rng.randint(80, 99),
                n=self._rng.randint(1, 1000),
                a=self._rng.randint(1, 20),
                i=self._rng.randint(5, 30),
                task=self._rng.choice(["cleanup", "sync", "refresh", "aggregate"]),
            )
            entry = LogEntry(
                timestamp=ts,
                service_name=svc,
                level=LogLevel[tmpl_level],
                message=msg,
            )
            entries.append(entry)

        entries.sort(key=lambda e: e.timestamp)
        return entries
