import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { DatasetProvider } from './context/DatasetContext'
import { StoryProvider } from './context/StoryContext'
import { AskAIProvider } from './context/AskAIContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { Layout } from './components/Layout'
import { Home } from './pages/Home'
import { Login } from './pages/Login'
import { Dashboard } from './pages/Dashboard'
import { About } from './pages/About'
import { AskAI } from './pages/AskAI'
import { Story } from './pages/Story'
import { SqlConsole } from './pages/SqlConsole'
import { Admin } from './pages/Admin'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
      <DatasetProvider>
      <StoryProvider>
      <AskAIProvider>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />

          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/about" element={<About />} />

              <Route element={<ProtectedRoute roles={['viewer', 'analyst', 'admin']} />}>
                <Route path="/ask" element={<AskAI />} />
                <Route path="/story" element={<Story />} />
              </Route>

              <Route element={<ProtectedRoute roles={['analyst', 'admin']} />}>
                <Route path="/query" element={<SqlConsole />} />
              </Route>

              <Route element={<ProtectedRoute roles={['admin']} />}>
                <Route path="/admin" element={<Admin />} />
              </Route>
            </Route>
          </Route>
        </Routes>
      </AskAIProvider>
      </StoryProvider>
      </DatasetProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
