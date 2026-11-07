import { useEffect } from 'react'
import { CircleMarker, MapContainer, Rectangle, TileLayer, Tooltip, useMap } from 'react-leaflet'
import { scoreColor, STATUS_LABEL } from './api'

const CENTER = [29.76, -95.37]

function FlyTo({ target }) {
  const map = useMap()
  useEffect(() => {
    if (target) map.flyTo(target, 16, { duration: 0.8 })
  }, [target, map])
  return null
}

function blockStyle(b, showSilence, maxPriority) {
  if (showSilence && b.flood_depth_ft > 0) {
    const p = maxPriority ? b.priority / maxPriority : 0
    return {
      color: b.flagged ? '#E31837' : '#f59e0b',
      weight: b.flagged ? 3 : 0.5,
      dashArray: b.flagged ? '6 4' : null,
      fillColor: b.flagged ? '#E31837' : '#f59e0b',
      fillOpacity: b.flagged ? 0.35 : 0.05 + 0.3 * p,
      className: b.flagged ? 'pulse-block' : '',
    }
  }
  const d = b.flood_depth_ft
  return {
    color: '#1e3a8a', weight: 0.4,
    fillColor: '#3b82f6', fillOpacity: d > 0 ? Math.min(0.55, 0.08 + d * 0.08) : 0,
  }
}

export default function MapView({ state, showSilence, selectedId, onSelect, flyTarget }) {
  const maxPriority = Math.max(0, ...state.blocks.map((b) => b.priority))
  return (
    <MapContainer center={CENTER} zoom={15} className="h-full w-full" zoomControl={false} preferCanvas>
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        className="dark-tiles"
      />
      <FlyTo target={flyTarget} />
      {state.blocks.map((b) => (
        <Rectangle
          key={`${b.id}-${showSilence}-${b.flagged}`}
          bounds={[[b.bounds[0], b.bounds[1]], [b.bounds[2], b.bounds[3]]]}
          pathOptions={blockStyle(b, showSilence, maxPriority)}
        >
          <Tooltip sticky>
            <div className="text-xs">
              <b>Block {b.id}</b> · water {b.flood_depth_ft} ft{b.power_out ? ' · power out' : ''}
              <br />Replies {b.replies} / expected {b.expected} · vulnerability {b.svi}
              {b.flagged && <><br /><b style={{ color: '#f87171' }}>Unusually quiet: flagged for sweep</b></>}
            </div>
          </Tooltip>
        </Rectangle>
      ))}
      {state.shelters.map((s) => (
        <CircleMarker key={s.id} center={[s.lat, s.lng]} radius={9}
          pathOptions={{ color: '#22c55e', weight: 3, fillColor: '#052e16', fillOpacity: 1 }}>
          <Tooltip direction="top">
            <div className="text-xs"><b>Shelter: {s.name}</b><br />{s.capacity - s.occupancy} beds free
              {s.wheelchair ? ' · wheelchair' : ''}{s.backup_power ? ' · backup power' : ''}{s.infant_supplies ? ' · infant supplies' : ''}</div>
          </Tooltip>
        </CircleMarker>
      ))}
      {state.teams.map((t) => (
        <CircleMarker key={t.id} center={[t.lat, t.lng]} radius={7}
          pathOptions={{ color: t.status === 'busy' ? '#60a5fa' : '#e2e8f0', weight: 2, fillColor: '#1e293b', fillOpacity: 1 }}>
          <Tooltip direction="top"><div className="text-xs"><b>{t.name}</b> · {t.status}</div></Tooltip>
        </CircleMarker>
      ))}
      {state.pins.filter((p) => p.in_zone || p.status !== 'unreached').map((p) => {
        const sel = p.id === selectedId
        const color = scoreColor(p.score, p.status)
        return (
          <CircleMarker key={p.id} center={[p.lat, p.lng]} radius={sel ? 10 : p.score >= 70 ? 6 : 4}
            eventHandlers={{ click: () => onSelect(p.id) }}
            pathOptions={{
              color: sel ? '#ffffff' : p.status === 'assigned' ? '#60a5fa' : color,
              weight: sel ? 3 : p.status === 'assigned' ? 2 : 1,
              fillColor: color, fillOpacity: p.status === 'unreached' ? 0.35 : 0.9,
            }}>
            <Tooltip direction="top">
              <div className="text-xs"><b>{p.name}</b><br />Score {p.score} · {STATUS_LABEL[p.status]}</div>
            </Tooltip>
          </CircleMarker>
        )
      })}
    </MapContainer>
  )
}
