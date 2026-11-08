import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import MapView from './MapView'
import { ClaimsPanel, QueuePanel, SilencePanel, TracePanel } from './panels'
import { AfterView, BeforeView, PhaseBanner, PhoneSim } from './phases'

const TABS = [
  ['queue', 'Priority queue'],
  ['silence', 'Quiet blocks'],
  ['trace', 'Agent trace'],
  ['claims', 'Claims'],
]
const JUDGE_TEXT = 'el agua está entrando, mi mamá usa oxígeno'
const REYES_PHONE = '+17135550188'
const PHASES = [['before', 'Before', 'T−72h → landfall'], ['during', 'During', 'landfall → T+48h'], ['after', 'After', 'T+48h → claims']]

function Kpi({ label, value, accent }) {
  return (
    <div className="rounded-lg bg-slate-900 px-3 py-1.5">
      <div className={`text-lg font-bold leading-tight ${accent || ''}`}>{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-slate-400">{label}</div>
    </div>
  )
}

function Badge({ on, label, onText, offText }) {
  return (
    <span className={`rounded px-2 py-0.5 text-[10px] font-semibold ${on ? 'bg-emerald-900 text-emerald-200' : 'bg-slate-800 text-slate-400'}`}>
      {label}: {on ? onText : offText}
    </span>
  )
}

export default function App() {
  const [state, setState] = useState(null)
  const [tab, setTab] = useState('queue')
  const [selectedId, setSelectedId] = useState(null)
  const [flyTarget, setFlyTarget] = useState(null)
  const [showSilence, setShowSilence] = useState(false)
  const [error, setError] = useState(null)
  const [jumps, setJumps] = useState({})
  const [textOpen, setTextOpen] = useState(false)
  const [phone, setPhone] = useState(REYES_PHONE)
  const [text, setText] = useState(JUDGE_TEXT)
  const prevRanks = useRef({})
  const demoPhoneSet = useRef(false)

  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const s = await api.state()
        if (!alive) return
        // Highlight cases that jumped 3+ places (or appeared in the top 5) since the last poll.
        const newJumps = {}
        s.queue.forEach((q) => {
          const before = prevRanks.current[q.id]
          if ((before && before - q.rank >= 3) || (!before && q.rank <= 5 && Object.keys(prevRanks.current).length)) {
            newJumps[q.id] = before ? before - q.rank : 'new'
          }
        })
        prevRanks.current = Object.fromEntries(s.queue.map((q) => [q.id, q.rank]))
        if (Object.keys(newJumps).length) {
          setJumps((j) => ({ ...j, ...newJumps }))
          setTimeout(() => setJumps((j) => {
            const next = { ...j }
            Object.keys(newJumps).forEach((k) => delete next[k])
            return next
          }), 4000)
        }
        setState(s)
        setError((e) => (e && e.startsWith("Can't reach the backend") ? null : e))  // clear once it's back
        if (s.config?.demo_phone && !demoPhoneSet.current) { demoPhoneSet.current = true; setPhone(s.config.demo_phone) }
      } catch (e) {
        if (alive) setError(`Can't reach the backend: ${e.message}`)
      }
    }
    load()
    const id = setInterval(load, 2000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  const run = async (fn) => {
    setError(null)
    try { await fn() } catch (e) { setError(e.message) }
  }

  const select = (id) => {
    setSelectedId(id)
    const p = state?.pins.find((x) => x.id === id)
    if (p) setFlyTarget([p.lat, p.lng])
  }

  if (!state) return <div className="grid h-full place-items-center text-slate-400">{error || 'Connecting to LifeLine…'}</div>
  const c = state.counts
  const started = state.phase !== 'idle'
  const phase = state.event_phase || 'before'
  const goPhase = (p) => run(async () => { await api.phase(p); setState(await api.state()) })

  return (
    <div className="flex h-full flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b border-slate-800 bg-slate-950 px-4 py-2">
        <div className="mr-2">
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-sf-red" />
            <span className="text-lg font-extrabold tracking-tight">LifeLine</span>
            <span className="text-xs text-slate-400">catastrophe response concept</span>
          </div>
          <div className="text-[11px] text-slate-500">Houston hurricane flood · <b>simulated data</b> · {state.clock}</div>
        </div>
        <nav className="flex overflow-hidden rounded-lg border border-slate-700">
          {PHASES.map(([id, label, sub]) => (
            <button key={id} onClick={() => goPhase(id)}
              className={`px-4 py-1 text-left ${started && phase === id ? 'bg-sf-red text-white' : 'text-slate-300 hover:bg-slate-800'}`}>
              <div className="text-sm font-bold">{label}</div>
              <div className="text-[10px] opacity-75">{sub}</div>
            </button>
          ))}
        </nav>
        {started && phase === 'during' && (
          <div className="flex flex-wrap gap-2">
            <Kpi label="In flood zone" value={c.in_zone} />
            <Kpi label="Replied" value={`${c.replied}/${c.contacted}`} />
            <Kpi label="Need help" value={c.needs_help} accent="text-red-400" />
            <Kpi label="No phone on file" value={c.unreachable} accent="text-amber-300" />
            <Kpi label="Quiet blocks" value={c.flagged_blocks} accent={c.flagged_blocks ? 'text-red-400' : ''} />
            <Kpi label="Confirmed safe" value={c.confirmed_safe} accent="text-emerald-400" />
          </div>
        )}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <div className="flex flex-col gap-1">
            <Badge on={state.config.nemotron} label="Nemotron" onText="live" offText="rules fallback" />
            <Badge on={state.config.photon} label="Photon" onText="live" offText="mock" />
          </div>
          <button onClick={() => run(() => api.start('before'))}
            className="rounded border border-slate-600 px-3 py-1.5 text-sm font-semibold hover:bg-slate-800">
            {started ? 'Restart scenario' : 'Start scenario'}
          </button>
          {phase === 'during' && (
            <button disabled={!started || state.outreach_at != null} onClick={() => run(api.checkinAll)}
              className="rounded bg-sf-red px-3 py-1.5 text-sm font-semibold hover:bg-sf-dark disabled:opacity-40">
              Check in all
            </button>
          )}
        </div>
      </header>

      {error && <div className="bg-red-950 px-4 py-1.5 text-sm text-red-200">{error} <button className="ml-2 underline" onClick={() => setError(null)}>dismiss</button></div>}

      {started && <PhaseBanner state={state} />}

      {started && phase === 'before' && <BeforeView state={state} onError={setError} />}
      {started && phase === 'after' && <AfterView state={state} onError={setError} />}

      {(!started || phase === 'during') && <main className="flex min-h-0 flex-1">
        <section className="relative min-w-0 flex-1">
          <MapView state={state} showSilence={showSilence} selectedId={selectedId} onSelect={select} flyTarget={flyTarget} />
          <div className="absolute left-3 top-3 z-[1000] flex flex-col gap-2">
            <button onClick={() => setShowSilence((v) => !v)}
              className={`rounded-lg px-3 py-1.5 text-sm font-semibold shadow ${showSilence ? 'bg-sf-red' : 'bg-slate-900/90 hover:bg-slate-800'}`}>
              {showSilence ? '◉ Silence map on' : '○ Silence map'}
            </button>
          </div>
          <div className="absolute bottom-3 left-3 z-[1000] rounded-lg bg-slate-900/90 p-2 text-[11px] text-slate-300 shadow">
            <div className="flex items-center gap-3">
              {[['#ef4444', '70+'], ['#f97316', '40–69'], ['#eab308', '15–39'], ['#64748b', 'low / unreached'], ['#22c55e', 'safe']].map(([col, l]) => (
                <span key={l} className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full" style={{ background: col }} />{l}</span>
              ))}
            </div>
            <div className="mt-1 text-slate-500">Blue = flood depth · ◯ green ring = shelter · ◯ white ring = team</div>
          </div>
        </section>

        <aside className="flex w-[440px] shrink-0 flex-col border-l border-slate-800 bg-slate-950">
          <nav className="flex border-b border-slate-800">
            {TABS.map(([id, label]) => (
              <button key={id} onClick={() => setTab(id)}
                className={`flex-1 px-2 py-2 text-xs font-semibold ${tab === id ? 'border-b-2 border-sf-red text-white' : 'text-slate-400 hover:text-slate-200'}`}>
                {label}{id === 'silence' && c.flagged_blocks ? ` (${c.flagged_blocks})` : ''}
              </button>
            ))}
          </nav>
          <div className="scroll-thin min-h-0 flex-1 overflow-y-auto p-3">
            {tab === 'queue' && <QueuePanel queue={state.queue} selectedId={selectedId} onSelect={select} jumps={jumps} onError={setError} />}
            {tab === 'silence' && <SilencePanel blocks={state.blocks} sweeps={state.sweeps} outreachAt={state.outreach_at}
              onFocus={(center) => { setShowSilence(true); setFlyTarget(center) }} onError={setError} />}
            {tab === 'trace' && <TracePanel trace={state.trace} />}
            {tab === 'claims' && <ClaimsPanel />}
          </div>
        </aside>
      </main>}
      {started && (
        <PhoneSim open={textOpen} setOpen={setTextOpen} phone={phone} setPhone={setPhone} text={text} setText={setText}
          phase={phase} onSend={(t) => run(async () => { await api.inbound(phone, t ?? text); if (phase === 'during') setTab('trace') })} />
      )}
    </div>
  )
}
