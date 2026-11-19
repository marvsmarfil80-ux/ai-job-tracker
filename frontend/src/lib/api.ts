import { ApiError } from '../types'
import type { ValidationItem } from '../types'

const BASE = '/api'
const TIMEOUT_MS = 180000

type Query = Record<string, string | number | boolean | null | undefined>

function buildUrl(path: string, query?: Query): string {
  const params = new URLSearchParams()
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== null && value !== undefined && value !== '') {
        params.set(key, String(value))
      }
    }
  }
  const qs = params.toString()
  return `${BASE}${path}${qs ? `?${qs}` : ''}`
}

async function request<T>(
  method: string,
  path: string,
  options: { query?: Query; body?: unknown; raw?: { data: Blob; contentType: string } } = {},
): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)

  try {
    const response = await fetch(buildUrl(path, options.query), {
      method,
      headers: options.raw
        ? { 'Content-Type': options.raw.contentType }
        : options.body !== undefined
          ? { 'Content-Type': 'application/json' }
          : undefined,
      body: options.raw
        ? options.raw.data
        : options.body !== undefined
          ? JSON.stringify(options.body)
          : undefined,
      signal: controller.signal,
    })

    if (!response.ok) {
      let detail = `Request failed (${response.status})`
      let validation: ValidationItem[] | null = null
      try {
        const data = await response.json()
        if (typeof data?.detail === 'string') {
          detail = data.detail
        } else if (Array.isArray(data?.detail)) {
          validation = data.detail as ValidationItem[]
          detail = 'Some fields are invalid.'
        }
      } catch {
        detail = `Request failed (${response.status})`
      }
      throw new ApiError(response.status, detail, validation)
    }

    if (response.status === 204) return undefined as T
    const text = await response.text()
    return (text ? JSON.parse(text) : undefined) as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(0, 'The request took too long and was stopped.')
    }
    throw new ApiError(0, 'Cannot reach the server. Check that the backend is running.')
  } finally {
    clearTimeout(timer)
  }
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>('GET', path, { query }),
  post: <T>(path: string, body?: unknown, query?: Query) => request<T>('POST', path, { body, query }),
  postRaw: <T>(path: string, data: Blob, contentType: string) =>
    request<T>('POST', path, { raw: { data, contentType } }),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, { body }),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, { body }),
  delete: <T>(path: string) => request<T>('DELETE', path),
}