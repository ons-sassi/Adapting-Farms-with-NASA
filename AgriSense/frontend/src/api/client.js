// Point d'accès unique aux données.
// Mode "api" (par défaut) : appels au backend FastAPI (backend/app/api/v1/frontend_bridge.py).
// Mode "demo" : données statiques locales, sans serveur (VITE_DATA_MODE=demo).
import { demoAnalyses, demoCrops, demoFarms, demoParcels } from '../data/demo/demoData.js'

export const DATA_MODE = import.meta.env.VITE_DATA_MODE || 'api'
// "/api/v1" passe par le proxy Vite (vite.config.js) : pas de souci de CORS en développement.
export const API_URL = import.meta.env.VITE_API_URL || '/api/v1'

const STORE_KEY = 'agrisense-demo-store'
const TOKEN_KEY = 'agrisense-token'
const USER_KEY = 'agrisense-user'
const delay = (ms = 250) => new Promise((r) => setTimeout(r, ms))

function readJson(key) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function writeJson(key, value) {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* stockage indisponible : on reste en mémoire */
  }
}

// ---------------------------------------------------------------- session ---
let token = readJson(TOKEN_KEY)
const authListeners = new Set()
export const getUser = () => readJson(USER_KEY)
export const isLoggedIn = () => DATA_MODE === 'demo' || Boolean(token)
export const onAuthChange = (fn) => { authListeners.add(fn); return () => authListeners.delete(fn) }

function setSession(newToken, user) {
  token = newToken
  writeJson(TOKEN_KEY, newToken)
  writeJson(USER_KEY, user)
  authListeners.forEach((fn) => fn(user))
}

// --------------------------------------------------------------- requêtes ---
function errorMessage(body, status) {
  const detail = body?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join(' · ')
  return `Erreur API ${status}`
}

async function http(path, { body, form, method = body || form ? 'POST' : 'GET', auth = true } = {}) {
  const headers = {}
  if (auth && token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  let res
  try {
    res = await fetch(`${API_URL}${path}`, {
      method, headers, body: form || (body !== undefined ? JSON.stringify(body) : undefined),
    })
  } catch {
    throw new Error('Serveur injoignable : vérifiez que le backend tourne (uvicorn app.main:app --reload).')
  }
  if (res.status === 401 && auth) {
    setSession(null, null) // jeton expiré : retour à l'écran de connexion
    throw new Error('Session expirée, reconnectez-vous.')
  }
  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new Error(errorMessage(data, res.status))
  return data
}

// ------------------------------------------------------------------ démo ---
let memory = readJson(STORE_KEY) || { parcels: demoParcels, analyses: demoAnalyses, savedRotations: [] }
const persist = () => writeJson(STORE_KEY, memory)

// ------------------------------------------------------------------- API ---
export const api = {
  async login(email, password) {
    const form = new URLSearchParams({ username: email, password })
    const res = await fetch(`${API_URL}/auth/login`, { method: 'POST', body: form })
      .catch(() => { throw new Error('Serveur injoignable : vérifiez que le backend tourne.') })
    const data = await res.json().catch(() => null)
    if (!res.ok) throw new Error(errorMessage(data, res.status))
    setSession(data.access_token, data.user)
    return data.user
  },
  async register(fullName, email, password) {
    await http('/auth/register', { body: { full_name: fullName, email, password }, auth: false })
    return api.login(email, password)
  },
  logout() {
    setSession(null, null)
  },

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
      return parcel.id ? http(`/parcels/${parcel.id}`, { method: 'PATCH', body: parcel }) : http('/parcels', { body: parcel })
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
    if (DATA_MODE === 'api') return http('/analyses', { body: request })
    // Démo : aucune analyse n'est calculée, on duplique le résultat de démonstration avec la saisie de l'utilisateur.
    await delay(900)
    const template = demoAnalyses[0]
    const analysis = { ...template, ...request, id: `a${Date.now()}`, createdAt: new Date().toISOString().slice(0, 10), isDemoResult: true }
    memory.analyses = [analysis, ...memory.analyses]
    persist()
    return analysis
  },
  async saveRotation(analysisId, rotation) {
    if (DATA_MODE === 'api') return http(`/analyses/${analysisId}/saved-rotations`, { body: rotation })
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
  // Chatbot (module chatbot du backend : compréhension derja -> moteur -> impact)
  async chatbotMessage({ text, parcelleId, previousCrop, nRate, lang = 'fr' }) {
    return http('/chatbot/message', { body: {
      text, lang, parcelle_id: parcelleId ? Number(parcelleId) : null,
      previous_crop: previousCrop || null, n_rate: nRate === '' || nRate == null ? null : Number(nRate),
    } })
  },
  // Sous-titres anglais d'une phrase en derja
  async chatbotCaptions(text) {
    return http('/chatbot/captions', { body: { text } })
  },
  // Réponse vocale ElevenLabs -> Blob audio/mpeg
  async chatbotSpeak(text) {
    const res = await fetch(`${API_URL}/chatbot/speak`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ text }),
    })
    if (!res.ok) throw new Error(errorMessage(await res.json().catch(() => null), res.status))
    return res.blob()
  },
  // Rapport de sol PDF/image -> { data, ph } (Gemini côté serveur)
  async extractDocument(file) {
    const form = new FormData()
    form.append('file', file)
    return http('/documents/extract', { form })
  },
  // Climat NASA POWER, sol SoilGrids, SMAP/GPM/MODIS si Earth Engine est configuré
  async parcelEnvironment(id, refresh = false) {
    if (DATA_MODE !== 'api') return null
    return http(`/parcels/${id}/environment${refresh ? '?refresh=true' : ''}`)
  },
  // Services configurés côté serveur (page Paramètres / Accueil)
  async status(check = false) {
    if (DATA_MODE !== 'api') return null
    return http(`/status${check ? '?check=true' : ''}`, { auth: false })
  },
  resetDemo() {
    memory = { parcels: demoParcels, analyses: demoAnalyses, savedRotations: [] }
    persist()
  },
}

// Noms des cultures (id -> nom), chargés une seule fois.
let cropNamesPromise = null
export function loadCropNames() {
  if (!cropNamesPromise) {
    cropNamesPromise = (DATA_MODE === 'api' ? http('/crops') : Promise.resolve(demoCrops))
      .then((crops) => Object.fromEntries(crops.map((c) => [c.id, c.name])))
      .catch((e) => { cropNamesPromise = null; throw e })
  }
  return cropNamesPromise
}
