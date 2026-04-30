from __future__ import annotations

from pydantic import BaseModel


class ServiceNode(BaseModel):
    name: str
    tier: int  # 0=frontend, 1=gateway, 2=middleware, 3=backend, 4=infra
    team: str
    tech_stack: list[str]


class ServiceEdge(BaseModel):
    source: str
    target: str
    protocol: str = "http"
    criticality: str = "normal"  # "critical" | "normal"


class ServiceTopology(BaseModel):
    nodes: list[ServiceNode]
    edges: list[ServiceEdge]

    def get_node(self, name: str) -> ServiceNode | None:
        for n in self.nodes:
            if n.name == name:
                return n
        return None

    def get_dependencies(self, service_name: str) -> list[str]:
        """Services that this service calls (downstream)."""
        return [e.target for e in self.edges if e.source == service_name]

    def get_dependents(self, service_name: str) -> list[str]:
        """Services that call this service (upstream)."""
        return [e.source for e in self.edges if e.target == service_name]

    def get_call_chain(self, source: str, target: str) -> list[str]:
        """BFS shortest path from source to target."""
        if source == target:
            return [source]
        visited = {source}
        queue = [[source]]
        while queue:
            path = queue.pop(0)
            current = path[-1]
            for dep in self.get_dependencies(current):
                if dep == target:
                    return path + [dep]
                if dep not in visited:
                    visited.add(dep)
                    queue.append(path + [dep])
        return []

    def get_upstream_cascade(self, service_name: str) -> list[str]:
        """All services that transitively depend on the given service."""
        result = []
        visited = set()
        queue = [service_name]
        while queue:
            current = queue.pop(0)
            for dep in self.get_dependents(current):
                if dep not in visited:
                    visited.add(dep)
                    result.append(dep)
                    queue.append(dep)
        return result

    def get_downstream_cascade(self, service_name: str) -> list[str]:
        """All services that the given service transitively depends on."""
        result = []
        visited = set()
        queue = [service_name]
        while queue:
            current = queue.pop(0)
            for dep in self.get_dependencies(current):
                if dep not in visited:
                    visited.add(dep)
                    result.append(dep)
                    queue.append(dep)
        return result

    def get_all_service_names(self) -> list[str]:
        return [n.name for n in self.nodes]

    def to_text(self) -> str:
        lines = ["Service Topology:"]
        for edge in self.edges:
            lines.append(
                f"  {edge.source} --[{edge.protocol}/{edge.criticality}]--> {edge.target}"
            )
        return "\n".join(lines)
