import { calculateLoads } from '../lib/loadCalculator.js'

self.onmessage = async ({ data }) => {
  try {
    const response = await fetch('/api/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data.carton),
    })
    if (!response.ok) throw new Error('Local V5 service unavailable')
    self.postMessage({ id: data.id, result: await response.json() })
  } catch {
    // GitHub Pages is static, so it uses the geometry-validated browser V5
    // solver. Local hosting prefers the Python CP-SAT service above.
    try {
      self.postMessage({ id: data.id, result: calculateLoads(data.carton) })
    } catch {
      self.postMessage({ id: data.id, error: 'The calculation could not be completed.' })
    }
  }
}
