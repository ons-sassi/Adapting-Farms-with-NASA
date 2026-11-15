import { useEffect, useState } from 'react'
import { loadCropNames } from '../api/client.js'

// Retourne une fonction id -> nom de culture (catalogue du backend ou de la démo).
export function useCropNames() {
  const [names, setNames] = useState({})
  useEffect(() => { loadCropNames().then(setNames).catch(() => {}) }, [])
  return (id) => names[id] || id
}
