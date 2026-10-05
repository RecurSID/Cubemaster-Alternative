import { calculateLoads } from '../lib/loadCalculator.js'

self.onmessage = ({ data }) => {
  try {
    self.postMessage({ id: data.id, result: calculateLoads(data.carton) })
  } catch {
    self.postMessage({ id: data.id, error: 'The calculation could not be completed.' })
  }
}
