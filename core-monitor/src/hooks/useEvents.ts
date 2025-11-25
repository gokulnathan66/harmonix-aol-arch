import { useEffect } from 'react';
import { useServiceStore } from '../store/serviceStore';

export function useEvents(eventType?: string, serviceName?: string, limit: number = 100) {
  const { setEvents } = useServiceStore();

  const fetchEvents = async () => {
    try {
      const params = new URLSearchParams();
      if (eventType) params.append('type', eventType);
      if (serviceName) params.append('service', serviceName);
      params.append('limit', limit.toString());

      const response = await fetch(`/api/events?${params}`);
      if (response.ok) {
        const events = await response.json();
        setEvents(events);
      }
    } catch (error) {
      console.error('Error fetching events:', error);
    }
  };

  useEffect(() => {
    fetchEvents();
    const interval = setInterval(fetchEvents, 5000);
    return () => clearInterval(interval);
  }, [eventType, serviceName, limit]);

  return { fetchEvents };
}

