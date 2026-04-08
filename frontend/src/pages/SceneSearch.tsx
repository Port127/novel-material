import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { cn, TAG_COLORS, TAG_LAYERS } from '@/lib/utils'
import { Search, X, ChevronDown, ChevronUp, Type, Tags, Check } from 'lucide-react'
import type { TagDictionary, SceneItem } from '@/types'

type Mode = 'tags' | 'text'

export default function SceneSearch() {
  const [mode, setMode] = useState<Mode>('tags')

  return (
    <div className="flex flex-col h-[100vh] overflow-hidden">
      <div className="flex gap-1 p-3 border-b shrink-0">
        <button onClick={() => setMode('tags')}
          className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors',
            mode === 'tags' ? 'bg-amber-500/15 text-amber-400' : 'text-slate-500 hover:text-slate-300')}>
          <Tags className="w-3.5 h-3.5" /> 标签搜索
        </button>
        <button onClick={() => setMode('text')}
          className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors',
            mode === 'text' ? 'bg-amber-500/15 text-amber-400' : 'text-slate-500 hover:text-slate-300')}>
          <Type className="w-3.5 h-3.5" /> 全文搜索
        </button>
      </div>
      {mode === 'tags' ? <TagSearchPanel /> : <TextSearchPanel />}
    </div>
  )
}

/* ── Text Search ──────────────────────────────────────── */

function TextSearchPanel() {
  const [query, setQuery] = useState('')
  const [submitted, setSubmitted] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['searchText', submitted],
    queryFn: () => api.searchText(submitted, 50),
    enabled: !!submitted,
  })

  const handleSubmit = () => { if (query.trim()) setSubmitted(query.trim()) }

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-4">
      <div className="flex gap-2 max-w-2xl">
        <input value={query} onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSubmit()}
          placeholder="输入关键词搜索场景标题和摘要..."
          className="flex-1 text-sm bg-slate-900 border border-slate-800 rounded-lg px-4 py-2.5 focus:outline-none focus:border-amber-500/50" />
        <button onClick={handleSubmit} disabled={!query.trim()}
          className={cn('px-5 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors',
            query.trim() ? 'bg-amber-500 text-slate-950 hover:bg-amber-400' : 'bg-slate-800 text-slate-500')}>
          <Search className="w-4 h-4" /> 搜索
        </button>
      </div>
      {!submitted ? (
        <div className="flex flex-col items-center justify-center py-20 text-slate-600">
          <Search className="w-10 h-10 mb-3 opacity-30" /><p className="text-sm">输入关键词，按回车搜索</p>
        </div>
      ) : isLoading ? (
        <LoadingSkeleton />
      ) : data && data.total > 0 ? (
        <div className="space-y-3">
          <p className="text-sm text-slate-500">找到 {data.total} 个场景</p>
          {data.results.map((s: SceneItem) => <SceneResultCard key={s.scene_id} scene={s} />)}
        </div>
      ) : (
        <p className="text-center text-sm text-slate-600 py-20">未找到匹配结果</p>
      )}
    </div>
  )
}

/* ── Tag Search ───────────────────────────────────────── */

function TagSearchPanel() {
  const [filters, setFilters] = useState<Record<string, string[]>>({})
  const [tensionMin, setTensionMin] = useState<string>('')
  const [tensionMax, setTensionMax] = useState<string>('')
  const [character, setCharacter] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [expandedLayers, setExpandedLayers] = useState<Set<string>>(new Set(['content', 'emotion']))

  const { data: tagDict } = useQuery({ queryKey: ['tagDict'], queryFn: api.getTagDict })

  const activeFilters: Record<string, string | number> = {}
  for (const [dim, vals] of Object.entries(filters)) {
    if (vals.length === 1) activeFilters[dim] = vals[0]
    else if (vals.length > 1) activeFilters[dim] = vals.join(',')
  }
  if (character) activeFilters.character = character
  if (tensionMin) activeFilters.tension_min = Number(tensionMin)
  if (tensionMax) activeFilters.tension_max = Number(tensionMax)
  const hasFilters = Object.keys(activeFilters).length > 0

  const { data: results, isLoading, isFetching } = useQuery({
    queryKey: ['searchScenes', activeFilters],
    queryFn: () => api.searchScenes(activeFilters),
    enabled: submitted && hasFilters,
  })

  const handleSearch = useCallback(() => { if (hasFilters) setSubmitted(true) }, [hasFilters])

  const clearAll = () => { setFilters({}); setTensionMin(''); setTensionMax(''); setCharacter(''); setSubmitted(false) }

  const toggleLayer = (id: string) => {
    setExpandedLayers(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n })
  }

  const toggleTag = (dim: string, val: string) => {
    setFilters(prev => {
      const cur = prev[dim] ?? []
      const next = cur.includes(val) ? cur.filter(v => v !== val) : [...cur, val]
      const out = { ...prev }
      if (next.length > 0) out[dim] = next; else delete out[dim]
      return out
    })
    setSubmitted(false)
  }

  const selectedCount = Object.values(filters).reduce((a, v) => a + v.length, 0) + (character ? 1 : 0)

  return (
    <div className="flex flex-1 overflow-hidden">
      <div className="w-72 shrink-0 border-r overflow-y-auto p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium">标签筛选 {selectedCount > 0 && <span className="text-xs text-amber-400 ml-1">({selectedCount})</span>}</h2>
          {hasFilters && (
            <button onClick={clearAll} className="text-xs text-slate-500 hover:text-slate-300 flex items-center gap-1">
              <X className="w-3 h-3" /> 清空
            </button>
          )}
        </div>

        <div>
          <label className="text-xs text-slate-500 block mb-1">人物名</label>
          <input value={character} onChange={e => setCharacter(e.target.value)} placeholder="如: 陈汉升"
            className="w-full text-xs bg-slate-900 border border-slate-800 rounded px-2 py-1.5 focus:outline-none focus:border-amber-500/50" />
        </div>

        <div className="flex gap-2">
          <div className="flex-1">
            <label className="text-xs text-slate-500 block mb-1">{'张力 >='}</label>
            <input type="number" min="1" max="5" value={tensionMin} onChange={e => setTensionMin(e.target.value)}
              className="w-full text-xs bg-slate-900 border border-slate-800 rounded px-2 py-1.5 focus:outline-none focus:border-amber-500/50" />
          </div>
          <div className="flex-1">
            <label className="text-xs text-slate-500 block mb-1">{'张力 <='}</label>
            <input type="number" min="1" max="5" value={tensionMax} onChange={e => setTensionMax(e.target.value)}
              className="w-full text-xs bg-slate-900 border border-slate-800 rounded px-2 py-1.5 focus:outline-none focus:border-amber-500/50" />
          </div>
        </div>

        {tagDict && TAG_LAYERS.map(layer => {
          const isExpanded = expandedLayers.has(layer.id)
          return (
            <div key={layer.id} className="border border-slate-800/60 rounded-lg overflow-hidden">
              <button onClick={() => toggleLayer(layer.id)}
                className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-slate-400 hover:bg-white/[0.02]">
                <span>{layer.label}</span>
                <span className="flex items-center gap-1">
                  {layer.dims.reduce((a, d) => a + (filters[d]?.length ?? 0), 0) > 0 && (
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                  )}
                  {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                </span>
              </button>
              {isExpanded && (
                <div className="px-3 pb-3 space-y-2">
                  {layer.dims.map(dim => {
                    const dimData = (tagDict as TagDictionary)[dim]
                    if (!dimData) return null
                    const color = TAG_COLORS[dim]
                    const selected = filters[dim] ?? []
                    return (
                      <div key={dim}>
                        <label className="text-xs text-slate-600 block mb-1">{color?.label ?? dim}</label>
                        <div className="flex flex-wrap gap-1">
                          {dimData.values.map((v: string) => {
                            const active = selected.includes(v)
                            return (
                              <button key={v} onClick={() => toggleTag(dim, v)}
                                className={cn(
                                  'text-xs px-1.5 py-0.5 rounded flex items-center gap-0.5 transition-colors',
                                  active ? `${color?.bg ?? 'bg-amber-500/15'} ${color?.text ?? 'text-amber-400'}` : 'bg-slate-800/60 text-slate-500 hover:text-slate-300',
                                )}>
                                {active && <Check className="w-2.5 h-2.5" />}
                                {v}
                              </button>
                            )
                          })}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}

        <button onClick={handleSearch} disabled={!hasFilters}
          className={cn(
            'w-full py-2 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2',
            hasFilters ? 'bg-amber-500 text-slate-950 hover:bg-amber-400' : 'bg-slate-800 text-slate-500 cursor-not-allowed',
          )}>
          <Search className="w-4 h-4" /> 搜索
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {!submitted ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-600">
            <Search className="w-10 h-10 mb-3 opacity-30" /><p className="text-sm">点击标签筛选，点击搜索</p>
          </div>
        ) : isLoading || isFetching ? (
          <LoadingSkeleton />
        ) : results && results.total > 0 ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <span>找到 {results.total} 个场景</span>
              {results.relaxed && <span className="text-xs px-2 py-0.5 rounded bg-amber-500/15 text-amber-400">已放宽条件</span>}
            </div>
            {results.results.map((s: SceneItem) => <SceneResultCard key={s.scene_id} scene={s} />)}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-slate-600">
            <p className="text-sm">未找到匹配的场景</p>
          </div>
        )}
      </div>
    </div>
  )
}

/* ── Shared ───────────────────────────────────────────── */

function SceneResultCard({ scene }: { scene: SceneItem }) {
  return (
    <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-4 animate-slide-up">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs text-slate-600 font-mono">{scene.scene_id}</span>
        <span className="text-sm font-medium">{scene.title}</span>
        {scene.tension > 0 && <span className="ml-auto text-xs px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 shrink-0">T{scene.tension}</span>}
        {scene.score !== undefined && scene.score < 1 && (
          <span className="text-xs text-slate-500">{Math.round(scene.score * 100)}%</span>
        )}
      </div>
      <p className="text-xs text-slate-500 mb-1">{scene.novel} · {scene.chapter}</p>
      <p className="text-xs text-slate-400 leading-relaxed mb-2">{scene.summary}</p>

      {scene.matched && scene.matched.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {scene.matched.map(m => <span key={m} className="text-xs px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400">{m}</span>)}
        </div>
      )}

      {scene.tags && Object.keys(scene.tags).length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {Object.entries(scene.tags).flatMap(([dim, vals]) =>
            (vals as string[]).map(v => {
              const c = TAG_COLORS[dim]
              return <span key={`${dim}-${v}`} className={cn('text-xs px-1.5 py-0.5 rounded', c?.bg ?? 'bg-slate-700', c?.text ?? 'text-slate-400')}>{v}</span>
            })
          )}
        </div>
      )}

      {scene.characters && scene.characters.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {scene.characters.map(c => <span key={c} className="text-xs px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400">{c}</span>)}
        </div>
      )}
    </div>
  )
}

function LoadingSkeleton() {
  return <div className="space-y-3">{[1, 2, 3].map(i => <div key={i} className="h-28 rounded-xl bg-slate-900/50 animate-pulse" />)}</div>
}
