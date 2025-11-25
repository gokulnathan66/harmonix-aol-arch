"""Metrics Service API - Receives metrics from services"""
import logging
from aiohttp import web
from typing import Dict, Any, List
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from collections import defaultdict

logger = logging.getLogger(__name__)

class MetricsService:
    """Handles metrics ingestion and aggregation"""
    
    def __init__(self):
        self.metrics_store: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.prometheus_metrics: Dict[str, Any] = {}
    
    async def ingest_metric(self, service_name: str, metric_name: str, metric_type: str, value: float, labels: Dict[str, str] = None):
        """Ingest a metric from a service"""
        key = f"{service_name}_{metric_name}"
        
        if metric_type == 'counter':
            if key not in self.prometheus_metrics:
                self.prometheus_metrics[key] = Counter(
                    key,
                    f'Metric {metric_name} from {service_name}',
                    list(labels.keys()) if labels else []
                )
            
            if labels:
                self.prometheus_metrics[key].labels(**labels).inc(value)
            else:
                self.prometheus_metrics[key].inc(value)
        
        elif metric_type == 'gauge':
            if key not in self.prometheus_metrics:
                self.prometheus_metrics[key] = Gauge(
                    key,
                    f'Metric {metric_name} from {service_name}',
                    list(labels.keys()) if labels else []
                )
            
            if labels:
                self.prometheus_metrics[key].labels(**labels).set(value)
            else:
                self.prometheus_metrics[key].set(value)
        
        elif metric_type == 'histogram':
            if key not in self.prometheus_metrics:
                self.prometheus_metrics[key] = Histogram(
                    key,
                    f'Metric {metric_name} from {service_name}',
                    list(labels.keys()) if labels else []
                )
            
            if labels:
                self.prometheus_metrics[key].labels(**labels).observe(value)
            else:
                self.prometheus_metrics[key].observe(value)
        
        # Store raw metric
        self.metrics_store[service_name][metric_name] = {
            'value': value,
            'type': metric_type,
            'labels': labels or {}
        }
    
    def get_service_metrics(self, service_name: str) -> Dict[str, Any]:
        """Get metrics for a specific service"""
        return self.metrics_store.get(service_name, {})

def setup_metrics_service_api(app: web.Application, metrics_service: MetricsService):
    """Setup metrics service API endpoints"""
    
    async def ingest_metrics(request):
        """POST /api/metrics - Submit metrics"""
        try:
            data = await request.json()
            
            service_name = data.get('service_name')
            if not service_name:
                return web.json_response({'error': 'service_name is required'}, status=400)
            
            metrics = data.get('metrics', [])
            
            for metric in metrics:
                await metrics_service.ingest_metric(
                    service_name=service_name,
                    metric_name=metric.get('name'),
                    metric_type=metric.get('type', 'gauge'),
                    value=metric.get('value', 0),
                    labels=metric.get('labels', {})
                )
            
            return web.json_response({'success': True, 'ingested': len(metrics)})
        except Exception as e:
            logger.error(f"Error ingesting metrics: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_service_metrics(request):
        """GET /api/metrics/{service_name} - Get service metrics"""
        try:
            service_name = request.match_info['service_name']
            metrics = metrics_service.get_service_metrics(service_name)
            return web.json_response(metrics)
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_prometheus_metrics(request):
        """GET /api/metrics/prometheus - Get Prometheus format metrics"""
        try:
            return web.Response(
                body=generate_latest(),
                content_type=CONTENT_TYPE_LATEST
            )
        except Exception as e:
            logger.error(f"Error getting Prometheus metrics: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    # Register routes
    app.router.add_post('/api/metrics', ingest_metrics)
    app.router.add_get('/api/metrics/{service_name}', get_service_metrics)
    app.router.add_get('/api/metrics/prometheus', get_prometheus_metrics)


