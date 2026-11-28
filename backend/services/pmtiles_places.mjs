// Read settlement names/points from the offline PMTiles `places` layer.
// Used by the on-the-fly settlement resolver; writes nothing.
//
// Usage:
//   node pmtiles_places.js --archive <file.pmtiles> --name "Красный Колос" \
//        [--zoom 8] [--limit 20] [--bbox south,west,north,east]
import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const frontendDir = process.env.ALBION_FRONTEND_DIR ||
  path.resolve(process.cwd(), 'frontend')

function parseArgs(argv) {
  const out = {
    archive: '',
    name: '',
    zoom: 8,
    limit: 20,
    bbox: null,
  }
  for (let i = 0; i < argv.length; i += 1) {
    const flag = argv[i]
    if (!flag.startsWith('--')) continue
    const key = flag.slice(2)
    const value = argv[i + 1]
    if (key === 'bbox') {
      out.bbox = String(value).split(',').map(Number)
      i += 1
    } else if (key === 'zoom' || key === 'limit') {
      out[key] = Number(value)
      i += 1
    } else if (key === 'archive' || key === 'name') {
      out[key] = String(value)
      i += 1
    }
  }
  return out
}

function tileRange(bbox, zoom) {
  const [south, west, north, east] = bbox
  const n = 2 ** zoom
  const lon2x = (lon) => Math.min(n - 1, Math.max(0, Math.floor(((lon + 180) / 360) * n)))
  const lat2y = (lat) => {
    const rad = (lat * Math.PI) / 180
    const y = (1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2
    return Math.min(n - 1, Math.max(0, Math.floor(y * n)))
  }
  const x0 = lon2x(west)
  const x1 = lon2x(east)
  // y grows southwards
  const y0 = lat2y(north)
  const y1 = lat2y(south)
  return { x0, x1, y0, y1, n }
}

function tileCenter(ring, x, y, n, extent) {
  if (!ring || !ring.length) return null
  let sx = 0
  let sy = 0
  for (const point of ring) {
    sx += point.x
    sy += point.y
  }
  const tx = (x + sx / ring.length / extent) / n
  const ty = (y + sy / ring.length / extent) / n
  const lng = tx * 360 - 180
  const lat = (Math.atan(Math.sinh(Math.PI * (1 - 2 * ty))) * 180) / Math.PI
  return { lat, lng }
}

async function main() {
  const options = parseArgs(process.argv.slice(2))
  if (!options.archive || !options.name) {
    console.log(JSON.stringify({ error: 'archive and name are required' }))
    return
  }

  const { PMTiles } = await import(pathToFileURL(
    path.join(frontendDir, 'node_modules', 'pmtiles', 'dist', 'esm', 'index.js')
  ).href)
  const { VectorTile } = await import(pathToFileURL(
    path.join(frontendDir, 'node_modules', '@mapbox/vector-tile', 'index.js')
  ).href)
  const { default: Pbf } = await import(pathToFileURL(
    path.join(frontendDir, 'node_modules', 'pbf', 'index.js')
  ).href)

  const fd = fs.openSync(options.archive, 'r')
  const source = {
    getKey: () => options.archive,
    getBytes: async (offset, length) => {
      const buffer = Buffer.allocUnsafe(length)
      fs.readSync(fd, buffer, 0, length, offset)
      const array = new Uint8Array(buffer)
      return { data: array.buffer }
    },
  }

  const archive = new PMTiles(source)
  const header = await archive.getHeader()
  const bbox = options.bbox || [
    header.minLat, header.minLon, header.maxLat, header.maxLon,
  ]
  const range = tileRange(bbox, options.zoom)

  const wanted = options.name.toLocaleLowerCase('ru').replaceAll('ё', 'е').trim()
  const results = []
  const seen = new Set()

  for (let x = range.x0; x <= range.x1; x += 1) {
    for (let y = range.y0; y <= range.y1; y += 1) {
      let tileData
      try {
        tileData = await archive.getZxy(options.zoom, x, y)
      } catch {
        continue
      }
      if (!tileData || !tileData.data) continue

      let layer
      try {
        const tile = new VectorTile(new Pbf(new Uint8Array(tileData.data)))
        layer = tile.layers.places
      } catch {
        continue
      }
      if (!layer) continue

      for (let i = 0; i < layer.length; i += 1) {
        const feature = layer.feature(i)
        const props = feature.properties || {}
        const kind = String(props.kind_detail || props.kind || 'locality')
        if (!['city', 'town', 'village', 'hamlet', 'isolated_dwelling', 'locality'].includes(kind)) {
          continue
        }
        const candidates = [props['name:ru'], props.name, props.name2, props.name3]
          .filter(Boolean)
          .map((value) => String(value).toLocaleLowerCase('ru').replaceAll('ё', 'е'))
        if (!candidates.some((value) => value.includes(wanted))) continue

        const geometry = feature.loadGeometry()
        const center = tileCenter(geometry[0], x, y, range.n, layer.extent)
        if (!center) continue
        const key = `${props['name:ru'] || props.name}:${center.lat.toFixed(4)}:${center.lng.toFixed(4)}`
        if (seen.has(key)) continue
        seen.add(key)
        results.push({
          name: props['name:ru'] || props.name,
          kind,
          lat: center.lat,
          lng: center.lng,
        })
        if (results.length >= options.limit) break
      }
      if (results.length >= options.limit) break
    }
    if (results.length >= options.limit) break
  }

  fs.closeSync(fd)
  console.log(JSON.stringify(results))
}

main().catch((error) => {
  console.log(JSON.stringify({ error: String(error && error.message || error) }))
})
