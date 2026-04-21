import { describe, it, expect } from 'vitest'
import { cn, TAG_COLORS, STATUS_MAP, TAG_LAYERS } from '@/lib/utils'

describe('cn()', () => {
  it('merges class names', () => {
    expect(cn('px-2', 'py-1')).toBe('px-2 py-1')
  })

  it('resolves tailwind conflicts (last wins)', () => {
    const result = cn('px-2', 'px-4')
    expect(result).toBe('px-4')
  })

  it('handles conditional classes', () => {
    expect(cn('base', false && 'hidden', 'extra')).toBe('base extra')
  })

  it('returns empty for no input', () => {
    expect(cn()).toBe('')
  })
})

describe('TAG_COLORS', () => {
  it('covers all 20 tag dimensions', () => {
    const dims = [
      'event_type', 'conflict', 'stakes',
      'relationship', 'interaction', 'power_dynamic', 'character_moment', 'moral_spectrum',
      'emotion', 'reader_effect',
      'plot_stage', 'plot_function', 'pacing',
      'technique', 'dialogue_type', 'pov', 'info_delivery',
      'setting', 'scale', 'time_weather',
    ]
    for (const d of dims) {
      expect(TAG_COLORS[d], `Missing TAG_COLORS for "${d}"`).toBeDefined()
      expect(TAG_COLORS[d].bg).toBeTruthy()
      expect(TAG_COLORS[d].text).toBeTruthy()
      expect(TAG_COLORS[d].label).toBeTruthy()
    }
  })
})

describe('STATUS_MAP', () => {
  it('covers all valid statuses', () => {
    for (const s of ['raw', 'outlined', 'tagged', 'complete', 'refined']) {
      expect(STATUS_MAP[s], `Missing STATUS_MAP for "${s}"`).toBeDefined()
      expect(STATUS_MAP[s].label).toBeTruthy()
      expect(STATUS_MAP[s].color).toBeTruthy()
    }
  })
})

describe('TAG_LAYERS', () => {
  it('has 6 layers covering all 20 dims', () => {
    expect(TAG_LAYERS).toHaveLength(6)
    const allDims = TAG_LAYERS.flatMap(l => l.dims)
    expect(allDims).toHaveLength(20)
    expect(new Set(allDims).size).toBe(20)
  })
})
