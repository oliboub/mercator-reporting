import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar.jsx'
import Dashboard from './pages/Dashboard.jsx'
import ReportView from './pages/ReportView.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-bg-primary font-body">
        <Navbar />
        <main className="pt-16">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/templates/:id" element={<ReportView />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
