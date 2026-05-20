import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Dashboard from './pages/Dashboard'
import Pending from './pages/Pending'
import Archive from './pages/Archive'

const qc = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <div className="min-h-screen bg-gray-950 text-gray-100">
          <nav className="bg-gray-900 border-b border-gray-800 px-6 py-4 flex items-center gap-6">
            <span className="font-bold text-lg text-white mr-4">Twitter Bot</span>
            {[
              { to: '/', label: 'Dashboard' },
              { to: '/pending', label: 'Onay Kuyruğu' },
              { to: '/archive', label: 'Arşiv' },
            ].map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `text-sm font-medium transition-colors ${
                    isActive ? 'text-blue-400' : 'text-gray-400 hover:text-white'
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          <main className="max-w-5xl mx-auto px-6 py-8">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/pending" element={<Pending />} />
              <Route path="/archive" element={<Archive />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
