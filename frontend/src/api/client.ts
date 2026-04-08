import type {
  Material, MaterialDetail, DashboardStats,
  ScenesResponse, SceneItem, SceneSearchResponse,
  CharacterSearchResponse, TextSearchResponse,
  TagDictionary, TagUsage, PipelineStatusResponse,
} from '@/types'

const BASE = import.meta.env.DEV ? 'http://127.0.0.1:5273/api' : '/api'

async function get<T>(path: string, params?: Record<string, string | number | undefined | null>): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin)
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v))
    }
  }
  const res = await fetch(url.toString())
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `${res.status} ${res.statusText}`)
  }
  return res.json()
}

export const api = {
  getStats: () => get<DashboardStats>('/stats'),

  listMaterials: () => get<Material[]>('/materials'),
  getMaterial: (id: string) => get<MaterialDetail>(`/materials/${id}`),
  getOutline: (id: string) => get<Record<string, unknown>>(`/materials/${id}/outline`),
  getWorldbuilding: (id: string) => get<Record<string, unknown>>(`/materials/${id}/worldbuilding`),
  getCharacters: (id: string) => get<Record<string, unknown>>(`/materials/${id}/characters`),
  getNovelTags: (id: string) => get<Record<string, unknown>>(`/materials/${id}/tags`),
  getScenes: (id: string, page = 1, limit = 50) =>
    get<ScenesResponse>(`/materials/${id}/scenes`, { page, limit }),
  getScene: (id: string, sceneId: string) =>
    get<SceneItem>(`/materials/${id}/scenes/${sceneId}`),
  getMaterialStats: (id: string) => get<Record<string, unknown>>(`/materials/${id}/stats`),

  searchScenes: (filters: Record<string, string | number | undefined>) =>
    get<SceneSearchResponse>('/search/scenes', filters),
  searchCharacters: (filters: Record<string, string | number | undefined>) =>
    get<CharacterSearchResponse>('/search/characters', filters),
  searchText: (query: string, limit = 20) =>
    get<TextSearchResponse>('/search/text', { query, limit }),

  getTagDict: () => get<TagDictionary>('/tags'),
  getTagUsage: () => get<TagUsage>('/tags/usage'),
  addTag: (dimension: string, value: string) =>
    post<{ ok: boolean; dimension: string; value: string }>('/tags/add', { dimension, value }),
  mergeTags: (dimension: string, source: string, target: string) =>
    post<{ ok: boolean; merged: string; into: string; db_updated: number }>('/tags/merge', { dimension, source, target }),

  uploadNovel: async (file: File, name?: string, author?: string) => {
    const form = new FormData()
    form.append('file', file)
    if (name) form.append('name', name)
    if (author) form.append('author', author)
    const res = await fetch(`${BASE}/upload`, { method: 'POST', body: form })
    if (!res.ok) throw new Error(await res.text())
    return res.json() as Promise<{ material_id: string; name: string; message: string }>
  },

  getPipelineStatus: (id: string) => get<PipelineStatusResponse>(`/pipeline/${id}/status`),
  triggerPipeline: (id: string, stage: string) => post<{ message: string }>(`/pipeline/${id}/trigger?stage=${stage}`),
  resetPipeline: (id: string) => post<{ message: string }>(`/pipeline/${id}/reset`),

  getLlmSettings: () => get<Record<string, unknown>>('/settings/llm'),
  saveLlmSettings: (cfg: Record<string, string>) => {
    return fetch(`${BASE}/settings/llm`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cfg),
    }).then(r => r.json())
  },
}
