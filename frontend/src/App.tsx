import { useEffect, useState } from 'react';
import { Link, NavLink, Route, Routes, useLocation } from 'react-router-dom';
import { api, type ServiceStatus } from './lib/api';
import { StatusDot } from './components/ui';
import Dashboard from './pages/Dashboard';
import Ask from './pages/Ask';
import Explorer from './pages/Explorer';
import Documents from './pages/Documents';
import DocDetail from './pages/DocDetail';
import Evaluation from './pages/Evaluation';
import Benchmark from './pages/Benchmark';
import Failures from './pages/Failures';
import Monitoring from './pages/Monitoring';
import Settings from './pages/Settings';

const NAV = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/ask', label: 'Ask RAG' },
  { to: '/retrieval', label: 'Retrieval' },
  { to: '/documents', label: 'Documents' },
  { to: '/evaluation', label: 'Evaluation' },
  { to: '/benchmark', label: 'Benchmarks' },
  { to: '/failures', label: 'Failures' },
  { to: '/monitoring', label: 'Monitoring' },
  { to: '/settings', label: 'Settings' },
];

function useSystemStatus() {
  const [overall, setOverall] = useState<string>('unknown');
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [demoMode, setDemoMode] = useState<boolean>(false);

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const s = await api<{ overall: string; services: ServiceStatus[] }>('/api/system/status');
        if (alive) {
          setOverall(s.overall);
          setServices(s.services);
        }
      } catch {
        if (alive) setOverall('unavailable');
      }
      try {
        const c = await api<{ runtime: { demo_mode: boolean } }>('/api/config/public');
        if (alive) setDemoMode(!!c.runtime.demo_mode);
      } catch {
        /* ignore */
      }
    }
    load();
    const t = setInterval(load, 30000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);
  return { overall, services, demoMode };
}

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showStatus, setShowStatus] = useState(false);
  const { overall, services, demoMode } = useSystemStatus();
  const location = useLocation();

  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  const pillColor =
    overall === 'operational' ? 'bg-emerald-100 text-emerald-800 border-emerald-200' : 'bg-amber-100 text-amber-900 border-amber-200';

  return (
    <div className="min-h-screen">
      {/* Top bar */}
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white">
        <div className="flex h-14 items-center gap-3 px-4">
          <button
            className="rounded-md p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
            onClick={() => setSidebarOpen((v) => !v)}
            aria-label="Toggle navigation"
            aria-expanded={sidebarOpen}
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>
          <Link to="/" className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-blue-700 font-mono text-sm font-bold text-white" aria-hidden="true">
              R
            </span>
            <span className="text-sm font-semibold text-slate-900">Enterprise RAG Intelligence</span>
          </Link>
          {demoMode && (
            <span className="rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-800">
              DEMO MODE
            </span>
          )}
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={() => setShowStatus((v) => !v)}
              aria-expanded={showStatus}
              aria-label="System status details"
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${pillColor}`}
            >
              <span
                className={`inline-block h-2 w-2 rounded-full ${overall === 'operational' ? 'bg-emerald-600' : 'bg-amber-600'}`}
                aria-hidden="true"
              />
              {overall === 'operational' ? 'All Systems Operational' : `Status: ${overall}`}
            </button>
          </div>
        </div>
        {showStatus && (
          <div className="border-t border-slate-200 bg-white px-4 py-3" role="dialog" aria-label="Service details">
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {services.length === 0 && <p className="text-sm text-slate-500">Status unavailable — is the API running?</p>}
              {services.map((s) => (
                <div key={s.name} className="rounded-md border border-slate-200 px-3 py-2 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-semibold text-slate-700">{s.name}</span>
                    <StatusDot status={s.status} />
                  </div>
                  {(s.model ?? s.provider ?? s.detail ?? s.error) && (
                    <p className="mt-1 truncate text-xs text-slate-500" title={String(s.model ?? s.provider ?? s.detail ?? s.error)}>
                      {String(s.model ?? s.provider ?? s.detail ?? s.error)}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </header>

      <div className="mx-auto flex max-w-[1400px]">
        {/* Sidebar */}
        <nav
          aria-label="Primary"
          className={`${
            sidebarOpen ? 'fixed inset-y-14 left-0 z-20 block w-60 border-r bg-white' : 'hidden'
          } w-60 shrink-0 border-r border-slate-200 bg-white lg:sticky lg:top-14 lg:block lg:h-[calc(100vh-3.5rem)]`}
        >
          <ul className="space-y-1 p-3">
            {NAV.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    `block rounded-md px-3 py-2 text-sm font-medium ${
                      isActive ? 'bg-blue-50 text-blue-800' : 'text-slate-600 hover:bg-slate-100'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
          <div className="p-3 text-xs text-slate-400">
            <p>Evaluation-driven retrieval.</p>
            <p className="mt-1">Every answer traces to evidence.</p>
          </div>
        </nav>

        {/* Main content */}
        <main className="min-w-0 flex-1 p-4 lg:p-6" id="main">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/ask" element={<Ask />} />
            <Route path="/retrieval" element={<Explorer />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/documents/:id" element={<DocDetail />} />
            <Route path="/evaluation" element={<Evaluation />} />
            <Route path="/benchmark" element={<Benchmark />} />
            <Route path="/failures" element={<Failures />} />
            <Route path="/monitoring" element={<Monitoring />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<p className="text-sm text-slate-600">Page not found.</p>} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
