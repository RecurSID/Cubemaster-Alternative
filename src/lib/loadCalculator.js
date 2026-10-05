const PALLET = { length: 1200, width: 1000, height: 1600 }
const CONTAINER_40HC = { length: 11998, width: 2330, height: 2655 }

function uniqueOrientations(length, width, height, rotateVertically) {
  if (!rotateVertically) {
    return length === width
      ? [[length, width, height]]
      : [[length, width, height], [width, length, height]]
  }

  const values = [length, width, height]
  const permutations = [
    [values[0], values[1], values[2]],
    [values[0], values[2], values[1]],
    [values[1], values[0], values[2]],
    [values[1], values[2], values[0]],
    [values[2], values[0], values[1]],
    [values[2], values[1], values[0]],
  ]

  return [...new Map(permutations.map((item) => [item.join('x'), item])).values()]
}

function createLayerPacker(cartonLength, cartonWidth) {
  const memo = new Map()
  const floorOrientations = cartonLength === cartonWidth
    ? [[cartonLength, cartonWidth]]
    : [[cartonLength, cartonWidth], [cartonWidth, cartonLength]]
  const cartonArea = cartonLength * cartonWidth

  function pack(areaLength, areaWidth) {
    if (areaLength <= 0 || areaWidth <= 0) return { count: 0, pattern: 'Empty' }

    const key = `${areaLength}:${areaWidth}`
    if (memo.has(key)) return memo.get(key)

    let best = { count: 0, pattern: 'No fit' }

    for (const [length, width] of floorOrientations) {
      if (length > areaLength || width > areaWidth) continue
      const across = Math.floor(areaLength / length)
      const deep = Math.floor(areaWidth / width)
      const count = across * deep
      if (count > best.count) {
        best = { count, pattern: `${across} × ${deep} grid (${length} × ${width})` }
      }
    }

    const areaLimit = Math.floor((areaLength * areaWidth) / cartonArea)
    if (best.count === areaLimit) {
      memo.set(key, best)
      return best
    }

    const xSplits = new Set()
    const ySplits = new Set()

    for (const [length, width] of floorOrientations) {
      for (let split = length; split < areaLength; split += length) xSplits.add(split)
      for (let split = width; split < areaWidth; split += width) ySplits.add(split)
    }

    for (const split of xSplits) {
      const left = pack(split, areaWidth)
      const right = pack(areaLength - split, areaWidth)
      const count = left.count + right.count
      if (count > best.count) {
        best = {
          count,
          pattern: `Vertical blocks: [${left.pattern}] + [${right.pattern}]`,
        }
        if (count === areaLimit) break
      }
    }

    if (best.count < areaLimit) {
      for (const split of ySplits) {
        const bottom = pack(areaLength, split)
        const top = pack(areaLength, areaWidth - split)
        const count = bottom.count + top.count
        if (count > best.count) {
          best = {
            count,
            pattern: `Horizontal blocks: [${bottom.pattern}] + [${top.pattern}]`,
          }
          if (count === areaLimit) break
        }
      }
    }

    memo.set(key, best)
    return best
  }

  return pack
}

function optimizeLoad(carton, load, rotateVertically) {
  const cartonVolume = carton.length * carton.width * carton.height
  const loadVolume = load.length * load.width * load.height
  let best = null

  for (const [length, width, height] of uniqueOrientations(
    carton.length,
    carton.width,
    carton.height,
    rotateVertically,
  )) {
    if (height > load.height) continue

    const layers = Math.floor(load.height / height)
    const layer = createLayerPacker(length, width)(load.length, load.width)
    if (!layer.count) continue

    const totalCartons = layer.count * layers
    const result = {
      totalCartons,
      cartonsPerLayer: layer.count,
      layers,
      orientation: { length, width, height },
      loadedHeight: layers * height,
      floorUtilization: (layer.count * length * width * 100) / (load.length * load.width),
      volumeUtilization: (totalCartons * cartonVolume * 100) / loadVolume,
      pattern: layer.pattern,
    }

    if (!best || result.totalCartons > best.totalCartons) best = result
  }

  return best
}

export function calculateLoads(carton) {
  return {
    pallet: optimizeLoad(carton, PALLET, true),
    container: optimizeLoad(carton, CONTAINER_40HC, false),
  }
}
