import { create } from 'zustand';
import { Service, Event, RouteData, RegistryStats } from '../types';

interface ServiceStore {
  services: Service[];
  events: Event[];
  routes: RouteData[];
  stats: RegistryStats | null;
  selectedService: Service | null;
  filter: {
    status?: string;
    type?: string;
    search?: string;
  };
  
  // Actions
  setServices: (services: Service[]) => void;
  addService: (service: Service) => void;
  updateService: (serviceId: string, updates: Partial<Service>) => void;
  removeService: (serviceId: string) => void;
  setEvents: (events: Event[]) => void;
  addEvent: (event: Event) => void;
  setRoutes: (routes: RouteData[]) => void;
  setStats: (stats: RegistryStats) => void;
  setSelectedService: (service: Service | null) => void;
  setFilter: (filter: Partial<ServiceStore['filter']>) => void;
  clearFilter: () => void;
}

export const useServiceStore = create<ServiceStore>((set) => ({
  services: [],
  events: [],
  routes: [],
  stats: null,
  selectedService: null,
  filter: {},
  
  setServices: (services) => set({ services }),
  
  addService: (service) => set((state) => ({
    services: [...state.services, service]
  })),
  
  updateService: (serviceId, updates) => set((state) => ({
    services: state.services.map(s => 
      s.service_id === serviceId ? { ...s, ...updates } : s
    )
  })),
  
  removeService: (serviceId) => set((state) => ({
    services: state.services.filter(s => s.service_id !== serviceId)
  })),
  
  setEvents: (events) => set({ events }),
  
  addEvent: (event) => set((state) => ({
    events: [event, ...state.events].slice(0, 1000) // Keep last 1000 events
  })),
  
  setRoutes: (routes) => set({ routes }),
  
  setStats: (stats) => set({ stats }),
  
  setSelectedService: (service) => set({ selectedService: service }),
  
  setFilter: (filter) => set((state) => ({
    filter: { ...state.filter, ...filter }
  })),
  
  clearFilter: () => set({ filter: {} }),
}));

