const PALLET = { length: 1200, width: 1000, height: 1600 }
const CONTAINER_40HC = { length: 11998, width: 2330, height: 2655 }

function uprightOrientations(length, width, height) {
  return length === width
    ? [[length, width, height]]
    : [[length, width, height], [width, length, height]]
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
          pattern: `Length blocks: [${left.pattern}] + [${right.pattern}]`,
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
            pattern: `Width blocks: [${bottom.pattern}] + [${top.pattern}]`,
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

function bestBandSwapPattern(areaLength, areaWidth, cartonLength, cartonWidth) {
  if (cartonLength === cartonWidth) return { count: 0, pattern: 'No fit' }

  const orientations = [
    [cartonLength, cartonWidth],
    [cartonWidth, cartonLength],
  ]
  let best = { count: 0, pattern: 'No fit' }

  // Two row bands use opposite carton orientations. At a staggered seam the
  // bands exchange vertical order. This produces physically valid orthogonal
  // interlocking layouts that a guillotine split cannot represent.
  for (const [bottomLength, bottomWidth] of orientations) {
    const [topLength, topWidth] = bottomLength === cartonLength
      ? orientations[1]
      : orientations[0]

    for (
      let bottomRows = 1;
      bottomRows * bottomWidth < areaWidth;
      bottomRows += 1
    ) {
      const bottomHeight = bottomRows * bottomWidth
      const maxTopRows = Math.floor((areaWidth - bottomHeight) / topWidth)

      for (let topRows = 1; topRows <= maxTopRows; topRows += 1) {
        const topHeight = topRows * topWidth
        const maxBottomColumns = Math.floor(areaLength / bottomLength)

        for (let bottomColumns = 0; bottomColumns <= maxBottomColumns; bottomColumns += 1) {
          const bottomEnd = bottomColumns * bottomLength
          const minTopEnd = Math.max(0, bottomEnd - Math.max(cartonLength, cartonWidth))
          const maxTopEnd = Math.min(areaLength, bottomEnd + Math.max(cartonLength, cartonWidth))
          const firstTopColumns = Math.max(0, Math.floor(minTopEnd / topLength) - 1)
          const lastTopColumns = Math.min(
            Math.floor(areaLength / topLength),
            Math.ceil(maxTopEnd / topLength) + 1,
          )

          for (let topColumns = firstTopColumns; topColumns <= lastTopColumns; topColumns += 1) {
            const topEnd = topColumns * topLength
            const seamIsValid = (
              (bottomEnd >= topEnd && bottomHeight <= topHeight)
              || (topEnd >= bottomEnd && topHeight <= bottomHeight)
            )
            if (!seamIsValid) continue

            const rightBottomColumns = Math.floor((areaLength - topEnd) / bottomLength)
            const rightTopColumns = Math.floor((areaLength - bottomEnd) / topLength)
            const count = (
              bottomRows * bottomColumns
              + topRows * topColumns
              + bottomRows * rightBottomColumns
              + topRows * rightTopColumns
            )

            if (count > best.count) {
              best = {
                count,
                pattern: `Interlocking band-swap pattern (${count} cartons)`,
              }
            }
          }
        }
      }
    }
  }

  return best
}

function optimizeUprightLoad(carton, load) {
  const cartonVolume = carton.length * carton.width * carton.height
  const loadVolume = load.length * load.width * load.height
  let best = null

  for (const [length, width, height] of uprightOrientations(
    carton.length,
    carton.width,
    carton.height,
  )) {
    if (height > load.height) continue

    const layers = Math.floor(load.height / height)
    const guillotineLayer = createLayerPacker(length, width)(load.length, load.width)
    const interlockingLayer = bestBandSwapPattern(
      load.length,
      load.width,
      length,
      width,
    )
    const layer = interlockingLayer.count > guillotineLayer.count
      ? interlockingLayer
      : guillotineLayer
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

    if (
      !best
      || result.totalCartons > best.totalCartons
      || (
        result.totalCartons === best.totalCartons
        && result.floorUtilization > best.floorUtilization
      )
    ) {
      best = result
    }
  }

  return best
}

export function calculateLoads(carton) {
  return {
    pallet: optimizeUprightLoad(carton, PALLET),
    container: optimizeUprightLoad(carton, CONTAINER_40HC),
  }
}
