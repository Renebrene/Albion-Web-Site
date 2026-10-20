import { postJson } from './api'

export function geocodeAddress(query) {
  return postJson('/geo/geocode', { query })
}

export function reverseGeocode(lat, lon) {
  return postJson('/geo/reverse', { lat, lon })
}

export function suggestAddress(query, limit = 8) {
  return postJson('/geo/suggest', { query, limit })
}
