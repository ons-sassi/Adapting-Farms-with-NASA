import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import { AnalysisProvider } from './components/AnalysisContext.jsx'
import Home from './pages/Home.jsx'
import Parcels from './pages/Parcels.jsx'
import ParcelEditor from './pages/ParcelEditor.jsx'
import CropSelection from './pages/CropSelection.jsx'
import Priorities from './pages/Priorities.jsx'
import AnalysisSummary from './pages/AnalysisSummary.jsx'
import Results from './pages/Results.jsx'
import Analyses from './pages/Analyses.jsx'
import Chatbot from './pages/Chatbot.jsx'
import Settings from './pages/Settings.jsx'

export default function App() {
  return (
    <AnalysisProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="terrains" element={<Parcels />} />
          <Route path="terrains/nouveau" element={<ParcelEditor />} />
          <Route path="terrains/:parcelId" element={<ParcelEditor />} />
          <Route path="analyse/cultures" element={<CropSelection />} />
          <Route path="analyse/priorites" element={<Priorities />} />
          <Route path="analyse/recapitulatif" element={<AnalysisSummary />} />
          <Route path="analyses" element={<Analyses />} />
          <Route path="analyses/:analysisId" element={<Results />} />
          <Route path="chatbot" element={<Chatbot />} />
          <Route path="parametres" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </AnalysisProvider>
  )
}
