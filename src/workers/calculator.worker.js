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
    self.postMessage({
      id: data.id,
      error: 'The local V5 solver is unavailable. Start the app with npm start.',
    })
  }
}
