import { useServiceStore } from '../../store/serviceStore';
import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

export default function MetricsView() {
  const { stats, services, routes } = useServiceStore();

  const statusData = stats?.by_status ? Object.entries(stats.by_status).map(([status, count]) => ({
    status,
    count,
  })) : [];

  const typeData = stats?.by_type ? Object.entries(stats.by_type).map(([type, count]) => ({
    type,
    count,
  })) : [];

  const routeData = routes.slice(0, 10).map(route => ({
    name: `${route.source}→${route.target}`,
    count: route.count,
    success: route.success_count,
    failure: route.failure_count,
  }));

  const COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981'];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">System Metrics</h2>
        <p className="text-sm text-slate-400">Overview of AOL Core system health</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
          <div className="text-sm text-slate-400">Total Services</div>
          <div className="text-3xl font-bold mt-2">{stats?.total_services || 0}</div>
        </div>
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
          <div className="text-sm text-slate-400">Unique Services</div>
          <div className="text-3xl font-bold mt-2">{stats?.unique_services || 0}</div>
        </div>
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
          <div className="text-sm text-slate-400">Active Routes</div>
          <div className="text-3xl font-bold mt-2">{routes.length}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
          <h3 className="text-lg font-semibold mb-4">Services by Status</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={statusData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ status, count }) => `${status}: ${count}`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="count"
              >
                {statusData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
          <h3 className="text-lg font-semibold mb-4">Services by Type</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={typeData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="type" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155' }}
                labelStyle={{ color: '#e2e8f0' }}
              />
              <Bar dataKey="count" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
        <h3 className="text-lg font-semibold mb-4">Top Routes by Call Count</h3>
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={routeData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="name" stroke="#94a3b8" angle={-45} textAnchor="end" height={100} />
            <YAxis stroke="#94a3b8" />
            <Tooltip
              contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155' }}
              labelStyle={{ color: '#e2e8f0' }}
            />
            <Legend />
            <Bar dataKey="success" stackId="a" fill="#10b981" name="Success" />
            <Bar dataKey="failure" stackId="a" fill="#ef4444" name="Failure" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

