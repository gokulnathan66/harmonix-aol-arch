import { useEffect, useRef, useState } from 'react';
import { useServiceStore } from '../store/serviceStore';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:50201/ws';
const POLL_INTERVAL = 5000; // Fallback polling interval in ms

export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const pollIntervalRef = useRef<number | null>(null);
  const { setServices, addEvent, addService, updateService, removeService } = useServiceStore();

  const connect = () => {
    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setError(null);
        console.log('WebSocket connected');
        
        // Clear polling if WebSocket is connected
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'initial_state') {
            setServices(data.services || []);
          } else if (data.type === 'event') {
            const eventData = data.data;
            addEvent(eventData);
            
            // Handle different event types
            if (eventData.event_type === 'service_registered') {
              // Fetch full service details
              fetch(`/api/services/${eventData.service_name}`)
                .then(res => res.json())
                .then(service => {
                  if (Array.isArray(service)) {
                    service.forEach(s => addService(s));
                  } else {
                    addService(service);
                  }
                })
                .catch(err => console.error('Error fetching service:', err));
            } else if (eventData.event_type === 'service_deregistered') {
              if (eventData.service_id) {
                removeService(eventData.service_id);
              }
            } else if (eventData.event_type === 'health_changed') {
              if (eventData.service_id && eventData.new_status) {
                updateService(eventData.service_id, { status: eventData.new_status });
              }
            }
          } else if (data.type === 'pong') {
            // Heartbeat response
          }
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };

      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        setError('WebSocket connection error');
      };

      ws.onclose = () => {
        setConnected(false);
        console.log('WebSocket disconnected');
        
        // Attempt to reconnect after 3 seconds
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 3000);
        
        // Fallback to polling
        startPolling();
      };
    } catch (err) {
      console.error('Error creating WebSocket:', err);
      setError('Failed to create WebSocket connection');
      startPolling();
    }
  };

  const startPolling = () => {
    if (pollIntervalRef.current) return;
    
    console.log('Starting polling fallback');
    pollIntervalRef.current = window.setInterval(async () => {
      try {
        const [servicesRes, eventsRes] = await Promise.all([
          fetch('/api/services'),
          fetch('/api/events?limit=50')
        ]);
        
        if (servicesRes.ok) {
          const services = await servicesRes.json();
          setServices(services);
        }
        
        if (eventsRes.ok) {
          const events = await eventsRes.json();
          events.forEach((event: any) => addEvent(event));
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    }, POLL_INTERVAL);
  };

  useEffect(() => {
    connect();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  return { connected, error };
}

