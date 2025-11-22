"""Prometheus metrics setup"""
from prometheus_client import start_http_server, Counter, Gauge, Histogram
import os

def setup_metrics(config):
    """Setup Prometheus metrics server"""
    metrics_port = config.get('spec', {}).get('monitoring', {}).get('metricsPort', 9090)
    start_http_server(metrics_port)
    return True


