import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import type { Dataset } from '../lib/types'

export const DATASET_LABELS: Record<Dataset, string> = {
  olist: 'Olist (Brazil)',
  us: 'US E-Commerce',
}

export const DATASET_SHORT_LABELS: Record<Dataset, string> = {
  olist: 'Olist',
  us: 'US',
}

interface DatasetState {
  dataset: Dataset
  setDataset: (d: Dataset) => void
}

const DatasetContext = createContext<DatasetState | null>(null)

function loadStored(): Dataset {
  const raw = localStorage.getItem('dataset')
  return raw === 'us' ? 'us' : 'olist'
}

export function DatasetProvider({ children }: { children: ReactNode }) {
  const [dataset, setDatasetState] = useState<Dataset>(loadStored)

  const setDataset = useCallback((d: Dataset) => {
    localStorage.setItem('dataset', d)
    setDatasetState(d)
  }, [])

  return <DatasetContext.Provider value={{ dataset, setDataset }}>{children}</DatasetContext.Provider>
}

export function useDataset() {
  const ctx = useContext(DatasetContext)
  if (!ctx) throw new Error('useDataset must be used within DatasetProvider')
  return ctx
}
