// DONNÉES DE DÉMONSTRATION — statiques, fictives, uniquement pour l'affichage de l'interface.
// Elles seront remplacées par les réponses de l'API FastAPI (voir src/api/client.js).

export const demoUser = { initials: 'BH', name: 'Agriculteur démo' }

export const demoFarms = [
  { id: 'farm-kairouan', name: 'Exploitation Kairouan' },
  { id: 'farm-beja', name: 'Exploitation Béja' },
]

export const demoParcels = [
  {
    id: 'p1', farmId: 'farm-kairouan', name: 'Parcelle Nord', crop: 'Blé dur', areaHa: 5.2, updatedAt: '2026-10-28',
    irrigation: 'Goutte-à-goutte (limitée)', zone: 'Dorsale et Tell (Kairouan)', ph: 7.8, status: 'ok',
    geometry: [[35.6838, 10.0952], [35.6851, 10.1004], [35.6812, 10.1021], [35.6798, 10.0967]],
  },
  {
    id: 'p2', farmId: 'farm-kairouan', name: 'Parcelle Oued', crop: 'Orge', areaHa: 3.4, updatedAt: '2026-10-21',
    irrigation: 'Pluviale', zone: 'Dorsale et Tell (Kairouan)', ph: 8.1, status: 'warning',
    geometry: [[35.6782, 10.1032], [35.6795, 10.1081], [35.6761, 10.1094], [35.6749, 10.1046]],
  },
  {
    id: 'p3', farmId: 'farm-kairouan', name: 'Parcelle Sud', crop: 'Pois chiche', areaHa: 2.1, updatedAt: '2026-09-30',
    irrigation: 'Pluviale', zone: 'Dorsale et Tell (Kairouan)', ph: 7.4, status: 'ok',
    geometry: [[35.6745, 10.0958], [35.6760, 10.0999], [35.6731, 10.1012], [35.6718, 10.0973]],
  },
  {
    id: 'p4', farmId: 'farm-beja', name: 'Parcelle Colline', crop: 'Féverole', areaHa: 6.8, updatedAt: '2026-10-11',
    irrigation: 'Pluviale', zone: 'Sub-humide', ph: 6.9, status: 'alert',
    geometry: [[36.7262, 9.1795], [36.7281, 9.1858], [36.7240, 9.1877], [36.7224, 9.1816]],
  },
]

export const demoCrops = [
  { id: 'ble-dur', name: 'Blé dur', family: 'Poacées', type: 'Céréale', season: 'Hiver', cycle: '210–240 j', water: 'Moyen', soil: 'Argileux à limoneux', nFixer: false },
  { id: 'ble-tendre', name: 'Blé tendre', family: 'Poacées', type: 'Céréale', season: 'Hiver', cycle: '210–240 j', water: 'Moyen', soil: 'Limoneux', nFixer: false },
  { id: 'orge', name: 'Orge', family: 'Poacées', type: 'Céréale', season: 'Hiver', cycle: '180–210 j', water: 'Faible', soil: 'Tolérant', nFixer: false },
  { id: 'avoine', name: 'Avoine', family: 'Poacées', type: 'Céréale / fourrage', season: 'Hiver', cycle: '165–240 j', water: 'Moyen', soil: 'Tolérant', nFixer: false },
  { id: 'mais', name: 'Maïs', family: 'Poacées', type: 'Céréale', season: 'Été', cycle: '120–150 j', water: 'Élevé', soil: 'Profond, drainé', nFixer: false },
  { id: 'sorgho', name: 'Sorgho', family: 'Poacées', type: 'Céréale', season: 'Été', cycle: '120–140 j', water: 'Faible', soil: 'Tolérant', nFixer: false },
  { id: 'pois-chiche', name: 'Pois chiche', family: 'Fabacées', type: 'Légumineuse', season: 'Hiver / printemps', cycle: '90–180 j', water: 'Faible', soil: 'Bien drainé', nFixer: true },
  { id: 'lentille', name: 'Lentille', family: 'Fabacées', type: 'Légumineuse', season: 'Hiver', cycle: '150–210 j', water: 'Faible', soil: 'Limoneux', nFixer: true },
  { id: 'feve', name: 'Fève / féverole', family: 'Fabacées', type: 'Légumineuse', season: 'Hiver', cycle: '150–235 j', water: 'Moyen', soil: 'Argileux', nFixer: true },
  { id: 'luzerne', name: 'Luzerne', family: 'Fabacées', type: 'Fourrage', season: 'Pérenne', cycle: 'Pluriannuelle', water: 'Élevé', soil: 'Profond, calcaire', nFixer: true },
  { id: 'tournesol', name: 'Tournesol', family: 'Astéracées', type: 'Oléagineux', season: 'Printemps', cycle: '130–180 j', water: 'Moyen', soil: 'Profond', nFixer: false },
  { id: 'tomate', name: 'Tomate', family: 'Solanacées', type: 'Maraîchage', season: 'Printemps / été', cycle: '120–180 j', water: 'Élevé', soil: 'Léger, riche', nFixer: false },
  { id: 'pomme-de-terre', name: 'Pomme de terre', family: 'Solanacées', type: 'Maraîchage', season: 'Hiver / printemps', cycle: '90–140 j', water: 'Élevé', soil: 'Léger', nFixer: false },
]

export const priorityCriteria = [
  { id: 'water', label: "Économie d'eau", hint: 'Réduire la consommation et le gaspillage' },
  { id: 'yield', label: 'Rendement', hint: 'Maximiser la production' },
  { id: 'soil', label: 'Santé et fertilité du sol', hint: 'Matière organique, azote, structure' },
  { id: 'profit', label: 'Rentabilité économique', hint: 'Marge par hectare' },
  { id: 'resilience', label: 'Résilience climatique', hint: 'Sécheresse, chaleur, gel' },
  { id: 'pests', label: 'Maladies et ravageurs', hint: 'Casser les cycles' },
  { id: 'sustainability', label: 'Durabilité', hint: 'Équilibre sur le long terme' },
]

// Les 6 sous-scores du moteur de rotation du backend (app/engine/rotation), sur 100.
export const compositeIndices = [
  { id: 'eau', label: "Disponibilité et efficacité de l'eau", short: 'Eau' },
  { id: 'climat_thermique', label: 'Adaptation climatique (calendrier de la zone)', short: 'Climat' },
  { id: 'fertilite_sol', label: 'Fertilité du sol (légumineuses, pH)', short: 'Sol' },
  { id: 'protection_erosion', label: "Protection contre l'érosion", short: 'Érosion' },
  { id: 'dynamique_vegetative', label: 'Dynamique végétative (NDVI, nécessite Earth Engine)', short: 'Végét.' },
  { id: 'compatibilite_succession', label: 'Compatibilité des successions', short: 'Succession' },
]

export const demoAnalyses = [
  {
    id: 'a1', parcelId: 'p1', createdAt: '2026-11-10', horizon: 4,
    crops: ['ble-dur', 'orge', 'pois-chiche', 'feve', 'sorgho'],
    priorities: { water: 5, yield: 3, soil: 4, profit: 3, resilience: 4, pests: 2, sustainability: 3 },
    recommendedId: 'r2',
    rotations: [
      {
        id: 'r1', name: "Économie d'eau", strategy: 'water', score: 74,
        years: ['orge', 'pois-chiche', 'orge', 'sorgho'],
        indices: { eau: 81, climat_thermique: 62, fertilite_sol: 70, protection_erosion: 66, dynamique_vegetative: null, compatibilite_succession: 72 },
        pros: ['Cultures sobres en eau', 'Une légumineuse dans la rotation'],
        cons: ['Rendement potentiel plus faible'],
        risks: ['Sorgho : semis de printemps dépendant des pluies'],
        explanation: "Privilégie les cultures à faible besoin en eau pour une parcelle à irrigation limitée.",
      },
      {
        id: 'r2', name: 'Équilibrée sol et résilience', strategy: 'soil', score: 82,
        years: ['ble-dur', 'feve', 'orge', 'pois-chiche'],
        indices: { eau: 72, climat_thermique: 84, fertilite_sol: 78, protection_erosion: 80, dynamique_vegetative: null, compatibilite_succession: 85 },
        pros: ['Deux légumineuses : apport d\'azote', 'Familles alternées : cycles de ravageurs rompus'],
        cons: ['Besoin en eau moyen la 1re année'],
        risks: ['Féverole sensible au gel tardif en bas-fond'],
        explanation: "Alterne céréales et légumineuses pour enrichir le sol et limiter les maladies, tout en restant adaptée au climat.",
      },
      {
        id: 'r3', name: 'Rendement et rentabilité', strategy: 'yield', score: 69,
        years: ['ble-dur', 'ble-dur', 'feve', 'ble-dur'],
        indices: { eau: 58, climat_thermique: 61, fertilite_sol: 83, protection_erosion: 64, dynamique_vegetative: null, compatibilite_succession: 50 },
        pros: ['Blé dur bien valorisé sur le marché'],
        cons: ['Blé répété : fatigue du sol', 'Une seule légumineuse'],
        risks: ['Pression des maladies des céréales'],
        explanation: 'Maximise la part de blé dur, au prix d\'une diversité plus faible.',
      },
    ],
  },
]

export const demoSoilSummary = { ph: 7.8, texture: 'Argileuse', organicMatter: '1,2 %', source: 'Démonstration' }

export const chatSuggestions = [
  'Quel est le risque pour mon blé ?',
  'Quelles cultures alternatives ?',
  "Comment améliorer l'infiltration ?",
]

export const chatDemoAnswers = {
  'Quel est le risque pour mon blé ?':
    "Exemple de réponse : votre parcelle présente un risque modéré de stress hydrique au printemps. Ce message est une démonstration, l'assistant n'est pas encore connecté aux données.",
  'Quelles cultures alternatives ?':
    "Exemple de réponse : une légumineuse comme le pois chiche ou la féverole pourrait remplacer une année de céréale. Démonstration uniquement.",
  "Comment améliorer l'infiltration ?":
    "Exemple de réponse : limiter les périodes de sol nu avec une culture de couverture. Démonstration uniquement.",
}
