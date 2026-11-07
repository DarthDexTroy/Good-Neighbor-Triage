import { useEffect, useRef, useState } from 'react'
import { api, band, scoreColor, SOURCE_LABEL, STATUS_LABEL } from './api'

export const chip = 'inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide'

const STATUS_CHIP = {
  needs_help: 'bg-red-900 text-red-200',
  welfare_check: 'bg-fuchsia-800 text-fuchsia-100',
  assigned: 'bg-blue-900 text-blue-200',
}

function ScoreBadge({ score, status }) {
  return (
    <div className="flex h-12 w-12 shrink-0 flex-col items-center justify-center rounded-lg text-slate-950"
      style={{ background: scoreColor(score, status) }}>
      <span className="text-lg font-extrabold leading-none">{score}</span>
      <span className="text-[8px] font-bold uppercase">{band(score)}</span>
    </div>
  )
}

/** Conversation for one case, polled while the card is open. */
export function Thread({ caseId, compact }) {
  const [msgs, setMsgs] = useState([])
  const end = useRef(null)
  useEffect(() => {
    if (!caseId) return
    let alive = true
    const load = () => api.messages(caseId).then((m) => alive && setMsgs(m)).catch(() => {})
    load()
    const id = setInterval(load, 2000)
    return () => { alive = false; clearInterval(id) }
  }, [caseId])
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest' }) }, [msgs.length])
  if (!msgs.length) return <div className="text-xs text-slate-500">No messages yet.</div>
  return (
    <div className={`scroll-thin space-y-1.5 overflow-y-auto ${compact ? 'max-h-56' : 'max-h-48'}`}>
      {msgs.map((m) => (
        <div key={m.id} className={`flex ${m.direction === 'out' ? 'justify-start' : 'justify-end'}`}>
          <div className={`max-w-[85%] rounded-xl px-2.5 py-1.5 text-xs ${m.direction === 'out' ? 'bg-slate-700 text-slate-100' : 'bg-sky-600 text-white'}`}>
            {m.body}
            <div className="mt-0.5 text-[9px] opacity-60">{m.when}{m.via ? ` · ${m.via}` : ''}</div>
          </div>
        </div>
      ))}
      <div ref={end} />
    </div>
  )
}

/** Shared queue. mode = "cat" (approve dispatch) or "responders" (take case + ETA). */
export function QueuePanel({ queue, selectedId, onSelect, jumps, onError, mode = 'cat', etas = {}, onTaken }) {
  const [busy, setBusy] = useState(null)
  const refs = useRef({})
  useEffect(() => {
    if (selectedId) refs.current[selectedId]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [selectedId])
  const act = async (id, fn) => {
    setBusy(id)
    try { return await fn() } catch (e) { onError(e.message) } finally { setBusy(null) }
  }
  if (!queue.length) {
    return <Empty text={mode === 'responders'
      ? 'No rescue cases yet. They appear when someone needs help or a welfare check is due.'
      : 'No cases yet. Start the scenario, then check in all households.'} />
  }
  return (
    <div className="space-y-2">
      {queue.map((q) => {
        const sel = q.id === selectedId
        const jump = jumps[q.id]
        const eta = etas[q.id]
        return (
          <div key={q.id} ref={(el) => { refs.current[q.id] = el }} onClick={() => onSelect(q.id)}
            className={`cursor-pointer rounded-lg border p-2.5 transition ${sel ? 'border-white/70 bg-slate-800' : 'border-slate-800 bg-slate-900 hover:border-slate-600'} ${jump ? 'flash' : ''}`}>
            <div className="flex gap-2.5">
              <div className="flex flex-col items-center gap-1">
                <span className="text-[11px] font-bold text-slate-400">#{q.rank}</span>
                <ScoreBadge score={q.score} status={q.status} />
                {jump && <span className="text-[10px] font-bold text-red-400">▲{jump}</span>}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="truncate font-semibold">{q.name}</span>
                  <span className={`${chip} bg-slate-700 text-slate-200`}>{SOURCE_LABEL[q.source] || q.source}</span>
                  <span className={`${chip} ${STATUS_CHIP[q.status] || 'bg-slate-800 text-slate-300'}`}>
                    {q.status === 'welfare_check' ? '⚠ ' : ''}{STATUS_LABEL[q.status] || q.status}</span>
                  {q.language === 'es' && <span className={`${chip} bg-violet-900 text-violet-200`}>ES</span>}
                </div>
                <div className="text-xs text-slate-400">{q.address} · block {q.block_id}{q.phone ? ` · ${q.phone}` : ' · no phone on file'}</div>
                {q.last_message && !sel && (
                  <div className="mt-1 rounded bg-slate-950/60 px-2 py-1 text-xs italic text-slate-300">
                    “{q.last_message}” <span className="not-italic text-slate-500">{q.last_reply}</span>
                  </div>
                )}
                <ul className="mt-1 space-y-0.5 text-[11px] text-slate-400">
                  {q.reasons.map((r, i) => <li key={i}>• {r}</li>)}
                </ul>
                {(q.shelter || q.sweep || q.assigned_team) && (
                  <div className="mt-1 text-[11px] text-emerald-300">
                    {q.assigned_team && <>🚤 {q.assigned_team} en route{eta != null ? `, ETA ~${eta} min` : ''}. </>}
                    {q.sweep && !q.assigned_team && <>Sweep team {q.sweep} heading to this block. </>}
                    {q.shelter && <>Shelter: {q.shelter}</>}
                  </div>
                )}
                {sel && (
                  <div className="mt-2 rounded-lg bg-slate-950/70 p-2" onClick={(e) => e.stopPropagation()}>
                    <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">Conversation</div>
                    <Thread caseId={q.id} />
                  </div>
                )}
                <div className="mt-2 flex flex-wrap gap-2" onClick={(e) => e.stopPropagation()}>
                  {mode === 'cat' && q.status !== 'assigned' && q.suggested_team && (
                    <button disabled={busy === q.id}
                      onClick={() => act(q.id, () => api.assign(q.id, q.suggested_team.id))}
                      className="rounded bg-sf-red px-2 py-1 text-xs font-semibold hover:bg-sf-dark disabled:opacity-50">
                      Approve dispatch: {q.suggested_team.name}
                    </button>
                  )}
                  {mode === 'responders' && q.status !== 'assigned' && (
                    <button disabled={busy === q.id || !q.suggested_team}
                      onClick={() => act(q.id, async () => {
                        const r = await api.assign(q.id, q.suggested_team.id)
                        onTaken?.(q.id, r)
                      })}
                      className="rounded bg-sf-red px-3 py-1 text-xs font-bold hover:bg-sf-dark disabled:opacity-50">
                      {q.suggested_team ? `Take case (${q.suggested_team.name})` : 'No team free'}
                    </button>
                  )}
                  <button disabled={busy === q.id} onClick={() => act(q.id, () => api.safe(q.id))}
                    className="rounded border border-emerald-600 px-2 py-1 text-xs font-semibold text-emerald-300 hover:bg-emerald-950 disabled:opacity-50">
                    Confirm safe
                  </button>
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function SilencePanel({ blocks, sweeps, outreachAt, onFocus, onError }) {
  const zone = blocks.filter((b) => b.flood_depth_ft > 0).sort((a, b) => b.priority - a.priority)
  if (outreachAt == null) return <Empty text="The silence map turns on after the check-in goes out." />
  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-400">
        Expected replies = households × 70%. A block is flagged when it sends back less than 40% of what we'd expect.
        In a disaster, silence often means people <i>can't</i> reply.
      </p>
      {zone.slice(0, 12).map((b) => {
        const pct = Math.min(100, Math.round(b.ratio * 100))
        return (
          <div key={b.id} onClick={() => onFocus(b.center)}
            className={`cursor-pointer rounded-lg border p-2.5 ${b.flagged ? 'border-sf-red bg-red-950/40' : 'border-slate-800 bg-slate-900'}`}>
            <div className="flex items-center justify-between">
              <span className="font-semibold">Block {b.id} {b.flagged && <span className="ml-1 text-xs text-red-300">⚠ unusually quiet</span>}</span>
              <span className="text-xs text-slate-400">water {b.flood_depth_ft} ft · vulnerability {b.svi}</span>
            </div>
            <div className="mt-1.5 h-2 rounded bg-slate-800">
              <div className="h-2 rounded" style={{ width: `${pct}%`, background: b.flagged ? '#E31837' : '#f59e0b' }} />
            </div>
            <div className="mt-1 flex items-center justify-between text-xs text-slate-400">
              <span>{b.replies} replies / {b.expected} expected ({pct}%)</span>
              {b.flagged && (sweeps[b.id]
                ? <span className="text-emerald-300">Sweep: {sweeps[b.id]}</span>
                : <button onClick={async (e) => { e.stopPropagation(); try { await api.sweep(b.id) } catch (err) { onError(err.message) } }}
                    className="rounded bg-sf-red px-2 py-0.5 font-semibold text-white">Send sweep team</button>)}
            </div>
          </div>
        )
      })}
    </div>
  )
}

const short = (o) => {
  if (!o) return ''
  const s = JSON.stringify(o)
  return s.length > 140 ? s.slice(0, 140) + '…' : s
}

export function TracePanel({ trace }) {
  const [showSim, setShowSim] = useState(false)
  const rows = showSim ? trace : trace.filter((t) => t.engine !== 'simulated')
  return (
    <div className="space-y-1.5 font-mono text-[11px]">
      <label className="flex items-center gap-2 font-sans text-xs text-slate-400">
        <input type="checkbox" checked={showSim} onChange={(e) => setShowSim(e.target.checked)} />
        Show simulated resident replies
      </label>
      {!rows.length && <Empty text="Agent steps appear here when a real (or rehearsal) text comes in." />}
      {rows.map((t) => (
        <div key={t.id} className="rounded border border-slate-800 bg-slate-900 p-2">
          <div className="flex items-center gap-2">
            <span className={`${chip} ${t.engine.startsWith('nemotron') ? 'bg-lime-800 text-lime-100' : 'bg-slate-700 text-slate-200'}`}>{t.engine}</span>
            <span className="font-bold text-sky-300">{t.tool}</span>
            <span className="truncate text-slate-500">{t.name}</span>
            <span className="ml-auto text-slate-500">{t.when}</span>
          </div>
          {Object.keys(t.args || {}).length > 0 && <div className="mt-1 text-slate-400">args {short(t.args)}</div>}
          <div className="text-slate-300">→ {short(t.result)}</div>
        </div>
      ))}
    </div>
  )
}

const FNOL_LABELS = [
  ['date_of_loss', 'Date of loss'], ['peril', 'Peril'], ['damage', 'Damage described'],
  ['injuries', 'Injuries'], ['temp_housing', 'Temporary housing'],
]

export function ClaimsPanel() {
  const [claims, setClaims] = useState([])
  const [open, setOpen] = useState(null)
  useEffect(() => {
    let alive = true
    const load = () => api.claims().then((c) => alive && setClaims(c)).catch(() => {})
    load()
    const id = setInterval(load, 3000)
    return () => { alive = false; clearInterval(id) }
  }, [])
  if (!claims.length) return <Empty text="No claims yet." />
  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-400">
        Every text, check-in and rescue becomes a verified timeline. Honest claims arrive pre-verified; unusual ones go to an
        adjuster. <b className="text-slate-300">Flags apply to claims only. Help is never blocked.</b>
      </p>
      {claims.map((c) => (
        <div key={c.id} className={`rounded-lg border p-2.5 ${c.flags.length ? 'border-amber-600 bg-amber-950/30' : 'border-slate-800 bg-slate-900'}`}>
          <div className="flex cursor-pointer items-center justify-between gap-2" onClick={() => setOpen(open === c.id ? null : c.id)}>
            <div className="min-w-0">
              <div className="font-semibold">
                {c.name}{c.claim_number && <span className="ml-2 font-mono text-xs text-sky-300">#{c.claim_number}</span>}
              </div>
              <div className="text-xs text-slate-400">{c.address} · {c.policy_number} · water {c.flood_depth_ft} ft</div>
            </div>
            <span className={`${chip} shrink-0 ${c.flags.length ? 'bg-amber-700 text-amber-50' : 'bg-emerald-800 text-emerald-100'}`}>
              {c.flags.length ? 'Flagged for adjuster review' : 'Verified'}</span>
          </div>
          {c.flags.length > 0 && (
            <ul className="mt-1.5 space-y-0.5 text-xs text-amber-200">{c.flags.map((f, i) => <li key={i}>⚑ {f}</li>)}</ul>
          )}
          {open === c.id && (
            <>
              {c.fnol && (
                <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 rounded bg-slate-950/60 p-2 text-xs">
                  {FNOL_LABELS.filter(([k]) => c.fnol[k] != null).map(([k, label]) => (
                    <div key={k} className="contents"><dt className="text-slate-500">{label}</dt><dd>{String(c.fnol[k])}</dd></div>
                  ))}
                  <dt className="text-slate-500">Photos</dt>
                  <dd>{c.fnol.photos?.length ? `${c.fnol.photos.length} attached` : 'Requested from policyholder'}</dd>
                </dl>
              )}
              <ol className="mt-2 space-y-1 border-l border-slate-700 pl-3 text-xs">
                {c.timeline.length ? c.timeline.map((e, i) => (
                  <li key={i}><span className="text-slate-500">{e.when}</span> <span className="text-slate-400">[{e.kind}]</span> {e.text}</li>
                )) : <li className="text-slate-500">No events recorded during the event.</li>}
              </ol>
            </>
          )}
        </div>
      ))}
    </div>
  )
}

export function Empty({ text }) {
  return <div className="p-6 text-center text-sm text-slate-500">{text}</div>
}
