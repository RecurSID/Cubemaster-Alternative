import { useEffect, useRef, useState } from 'react'

const fields = [
  { key: 'length', label: 'Length', placeholder: '600' },
  { key: 'width', label: 'Width', placeholder: '400' },
  { key: 'height', label: 'Height', placeholder: '300' },
]

const formatNumber = (value) => String(value)

function ResultCard({ title, eyebrow, result }) {
  if (!result) {
    return (
      <article className="result-card result-card--empty">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
        </div>
        <p className="no-fit">Carton does not fit.</p>
      </article>
    )
  }

  const details = [
    ['Per layer', formatNumber(result.cartonsPerLayer)],
    ['Layers', formatNumber(result.layers)],
    [
      'Orientation',
      `${result.orientation.length} × ${result.orientation.width} × ${result.orientation.height} mm`,
    ],
    ['Loaded height', `${formatNumber(result.loadedHeight)} mm`],
  ]

  return (
    <article className="result-card">
      <div className="result-heading">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
        </div>
        <span className="status-dot" aria-label="Calculated" />
      </div>

      <div className="result-summary">
        <div className="total">
          <strong>{formatNumber(result.totalCartons)}</strong>
          <span>cartons</span>
        </div>

        <div className="utilization-grid">
          <Utilization label="Floor utilization" value={result.floorUtilization} />
          <Utilization label="Volume utilization" value={result.volumeUtilization} />
        </div>
      </div>

      <dl className="details">
        {details.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>

      <details className="pattern">
        <summary>Packing pattern</summary>
        <p>{result.pattern}</p>
      </details>
    </article>
  )
}

function Utilization({ label, value }) {
  return (
    <div className="utilization">
      <strong>{Math.round(value)}%</strong>
      <span>{label}</span>
    </div>
  )
}

function App() {
  const [dimensions, setDimensions] = useState({ length: '', width: '', height: '' })
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')
  const [isCalculating, setIsCalculating] = useState(false)
  const workerRef = useRef(null)
  const requestRef = useRef(0)
  const inputRefs = useRef([])

  useEffect(() => {
    const worker = new Worker(new URL('./workers/calculator.worker.js', import.meta.url), {
      type: 'module',
    })

    worker.onmessage = ({ data }) => {
      if (data.id !== requestRef.current) return
      setIsCalculating(false)
      if (data.error) {
        setError(data.error)
        return
      }
      setResults(data.result)
    }

    workerRef.current = worker
    return () => worker.terminate()
  }, [])

  function updateDimension(key, value) {
    if (value === '' || /^\d{0,5}$/.test(value)) {
      setDimensions((current) => ({ ...current, [key]: value }))
      setError('')
    }
  }

  function moveBetweenFields(event, index) {
    const atStart = event.currentTarget.selectionStart === 0
    const atEnd = event.currentTarget.selectionStart === event.currentTarget.value.length
    const isPrevious = event.key === 'ArrowLeft' && atStart
    const isNext = event.key === 'ArrowRight' && atEnd

    if (!isPrevious && !isNext) return

    const target = inputRefs.current[index + (isPrevious ? -1 : 1)]
    if (!target) return

    event.preventDefault()
    target.focus({ preventScroll: true })
    const caretPosition = isPrevious ? target.value.length : 0
    target.setSelectionRange(caretPosition, caretPosition)
  }

  function calculate(event) {
    event.preventDefault()
    const carton = Object.fromEntries(
      Object.entries(dimensions).map(([key, value]) => [key, Number(value)]),
    )

    if (Object.values(carton).some((value) => !Number.isInteger(value) || value <= 0)) {
      setError('Enter a whole number greater than zero for each dimension.')
      return
    }

    requestRef.current += 1
    setError('')
    setResults(null)
    setIsCalculating(true)
    workerRef.current?.postMessage({ id: requestRef.current, carton })
  }

  return (
    <main className="app-shell">
      <section className="hero" id="top">
        <div className="intro">
          <p className="eyebrow">Pallet + 40HC planning</p>
          <h1>Know what fits.</h1>
          <p className="lead">
            Enter one carton's dimensions to compare pallet and container capacity.
          </p>
          <div className="orientation-note" aria-label="Calculation orientation rules">
            <span><strong>Pallet</strong> All orientations</span>
            <span><strong>40HC container</strong> Height stays upright</span>
          </div>
        </div>

        <form className="calculator" onSubmit={calculate} noValidate>
          <div className="input-grid">
            {fields.map((field, index) => (
              <label key={field.key}>
                <span>{field.label}</span>
                <div className="input-wrap">
                  <input
                    ref={(element) => { inputRefs.current[index] = element }}
                    type="text"
                    inputMode="numeric"
                    autoComplete="off"
                    value={dimensions[field.key]}
                    placeholder={field.placeholder}
                    onChange={(event) => updateDimension(field.key, event.target.value)}
                    onKeyDown={(event) => moveBetweenFields(event, index)}
                    aria-describedby={error ? 'form-error' : undefined}
                  />
                  <span>mm</span>
                </div>
              </label>
            ))}
          </div>

          <div className="form-footer">
            <p className="form-note">40HC keeps the entered height upright.</p>
            <button type="submit" disabled={isCalculating}>
              {isCalculating ? 'Calculating…' : 'Calculate load'}
              <span aria-hidden="true">→</span>
            </button>
          </div>
          {error && <p className="error" id="form-error" role="alert">{error}</p>}
        </form>
      </section>

      <section className="results" aria-live="polite" aria-busy={isCalculating}>
        {isCalculating && (
          <div className="loading-state">
            <span />
            Optimizing packing patterns…
          </div>
        )}

        {!isCalculating && !results && (
          <div className="empty-state">
            <span>01</span>
            <p>Your load comparison will appear here.</p>
          </div>
        )}

        {!isCalculating && results && (
          <div className="result-grid">
            <ResultCard title="Local pallet" eyebrow="All orientations · 1200 × 1000 × 1600 mm usable" result={results.pallet} />
            <ResultCard title="40HC container" eyebrow="Height upright · 11998 × 2330 × 2655 mm" result={results.container} />
          </div>
        )}
      </section>

      <footer className="site-footer">
        <span>All-orientation pallet &amp; upright-height 40HC container calculator.</span>
        <span>
          Developed by{' '}
          <a href="https://github.com/RecurSID" target="_blank" rel="noreferrer">
            RecurSID
          </a>
        </span>
      </footer>
    </main>
  )
}

export default App
