"""Enhanced Monitoring API for AOL Core with Galileo-Style Observability

This module provides comprehensive monitoring including:
- Real-time service status via WebSocket
- Agent performance dashboards
- Workflow timeline views
- Failure analysis graphs
- Credit assignment metrics
- Anomaly detection alerts

Based on: "Galileo-style graph/timeline views that catch 80% of deviations" (2025)
"""
import json
import logging
import uuid
from typing import Dict, List, Optional
from aiohttp import web, WSMsgType
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


def setup_monitor_api(app: web.Application, registry, event_store):
    """Setup enhanced monitoring API routes"""
    
    # CORS middleware
    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == 'OPTIONS':
            return web.Response(
                headers={
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type',
                }
            )
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    
    app.middlewares.append(cors_middleware)
    
    # WebSocket connections
    ws_connections = []
    alert_subscribers = []  # Separate list for alert-only subscribers
    
    async def broadcast_event(event_dict, event_type="event"):
        """Broadcast event to all WebSocket connections"""
        message = json.dumps({
            'type': event_type,
            'data': event_dict,
            'timestamp': datetime.utcnow().isoformat()
        })
        disconnected = []
        for ws in ws_connections:
            try:
                await ws.send_str(message)
            except Exception:
                disconnected.append(ws)
        
        for ws in disconnected:
            ws_connections.remove(ws)
    
    async def broadcast_alert(alert_data):
        """Broadcast alert to alert subscribers"""
        message = json.dumps({
            'type': 'alert',
            'data': alert_data,
            'timestamp': datetime.utcnow().isoformat()
        })
        disconnected = []
        for ws in alert_subscribers:
            try:
                await ws.send_str(message)
            except Exception:
                disconnected.append(ws)
        
        for ws in disconnected:
            alert_subscribers.remove(ws)
    
    # Override add_event to broadcast events via WebSocket
    original_add_event = event_store.add_event
    
    async def new_add_event(event):
        await original_add_event(event)
        try:
            event_dict = event.__dict__.copy()
            event_dict['event_type'] = event_dict['event_type'].value if hasattr(event_dict['event_type'], 'value') else str(event_dict['event_type'])
            event_dict['timestamp'] = event_dict['timestamp'].isoformat() if hasattr(event_dict['timestamp'], 'isoformat') else str(event_dict['timestamp'])
            await broadcast_event(event_dict)
            
            # Check for alert conditions
            if event_dict['event_type'] in ['agent_lazy_detected', 'workflow_failed', 'health_changed']:
                if event_dict.get('new_status') == 'unhealthy' or event_dict['event_type'] != 'health_changed':
                    await broadcast_alert({
                        'alert_type': event_dict['event_type'],
                        'service': event_dict.get('service_name'),
                        'details': event_dict
                    })
        except Exception as e:
            logger.error(f"Error broadcasting event: {e}", exc_info=True)
    
    event_store.add_event = new_add_event
    
    # ==========================================================================
    # REST API Routes - Service Management
    # ==========================================================================
    
    async def get_services(request):
        """GET /api/services - List all registered services with enhanced metadata"""
        try:
            services = await registry.list_services()
            result = []
            
            for service_name, instances in services.items():
                for instance in instances:
                    # Get agent metrics if available
                    agent_report = {}
                    try:
                        agent_report = await event_store.get_agent_report(instance.service_id)
                    except Exception:
                        pass
                    
                    result.append({
                        'name': instance.name,
                        'version': instance.version,
                        'host': instance.host,
                        'grpc_port': instance.grpc_port,
                        'health_port': instance.health_port,
                        'metrics_port': instance.metrics_port,
                        'status': instance.status,
                        'service_id': instance.service_id,
                        'registered_at': instance.last_heartbeat.isoformat(),
                        'manifest': instance.manifest,
                        # Enhanced: agent performance metrics
                        'performance': {
                            'total_contributions': agent_report.get('total_contributions', 0),
                            'success_rate': agent_report.get('success_rate', 0),
                            'avg_influence': agent_report.get('average_influence_per_contribution', 0),
                            'lazy_flags': agent_report.get('lazy_flags', 0)
                        }
                    })
            
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Error getting services: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_service(request):
        """GET /api/services/{name} - Get specific service details with metrics"""
        try:
            service_name = request.match_info['name']
            services = await registry.list_services()
            
            if service_name not in services:
                return web.json_response({'error': 'Service not found'}, status=404)
            
            instances = services[service_name]
            result = []
            
            for instance in instances:
                agent_report = {}
                try:
                    agent_report = await event_store.get_agent_report(instance.service_id)
                except Exception:
                    pass
                
                result.append({
                    'name': instance.name,
                    'version': instance.version,
                    'host': instance.host,
                    'grpc_port': instance.grpc_port,
                    'health_port': instance.health_port,
                    'metrics_port': instance.metrics_port,
                    'status': instance.status,
                    'service_id': instance.service_id,
                    'registered_at': instance.last_heartbeat.isoformat(),
                    'manifest': instance.manifest,
                    'performance': agent_report
                })
            
            return web.json_response(result if len(result) > 1 else result[0])
        except Exception as e:
            logger.error(f"Error getting service: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_registry_stats(request):
        """GET /api/registry/stats - Get comprehensive registry statistics"""
        try:
            services = await registry.list_services()
            event_stats = await event_store.get_stats()
            
            stats = {
                'total_services': sum(len(instances) for instances in services.values()),
                'unique_services': len(services),
                'by_status': {},
                'by_type': {},
                # Enhanced: Include event store stats
                'events': event_stats,
                # Enhanced: System health indicators
                'system_health': {
                    'healthy_services': 0,
                    'unhealthy_services': 0,
                    'lazy_agents': event_stats.get('lazy_agent_flags', 0),
                    'active_workflows': event_stats.get('active_workflows', 0),
                    'completed_workflows': event_stats.get('completed_workflows', 0),
                    'failed_workflows': event_stats.get('failed_workflows', 0)
                }
            }
            
            for service_name, instances in services.items():
                for instance in instances:
                    # Count by status
                    status = instance.status
                    stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
                    
                    if status == 'healthy':
                        stats['system_health']['healthy_services'] += 1
                    else:
                        stats['system_health']['unhealthy_services'] += 1
                    
                    # Count by type
                    service_type = instance.manifest.get('metadata', {}).get('labels', {}).get('aol.service.type', 'unknown')
                    stats['by_type'][service_type] = stats['by_type'].get(service_type, 0) + 1
            
            # Calculate health score
            total = stats['system_health']['healthy_services'] + stats['system_health']['unhealthy_services']
            stats['system_health']['health_score'] = (
                stats['system_health']['healthy_services'] / max(total, 1)
            )
            
            return web.json_response(stats)
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    # ==========================================================================
    # REST API Routes - Events & Routes
    # ==========================================================================
    
    async def get_events(request):
        """GET /api/events - Get historical events with filtering"""
        try:
            event_type = request.query.get('type')
            service_name = request.query.get('service')
            workflow_id = request.query.get('workflow')
            limit = int(request.query.get('limit', 100))
            
            from event_store import EventType
            
            filter_type = None
            if event_type:
                try:
                    filter_type = EventType(event_type)
                except ValueError:
                    pass
            
            events = await event_store.get_events(
                event_type=filter_type,
                service_name=service_name,
                workflow_id=workflow_id,
                limit=limit
            )
            
            result = [event.to_dict() for event in events]
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Error getting events: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_routes(request):
        """GET /api/routes - Get communication flow data"""
        try:
            source_service = request.query.get('source')
            target_service = request.query.get('target')
            limit = int(request.query.get('limit', 100))
            
            events = await event_store.get_route_events(
                source_service=source_service,
                target_service=target_service,
                limit=limit
            )
            
            # Aggregate route data
            route_map = {}
            for event in events:
                key = f"{event.source_service}->{event.target_service}"
                if key not in route_map:
                    route_map[key] = {
                        'source': event.source_service,
                        'target': event.target_service,
                        'count': 0,
                        'success_count': 0,
                        'failure_count': 0,
                        'methods': set(),
                        'total_latency_ms': 0
                    }
                
                route_map[key]['count'] += 1
                if event.success:
                    route_map[key]['success_count'] += 1
                else:
                    route_map[key]['failure_count'] += 1
                
                if event.method:
                    route_map[key]['methods'].add(event.method)
                
                # Track latency from metadata
                if event.metadata and 'latency_ms' in event.metadata:
                    route_map[key]['total_latency_ms'] += event.metadata['latency_ms']
            
            # Convert sets to lists and calculate averages
            result = []
            for route_data in route_map.values():
                route_data['methods'] = list(route_data['methods'])
                route_data['avg_latency_ms'] = (
                    route_data['total_latency_ms'] / max(route_data['count'], 1)
                )
                route_data['success_rate'] = (
                    route_data['success_count'] / max(route_data['count'], 1)
                )
                result.append(route_data)
            
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Error getting routes: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    # ==========================================================================
    # REST API Routes - Agent Performance (Galileo-Style)
    # ==========================================================================
    
    async def get_agent_report(request):
        """GET /api/agents/{id}/report - Get detailed agent performance report"""
        try:
            agent_id = request.match_info['id']
            report = await event_store.get_agent_report(agent_id)
            return web.json_response(report)
        except Exception as e:
            logger.error(f"Error getting agent report: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_all_agents(request):
        """GET /api/agents - Get all agents with performance metrics"""
        try:
            services = await registry.list_services()
            agents = []
            
            for service_name, instances in services.items():
                for instance in instances:
                    report = {}
                    try:
                        report = await event_store.get_agent_report(instance.service_id)
                    except Exception:
                        pass
                    
                    agents.append({
                        'agent_id': instance.service_id,
                        'name': instance.name,
                        'status': instance.status,
                        'type': instance.manifest.get('kind', 'unknown'),
                        **report
                    })
            
            return web.json_response(agents)
        except Exception as e:
            logger.error(f"Error getting agents: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_lazy_agents(request):
        """GET /api/agents/lazy - Get currently flagged lazy agents"""
        try:
            threshold = float(request.query.get('threshold', 0.1))
            
            # Get all agents and filter lazy ones
            services = await registry.list_services()
            lazy_agents = []
            
            for service_name, instances in services.items():
                for instance in instances:
                    report = await event_store.get_agent_report(instance.service_id)
                    if report.get('lazy_flags', 0) > 0:
                        lazy_agents.append({
                            'agent_id': instance.service_id,
                            'name': instance.name,
                            'lazy_flags': report.get('lazy_flags', 0),
                            'avg_influence': report.get('average_influence_per_contribution', 0),
                            'success_rate': report.get('success_rate', 0)
                        })
            
            return web.json_response(lazy_agents)
        except Exception as e:
            logger.error(f"Error getting lazy agents: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    # ==========================================================================
    # REST API Routes - Workflow Monitoring
    # ==========================================================================
    
    async def get_workflows(request):
        """GET /api/workflows - Get all workflows with status"""
        try:
            workflows = []
            for workflow_id, workflow_data in event_store.active_workflows.items():
                report = await event_store.get_workflow_report(workflow_id)
                workflows.append(report)
            
            return web.json_response(workflows)
        except Exception as e:
            logger.error(f"Error getting workflows: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_workflow_report(request):
        """GET /api/workflows/{id}/report - Get detailed workflow report"""
        try:
            workflow_id = request.match_info['id']
            report = await event_store.get_workflow_report(workflow_id)
            return web.json_response(report)
        except Exception as e:
            logger.error(f"Error getting workflow report: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_workflow_timeline(request):
        """GET /api/workflows/{id}/timeline - Get Galileo-style timeline view"""
        try:
            workflow_id = request.match_info['id']
            
            # Get all events for this workflow
            events = await event_store.get_events(workflow_id=workflow_id, limit=1000)
            
            # Build timeline
            timeline = []
            for event in events:
                timeline.append({
                    'timestamp': event.timestamp.isoformat(),
                    'event_type': event.event_type.value,
                    'agent': event.service_name,
                    'success': event.success,
                    'contribution_score': event.contribution_score,
                    'metadata': event.metadata
                })
            
            # Sort by timestamp
            timeline.sort(key=lambda x: x['timestamp'])
            
            return web.json_response({
                'workflow_id': workflow_id,
                'timeline': timeline,
                'total_events': len(timeline)
            })
        except Exception as e:
            logger.error(f"Error getting workflow timeline: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    # ==========================================================================
    # REST API Routes - Failure Analysis (Galileo Insights Engine)
    # ==========================================================================
    
    async def get_failure_analysis(request):
        """GET /api/analysis/failures - Get failure analysis report"""
        try:
            hours = int(request.query.get('hours', 24))
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            
            # Get failure events
            from event_store import EventType
            
            failure_events = []
            for event in event_store.events:
                if event.timestamp >= cutoff:
                    if not event.success or event.event_type in [
                        EventType.WORKFLOW_FAILED,
                        EventType.AGENT_LAZY_DETECTED,
                        EventType.DELIBERATION_RESTARTED
                    ]:
                        failure_events.append(event)
            
            # Analyze failures by type
            by_type = defaultdict(int)
            by_agent = defaultdict(int)
            by_workflow = defaultdict(int)
            
            for event in failure_events:
                by_type[event.event_type.value] += 1
                if event.service_name:
                    by_agent[event.service_name] += 1
                if event.workflow_id:
                    by_workflow[event.workflow_id] += 1
            
            # Find most problematic agents
            problematic_agents = sorted(
                by_agent.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            return web.json_response({
                'period_hours': hours,
                'total_failures': len(failure_events),
                'by_type': dict(by_type),
                'by_agent': dict(by_agent),
                'by_workflow': dict(by_workflow),
                'problematic_agents': [
                    {'agent': a[0], 'failure_count': a[1]}
                    for a in problematic_agents
                ],
                'failure_rate': len(failure_events) / max(len(event_store.events), 1)
            })
        except Exception as e:
            logger.error(f"Error getting failure analysis: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_insights(request):
        """GET /api/analysis/insights - Get automated insights (Galileo Insights Engine)"""
        try:
            insights = []
            stats = await event_store.get_stats()
            
            # Check for lazy agent issues
            if stats.get('lazy_agent_flags', 0) > 5:
                insights.append({
                    'severity': 'warning',
                    'type': 'lazy_agents',
                    'message': f"Multiple lazy agents detected ({stats['lazy_agent_flags']} flags). Consider reviewing agent configurations.",
                    'recommendation': 'Review agent contribution thresholds and consider enabling auto-recovery.'
                })
            
            # Check for workflow failures
            failed = stats.get('failed_workflows', 0)
            completed = stats.get('completed_workflows', 0)
            if completed > 0 and (failed / (failed + completed)) > 0.2:
                insights.append({
                    'severity': 'critical',
                    'type': 'high_failure_rate',
                    'message': f"High workflow failure rate: {failed}/{failed + completed} ({failed/(failed+completed)*100:.1f}%)",
                    'recommendation': 'Review workflow configurations and check for resource constraints.'
                })
            
            # Check for performance degradation
            services = await registry.list_services()
            unhealthy_count = 0
            for instances in services.values():
                for instance in instances:
                    if instance.status != 'healthy':
                        unhealthy_count += 1
            
            total_services = sum(len(i) for i in services.values())
            if total_services > 0 and (unhealthy_count / total_services) > 0.1:
                insights.append({
                    'severity': 'warning',
                    'type': 'service_health',
                    'message': f"{unhealthy_count}/{total_services} services are unhealthy.",
                    'recommendation': 'Check service logs and resource availability.'
                })
            
            # Check for event store pressure
            if stats.get('total_events', 0) > 900:
                insights.append({
                    'severity': 'info',
                    'type': 'event_store_pressure',
                    'message': 'Event store approaching capacity limit.',
                    'recommendation': 'Consider enabling external event storage (Redis/Kafka).'
                })
            
            return web.json_response({
                'generated_at': datetime.utcnow().isoformat(),
                'insights': insights,
                'system_health_score': stats.get('lazy_agent_flags', 0) == 0 and unhealthy_count == 0
            })
        except Exception as e:
            logger.error(f"Error getting insights: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    # ==========================================================================
    # WebSocket Handlers
    # ==========================================================================
    
    async def websocket_handler(request):
        """WebSocket handler for real-time updates"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        ws_connections.append(ws)
        logger.info(f"WebSocket client connected. Total connections: {len(ws_connections)}")
        
        # Send initial state
        try:
            services = await registry.list_services()
            stats = await event_store.get_stats()
            
            initial_data = {
                'type': 'initial_state',
                'services': [],
                'stats': stats
            }
            
            for service_name, instances in services.items():
                for instance in instances:
                    initial_data['services'].append({
                        'name': instance.name,
                        'version': instance.version,
                        'host': instance.host,
                        'grpc_port': instance.grpc_port,
                        'status': instance.status,
                        'service_id': instance.service_id
                    })
            
            await ws.send_str(json.dumps(initial_data))
        except Exception as e:
            logger.error(f"Error sending initial state: {e}")
        
        # Keep connection alive and handle messages
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    msg_type = data.get('type')
                    
                    if msg_type == 'ping':
                        await ws.send_str(json.dumps({'type': 'pong'}))
                    
                    elif msg_type == 'subscribe_alerts':
                        if ws not in alert_subscribers:
                            alert_subscribers.append(ws)
                        await ws.send_str(json.dumps({
                            'type': 'subscribed',
                            'channel': 'alerts'
                        }))
                    
                    elif msg_type == 'get_stats':
                        stats = await event_store.get_stats()
                        await ws.send_str(json.dumps({
                            'type': 'stats',
                            'data': stats
                        }))
                    
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
                    break
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            if ws in ws_connections:
                ws_connections.remove(ws)
            if ws in alert_subscribers:
                alert_subscribers.remove(ws)
            logger.info(f"WebSocket client disconnected. Total connections: {len(ws_connections)}")
        
        return ws
    
    # ==========================================================================
    # Register Routes
    # ==========================================================================
    
    # Service routes
    app.router.add_get('/api/services', get_services)
    app.router.add_get('/api/services/{name}', get_service)
    app.router.add_get('/api/registry/stats', get_registry_stats)
    
    # Event routes
    app.router.add_get('/api/events', get_events)
    app.router.add_get('/api/routes', get_routes)
    
    # Agent routes (Galileo-style)
    app.router.add_get('/api/agents', get_all_agents)
    app.router.add_get('/api/agents/lazy', get_lazy_agents)
    app.router.add_get('/api/agents/{id}/report', get_agent_report)
    
    # Workflow routes
    app.router.add_get('/api/workflows', get_workflows)
    app.router.add_get('/api/workflows/{id}/report', get_workflow_report)
    app.router.add_get('/api/workflows/{id}/timeline', get_workflow_timeline)
    
    # Analysis routes (Insights Engine)
    app.router.add_get('/api/analysis/failures', get_failure_analysis)
    app.router.add_get('/api/analysis/insights', get_insights)
    
    # WebSocket
    app.router.add_get('/ws', websocket_handler)
