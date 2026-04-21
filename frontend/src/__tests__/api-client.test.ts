import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

// Must import after stubbing fetch
const { api } = await import('@/api/client')

function jsonResponse(data: unknown, status = 200) {
  return Promise.resolve({
    ok: status < 400,
    status,
    statusText: status < 400 ? 'OK' : 'Error',
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  })
}

beforeEach(() => {
  mockFetch.mockReset()
})

describe('api.getStats', () => {
  it('calls /stats', async () => {
    const data = { novels: 3, events: 100, characters: 20, tag_records: 500 }
    mockFetch.mockReturnValueOnce(jsonResponse(data))
    const result = await api.getStats()
    expect(result.novels).toBe(3)
    expect(mockFetch).toHaveBeenCalledOnce()
    expect(mockFetch.mock.calls[0][0]).toContain('/stats')
  })
})

describe('api.listMaterials', () => {
  it('returns material array', async () => {
    mockFetch.mockReturnValueOnce(jsonResponse([{ id: 'nm_1', name: 'test' }]))
    const result = await api.listMaterials()
    expect(result).toHaveLength(1)
  })
})

describe('api.getMaterial', () => {
  it('fetches by id', async () => {
    mockFetch.mockReturnValueOnce(jsonResponse({ material_id: 'nm_1', has_outline: true }))
    const result = await api.getMaterial('nm_1')
    expect(result.material_id).toBe('nm_1')
    expect(mockFetch.mock.calls[0][0]).toContain('/materials/nm_1')
  })
})

describe('api.searchEvents', () => {
  it('passes filters as query params', async () => {
    mockFetch.mockReturnValueOnce(jsonResponse({ total: 5, results: [], relaxed: false }))
    await api.searchEvents({ event_type: '对决', emotion: '燃' })
    const url = mockFetch.mock.calls[0][0]
    expect(url).toContain('event_type=')
    expect(url).toContain('emotion=')
  })

  it('omits undefined filters', async () => {
    mockFetch.mockReturnValueOnce(jsonResponse({ total: 0, results: [], relaxed: false }))
    await api.searchEvents({ event_type: '对决', conflict: undefined })
    const url: string = mockFetch.mock.calls[0][0]
    expect(url).not.toContain('conflict')
  })
})

describe('api.searchCharacters', () => {
  it('passes filters', async () => {
    mockFetch.mockReturnValueOnce(jsonResponse({ total: 1, results: [{ name: '张三' }] }))
    const result = await api.searchCharacters({ name: '张三' })
    expect(result.total).toBe(1)
  })
})

describe('api.searchText', () => {
  it('sends query param', async () => {
    mockFetch.mockReturnValueOnce(jsonResponse({ total: 0, results: [] }))
    await api.searchText('黎明', 10)
    const url: string = mockFetch.mock.calls[0][0]
    expect(url).toContain('query=')
  })
})

describe('api.getTagDict', () => {
  it('fetches tags', async () => {
    const data = { event_type: { values: ['对决', '日常'] } }
    mockFetch.mockReturnValueOnce(jsonResponse(data))
    const result = await api.getTagDict()
    expect(result.event_type.values).toContain('对决')
  })
})

describe('api.addTag', () => {
  it('posts tag add request', async () => {
    mockFetch.mockReturnValueOnce(jsonResponse({ ok: true, dimension: 'event_type', value: '新标签' }))
    const result = await api.addTag('event_type', '新标签')
    expect(result.ok).toBe(true)
    const [, opts] = mockFetch.mock.calls[0]
    expect(opts.method).toBe('POST')
  })
})

describe('api.mergeTags', () => {
  it('posts merge request', async () => {
    mockFetch.mockReturnValueOnce(jsonResponse({ ok: true, merged: 'a', into: 'b', db_updated: 5 }))
    const result = await api.mergeTags('emotion', 'a', 'b')
    expect(result.ok).toBe(true)
  })
})

describe('api.uploadNovel', () => {
  it('sends multipart form', async () => {
    mockFetch.mockReturnValueOnce(jsonResponse({ material_id: 'nm_1', name: 'test', message: 'ok' }))
    const file = new File(['content'], 'novel.txt', { type: 'text/plain' })
    const result = await api.uploadNovel(file, '测试', '作者')
    expect(result.material_id).toBe('nm_1')
    const [, opts] = mockFetch.mock.calls[0]
    expect(opts.method).toBe('POST')
    expect(opts.body).toBeInstanceOf(FormData)
  })
})

describe('api.getPipelineStatus', () => {
  it('fetches pipeline status', async () => {
    mockFetch.mockReturnValueOnce(jsonResponse({
      stages_completed: ['ingest'], running: false, current_stage: null,
    }))
    const result = await api.getPipelineStatus('nm_1')
    expect(result.stages_completed).toContain('ingest')
  })
})

describe('api.triggerPipeline', () => {
  it('triggers stage', async () => {
    mockFetch.mockReturnValueOnce(jsonResponse({ message: '已触发 analyze' }))
    const result = await api.triggerPipeline('nm_1', 'analyze')
    expect(result.message).toContain('analyze')
  })
})

describe('api.getLlmSettings', () => {
  it('fetches settings', async () => {
    mockFetch.mockReturnValueOnce(jsonResponse({ base_url: 'http://test', model: 'gpt-4' }))
    const result = await api.getLlmSettings()
    expect(result).toHaveProperty('base_url')
  })
})

describe('api.saveLlmSettings', () => {
  it('sends PUT', async () => {
    mockFetch.mockReturnValueOnce(jsonResponse({ message: '已保存' }))
    await api.saveLlmSettings({ base_url: 'http://test/v1', model: 'gpt-4o' })
    const [, opts] = mockFetch.mock.calls[0]
    expect(opts.method).toBe('PUT')
  })

  it('throws on non-ok response', async () => {
    mockFetch.mockReturnValueOnce({ ok: false, status: 500, statusText: 'Server Error' })
    await expect(api.saveLlmSettings({ base_url: 'x' })).rejects.toThrow('500')
  })
})

describe('api.testLlm', () => {
  it('sends POST to llm/test', async () => {
    mockFetch.mockReturnValueOnce(jsonResponse({ ok: true }))
    const result = await api.testLlm({ base_url: 'http://test/v1', api_key: 'sk-123', model: 'gpt-4' })
    expect(result).toHaveProperty('ok', true)
  })
})

describe('error handling', () => {
  it('throws on non-ok GET response', async () => {
    mockFetch.mockReturnValueOnce(jsonResponse({}, 404))
    await expect(api.getStats()).rejects.toThrow('404')
  })

  it('throws on non-ok POST response', async () => {
    mockFetch.mockReturnValueOnce({
      ok: false, status: 400, statusText: 'Bad Request',
      text: () => Promise.resolve('bad'),
      json: () => Promise.resolve({}),
    })
    await expect(api.addTag('x', 'y')).rejects.toThrow()
  })
})
