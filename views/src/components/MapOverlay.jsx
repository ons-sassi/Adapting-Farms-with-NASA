import { useEffect, useLayoutEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Check, X } from 'lucide-react'
import { ParcelDrawMap, polygonAreaHa } from './ParcelMap.jsx'

// Carte plein écran : s'agrandit depuis l'aperçu (originRect) jusqu'à couvrir toute la page.
export default function MapOverlay({ originRect, geometry, onChange, onClose }) {
  const [open, setOpen] = useState(false)
  const [ready, setReady] = useState(false)

  const r = originRect || { top: window.innerHeight / 2, left: window.innerWidth / 2, width: 0, height: 0 }
  const closed = `inset(${r.top}px ${window.innerWidth - r.left - r.width}px ${window.innerHeight - r.top - r.height}px ${r.left}px round 20px)`

  useLayoutEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const id = requestAnimationFrame(() => requestAnimationFrame(() => setOpen(true)))
    const t = setTimeout(() => setReady(true), 350)
    return () => { document.body.style.overflow = prev; cancelAnimationFrame(id); clearTimeout(t) }
  }, [])

  const close = () => { setReady(false); setOpen(false); setTimeout(onClose, 520) }

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && close()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const ha = geometry?.length >= 3 ? polygonAreaHa(geometry) : 0

  return createPortal(
    <div className={`mo ${open ? 'open' : ''}`} style={{ clipPath: open ? 'inset(0 0 0 0 round 0px)' : closed }} role="dialog" aria-label="Délimiter le terrain">
      <header className="mo-head">
        <div>
          <strong>Délimitez votre terrain</strong>
          <small>Entourez-le au crayon, quelle que soit sa forme</small>
        </div>
        <button type="button" className="mo-x" onClick={close} aria-label="Fermer"><X size={20} /></button>
      </header>
      <div className="mo-map">
        {ready || open ? <ParcelDrawMap geometry={geometry} onChange={onChange} height="100%" search /> : null}
      </div>
      <footer className="mo-foot">
        <span className="mo-area">{ha ? <><b>{ha.toFixed(2)}</b> ha · {geometry.length} sommets</> : 'Aucun terrain dessiné'}</span>
        <button type="button" className="btn btn-primary btn-lg" disabled={!ha} onClick={close}><Check size={18} /> Valider ce terrain</button>
      </footer>
    </div>,
    document.body,
  )
}
