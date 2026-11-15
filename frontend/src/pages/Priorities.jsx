import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { api } from '../api/client.js'
import { priorityCriteria } from '../data/demo/demoData.js'
import { ANALYSIS_STEPS, useAnalysisDraft } from '../components/AnalysisContext.jsx'
import { Card, PageHeader, Stepper } from '../components/ui.jsx'

const LEVELS = ['Ignoré', 'Faible', 'Modéré', 'Important', 'Très important', 'Essentiel']

export default function Priorities() {
  const navigate = useNavigate()
  const { draft, update } = useAnalysisDraft()
  const [crops, setCrops] = useState([])
  const { priorities, constraints } = draft

  useEffect(() => { api.listCrops().then(setCrops).catch(() => setCrops([])) }, [])

  const setPriority = (id, value) => update({ priorities: { ...priorities, [id]: Number(value) } })
  const setConstraint = (patch) => update({ constraints: { ...constraints, ...patch } })
  const toggleForbidden = (id) => setConstraint({
    forbidden: constraints.forbidden.includes(id) ? constraints.forbidden.filter((c) => c !== id) : [...constraints.forbidden, id],
  })

  return (
    <>
      <PageHeader back="/analyse/cultures" title="Vos priorités" subtitle="Indiquez l'importance de chaque critère pour votre exploitation." />
      <Stepper steps={ANALYSIS_STEPS} current={2} />

      <div className="two-cols wide-left">
        <Card>
          <h3>Importance des critères</h3>
          <div className="priority-list">
            {priorityCriteria.map((c) => (
              <div className="priority" key={c.id}>
                <div><strong>{c.label}</strong><small>{c.hint}</small></div>
                <input type="range" min="0" max="5" value={priorities[c.id]} onChange={(e) => setPriority(c.id, e.target.value)} aria-label={c.label} />
                <span className={`level level-${priorities[c.id]}`}>{LEVELS[priorities[c.id]]}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h3>Contraintes</h3>
          <div className="form-grid single">
            <label>Durée de planification
              <div className="segmented">
                {[3, 4].map((y) => <button type="button" key={y} className={constraints.horizon === y ? 'active' : ''} onClick={() => setConstraint({ horizon: y })}>{y} ans</button>)}
              </div>
            </label>
            <label>Irrigation disponible
              <select value={constraints.irrigation} onChange={(e) => setConstraint({ irrigation: e.target.value })}>
                <option value="none">Aucune (pluvial)</option><option value="limited">Limitée</option><option value="full">Complète</option>
              </select>
            </label>
            <label>Budget (DT / ha / an)<input type="number" min="0" value={constraints.budget} onChange={(e) => setConstraint({ budget: e.target.value })} placeholder="Facultatif" /></label>
            <label>Matériel disponible<input value={constraints.equipment} onChange={(e) => setConstraint({ equipment: e.target.value })} placeholder="Ex. semoir céréales, pas de récolteuse à pommes de terre" /></label>
          </div>
          <h4>Cultures interdites</h4>
          <div className="chips-select">
            {crops.filter((c) => draft.crops.includes(c.id)).map((c) => (
              <button type="button" key={c.id} className={constraints.forbidden.includes(c.id) ? 'chip-on danger' : ''} onClick={() => toggleForbidden(c.id)}>{c.name}</button>
            ))}
            {draft.crops.length === 0 && <small className="muted">Choisissez d'abord des cultures.</small>}
          </div>
        </Card>
      </div>

      <div className="center-actions">
        <button className="btn btn-primary btn-lg" onClick={() => navigate('/analyse/recapitulatif')}>Continuer <ArrowRight size={18} /></button>
      </div>
    </>
  )
}
