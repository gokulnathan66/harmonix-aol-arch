import { useState } from 'react';
import { useServiceStore } from '../../store/serviceStore';
import { useNavigate } from 'react-router-dom';
import { Search, Filter, Eye } from 'lucide-react';
import { Service } from '../../types';

export default function ListView() {
  const { services, filter, setFilter } = useServiceStore();
  const navigate = useNavigate();
  const [sortField, setSortField] = useState<keyof Service>('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  // Filter services
  const filteredServices = services.filter(service => {
    if (!service || !service.service_id) return false;
    
    if (filter.status && service.status !== filter.status) return false;
    if (filter.type) {
      const serviceType = service?.manifest?.metadata?.labels?.['aol.service.type'] 
        || service?.manifest?.kind 
        || 'unknown';
      if (serviceType !== filter.type) return false;
    }
    if (filter.search) {
      const searchLower = filter.search.toLowerCase();
      if (!service.name?.toLowerCase().includes(searchLower)) return false;
    }
    return true;
  });

  // Sort services
  const sortedServices = [...filteredServices].sort((a, b) => {
    const aVal = a[sortField];
    const bVal = b[sortField];
    const comparison = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
    return sortDirection === 'asc' ? comparison : -comparison;
  });

  const handleSort = (field: keyof Service) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const getStatusBadge = (status: string) => {
    const colors = {
      healthy: 'bg-green-500/20 text-green-400 border-green-500/50',
      unhealthy: 'bg-red-500/20 text-red-400 border-red-500/50',
      starting: 'bg-amber-500/20 text-amber-400 border-amber-500/50',
    };
    return colors[status as keyof typeof colors] || colors.healthy;
  };

  const uniqueTypes = Array.from(new Set(services.map(s => 
    s?.manifest?.metadata?.labels?.['aol.service.type'] 
    || s?.manifest?.kind 
    || 'unknown'
  )));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Services List</h2>
        <div className="flex gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search services..."
              value={filter.search || ''}
              onChange={(e) => setFilter({ search: e.target.value })}
              className="pl-10 pr-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <select
            value={filter.status || ''}
            onChange={(e) => setFilter({ status: e.target.value || undefined })}
            className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="healthy">Healthy</option>
            <option value="unhealthy">Unhealthy</option>
            <option value="starting">Starting</option>
          </select>
          <select
            value={filter.type || ''}
            onChange={(e) => setFilter({ type: e.target.value || undefined })}
            className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Types</option>
            {uniqueTypes.map(type => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="border border-slate-700 rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-slate-800 border-b border-slate-700">
            <tr>
              <th
                className="px-4 py-3 text-left text-sm font-medium text-slate-300 cursor-pointer hover:bg-slate-700"
                onClick={() => handleSort('name')}
              >
                Name {sortField === 'name' && (sortDirection === 'asc' ? '↑' : '↓')}
              </th>
              <th
                className="px-4 py-3 text-left text-sm font-medium text-slate-300 cursor-pointer hover:bg-slate-700"
                onClick={() => handleSort('status')}
              >
                Status {sortField === 'status' && (sortDirection === 'asc' ? '↑' : '↓')}
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">Type</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">Host</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">Ports</th>
              <th
                className="px-4 py-3 text-left text-sm font-medium text-slate-300 cursor-pointer hover:bg-slate-700"
                onClick={() => handleSort('registered_at')}
              >
                Registered {sortField === 'registered_at' && (sortDirection === 'asc' ? '↑' : '↓')}
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-slate-300">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700">
            {sortedServices.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                  No services found
                </td>
              </tr>
            ) : (
              sortedServices.map((service) => (
                <tr key={service.service_id} className="hover:bg-slate-800/50">
                  <td className="px-4 py-3">
                    <div className="font-medium">{service.name}</div>
                    <div className="text-xs text-slate-400">{service.version}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded border text-xs ${getStatusBadge(service.status)}`}>
                      {service.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-300">
                    {service?.manifest?.metadata?.labels?.['aol.service.type'] 
                      || service?.manifest?.kind 
                      || 'unknown'}
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-300">{service.host}</td>
                  <td className="px-4 py-3 text-sm text-slate-300">
                    <div className="text-xs">
                      <div>gRPC: {service.grpc_port}</div>
                      <div>Health: {service.health_port}</div>
                      <div>Metrics: {service.metrics_port}</div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-400">
                    {new Date(service.registered_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => navigate(`/service/${service.service_id}`)}
                      className="p-1 hover:bg-slate-700 rounded transition-colors"
                      title="View Details"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

