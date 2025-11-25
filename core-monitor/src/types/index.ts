export interface Service {
  name: string;
  version: string;
  host: string;
  grpc_port: number;
  health_port: number;
  metrics_port: number;
  status: 'healthy' | 'unhealthy' | 'starting';
  service_id: string;
  registered_at: string;
  manifest: {
    kind: string;
    apiVersion: string;
    metadata: {
      name: string;
      version: string;
      labels: Record<string, string>;
    };
    spec: {
      endpoints: {
        grpc: number;
        sidecar?: number;
        health: number;
        metrics: number;
      };
      dependencies?: Array<{
        service: string;
        optional: boolean;
      }>;
    };
  };
}

export interface Event {
  event_id: string;
  event_type: 'service_registered' | 'service_deregistered' | 'health_changed' | 'route_called' | 'service_discovered';
  timestamp: string;
  service_name?: string;
  service_id?: string;
  source_service?: string;
  target_service?: string;
  method?: string;
  success?: boolean;
  old_status?: string;
  new_status?: string;
  metadata?: Record<string, any>;
}

export interface RouteData {
  source: string;
  target: string;
  count: number;
  success_count: number;
  failure_count: number;
  methods: string[];
}

export interface RegistryStats {
  total_services: number;
  unique_services: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
}

export interface GraphNode {
  id: string;
  name: string;
  type: string;
  status: string;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
  vx?: number;
  vy?: number;
}

export interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  count: number;
  success_rate: number;
}

