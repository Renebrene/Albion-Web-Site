/*
 * Слой PMTiles для Leaflet.
 *
 * PMTiles-архив — один файл с тайлами и оглавлением. Браузер запрашивает
 * только нужные диапазоны байт (HTTP Range), поэтому вся карта региона
 * не загружается в память.
 *
 * Векторные архивы (MVT) рисует protomaps-leaflet: он даёт улицы,
 * подписи городов и районов, сохраняя поверх слой маркеров Leaflet.
 * Растровые архивы (PNG/JPEG/WebP/AVIF) рисует собственный GridLayer.
 */
import L from 'leaflet'
import { PMTiles, TileType } from 'pmtiles'
import { leafletLayer } from 'protomaps-leaflet'

/* protomaps-leaflet использует глобальный L, как и оригинальный Leaflet. */
if (typeof window !== 'undefined') {
  window.L = L
}

const MIME_BY_TILE_TYPE = {
  [TileType.Png]: 'image/png',
  [TileType.Jpeg]: 'image/jpeg',
  [TileType.Webp]: 'image/webp',
  [TileType.Avif]: 'image/avif'
}

const PMTILES_ATTRIBUTION = '&copy; OpenStreetMap contributors · PMTiles'

/*
 * Создаёт слой и проверяет архив по заголовку.
 *
 * Возвращает Promise: пока не прочитан заголовок, слой не добавляется
 * к карте — так ошибка «файл не найден» не оставляет пустую карту.
 */
export async function createPmtilesLayer(url, options = {}) {
  if (!url) {
    throw new Error('PMTiles: не задан URL архива')
  }

  const source = new PMTiles(String(url))
  const header = await source.getHeader()

  if (header.tileType === TileType.Mvt || header.tileType === TileType.Mlt) {
    const layer = leafletLayer({
      url: String(url),
      flavor: 'light',
      lang: 'ru',
      maxDataZoom: header.maxZoom,
      maxZoom: 19,
      attribution: PMTILES_ATTRIBUTION,
      ...options
    })

    layer.pmtilesHeader = header
    return layer
  }

  const mimeType = MIME_BY_TILE_TYPE[header.tileType]

  if (!mimeType) {
    throw new Error(
      'PMTiles: неизвестный тип тайлов. Нужен растровый архив ' +
        '(PNG/JPEG/WebP) или векторный MVT.'
    )
  }

  const PmtilesGrid = L.GridLayer.extend({
    createTile(coords, done) {
      const tile = document.createElement('img')
      const controller = new AbortController()

      /* Обёртка, чтобы lint не считал done() вызовом внутри Promise. */
      const finish = (error, element) => done(error, element)

      tile.alt = ''
      tile.decoding = 'async'
      tile.cancel = () => controller.abort()

      source
        .getZxy(coords.z, coords.x, coords.y, controller.signal)
        .then(result => {
          if (!result) {
            /* За пределами покрытия архива — просто пустой тайл. */
            tile.style.visibility = 'hidden'
            finish(null, tile)
            return
          }

          const objectUrl = URL.createObjectURL(
            new Blob([result.data], { type: mimeType })
          )

          const release = () => URL.revokeObjectURL(objectUrl)

          tile.onload = () => {
            release()
            finish(null, tile)
          }
          tile.onerror = () => {
            release()
            finish(null, tile)
          }
          tile.src = objectUrl
        })
        .catch(error => {
          if (error?.name === 'AbortError') {
            finish(null, tile)
            return
          }

          options.onError?.(error)
          finish(error, tile)
        })

      return tile
    },

    _removeTile(key) {
      const tile = this._tiles[key]

      if (!tile) {
        return
      }

      tile.el?.cancel?.()

      if (tile.el?.src?.startsWith('blob:')) {
        URL.revokeObjectURL(tile.el.src)
      }

      tile.el.width = 0
      tile.el.height = 0
      L.DomUtil.remove(tile.el)
      delete this._tiles[key]

      this.fire('tileunload', {
        tile: tile.el,
        coords: this._keyToTileCoords(key)
      })
    }
  })

  const layer = new PmtilesGrid({
    tileSize: 256,
    minZoom: header.minZoom,
    maxZoom: 19,
    attribution: PMTILES_ATTRIBUTION,
    keepBuffer: 2,
    ...options
  })

  /* Заголовок нужен useMap, чтобы ограничить карту границами архива. */
  layer.pmtilesHeader = header

  return layer
}
