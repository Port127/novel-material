import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import { cn, TAG_COLORS, TAG_LAYERS } from '@/lib/utils'
import { ChevronDown, ChevronRight, Hash, Plus, Merge, X, Loader2, CheckCircle2 } from 'lucide-react'
import type { TagDictionary as TagDictType, TagUsage } from '@/types'

export default function TagDictionary() {
  const qc = useQueryClient()
  const { data: tagDict, isLoading, isError } = useQuery({ queryKey: ['tagDict'], queryFn: api.getTagDict })
  const { data: usage } = useQuery({ queryKey: ['tagUsage'], queryFn: api.getTagUsage })
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [showAdd, setShowAdd] = useState<string | null>(null)
  const [showMerge, setShowMerge] = useState<string | null>(null)

  if (isLoading) {
    return (
      <div className="p-6 max-w-5xl mx-auto space-y-4">
        <h1 className="text-xl font-semibold">标签字典</h1>
        {[1, 2, 3].map(i => <div key={i} className="h-20 rounded-xl bg-slate-900/50 animate-pulse" />)}
      </div>
    )
  }

  if (isError || !tagDict) {
    return (
      <div className="p-6 max-w-5xl mx-auto space-y-4">
        <h1 className="text-xl font-semibold">标签字典</h1>
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-8 text-center">
          <p className="text-sm text-slate-500">加载标签字典失败，请检查后端服务。</p>
        </div>
      </div>
    )
  }

  const toggle = (dim: string) => {
    setExpanded(prev => { const n = new Set(prev); n.has(dim) ? n.delete(dim) : n.add(dim); return n })
  }

  const expandAll = () => {
    const all = new Set<string>()
    TAG_LAYERS.forEach(l => l.dims.forEach(d => all.add(d)))
    setExpanded(all)
  }

  const usageMap = (usage ?? {}) as TagUsage
  const dict = tagDict as TagDictType

  const totalDims = TAG_LAYERS.reduce((a, l) => a + l.dims.length, 0)
  const totalVals = TAG_LAYERS.reduce((a, l) =>
    a + l.dims.reduce((b, d) => b + (dict[d]?.values?.length ?? 0), 0), 0)

  const refreshTags = () => {
    qc.invalidateQueries({ queryKey: ['tagDict'] })
    qc.invalidateQueries({ queryKey: ['tagUsage'] })
  }

  const renderDim = (dim: string, color: { bg: string; text: string; label: string } | undefined) => {
    const dimData = dict[dim]
    if (!dimData) return null
    const isOpen = expanded.has(dim)
    const dimUsage = usageMap[dim] ?? []
    const usageLookup = Object.fromEntries(dimUsage.map(u => [u.value, u.count]))

    return (
      <div key={dim} className="rounded-lg bg-slate-900/80 border border-slate-800/60 overflow-hidden">
        <button onClick={() => toggle(dim)}
          className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-white/[0.02] transition-colors">
          {isOpen ? <ChevronDown className="w-3.5 h-3.5 text-slate-500" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-500" />}
          <span className={cn('text-sm font-medium', color?.text ?? 'text-slate-300')}>{color?.label ?? dimData.description ?? dim}</span>
          <span className="text-xs text-slate-600">{dim}</span>
          <span className="ml-auto text-xs text-slate-600">{dimData.values.length} 值</span>
        </button>
        {isOpen && (
          <div className="px-4 pb-3 animate-fade-in">
            {dimData.description && <p className="text-xs text-slate-500 mb-2">{dimData.description}</p>}
            <div className="flex flex-wrap gap-1.5">
              {dimData.values.map((v: string) => {
                const count = usageLookup[v]
                return (
                  <span key={v} className={cn('text-xs px-2 py-1 rounded inline-flex items-center gap-1.5', color?.bg ?? 'bg-slate-800', color?.text ?? 'text-slate-400')}>
                    {v}
                    {count !== undefined && <span className="text-[10px] opacity-60">{count}</span>}
                  </span>
                )
              })}
            </div>
            <div className="flex gap-2 mt-3">
              <button onClick={() => { setShowAdd(dim); setShowMerge(null) }}
                className="text-xs text-slate-500 hover:text-amber-400 flex items-center gap-1 transition-colors">
                <Plus className="w-3 h-3" /> 新增
              </button>
              {dimData.values.length >= 2 && (
                <button onClick={() => { setShowMerge(dim); setShowAdd(null) }}
                  className="text-xs text-slate-500 hover:text-blue-400 flex items-center gap-1 transition-colors">
                  <Merge className="w-3 h-3" /> 合并
                </button>
              )}
            </div>
            {showAdd === dim && <AddTagInline dimension={dim} onDone={() => { setShowAdd(null); refreshTags() }} />}
            {showMerge === dim && <MergeTagInline dimension={dim} values={dimData.values} onDone={() => { setShowMerge(null); refreshTags() }} />}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">标签字典</h1>
          <p className="text-sm text-slate-500 mt-1">{totalDims} 个维度，{totalVals} 个标签值</p>
        </div>
        <div className="flex gap-2">
          <button onClick={expandAll} className="text-xs px-3 py-1.5 rounded bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors">展开全部</button>
          <button onClick={() => setExpanded(new Set())} className="text-xs px-3 py-1.5 rounded bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors">收起全部</button>
        </div>
      </div>

      {TAG_LAYERS.map(layer => (
        <div key={layer.id} className="space-y-2">
          <h2 className="text-sm font-medium text-slate-400 flex items-center gap-2">
            <Hash className="w-3.5 h-3.5" /> {layer.label}
          </h2>
          {layer.dims.map(dim => renderDim(dim, TAG_COLORS[dim]))}
        </div>
      ))}

      <div className="space-y-2">
        <h2 className="text-sm font-medium text-slate-400 flex items-center gap-2">
          <Hash className="w-3.5 h-3.5" /> G. 小说级标签
        </h2>
        {['genre', 'tone', 'narrative_structure', 'time_handling', 'prose_style', 'writing_strength', 'tropes'].map(dim =>
          renderDim(dim, { bg: 'bg-pink-500/10', text: 'text-pink-400', label: dict[dim]?.description ?? dim })
        )}
      </div>
    </div>
  )
}

function AddTagInline({ dimension, onDone }: { dimension: string; onDone: () => void }) {
  const [value, setValue] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle')
  const [error, setError] = useState('')

  const submit = async () => {
    if (!value.trim()) return
    setStatus('loading')
    try {
      await api.addTag(dimension, value.trim())
      setStatus('ok')
      setTimeout(onDone, 800)
    } catch (e) {
      setError(e instanceof Error ? e.message : '添加失败')
      setStatus('error')
    }
  }

  return (
    <div className="mt-2 flex items-center gap-2 animate-fade-in">
      <input value={value} onChange={e => setValue(e.target.value)} onKeyDown={e => e.key === 'Enter' && submit()}
        placeholder="新标签值..." autoFocus
        className="text-xs bg-slate-950 border border-slate-700 rounded px-2 py-1.5 focus:outline-none focus:border-amber-500/50 w-40" />
      <button onClick={submit} disabled={!value.trim() || status === 'loading'}
        className="text-xs px-2 py-1.5 rounded bg-amber-500/15 text-amber-400 hover:bg-amber-500/25 transition-colors disabled:opacity-50">
        {status === 'loading' ? <Loader2 className="w-3 h-3 animate-spin" /> : status === 'ok' ? <CheckCircle2 className="w-3 h-3" /> : '添加'}
      </button>
      <button onClick={onDone} className="text-xs text-slate-600 hover:text-slate-400"><X className="w-3 h-3" /></button>
      {status === 'error' && <span className="text-xs text-red-400">{error}</span>}
    </div>
  )
}

function MergeTagInline({ dimension, values, onDone }: { dimension: string; values: string[]; onDone: () => void }) {
  const [source, setSource] = useState('')
  const [target, setTarget] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle')
  const [error, setError] = useState('')

  const submit = async () => {
    if (!source || !target || source === target) return
    setStatus('loading')
    try {
      await api.mergeTags(dimension, source, target)
      setStatus('ok')
      setTimeout(onDone, 800)
    } catch (e) {
      setError(e instanceof Error ? e.message : '合并失败')
      setStatus('error')
    }
  }

  return (
    <div className="mt-2 flex items-center gap-2 flex-wrap animate-fade-in">
      <span className="text-xs text-slate-500">将</span>
      <select value={source} onChange={e => setSource(e.target.value)}
        className="text-xs bg-slate-950 border border-slate-700 rounded px-2 py-1.5 focus:outline-none focus:border-blue-500/50">
        <option value="">选择源标签</option>
        {values.map(v => <option key={v} value={v}>{v}</option>)}
      </select>
      <span className="text-xs text-slate-500">合并到</span>
      <select value={target} onChange={e => setTarget(e.target.value)}
        className="text-xs bg-slate-950 border border-slate-700 rounded px-2 py-1.5 focus:outline-none focus:border-blue-500/50">
        <option value="">选择目标标签</option>
        {values.filter(v => v !== source).map(v => <option key={v} value={v}>{v}</option>)}
      </select>
      <button onClick={submit} disabled={!source || !target || source === target || status === 'loading'}
        className="text-xs px-2 py-1.5 rounded bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 transition-colors disabled:opacity-50">
        {status === 'loading' ? <Loader2 className="w-3 h-3 animate-spin" /> : status === 'ok' ? <CheckCircle2 className="w-3 h-3" /> : '合并'}
      </button>
      <button onClick={onDone} className="text-xs text-slate-600 hover:text-slate-400"><X className="w-3 h-3" /></button>
      {status === 'error' && <span className="text-xs text-red-400">{error}</span>}
    </div>
  )
}
