import { Component, lazy, Suspense } from 'react'
import type { ReactNode } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Layout from './components/Layout'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const MaterialList = lazy(() => import('./pages/MaterialList'))
const MaterialDetail = lazy(() => import('./pages/MaterialDetail'))
const SceneSearch = lazy(() => import('./pages/SceneSearch'))
const CharacterSearch = lazy(() => import('./pages/CharacterSearch'))
const TagDictionary = lazy(() => import('./pages/TagDictionary'))
const Settings = lazy(() => import('./pages/Settings'))
const UploadPage = lazy(() => import('./pages/Upload'))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 5 * 60_000, refetchOnWindowFocus: false },
  },
})

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null }
  static getDerivedStateFromError(error: Error) { return { error } }
  render() {
    if (this.state.error) {
      return (
        <div style={{ color: '#f87171', padding: 24, fontFamily: 'monospace' }}>
          <h2>Render Error</h2>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>
            {this.state.error.message}
            {'\n\n'}
            {this.state.error.stack}
          </pre>
        </div>
      )
    }
    return this.props.children
  }
}

function Loading() {
  return <div className="p-6 text-slate-500 text-sm">Loading...</div>
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Suspense fallback={<Loading />}>
            <Routes>
              <Route element={<Layout />}>
                <Route index element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
                <Route path="materials" element={<ErrorBoundary><MaterialList /></ErrorBoundary>} />
                <Route path="materials/:id" element={<ErrorBoundary><MaterialDetail /></ErrorBoundary>} />
                <Route path="search/scenes" element={<ErrorBoundary><SceneSearch /></ErrorBoundary>} />
                <Route path="search/characters" element={<ErrorBoundary><CharacterSearch /></ErrorBoundary>} />
                <Route path="tags" element={<ErrorBoundary><TagDictionary /></ErrorBoundary>} />
                <Route path="upload" element={<ErrorBoundary><UploadPage /></ErrorBoundary>} />
                <Route path="settings" element={<ErrorBoundary><Settings /></ErrorBoundary>} />
              </Route>
            </Routes>
          </Suspense>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
