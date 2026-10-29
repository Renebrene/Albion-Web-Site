/*
 * Валидация координат конструкции.
 *
 * В базе есть записи с lat/lng = NULL (адреса без геокодирования).
 * Number(null) === 0, поэтому без явной проверки такие точки попадали
 * на «нулевой остров» (0,0) и растягивали bounds карты на весь мир.
 */
export function normalizeCoordinates(latValue, lngValue) {
  if (
    latValue === null ||
    latValue === undefined ||
    latValue === '' ||
    lngValue === null ||
    lngValue === undefined ||
    lngValue === ''
  ) {
    return null
  }

  const lat = Number(latValue)
  const lng = Number(lngValue)

  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return null
  }

  if (Math.abs(lat) > 90 || Math.abs(lng) > 180) {
    return null
  }

  /* 0,0 для Ростовской области — заведомо битая запись. */
  if (lat === 0 && lng === 0) {
    return null
  }

  return { lat, lng }
}
