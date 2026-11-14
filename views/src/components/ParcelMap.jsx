import { useEffect, useRef, useState } from 'react'
import { Move, Pencil, PenTool, Search, Trash2 } from 'lucide-react'
import { LayersControl, MapContainer, Polygon, TileLayer, Tooltip, useMap } from 'react-leaflet'
import L from 'leaflet'
import '@geoman-io/leaflet-geoman-free'

const STATUS_COLORS = { ok: '#3f9d3f', warning: '#e0a526', alert: '#d6513b', selected: '#1f6f3a' }

function FitBounds({ positions }) {
  const map = useMap()
  const key = JSON.stringify(positions)  // on ne recadre que si les parcelles changent vraiment
  useEffect(() => {
    if (positions.length) map.fitBounds(L.latLngBounds(positions.flat()), { padding: [30, 30] })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, key])
  return null
}

// Zoom automatique, animé, sur la parcelle sélectionnée (clic sur la carte ou dans la liste)
function FlyToSelected({ parcels, selectedId, tick }) {
  const map = useMap()
  const first = useRef(true)
  useEffect(() => {
    if (first.current) { first.current = false; return }   // au chargement : vue d'ensemble
    const geo = parcels.find((p) => p.id === selectedId)?.geometry
    if (geo?.length) map.flyToBounds(L.latLngBounds(geo), { padding: [70, 70], maxZoom: 18, duration: 1.1 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, tick])
  return null
}

function ShowAllButton({ positions }) {
  const map = useMap()
  const ref = useRef(null)
  useEffect(() => { if (ref.current) L.DomEvent.disableClickPropagation(ref.current) }, [])
  return (
    <button ref={ref} type="button" className="map-showall" onClick={() => positions.length && map.flyToBounds(L.latLngBounds(positions.flat()), { padding: [30, 30], duration: 1 })}>
      Tout voir
    </button>
  )
}

// Douglas-Peucker (en pixels) pour lisser le tracé à main levée
function simplify(pts, tol) {
  if (pts.length < 3) return pts
  const d2 = (p, a, b) => {
    let x = a.x, y = a.y, dx = b.x - x, dy = b.y - y
    if (dx || dy) {
      const t = Math.max(0, Math.min(1, ((p.x - x) * dx + (p.y - y) * dy) / (dx * dx + dy * dy)))
      x += dx * t; y += dy * t
    }
    return (p.x - x) ** 2 + (p.y - y) ** 2
  }
  const keep = new Array(pts.length).fill(false)
  keep[0] = keep[pts.length - 1] = true
  const stack = [[0, pts.length - 1]]
  while (stack.length) {
    const [a, b] = stack.pop()
    let max = 0, idx = -1
    for (let i = a + 1; i < b; i++) {
      const d = d2(pts[i], pts[a], pts[b])
      if (d > max) { max = d; idx = i }
    }
    if (max > tol * tol && idx > -1) { keep[idx] = true; stack.push([a, idx], [idx, b]) }
  }
  return pts.filter((_, i) => keep[i])
}

function DrawControl({ onChange, initial }) {
  const map = useMap()
  const polyRef = useRef(null)
  const [tool, setTool] = useState('pencil') // pencil | polygon | edit | none
  const toolRef = useRef(tool)
  toolRef.current = tool
  const emit = () => onChange(polyRef.current ? polyRef.current.getLatLngs()[0].map((p) => [p.lat, p.lng]) : [])

  const setPoly = (layer) => {
    if (polyRef.current) polyRef.current.remove()
    polyRef.current = layer
    if (layer) {
      layer.addTo(map)
      layer.on('pm:edit', emit)
      layer.on('pm:dragend', emit)
    }
  }

  // polygone initial
  useEffect(() => {
    if (initial?.length) {
      setPoly(L.polygon(initial, { color: STATUS_COLORS.selected, weight: 3, fillOpacity: 0.3 }))
      setTool('edit')
    }
    return () => { polyRef.current?.remove(); polyRef.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map])

  // crayon : tracé libre au doigt / à la souris, quelle que soit la forme du terrain
  useEffect(() => {
    const el = map.getContainer()
    let drawing = false, pts = [], line = null
    const lat = (e) => map.mouseEventToLatLng(e)
    const down = (e) => {
      if (toolRef.current !== 'pencil' || e.target.closest('.draw-bar, .leaflet-control')) return
      drawing = true
      pts = [lat(e)]
      line = L.polyline(pts, { color: '#ffffff', weight: 4, dashArray: '2 6', interactive: false }).addTo(map)
      map.dragging.disable()
      el.setPointerCapture?.(e.pointerId)
      e.preventDefault()
    }
    const move = (e) => {
      if (!drawing) return
      pts.push(lat(e))
      line.setLatLngs(pts)
    }
    const up = () => {
      if (!drawing) return
      drawing = false
      map.dragging.enable()
      line.remove()
      const px = simplify(pts.map((ll) => map.latLngToContainerPoint(ll)), 3)
      if (px.length >= 3) {
        const ll = px.map((p) => map.containerPointToLatLng(p))
        setPoly(L.polygon(ll, { color: STATUS_COLORS.selected, weight: 3, fillOpacity: 0.3 }))
        emit()
        setTool('edit')
      }
    }
    el.addEventListener('pointerdown', down)
    el.addEventListener('pointermove', move)
    el.addEventListener('pointerup', up)
    el.addEventListener('pointercancel', up)
    return () => {
      el.removeEventListener('pointerdown', down)
      el.removeEventListener('pointermove', move)
      el.removeEventListener('pointerup', up)
      el.removeEventListener('pointercancel', up)
      map.dragging.enable()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map])

  // polygone point par point
  useEffect(() => {
    if (tool !== 'polygon') return
    map.pm.enableDraw('Polygon', { snappable: false, templineStyle: { color: '#fff' }, pathOptions: { color: STATUS_COLORS.selected, weight: 3, fillOpacity: 0.3 } })
    const onCreate = (e) => { setPoly(e.layer); e.layer.remove(); e.layer.addTo(map); emit(); setTool('edit') }
    map.on('pm:create', onCreate)
    return () => { map.off('pm:create', onCreate); map.pm.disableDraw() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tool])

  // modification des sommets
  useEffect(() => {
    const layer = polyRef.current
    if (tool === 'edit' && layer) layer.pm.enable({ allowSelfIntersection: true, draggable: true })
    return () => { layer?.pm?.disable?.() }
  }, [tool])

  useEffect(() => { map.getContainer().style.cursor = tool === 'pencil' ? 'crosshair' : '' }, [tool, map])

  const bar = useRef(null)
  useEffect(() => { if (bar.current) { L.DomEvent.disableClickPropagation(bar.current); L.DomEvent.disableScrollPropagation(bar.current) } }, [])

  const clear = () => { setPoly(null); onChange([]); setTool('pencil') }
  const Btn = ({ id, icon: Icon, label, onClick, danger }) => (
    <button type="button" className={`draw-btn ${tool === id ? 'on' : ''} ${danger ? 'danger' : ''}`} onClick={onClick || (() => setTool(id))}>
      <Icon size={18} /><span>{label}</span>
    </button>
  )
  return (
    <div className="draw-bar" ref={bar}>
      <Btn id="pencil" icon={Pencil} label="Crayon" />
      <Btn id="polygon" icon={PenTool} label="Points" />
      <Btn id="edit" icon={Move} label="Ajuster" onClick={() => polyRef.current && setTool('edit')} />
      <Btn id="clear" icon={Trash2} label="Effacer" onClick={clear} danger />
      {tool === 'pencil' && <p className="draw-hint">Entourez votre terrain en tenant le doigt ou la souris appuyé(e).</p>}
    </div>
  )
}

function SearchBox() {
  const map = useMap()
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const ref = useRef(null)
  useEffect(() => { if (ref.current) L.DomEvent.disableClickPropagation(ref.current) }, [])
  const go = async (e) => {
    e.preventDefault()
    if (!q.trim()) return
    setBusy(true)
    try {
      const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(q)}`)
      const [hit] = await r.json()
      if (hit) map.flyTo([+hit.lat, +hit.lon], 16, { duration: 1.2 })
    } catch { /* hors ligne : on ignore */ }
    setBusy(false)
  }
  return (
    <form className="map-search" ref={ref} onSubmit={go}>
      <Search size={17} />
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher un lieu, un village…" />
      <button type="submit" disabled={busy}>{busy ? '…' : 'Aller'}</button>
    </form>
  )
}

function AutoResize() {
  const map = useMap()
  useEffect(() => {
    const ro = new ResizeObserver(() => map.invalidateSize())
    ro.observe(map.getContainer())
    return () => ro.disconnect()
  }, [map])
  return null
}

const TILES = (
  <LayersControl position="topright">
    <LayersControl.BaseLayer checked name="Satellite">
      <TileLayer attribution="Imagery © Esri" url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" />
    </LayersControl.BaseLayer>
    <LayersControl.BaseLayer name="Plan">
      <TileLayer attribution="© OpenStreetMap" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
    </LayersControl.BaseLayer>
  </LayersControl>
)

export function ParcelsOverviewMap({ parcels, selectedId, onSelect, height = 520 }) {
  const [tick, setTick] = useState(0)
  const positions = parcels.map((p) => p.geometry).filter(Boolean)
  return (
    <MapContainer className="map" style={{ height }} center={[35.68, 10.1]} zoom={14} scrollWheelZoom>
      {TILES}
      <FitBounds positions={positions} />
      <FlyToSelected parcels={parcels} selectedId={selectedId} tick={tick} />
      <ShowAllButton positions={positions} />
      {parcels.map((p) => (
        <Polygon key={p.id} positions={p.geometry}
          pathOptions={{ color: p.id === selectedId ? '#ffffff' : STATUS_COLORS[p.status] || STATUS_COLORS.ok,
            fillColor: STATUS_COLORS[p.status] || STATUS_COLORS.ok, fillOpacity: p.id === selectedId ? 0.55 : 0.35, weight: p.id === selectedId ? 3 : 2 }}
          eventHandlers={{ click: () => { onSelect?.(p.id); setTick((t) => t + 1) } }}>
          <Tooltip permanent direction="center" className="parcel-label">{p.name}<br />pH {p.ph}</Tooltip>
        </Polygon>
      ))}
    </MapContainer>
  )
}

export function ParcelDrawMap({ geometry, onChange, height = 460, search = false }) {
  return (
    <MapContainer className="map" style={{ height }} center={geometry?.[0] || [35.68, 10.1]} zoom={15} scrollWheelZoom>
      {TILES}
      {geometry?.length ? <FitBounds positions={[geometry]} /> : null}
      <AutoResize />
      {search && <SearchBox />}
      <DrawControl onChange={onChange} initial={geometry} />
    </MapContainer>
  )
}

export function polygonAreaHa(latlngs) {
  if (!latlngs || latlngs.length < 3) return 0
  const R = 6378137
  let area = 0
  for (let i = 0; i < latlngs.length; i++) {
    const [lat1, lon1] = latlngs[i]
    const [lat2, lon2] = latlngs[(i + 1) % latlngs.length]
    area += ((lon2 - lon1) * Math.PI / 180) * (2 + Math.sin(lat1 * Math.PI / 180) + Math.sin(lat2 * Math.PI / 180))
  }
  return Math.abs((area * R * R) / 2) / 10000
}
