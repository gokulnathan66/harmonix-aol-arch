import { useEffect } from 'react';
import { useServiceStore } from '../store/serviceStore';

export function useServices() {
  const { setServices, setStats, setRoutes } = useServiceStore();

  const fetchServices = async () => {
    try {
      const [servicesRes, statsRes, routesRes] = await Promise.all([
        fetch('/api/services'),
        fetch('/api/registry/stats'),
        fetch('/api/routes')
      ]);

      if (servicesRes.ok) {
        const services = await servicesRes.json();
        setServices(services);
      }

      if (statsRes.ok) {
        const stats = await statsRes.json();
        setStats(stats);
      }

      if (routesRes.ok) {
        const routes = await routesRes.json();
        setRoutes(routes);
      }
    } catch (error) {
      console.error('Error fetching services:', error);
    }
  };

  useEffect(() => {
    fetchServices();
    // Refresh every 30 seconds as backup
    const interval = setInterval(fetchServices, 30000);
    return () => clearInterval(interval);
  }, []);

  return { fetchServices };
}

