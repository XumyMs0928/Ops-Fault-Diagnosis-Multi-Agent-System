from __future__ import annotations

from models.topology import ServiceNode, ServiceEdge, ServiceTopology


def build_topology() -> ServiceTopology:
    """Build a typical e-commerce microservice topology with 10 services."""
    nodes = [
        ServiceNode(name="web-frontend", tier=0, team="frontend", tech_stack=["react", "next.js"]),
        ServiceNode(name="api-gateway", tier=1, team="platform", tech_stack=["go", "grpc-gateway"]),
        ServiceNode(name="user-svc", tier=2, team="user", tech_stack=["java", "spring-boot", "mysql"]),
        ServiceNode(name="order-svc", tier=2, team="order", tech_stack=["java", "spring-boot", "redis"]),
        ServiceNode(name="product-svc", tier=2, team="product", tech_stack=["python", "fastapi", "elasticsearch"]),
        ServiceNode(name="payment-svc", tier=3, team="payment", tech_stack=["java", "spring-boot", "hikaricp"]),
        ServiceNode(name="inventory-svc", tier=3, team="inventory", tech_stack=["python", "fastapi", "redis"]),
        ServiceNode(name="notification-svc", tier=3, team="platform", tech_stack=["node", "express", "rabbitmq"]),
        ServiceNode(name="db-primary", tier=4, team="dba", tech_stack=["mysql", "8.0"]),
        ServiceNode(name="db-replica", tier=4, team="dba", tech_stack=["mysql", "8.0"]),
    ]

    edges = [
        ServiceEdge(source="web-frontend", target="api-gateway", protocol="https", criticality="critical"),
        ServiceEdge(source="api-gateway", target="user-svc", protocol="grpc", criticality="normal"),
        ServiceEdge(source="api-gateway", target="order-svc", protocol="grpc", criticality="critical"),
        ServiceEdge(source="api-gateway", target="product-svc", protocol="http", criticality="normal"),
        ServiceEdge(source="order-svc", target="payment-svc", protocol="grpc", criticality="critical"),
        ServiceEdge(source="order-svc", target="inventory-svc", protocol="http", criticality="normal"),
        ServiceEdge(source="payment-svc", target="db-primary", protocol="tcp", criticality="critical"),
        ServiceEdge(source="user-svc", target="db-replica", protocol="tcp", criticality="normal"),
        ServiceEdge(source="user-svc", target="notification-svc", protocol="amqp", criticality="normal"),
        ServiceEdge(source="db-primary", target="db-replica", protocol="mysql-repl", criticality="critical"),
        ServiceEdge(source="product-svc", target="inventory-svc", protocol="http", criticality="normal"),
    ]

    return ServiceTopology(nodes=nodes, edges=edges)
