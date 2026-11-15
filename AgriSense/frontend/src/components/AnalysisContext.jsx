import { createContext, useContext, useState } from 'react'

const DEFAULT_PRIORITIES = { water: 3, yield: 3, soil: 3, profit: 3, resilience: 3, pests: 3, sustainability: 3 }
const DEFAULT_CONSTRAINTS = { budget: '', irrigation: 'limited', equipment: '', forbidden: [], horizon: 4 }

const AnalysisContext = createContext(null)

export function AnalysisProvider({ children }) {
  const [draft, setDraft] = useState({ parcelId: null, crops: [], priorities: DEFAULT_PRIORITIES, constraints: DEFAULT_CONSTRAINTS })
  const update = (patch) => setDraft((d) => ({ ...d, ...patch }))
  const reset = () => setDraft({ parcelId: null, crops: [], priorities: DEFAULT_PRIORITIES, constraints: DEFAULT_CONSTRAINTS })
  return <AnalysisContext.Provider value={{ draft, update, reset }}>{children}</AnalysisContext.Provider>
}

export const useAnalysisDraft = () => useContext(AnalysisContext)
export const ANALYSIS_STEPS = ['Parcelle', 'Cultures', 'Priorités', 'Récapitulatif']
