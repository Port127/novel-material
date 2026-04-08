import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { cn } from '@/lib/utils'
import { Search, Users, Heart, Swords, User as UserIcon, ChevronDown, ChevronUp } from 'lucide-react'
import type { CharacterItem, TagDictionary } from '@/types'

export default function CharacterSearch() {
  const [name, setName] = useState('')
  const [archetype, setArchetype] = useState('')
  const [role, setRole] = useState('')
  const [moralSpectrum, setMoralSpectrum] = useState('')
  const [submitted, setSubmitted] = useState(false)

  const { data: tagDict } = useQuery({ queryKey: ['tagDict'], queryFn: api.getTagDict })

  const archetypes = (tagDict as TagDictionary)?.archetype?.values ?? []
  const moralValues = (tagDict as TagDictionary)?.moral_spectrum?.values ?? []

  const filters = {
    ...(name ? { name } : {}),
    ...(archetype ? { archetype } : {}),
    ...(role ? { role } : {}),
    ...(moralSpectrum ? { moral_spectrum: moralSpectrum } : {}),
  }
  const hasFilters = Object.keys(filters).length > 0

  const { data: results, isLoading } = useQuery({
    queryKey: ['searchCharacters', filters],
    queryFn: () => api.searchCharacters(filters),
    enabled: submitted && hasFilters,
  })

  const handleSearch = useCallback(() => { if (hasFilters) setSubmitted(true) }, [hasFilters])

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <h1 className="text-xl font-semibold">人物搜索</h1>

      <div className="flex flex-wrap gap-3 items-end">
        <div className="w-48">
          <label className="text-xs text-slate-500 block mb-1">人物名</label>
          <input value={name}
            onChange={e => { setName(e.target.value); setSubmitted(false) }}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="模糊搜索..."
            className="w-full text-sm bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 focus:outline-none focus:border-amber-500/50" />
        </div>
        <div className="w-40">
          <label className="text-xs text-slate-500 block mb-1">角色类型</label>
          <select value={role} onChange={e => { setRole(e.target.value); setSubmitted(false) }}
            className="w-full text-sm bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 focus:outline-none focus:border-amber-500/50">
            <option value="">不限</option>
            <option value="protagonist">主角</option>
            <option value="antagonist">反派</option>
            <option value="supporting">配角</option>
            <option value="minor">龙套</option>
          </select>
        </div>
        <div className="w-40">
          <label className="text-xs text-slate-500 block mb-1">原型</label>
          <select value={archetype} onChange={e => { setArchetype(e.target.value); setSubmitted(false) }}
            className="w-full text-sm bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 focus:outline-none focus:border-amber-500/50">
            <option value="">不限</option>
            {archetypes.map((v: string) => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
        <div className="w-36">
          <label className="text-xs text-slate-500 block mb-1">道德光谱</label>
          <select value={moralSpectrum} onChange={e => { setMoralSpectrum(e.target.value); setSubmitted(false) }}
            className="w-full text-sm bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 focus:outline-none focus:border-amber-500/50">
            <option value="">不限</option>
            {moralValues.map((v: string) => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
        <button onClick={handleSearch} disabled={!hasFilters}
          className={cn(
            'px-5 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors',
            hasFilters ? 'bg-amber-500 text-slate-950 hover:bg-amber-400' : 'bg-slate-800 text-slate-500 cursor-not-allowed',
          )}>
          <Search className="w-4 h-4" /> 搜索
        </button>
      </div>

      {!submitted ? (
        <div className="flex flex-col items-center justify-center py-20 text-slate-600">
          <Users className="w-10 h-10 mb-3 opacity-30" />
          <p className="text-sm">输入条件搜索人物</p>
        </div>
      ) : isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map(i => <div key={i} className="h-36 rounded-xl bg-slate-900/50 animate-pulse" />)}
        </div>
      ) : results && results.total > 0 ? (
        <>
          <p className="text-sm text-slate-500">找到 {results.total} 个人物</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {results.results.map((ch: CharacterItem) => (
              <CharacterCard key={`${ch.material_id}-${ch.name}`} char={ch} />
            ))}
          </div>
        </>
      ) : (
        <p className="text-center text-sm text-slate-600 py-20">未找到匹配人物</p>
      )}
    </div>
  )
}

function parseArcSummary(raw: string): { stage: string; state: string; trigger?: string; chapter?: number }[] {
  if (!raw) return []
  try { return JSON.parse(raw) } catch { /* not valid JSON */ }
  try {
    const fixed = raw.replace(/'/g, '"').replace(/None/g, 'null').replace(/True/g, 'true').replace(/False/g, 'false')
    return JSON.parse(fixed)
  } catch { /* not fixable */ }
  return []
}

const roleLabels: Record<string, string> = {
  protagonist: '主角', antagonist: '反派', supporting: '配角', minor: '龙套',
}
const roleIcons: Record<string, typeof UserIcon> = {
  protagonist: Heart, antagonist: Swords, supporting: UserIcon, minor: UserIcon,
}
const psychLabels: Record<string, string> = {
  fatal_flaw: '致命缺陷', obsession: '执念', soft_spot: '软肋', misbelief: '误信',
}

function CharacterCard({ char: ch }: { char: CharacterItem }) {
  const [showArc, setShowArc] = useState(false)
  const arcStages = parseArcSummary(ch.arc_summary)
  const RoleIcon = roleIcons[ch.role] ?? UserIcon

  return (
    <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-4 animate-slide-up">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-lg bg-violet-500/15 flex items-center justify-center shrink-0 mt-0.5">
          <RoleIcon className="w-4 h-4 text-violet-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-medium">{ch.name}</h3>
            {ch.role && <span className="text-xs px-2 py-0.5 rounded bg-blue-500/15 text-blue-400">{roleLabels[ch.role] ?? ch.role}</span>}
            {ch.archetype && <span className="text-xs px-2 py-0.5 rounded bg-violet-500/15 text-violet-400">{ch.archetype}</span>}
          </div>
          <p className="text-xs text-slate-500 mt-0.5">{ch.novel}</p>

          <div className="flex flex-wrap gap-3 mt-2 text-xs text-slate-500">
            {ch.moral_spectrum && <span className="flex items-center gap-1">道德: <strong className="text-slate-300">{ch.moral_spectrum}</strong></span>}
            {ch.narrative_function && <span className="flex items-center gap-1">功能: <strong className="text-slate-300">{ch.narrative_function}</strong></span>}
            <span>出场 <strong className="text-slate-300">{ch.appearance_count}</strong> 次</span>
          </div>

          {ch.psychology && Object.keys(ch.psychology).length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {Object.entries(ch.psychology).map(([k, v]) => (
                <span key={k} className="text-xs px-2 py-0.5 rounded bg-rose-500/10 text-rose-400">
                  {psychLabels[k] ?? k}: {v}
                </span>
              ))}
            </div>
          )}

          {arcStages.length > 0 && (
            <div className="mt-2">
              <button onClick={() => setShowArc(!showArc)}
                className="text-xs text-slate-500 hover:text-slate-300 flex items-center gap-1 transition-colors">
                {showArc ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                人物弧线 ({arcStages.length} 阶段)
              </button>
              {showArc && (
                <div className="mt-2 relative ml-2 border-l border-slate-800 space-y-0 animate-fade-in">
                  {arcStages.map((a, j) => (
                    <div key={j} className="relative pl-4 pb-2 last:pb-0">
                      <div className="absolute left-0 top-1.5 w-1.5 h-1.5 -translate-x-[4px] rounded-full bg-amber-500" />
                      <p className="text-xs font-medium text-slate-300">{a.stage}</p>
                      <p className="text-xs text-slate-500">{a.state}</p>
                      <div className="flex gap-2 text-[10px] text-slate-600">
                        {a.trigger && <span>触发: {a.trigger}</span>}
                        {a.chapter !== undefined && <span>Ch.{a.chapter}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {!arcStages.length && ch.arc_summary && typeof ch.arc_summary === 'string' && ch.arc_summary.length > 0 && !ch.arc_summary.startsWith('[') && (
            <p className="text-xs text-slate-400 mt-2 leading-relaxed">{ch.arc_summary}</p>
          )}
        </div>
      </div>
    </div>
  )
}
