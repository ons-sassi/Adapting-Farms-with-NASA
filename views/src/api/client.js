// Point d'accès unique aux données. Mode "demo" (actuel) : données statiques.
// Mode "api" : appels FastAPI (à brancher ; les chemins sont prévus ci-dessous).
import { demoAnalyses, demoCrops, demoFarms, demoParcels } from '../data/demo/demoData.js'

export const DATA_MODE = import.meta.env.VITE_DATA_MODE || 'demo'
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

const STORE_KEY = 'agrisense-demo-store'
const delay = (ms = 250) => new Promise((r) => setTimeout(r, ms))

function readStore() {
  try {
    const raw = localStorage.getItem(STORE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function writeStore(store) {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(store))
  } catch {
    /* stockage indisponible : la démo reste en mémoire */
  }
}

let memory = readStore() || { parcels: demoParcels, analyses: demoAnalyses, savedRotations: [] }
const persist = () => writeStore(memory)

async function http(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, { headers: { 'Content-Type': 'application/json' }, ...options })
  if (!res.ok) throw new Error(`Erreur API ${res.status}`)
  return res.json()
}

export const api = {
  async listFarms() {
    if (DATA_MODE === 'api') return http('/farms')
    await delay()
    return demoFarms
  },
  async listParcels() {
    if (DATA_MODE === 'api') return http('/parcels')
    await delay()
    return memory.parcels
  },
  async getParcel(id) {
    if (DATA_MODE === 'api') return http(`/parcels/${id}`)
    await delay()
    const parcel = memory.parcels.find((p) => p.id === id)
    if (!parcel) throw new Error('Parcelle introuvable')
    return parcel
  },
  async saveParcel(parcel) {
    if (DATA_MODE === 'api') {
      const method = parcel.id ? 'PATCH' : 'POST'
      return http(parcel.id ? `/parcels/${parcel.id}` : '/parcels', { method, body: JSON.stringify(parcel) })
    }
    await delay()
    const saved = { ...parcel, id: parcel.id || `p${Date.now()}`, updatedAt: new Date().toISOString().slice(0, 10) }
    memory.parcels = parcel.id ? memory.parcels.map((p) => (p.id === parcel.id ? saved : p)) : [saved, ...memory.parcels]
    persist()
    return saved
  },
  async deleteParcel(id) {
    if (DATA_MODE === 'api') return http(`/parcels/${id}`, { method: 'DELETE' })
    await delay()
    memory.parcels = memory.parcels.filter((p) => p.id !== id)
    persist()
  },
  async listCrops() {
    if (DATA_MODE === 'api') return http('/crops?eligible_only=true')
    await delay()
    return demoCrops
  },
  async listAnalyses() {
    if (DATA_MODE === 'api') return http('/analyses')
    await delay()
    return memory.analyses
  },
  async getAnalysis(id) {
    if (DATA_MODE === 'api') return http(`/analyses/${id}`)
    await delay()
    const analysis = memory.analyses.find((a) => a.id === id)
    if (!analysis) throw new Error('Analyse introuvable')
    return analysis
  },
  async createAnalysis(request) {
    if (DATA_MODE === 'api') return http('/analyses', { method: 'POST', body: JSON.stringify(request) })
    // Démo : aucune analyse n'est calculée, on duplique le résultat de démonstration avec la saisie de l'utilisateur.
    await delay(900)
    const template = demoAnalyses[0]
    const analysis = { ...template, ...request, id: `a${Date.now()}`, createdAt: new Date().toISOString().slice(0, 10), isDemoResult: true }
    memory.analyses = [analysis, ...memory.analyses]
    persist()
    return analysis
  },
  async saveRotation(analysisId, rotation) {
    if (DATA_MODE === 'api') return http(`/analyses/${analysisId}/saved-rotations`, { method: 'POST', body: JSON.stringify(rotation) })
    await delay()
    const saved = { ...rotation, analysisId, savedAt: new Date().toISOString().slice(0, 10) }
    memory.savedRotations = [saved, ...memory.savedRotations.filter((r) => !(r.id === rotation.id && r.analysisId === analysisId))]
    persist()
    return saved
  },
  async listSavedRotations() {
    if (DATA_MODE === 'api') return http('/saved-rotations')
    await delay()
    return memory.savedRotations
  },
  resetDemo() {
    memory = { parcels: demoParcels, analyses: demoAnalyses, savedRotations: [] }
    persist()
  },
}
