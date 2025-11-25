import { Service, RouteData, GraphNode, GraphLink } from '../types';
import * as d3 from 'd3';

export function buildGraphData(services: Service[], routes: RouteData[]): {
  nodes: GraphNode[];
  links: GraphLink[];
} {
  // Create nodes from services with defensive checks
  const nodes: GraphNode[] = services
    .filter(service => service && service.service_id) // Filter out invalid services
    .map(service => {
      // Safely extract service type with fallbacks
      const serviceType = service?.manifest?.metadata?.labels?.['aol.service.type'] 
        || service?.manifest?.kind 
        || 'unknown';
      
      return {
        id: service.service_id,
        name: service.name || 'unknown',
        type: serviceType,
        status: service.status || 'starting',
      };
    });

  // Create links from routes
  const routeMap = new Map<string, RouteData>();
  routes.forEach(route => {
    const key = `${route.source}->${route.target}`;
    routeMap.set(key, route);
  });

  const links: GraphLink[] = [];
  const nodeMap = new Map(nodes.map(n => [n.name, n]));

  routes.forEach(route => {
    const sourceNode = nodeMap.get(route.source);
    const targetNode = nodeMap.get(route.target);

    if (sourceNode && targetNode) {
      links.push({
        source: sourceNode.id,
        target: targetNode.id,
        count: route.count,
        success_rate: route.count > 0 ? route.success_count / route.count : 0,
      });
    }
  });

  return { nodes, links };
}

export function createForceSimulation(
  nodes: GraphNode[],
  links: GraphLink[],
  width: number,
  height: number
) {
  const simulation = d3.forceSimulation(nodes as any)
    .force('link', d3.forceLink(links).id((d: any) => d.id).distance(100))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(30));

  return simulation;
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'healthy':
      return '#10b981'; // green
    case 'unhealthy':
      return '#ef4444'; // red
    case 'starting':
      return '#f59e0b'; // amber
    default:
      return '#6b7280'; // gray
  }
}

export function getTypeColor(type: string): string {
  const colors: Record<string, string> = {
    'orchestrator': '#3b82f6', // blue
    'agent': '#8b5cf6', // purple
    'plugin': '#ec4899', // pink
    'core': '#f59e0b', // amber
  };
  return colors[type] || '#6b7280';
}

