from __future__ import annotations

import random
from datetime import datetime, timedelta

from models.changes import ChangeRecord, ChangeType
from models.topology import ServiceTopology
from simulation.scenarios.base_scenario import BaseScenario


class ChangeGenerator:
    def __init__(self, topology: ServiceTopology, scenario: BaseScenario):
        self.topology = topology
        self.scenario = scenario
        self._rng = random.Random(hash(scenario.scenario_id()) + 3)

    def generate_changes(self) -> list[ChangeRecord]:
        profile = self.scenario.get_change_profile()
        incident_ts = self.scenario.incident_timestamp()
        changes: list[ChangeRecord] = []

        # Root cause changes
        for c in profile.root_cause_changes:
            ts = incident_ts - timedelta(hours=c["delay_hours"])
            changes.append(ChangeRecord(
                timestamp=ts,
                service_name=c["service"],
                change_type=ChangeType(c["change_type"]),
                description=c["description"],
                author=c["author"],
                rollback_possible=True,
            ))

        # Noise changes
        for c in profile.noise_changes:
            ts = incident_ts - timedelta(hours=c["delay_hours"])
            changes.append(ChangeRecord(
                timestamp=ts,
                service_name=c["service"],
                change_type=ChangeType(c["change_type"]),
                description=c["description"],
                author=c["author"],
                rollback_possible=self._rng.choice([True, False]),
            ))

        changes.sort(key=lambda c: c.timestamp)
        return changes
