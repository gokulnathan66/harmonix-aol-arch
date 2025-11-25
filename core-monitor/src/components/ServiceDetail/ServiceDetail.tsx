import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useServiceStore } from '../../store/serviceStore';
import { Service, Event } from '../../types';
import { ArrowLeft, Activity } from 'lucide-react';

export default function ServiceDetail() {
  const { serviceId } = useParams<{ serviceId: string }>();
  const navigate = useNavigate();
  const { services, events } = useServiceStore();
  const [service, setService] = useState<Service | null>(null);
  const [serviceEvents, setServiceEvents] = useState<Event[]>([]);

  useEffect(() => {
    if (serviceId) {
      const found = services.find(s => s.service_id === serviceId);
      if (found) {
        setService(found);
        // Filter events for this service
        const filtered = events.filter(
          e => e.service_id === serviceId || e.service_name === found.name
        );
        setServiceEvents(filtered);
      } else {
        // Try to fetch from API
        fetch(`/api/services/${serviceId}`)
          .then(res => res.json())
          .then(data => {
            if (Array.isArray(data) && data.length > 0) {
              setService(data[0]);
            }
          })
          .catch(err => console.error('Error fetching service:', err));
      }
    }
  }, [serviceId, services, events]);

  if (!service) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-400">Service not found</p>
        <button
          onClick={() => navigate('/list')}
          className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded transition-colors"
        >
          Back to List
        </button>
      </div>
    );
  }

  const getStatusBadge = (status: string) => {
    const colors = {
      healthy: 'bg-green-500/20 text-green-400 border-green-500/50',
      unhealthy: 'bg-red-500/20 text-red-400 border-red-500/50',
      starting: 'bg-amber-500/20 text-amber-400 border-amber-500/50',
    };
    return colors[status as keyof typeof colors] || colors.healthy;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/list')}
          className="p-2 hover:bg-slate-700 rounded transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h2 className="text-2xl font-semibold">{service.name}</h2>
          <p className="text-sm text-slate-400">Version {service.version}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 space-y-4">
          <h3 className="text-lg font-semibold">Service Information</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">Status:</span>
              <span className={`px-2 py-1 rounded border ${getStatusBadge(service.status)}`}>
                {service.status}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Host:</span>
              <span className="text-slate-200">{service.host}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Service ID:</span>
              <span className="text-slate-200 font-mono text-xs">{service.service_id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Registered:</span>
              <span className="text-slate-200">
                {new Date(service.registered_at).toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 space-y-4">
          <h3 className="text-lg font-semibold">Endpoints</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">gRPC:</span>
              <span className="text-slate-200 font-mono">{service.grpc_port}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Health:</span>
              <span className="text-slate-200 font-mono">{service.health_port}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Metrics:</span>
              <span className="text-slate-200 font-mono">{service.metrics_port}</span>
            </div>
            {service.manifest.spec.endpoints.sidecar && (
              <div className="flex justify-between">
                <span className="text-slate-400">Sidecar:</span>
                <span className="text-slate-200 font-mono">
                  {service.manifest.spec.endpoints.sidecar}
                </span>
              </div>
            )}
          </div>
        </div>

        <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 space-y-4">
          <h3 className="text-lg font-semibold">Manifest</h3>
          <pre className="text-xs bg-slate-900 p-4 rounded overflow-auto max-h-96">
            {JSON.stringify(service.manifest, null, 2)}
          </pre>
        </div>

        <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 space-y-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Activity className="w-5 h-5" />
            Recent Events ({serviceEvents.length})
          </h3>
          <div className="space-y-2 max-h-96 overflow-auto">
            {serviceEvents.length === 0 ? (
              <p className="text-sm text-slate-400">No events</p>
            ) : (
              serviceEvents.slice(0, 20).map((event) => (
                <div
                  key={event.event_id}
                  className="p-3 bg-slate-900 rounded text-sm border border-slate-700"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-medium">{event.event_type}</div>
                      {event.event_type === 'health_changed' && (
                        <div className="text-xs text-slate-400 mt-1">
                          {event.old_status} → {event.new_status}
                        </div>
                      )}
                      {event.event_type === 'route_called' && (
                        <div className="text-xs text-slate-400 mt-1">
                          {event.source_service} → {event.target_service}
                        </div>
                      )}
                    </div>
                    <div className="text-xs text-slate-400">
                      {new Date(event.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

