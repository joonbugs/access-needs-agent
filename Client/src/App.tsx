import { useEffect, useMemo, useRef, useState } from 'react'
import './App.css'

type AnalysisEvent = {
  ts?: number
  file_name?: string
  summary?: string
}

const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://127.0.0.1:8000'

function formatTime(ts?: number) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString()
}

function App() {
  const [events, setEvents] = useState<AnalysisEvent[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const seenKeys = useRef<Set<string>>(new Set())

  const newestFirst = useMemo(() => [...events].reverse(), [events])

  useEffect(() => {
    let cancelled = false

    async function loadInitial() {
      try {
        const res = await fetch(`${API_BASE}/api/analysis/latest?limit=100`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = (await res.json()) as { events?: AnalysisEvent[] }
        const items = Array.isArray(data.events) ? data.events : []
        if (cancelled) return
        setEvents(items)
        for (const e of items) {
          const key = `${e.ts ?? ''}:${e.file_name ?? ''}:${e.summary ?? ''}`
          seenKeys.current.add(key)
        }
      } catch (e) {
        if (!cancelled) setError(`Failed to load latest analysis: ${String(e)}`)
      }
    }

    loadInitial()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const es = new EventSource(`${API_BASE}/api/analysis/stream`)
    setConnected(false)
    setError(null)

    function onOpen() {
      setConnected(true)
      setError(null)
    }

    function onError() {
      setConnected(false)
    }

    function onAnalysis(ev: MessageEvent) {
      try {
        const parsed = JSON.parse(ev.data) as AnalysisEvent
        const key = `${parsed.ts ?? ''}:${parsed.file_name ?? ''}:${parsed.summary ?? ''}`
        if (seenKeys.current.has(key)) return
        seenKeys.current.add(key)
        setEvents((prev) => {
          const next = [...prev, parsed]
          // Keep last 500 to avoid unbounded growth
          return next.length > 500 ? next.slice(next.length - 500) : next
        })
      } catch {
        // ignore
      }
    }

    es.addEventListener('open', onOpen as EventListener)
    es.addEventListener('error', onError as EventListener)
    es.addEventListener('analysis', onAnalysis as EventListener)

    return () => {
      es.close()
    }
  }, [])

  return (
    <div className="page">
      <header className="header">
        <div>
          <h1>Access Needs Agent</h1>
          <p className="subtitle">Live analysis from transcript processing</p>
        </div>
        <div className="status">
          <span className={`dot ${connected ? 'ok' : 'bad'}`} />
          <span className="label">{connected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </header>

      {error ? <div className="error">{error}</div> : null}

      <main className="content">
        <section className="panel">
          <div className="panelHeader">
            <h2>Latest analysis</h2>
            <div className="meta">{events.length} events</div>
          </div>
          <div className="list">
            {newestFirst.length === 0 ? (
              <div className="empty">
                No analysis events yet. Start the watcher and pipeline, then speak for a bit.
              </div>
            ) : (
              newestFirst.map((e, idx) => (
                <article className="card" key={`${e.ts ?? 'na'}-${idx}`}>
                  <div className="cardHeader">
                    <div className="file">{e.file_name ?? 'unknown file'}</div>
                    <div className="time">{formatTime(e.ts)}</div>
                  </div>
                  <pre className="summary">{e.summary ?? ''}</pre>
                </article>
              ))
            )}
          </div>
        </section>
      </main>
    </div>
  )
}

export default App
