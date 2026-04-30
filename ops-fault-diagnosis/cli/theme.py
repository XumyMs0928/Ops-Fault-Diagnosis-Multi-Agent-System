from __future__ import annotations

AGENT_STYLES = {
    "alert-aggregation": {
        "avatar": "\U0001f50d",
        "name": "Alert Aggregation",
        "color": "cyan",
    },
    "root-cause": {
        "avatar": "\U0001f3af",
        "name": "Root Cause",
        "color": "red",
    },
    "fix-suggestion": {
        "avatar": "\U0001f527",
        "name": "Fix Suggestion",
        "color": "green",
    },
    "post-incident": {
        "avatar": "\U0001f4cb",
        "name": "Post-Incident",
        "color": "yellow",
    },
}

PHASE_STYLES = {
    "alert_ingestion": {"label": "PHASE 1", "emoji": "\U0001f50d", "color": "cyan"},
    "root_cause":      {"label": "PHASE 2", "emoji": "\U0001f3af", "color": "red"},
    "fix":             {"label": "PHASE 3", "emoji": "\U0001f527", "color": "green"},
    "review":          {"label": "PHASE 4", "emoji": "\U0001f4cb", "color": "yellow"},
}

SCENARIO_INFO = {
    "1": {
        "name": "Database Connection Pool Exhaustion Cascade",
        "desc": "payment-svc connection leak + db-primary pool reduction",
    },
    "2": {
        "name": "Memory Leak OOM Kill Cascade",
        "desc": "order-svc cache memory leak causing OOM kills",
    },
    "3": {
        "name": "Disk Full Cascade",
        "desc": "db-primary log rotation misconfigure causing disk full",
    },
}
