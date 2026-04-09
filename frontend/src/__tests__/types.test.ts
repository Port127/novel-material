import { describe, it, expect } from 'vitest'
import type {
  Material, MaterialDetail, DashboardStats,
  ScenesResponse, SceneItem, SceneSearchResponse,
  CharacterSearchResponse, CharacterItem, TextSearchResponse,
  TagDictionary, TagUsage, PipelineStatusResponse,
} from '@/types'

describe('Type contracts', () => {
  it('Material has required fields', () => {
    const m: Material = {
      id: 'nm_test', type: 'novel', name: '测试', author: '作者',
      folder: 'novels/nm_test', status: 'raw', added: '2026-01-01', scene_count: 0,
    }
    expect(m.id).toBeTruthy()
    expect(m.scene_count).toBeDefined()
  })

  it('MaterialDetail extends Material', () => {
    const d: MaterialDetail = {
      id: 'nm_test', type: 'novel', name: '测试', author: '作者',
      folder: 'novels/nm_test', status: 'complete', added: '2026-01-01',
      scene_count: 100, material_id: 'nm_test',
      has_outline: true, has_worldbuilding: true, has_characters: true,
      has_tags: true, has_stats: true, has_scenes: true,
    }
    expect(d.has_outline).toBe(true)
    expect(d.material_id).toBe('nm_test')
  })

  it('DashboardStats structure', () => {
    const s: DashboardStats = {
      novels: 5, scenes: 500, characters: 50, tag_records: 2000,
      per_novel: [{ material_id: 'nm_1', name: 'Novel 1', scenes: 100 }],
      top_scene_types: [{ value: '对决', count: 50 }],
      top_emotions: [{ value: '燃', count: 30 }],
      tension_distribution: [{ tension: 3, count: 100 }],
      top_techniques: [{ value: '伏笔', count: 20 }],
    }
    expect(s.novels).toBe(5)
    expect(s.per_novel).toHaveLength(1)
  })

  it('SceneItem has tag map', () => {
    const scene: SceneItem = {
      scene_id: 'nm_test_ch001_s1', chapter: '第1章', title: '测试',
      summary: '测试场景', tension: 3,
      tags: { scene_type: ['对决'], emotion: ['燃'] },
      characters: ['张三'],
    }
    expect(scene.tags?.scene_type).toContain('对决')
  })

  it('SceneSearchResponse includes relaxed flag', () => {
    const r: SceneSearchResponse = {
      query: { scene_type: '对决' }, total: 0, results: [], relaxed: true,
    }
    expect(r.relaxed).toBe(true)
  })

  it('CharacterItem has psychology', () => {
    const c: CharacterItem = {
      name: '张三', novel: '测试', material_id: 'nm_1',
      role: 'protagonist', archetype: '英雄', moral_spectrum: '正义',
      arc_summary: '成长', narrative_function: '推动主线', appearance_count: 50,
      psychology: { fatal_flaw: '冲动', obsession: '力量' },
    }
    expect(c.psychology?.fatal_flaw).toBe('冲动')
  })

  it('PipelineStatusResponse shape', () => {
    const p: PipelineStatusResponse = {
      stages_completed: ['ingest', 'format'],
      running: false, current_stage: null, last_error: null, updated_at: null,
    }
    expect(p.stages_completed).toHaveLength(2)
    expect(p.running).toBe(false)
  })
})
