import { useEvents } from '../../hooks/useEvents';
import { useServiceStore } from '../../store/serviceStore';
import { Event } from '../../types';
import { Clock, Activity, XCircle, CheckCircle, Network } from 'lucide-react';

export default function TimelineView() {
  const { events } = useServiceStore();
  useEvents();

  const getEventIcon = (eventType: Event['event_type']) => {
    switch (eventType) {
      case 'service_registered':
        return <CheckCircle className="w-5 h-5 text-green-400" />;
      case 'service_deregistered':
        return <XCircle className="w-5 h-5 text-red-400" />;
      case 'health_changed':
        return <Activity className="w-5 h-5 text-amber-400" />;
      case 'route_called':
        return <Network className="w-5 h-5 text-blue-400" />;
      default:
        return <Clock className="w-5 h-5 text-slate-400" />;
    }
  };

  const getEventColor = (eventType: Event['event_type']) => {
    switch (eventType) {
      case 'service_registered':
        return 'border-green-500/50 bg-green-500/10';
      case 'service_deregistered':
        return 'border-red-500/50 bg-red-500/10';
      case 'health_changed':
        return 'border-amber-500/50 bg-amber-500/10';
      case 'route_called':
        return 'border-blue-500/50 bg-blue-500/10';
      default:
        return 'border-slate-500/50 bg-slate-500/10';
    }
  };

  const formatEventDescription = (event: Event) => {
    switch (event.event_type) {
      case 'service_registered':
        return `Service ${event.service_name} registered`;
      case 'service_deregistered':
        return `Service ${event.service_name} deregistered`;
      case 'health_changed':
        return `${event.service_name}: ${event.old_status} → ${event.new_status}`;
      case 'route_called':
        return `${event.source_service} → ${event.target_service} (${event.method || 'unknown'})`;
      default:
        return event.event_type;
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Event Timeline</h2>
        <p className="text-sm text-slate-400">{events.length} events</p>
      </div>

      <div className="space-y-2">
        {events.length === 0 ? (
          <div className="text-center py-12 text-slate-400">
            No events yet
          </div>
        ) : (
          events.map((event) => (
            <div
              key={event.event_id}
              className={`flex items-start gap-4 p-4 border rounded-lg ${getEventColor(event.event_type)}`}
            >
              <div className="mt-0.5">{getEventIcon(event.event_type)}</div>
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <div className="font-medium text-sm">{formatEventDescription(event)}</div>
                  <div className="text-xs text-slate-400">
                    {new Date(event.timestamp).toLocaleString()}
                  </div>
                </div>
                {event.event_type === 'route_called' && (
                  <div className="mt-2 text-xs text-slate-400">
                    Success: {event.success ? 'Yes' : 'No'}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

