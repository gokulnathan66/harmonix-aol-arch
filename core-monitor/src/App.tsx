import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { useWebSocket } from './hooks/useWebSocket';
import { useServices } from './hooks/useServices';
import GraphView from './components/GraphView/GraphView';
import ListView from './components/ListView/ListView';
import TimelineView from './components/TimelineView/TimelineView';
import MetricsView from './components/MetricsView/MetricsView';
import ServiceDetail from './components/ServiceDetail/ServiceDetail';
import { Activity, List, Clock, BarChart3, Network } from 'lucide-react';

function NavLink({ to, icon: Icon, children }: { to: string; icon: any; children: React.ReactNode }) {
  const location = useLocation();
  const isActive = location.pathname === to || (to === '/' && location.pathname === '/');
  
  return (
    <Link
      to={to}
      className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors ${
        isActive ? 'bg-slate-700 text-blue-400' : 'hover:bg-slate-700'
      }`}
    >
      <Icon className="w-4 h-4" />
      {children}
    </Link>
  );
}

function AppContent() {
  const { connected } = useWebSocket();
  useServices();

  return (
    <div className="min-h-screen bg-slate-900 text-white">
        {/* Header */}
        <header className="bg-slate-800 border-b border-slate-700">
          <div className="container mx-auto px-4 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Network className="w-8 h-8 text-blue-400" />
                <h1 className="text-2xl font-bold">AOL Core Monitor</h1>
              </div>
              <div className="flex items-center gap-2">
                <div className={`w-3 h-3 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-sm">{connected ? 'Connected' : 'Disconnected'}</span>
              </div>
            </div>
          </div>
        </header>

        {/* Navigation */}
        <nav className="bg-slate-800 border-b border-slate-700">
          <div className="container mx-auto px-4">
            <div className="flex gap-1">
              <NavLink to="/" icon={Activity}>Graph</NavLink>
              <NavLink to="/list" icon={List}>List</NavLink>
              <NavLink to="/timeline" icon={Clock}>Timeline</NavLink>
              <NavLink to="/metrics" icon={BarChart3}>Metrics</NavLink>
            </div>
          </div>
        </nav>

        {/* Main Content */}
        <main className="container mx-auto px-4 py-6">
          <Routes>
            <Route path="/" element={<GraphView />} />
            <Route path="/list" element={<ListView />} />
            <Route path="/timeline" element={<TimelineView />} />
            <Route path="/metrics" element={<MetricsView />} />
            <Route path="/service/:serviceId" element={<ServiceDetail />} />
          </Routes>
        </main>
      </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

export default App;

