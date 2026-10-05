import test from 'node:test'
import assert from 'node:assert/strict'

import { calculateLoads } from '../src/lib/loadCalculator.js'


const cases = [
  [[220, 220, 230], 120, 5940],
  [[280, 270, 320], 60, 2816],
  [[1000, 400, 120], 39, 1408],
  [[1000, 360, 230], 18, 770],
  [[1080, 430, 60], 52, 2420],
  [[530, 340, 180], 40, 2086],
  [[420, 260, 240], 60, 2761],
]

test('browser solver preserves upright regression results', () => {
  for (const [[length, width, height], palletTotal, containerTotal] of cases) {
    const result = calculateLoads({ length, width, height })
    assert.equal(result.pallet.totalCartons, palletTotal, `${length}x${width}x${height} pallet`)
    assert.equal(result.container.totalCartons, containerTotal, `${length}x${width}x${height} 40HC`)
  }
})

test('browser solver discovers both critical interlocking layers', () => {
  const result = calculateLoads({ length: 420, width: 260, height: 240 })
  assert.equal(result.pallet.cartonsPerLayer, 10)
  assert.equal(result.pallet.layers, 6)
  assert.equal(result.pallet.totalCartons, 60)
  assert.equal(result.container.cartonsPerLayer, 251)
  assert.equal(result.container.layers, 11)
  assert.equal(result.container.totalCartons, 2761)
  assert.match(result.container.pattern, /Interlocking band-swap/)
})
