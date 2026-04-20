import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { cn, STATUS_MAP, TAG_COLORS } from '@/lib/utils'
import {
  ArrowLeft, BookOpen, Film, Users, ChevronLeft, ChevronRight,
  Milestone, Sparkles, User, Swords, Heart,
  Play, Loader2, CheckCircle2, AlertCircle, RefreshCw,
} from 'lucide-react'
import ReactECharts from 'echarts-for-react'
import type { SceneItem } from '@/types'

const tabs = [
  { id: 'overview', label: '概览' },
  { id: 'outline', label: '大纲' },
  { id: 'worldbuilding', label: '世界观' },
  { id: 'characters', label: '人物' },
  { id: 'tags', label: '标签' },
  { id: 'scenes', label: '场景' },
  { id: 'stats', label: '统计' },
]

export default function MaterialDetail() {
  const { id } = useParams<{ id: string }>()
  const [tab, setTab] = useState('overview')

  const { data: meta, isLoading, isError } = useQuery({
    queryKey: ['material', id],
    queryFn: () => api.getMaterial(id!),
    enabled: !!id,
  })

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="h-8 w-48 bg-slate-900/50 rounded animate-pulse mb-6" />
        <div className="h-96 bg-slate-900/50 rounded-xl animate-pulse" />
      </div>
    )
  }

  if (isError || !meta) {
    return (
      <div className="p-6 max-w-7xl mx-auto space-y-4">
        <Link to="/materials" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-300 transition-colors">
          <ArrowLeft className="w-3.5 h-3.5" /> 返回素材库
        </Link>
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-8 text-center">
          <p className="text-sm text-slate-500">素材不存在或加载失败</p>
        </div>
      </div>
    )
  }

  const status = STATUS_MAP[meta.status] ?? STATUS_MAP.raw

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      <Link to="/materials" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-300 transition-colors">
        <ArrowLeft className="w-3.5 h-3.5" /> 返回素材库
      </Link>

      <div className="flex items-start gap-3">
        <BookOpen className="w-5 h-5 text-amber-500 mt-1 shrink-0" />
        <div>
          <h1 className="text-lg font-semibold">{meta.name}</h1>
          <div className="flex items-center gap-3 mt-1 flex-wrap">
            <span className="text-sm text-slate-500">{meta.author}</span>
            <span className={cn('text-xs px-2 py-0.5 rounded-full', status.color)}>{status.label}</span>
            {meta.scene_count > 0 && (
              <span className="text-xs text-slate-500 flex items-center gap-1">
                <Film className="w-3 h-3" /> {meta.scene_count} 场景
              </span>
            )}
            {(meta.character_count ?? 0) > 0 && (
              <span className="text-xs text-slate-500 flex items-center gap-1">
                <Users className="w-3 h-3" /> {meta.character_count} 人物
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="flex gap-1 border-b border-slate-800 overflow-x-auto">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              'px-4 py-2 text-sm whitespace-nowrap transition-colors border-b-2 -mb-px',
              tab === t.id
                ? 'border-amber-500 text-amber-400'
                : 'border-transparent text-slate-500 hover:text-slate-300',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="animate-fade-in">
        {tab === 'overview' && <OverviewTab meta={meta} />}
        {tab === 'outline' && <OutlineTab id={id!} />}
        {tab === 'worldbuilding' && <WorldbuildingTab id={id!} />}
        {tab === 'characters' && <CharactersTab id={id!} />}
        {tab === 'tags' && <NovelTagsTab id={id!} />}
        {tab === 'scenes' && <ScenesTab id={id!} />}
        {tab === 'stats' && <StatsTab id={id!} />}
      </div>
    </div>
  )
}

/* ── Overview ─────────────────────────────────────────── */

function OverviewTab({ meta }: { meta: Record<string, unknown> }) {
  const materialId = String(meta.material_id ?? meta.id ?? '')

  const { data: pipelineStatus, refetch: refetchStatus } = useQuery({
    queryKey: ['pipeline-status', materialId],
    queryFn: () => api.getPipelineStatus(materialId),
    enabled: !!materialId,
    refetchInterval: (query) => query.state.data?.running ? 3000 : false,
  })

  const [triggering, setTriggering] = useState<string | null>(null)

  const triggerStage = async (stage: string) => {
    setTriggering(stage)
    try {
      await api.triggerPipeline(materialId, stage)
      setTimeout(() => refetchStatus(), 1000)
    } catch (e) {
      const msg = e instanceof Error ? e.message : '触发失败'
      if (msg.includes('409') || msg.toLowerCase().includes('already running')) {
        if (confirm('Pipeline 似乎卡住了。是否强制重置状态？')) {
          await api.resetPipeline(materialId)
          refetchStatus()
        }
      } else {
        alert(msg)
      }
    } finally {
      setTriggering(null)
    }
  }

  const resetPipeline = async () => {
    try {
      await api.resetPipeline(materialId)
    } catch (e) {
      alert(e instanceof Error ? e.message : '重置失败')
    }
    refetchStatus()
  }

  const completed = pipelineStatus?.stages_completed ?? []
  const running = pipelineStatus?.running
  const currentStage = pipelineStatus?.current_stage

  const SUB_STAGE_LABELS: Record<string, string> = {
    'analyze:outline': '生成大纲…',
    'analyze:worldbuilding': '提取世界观…',
    'analyze:characters': '提取人物…',
    'analyze:tags': '生成标签…',
    'finalize:stats': '生成统计报告…',
  }
  const stageDisplayLabel = currentStage
    ? SUB_STAGE_LABELS[currentStage] ?? currentStage
    : ''

  const pipelineStages = [
    { id: 'ingest', label: '入库检查', needsLlm: false },
    { id: 'format', label: '格式清洗', needsLlm: false },
    { id: 'analyze', label: '分析(LLM)', needsLlm: true },
    { id: 'scenes', label: '场景拆分', needsLlm: true, hint: '需 Agent' },
    { id: 'build-index', label: '构建索引', needsLlm: false },
    { id: 'finalize', label: '统计报告', needsLlm: true },
  ]

  return (
    <div className="space-y-4">
      <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-slate-400">Pipeline</h3>
          <button onClick={() => refetchStatus()} className="text-xs text-slate-500 hover:text-slate-300 flex items-center gap-1">
            <RefreshCw className="w-3 h-3" /> 刷新
          </button>
        </div>

        {running && currentStage && (
          <div className="flex items-center gap-2 text-sm text-amber-400 mb-3 animate-pulse">
            <Loader2 className="w-4 h-4 animate-spin" />
            正在执行: {stageDisplayLabel}
            {currentStage.startsWith('analyze:') && (
              <span className="text-[10px] text-slate-500 ml-1">LLM 分析中，可能需要几分钟</span>
            )}
          </div>
        )}

        {pipelineStatus?.last_error && (
          <div className="flex items-start gap-2 text-sm text-red-400 mb-3 bg-red-500/10 rounded-lg p-3">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <div className="flex-1">
              <span className="text-xs">{pipelineStatus.last_error}</span>
              <button
                onClick={resetPipeline}
                className="ml-2 text-xs text-amber-400 hover:text-amber-300 underline"
              >
                清除错误并重试
              </button>
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {pipelineStages.map(s => {
            const done = completed.includes(s.id)
            const isRunning = currentStage === s.id || currentStage?.startsWith(s.id + ':')
            const isTrigger = triggering === s.id
            const hint = (s as Record<string, unknown>).hint as string | undefined
            return (
              <button
                key={s.id}
                onClick={() => triggerStage(s.id)}
                disabled={!!running || !!isTrigger}
                className={cn(
                  'flex flex-col items-center gap-1.5 p-3 rounded-lg border text-xs transition-colors',
                  done
                    ? 'border-emerald-500/30 bg-emerald-500/5'
                    : 'border-slate-800 hover:border-slate-600',
                  (running || isTrigger) && 'opacity-50 cursor-not-allowed',
                )}
              >
                {isRunning || isTrigger ? (
                  <Loader2 className="w-4 h-4 animate-spin text-amber-400" />
                ) : done ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : (
                  <Play className="w-4 h-4 text-slate-500" />
                )}
                <span className={done ? 'text-emerald-400' : 'text-slate-400'}>{s.label}</span>
                {hint && !done && <span className="text-[10px] text-orange-400/60">{hint}</span>}
                {s.needsLlm && !hint && !done && <span className="text-[10px] text-slate-600">需要 LLM</span>}
              </button>
            )
          })}
        </div>
      </div>

      <TensionOverview materialId={materialId} />

      <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
        <h3 className="text-sm font-medium text-slate-400 mb-3">可用数据</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {([
            ['大纲', meta.has_outline],
            ['世界观', meta.has_worldbuilding],
            ['人物', meta.has_characters],
            ['标签', meta.has_tags],
            ['场景', meta.has_scenes],
            ['统计', meta.has_stats],
          ] as [string, unknown][]).map(([label, ok]) => (
            <div key={label} className="flex items-center gap-2 text-sm">
              <div className={cn('w-2 h-2 rounded-full', ok ? 'bg-emerald-400' : 'bg-slate-600')} />
              <span className={ok ? 'text-slate-200' : 'text-slate-600'}>{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function TensionOverview({ materialId }: { materialId: string }) {
  const { data } = useQuery({
    queryKey: ['material-stats', materialId],
    queryFn: () => api.getMaterialStats(materialId),
    enabled: !!materialId,
  })
  if (!data) return null

  const d = data as Record<string, unknown>
  const basic = (d.basic ?? {}) as Record<string, number>
  const pacing = (d.pacing ?? {}) as Record<string, unknown>
  const tensionDist = (pacing.tension_distribution ?? {}) as Record<string, number>
  const entries = Object.entries(tensionDist).map(([k, v]) => ({ t: Number(k), c: v })).sort((a, b) => a.t - b.t)
  const total = entries.reduce((a, e) => a + e.c, 0)

  if (!total && !basic.total_scenes) return null

  return (
    <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
      <h3 className="text-sm font-medium text-slate-400 mb-3">核心指标</h3>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
        {basic.total_chapters !== undefined && (
          <div className="text-center">
            <p className="text-lg font-bold">{basic.total_chapters}</p>
            <p className="text-xs text-slate-500">总章节</p>
          </div>
        )}
        {basic.total_scenes !== undefined && (
          <div className="text-center">
            <p className="text-lg font-bold">{basic.total_scenes}</p>
            <p className="text-xs text-slate-500">总场景</p>
          </div>
        )}
        {pacing.avg_tension !== undefined && (
          <div className="text-center">
            <p className="text-lg font-bold text-amber-400">{Number(pacing.avg_tension).toFixed(1)}</p>
            <p className="text-xs text-slate-500">平均张力</p>
          </div>
        )}
        {pacing.high_tension_scenes !== undefined && (
          <div className="text-center">
            <p className="text-lg font-bold text-rose-400">{String(pacing.high_tension_scenes)}</p>
            <p className="text-xs text-slate-500">高张力场景</p>
          </div>
        )}
      </div>
      {entries.length > 0 && (
        <div className="flex items-end gap-1 h-12">
          {entries.map(e => (
            <div key={e.t} className="flex-1 flex flex-col items-center gap-0.5">
              <div className="w-full rounded-t" style={{ height: `${(e.c / Math.max(...entries.map(x => x.c))) * 40}px`, backgroundColor: e.t >= 4 ? '#f59e0b' : '#334155' }} />
              <span className="text-[9px] text-slate-600">T{e.t}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ── Outline ──────────────────────────────────────────── */

function OutlineTab({ id }: { id: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['outline', id],
    queryFn: () => api.getOutline(id),
  })

  if (isLoading) return <Skeleton />
  if (isError || !data) return <p className="text-sm text-slate-500">暂无大纲数据</p>

  const d = data as Record<string, unknown>
  const structure = asObjArr(d.structure ?? d.acts ?? d.plot_structure ?? d.story_structure)
  const themes = asArr(d.theme ?? d.themes)
  const tones = asArr(d.tone ?? d.tones)
  const timelines = asObjArr(d.timelines ?? d.timeline)
  const foreshadowing = asObjArr(d.foreshadowing ?? d.foreshadowings ?? d.foreshadow)
  const pacingCurve = asObjArr(d.pacing_curve ?? d.pacing)
  const premise = d.premise ?? d.synopsis ?? d.summary ?? d.overview

  return (
    <div className="space-y-4">
      {premise && (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
          <h3 className="text-sm font-medium text-slate-400 mb-2 flex items-center gap-2">
            <Sparkles className="w-4 h-4" /> 故事前提
          </h3>
          <p className="text-sm text-slate-200 leading-relaxed">{String(premise)}</p>
          {(themes.length > 0 || tones.length > 0) && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {themes.map(t => <span key={t} className="text-xs px-2 py-0.5 rounded bg-amber-500/15 text-amber-400">{t}</span>)}
              {tones.map(t => <span key={t} className="text-xs px-2 py-0.5 rounded bg-blue-500/15 text-blue-400">{t}</span>)}
            </div>
          )}
        </div>
      )}

      {structure.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-slate-400 flex items-center gap-2">
            <Milestone className="w-4 h-4" /> 故事结构 ({structure.length} 幕)
          </h3>
          <div className="relative ml-3 border-l-2 border-slate-800 space-y-0">
            {structure.map((act, i) => {
              const chapters = act.chapters as number[] | undefined
              return (
                <div key={i} className="relative pl-6 pb-6 last:pb-0">
                  <div className="absolute left-0 top-1 w-3 h-3 -translate-x-[7px] rounded-full bg-amber-500 border-2 border-slate-950" />
                  <div className="rounded-lg bg-slate-900/80 border border-slate-800/60 p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="text-sm font-medium">{String(act.act ?? act.title ?? `第${i + 1}幕`)}</h4>
                      {chapters && (
                        <span className="text-xs text-slate-600">Ch.{chapters[0]}-{chapters[1]}</span>
                      )}
                    </div>
                    {act.title && act.act && <p className="text-xs text-slate-500 mb-1">{String(act.title)}</p>}
                    {act.arc && <p className="text-xs text-slate-400 leading-relaxed mb-2">{String(act.arc)}</p>}
                    <div className="flex flex-wrap gap-3 text-xs">
                      {act.key_event && (
                        <span className="text-rose-400">
                          <strong className="text-rose-500">关键事件:</strong> {String(act.key_event)}
                        </span>
                      )}
                      {act.turning_point && (
                        <span className="text-blue-400">
                          <strong className="text-blue-500">转折点:</strong> {String(act.turning_point)}
                        </span>
                      )}
                    </div>
                    {act.pacing_note && (
                      <p className="text-xs text-slate-600 mt-1 italic">{String(act.pacing_note)}</p>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {timelines.length > 0 && (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
          <h3 className="text-sm font-medium text-slate-400 mb-3">时间线</h3>
          <div className="space-y-2">
            {timelines.map((tl, i) => (
              <div key={i} className="bg-slate-800/40 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium text-slate-200">{String(tl.name ?? `时间线 ${i + 1}`)}</span>
                  {tl.chapters && <span className="text-[10px] text-slate-600">Ch.{(tl.chapters as number[]).join('→')}</span>}
                </div>
                {tl.description && <p className="text-xs text-slate-400 leading-relaxed">{String(tl.description)}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {foreshadowing.length > 0 && (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
          <h3 className="text-sm font-medium text-slate-400 mb-3">钩子网络 ({foreshadowing.length})</h3>
          <div className="space-y-2">
            {foreshadowing.map((f, i) => (
              <div key={i} className="bg-slate-800/40 rounded-lg p-3 text-xs">
                <div className="flex items-start gap-2">
                  <span className="shrink-0 text-amber-400 mt-0.5">→</span>
                  <div>
                    <p className="text-slate-300 leading-relaxed">{String(f.plant_description ?? f.description ?? '')}</p>
                    <div className="flex gap-3 mt-1 text-slate-600">
                      {f.plant_chapter !== undefined && <span>埋设 Ch.{String(f.plant_chapter)}</span>}
                      {f.payoff_chapter !== undefined && <span>回收 Ch.{String(f.payoff_chapter)}</span>}
                      {f.payoff_description && <span className="text-emerald-500/60">⟵ {String(f.payoff_description)}</span>}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {pacingCurve.length > 0 && (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
          <h3 className="text-sm font-medium text-slate-400 mb-3">节奏曲线</h3>
          <div className="flex items-end gap-0.5 h-16">
            {pacingCurve.map((p, i) => {
              const t = Number(p.tension ?? 3)
              return (
                <div key={i} className="flex-1 flex flex-col items-center group relative">
                  <div className="w-full rounded-t min-h-[2px]" style={{ height: `${(t / 5) * 56}px`, backgroundColor: t >= 4 ? '#f59e0b' : t >= 3 ? '#475569' : '#1e293b' }} />
                  <div className="hidden group-hover:block absolute bottom-full mb-1 bg-slate-800 border border-slate-700 rounded px-2 py-1 text-[10px] text-slate-300 whitespace-nowrap z-10">
                    Ch.{String(p.chapter)} T{t} {p.note ? `— ${String(p.note).slice(0, 30)}` : ''}
                  </div>
                </div>
              )
            })}
          </div>
          <div className="flex justify-between text-[9px] text-slate-600 mt-1">
            <span>Ch.{String(pacingCurve[0]?.chapter)}</span>
            <span>Ch.{String(pacingCurve[pacingCurve.length - 1]?.chapter)}</span>
          </div>
        </div>
      )}

      <RemainingFields data={d} consumed={['material_id', 'premise', 'synopsis', 'summary', 'overview', 'structure', 'acts', 'plot_structure', 'story_structure', 'theme', 'themes', 'tone', 'tones', 'timelines', 'timeline', 'foreshadowing', 'foreshadowings', 'foreshadow', 'pacing_curve', 'pacing']} />
    </div>
  )
}

/* ── Characters ───────────────────────────────────────── */

function CharactersTab({ id }: { id: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['characters-yaml', id],
    queryFn: () => api.getCharacters(id),
  })

  if (isLoading) return <Skeleton />
  if (isError || !data) return <p className="text-sm text-slate-500">暂无人物数据</p>

  const d = data as Record<string, unknown>
  const roster = asObjArr(d.roster ?? d.characters ?? d.cast ?? d.people)
  if (!roster.length) return <RemainingFields data={d} consumed={['material_id']} />

  const roleIcons: Record<string, typeof User> = {
    protagonist: Heart, antagonist: Swords, supporting: User, minor: User,
  }
  const roleLabels: Record<string, string> = {
    protagonist: '主角', antagonist: '反派', supporting: '配角', minor: '龙套',
  }

  return (
    <div className="space-y-3">
      {roster.map((ch, i) => {
        const role = String(ch.role ?? '')
        const RoleIcon = roleIcons[role] ?? User
        const aliases = asArr(ch.aliases)
        const traits = asArr(ch.traits)
        const arcs = asObjArr(ch.arc ?? ch.arcs ?? ch.arc_summary)

        return (
          <div key={i} className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-4">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-lg bg-violet-500/15 flex items-center justify-center shrink-0 mt-0.5">
                <RoleIcon className="w-4 h-4 text-violet-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h4 className="font-medium">{String(ch.name)}</h4>
                  {role && <span className="text-xs px-2 py-0.5 rounded bg-blue-500/15 text-blue-400">{roleLabels[role] ?? role}</span>}
                  {ch.archetype && <span className="text-xs px-2 py-0.5 rounded bg-violet-500/15 text-violet-400">{String(ch.archetype)}</span>}
                  {ch.moral_spectrum && <span className="text-xs text-slate-600">{String(ch.moral_spectrum)}</span>}
                </div>
                {aliases.length > 0 && (
                  <p className="text-xs text-slate-600 mt-0.5">别名: {aliases.join('、')}</p>
                )}
                {ch.description && <p className="text-xs text-slate-400 mt-1 leading-relaxed">{String(ch.description)}</p>}
                {traits.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {traits.map(t => <span key={t} className="text-xs px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400">{t}</span>)}
                  </div>
                )}
                {arcs.length > 0 && (
                  <div className="mt-3 flex gap-1 overflow-x-auto pb-1">
                    {arcs.map((a, j) => (
                      <div key={j} className="shrink-0 text-xs bg-slate-800/60 rounded px-2 py-1.5 max-w-[180px]">
                        <p className="font-medium text-slate-300 truncate">{String(a.stage ?? a.state ?? '')}</p>
                        {a.chapter !== undefined && <p className="text-slate-600">Ch.{String(a.chapter)}</p>}
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex gap-3 mt-2 text-xs text-slate-600">
                  {ch.appearance_count !== undefined && <span>出场 {String(ch.appearance_count)} 次</span>}
                  {ch.narrative_function && <span>功能: {String(ch.narrative_function)}</span>}
                </div>
              </div>
            </div>
          </div>
        )
      })}
      <RemainingFields data={d} consumed={['material_id', 'roster', 'characters', 'cast', 'people', 'relationships', 'relation']} />
    </div>
  )
}

/* ── Novel Tags ───────────────────────────────────────── */

function NovelTagsTab({ id }: { id: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['novel-tags', id],
    queryFn: () => api.getNovelTags(id),
  })

  if (isLoading) return <Skeleton />
  if (isError || !data) return <p className="text-sm text-slate-500">暂无标签数据</p>

  const d = data as Record<string, unknown>
  const narrative = (d.narrative ?? {}) as Record<string, unknown>
  const style = (d.style ?? {}) as Record<string, unknown>

  const sections: { label: string; color: string; items: string[] }[] = [
    { label: '类型', color: 'bg-rose-500/15 text-rose-400', items: [...asArr(d.genre), ...asArr(d.sub_genre)] },
    { label: '主题', color: 'bg-amber-500/15 text-amber-400', items: asArr(d.theme) },
    { label: '基调', color: 'bg-blue-500/15 text-blue-400', items: asArr(d.tone) },
    { label: '文笔', color: 'bg-emerald-500/15 text-emerald-400', items: asArr(style.prose ?? style.prose_style) },
    { label: '写作长板', color: 'bg-violet-500/15 text-violet-400', items: asArr(style.strength ?? style.writing_strength) },
    { label: '套路', color: 'bg-pink-500/15 text-pink-400', items: asArr(d.tropes) },
  ]

  const goodFor = asArr(d.good_for)
  const highlights = asArr(d.highlights)

  return (
    <div className="space-y-4">
      {sections.filter(s => s.items.length > 0).map(s => (
        <div key={s.label} className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-4">
          <h4 className="text-xs font-medium text-slate-500 mb-2">{s.label}</h4>
          <div className="flex flex-wrap gap-1.5">
            {s.items.map(v => <span key={v} className={cn('text-xs px-2 py-1 rounded', s.color)}>{v}</span>)}
          </div>
        </div>
      ))}

      {(narrative.structure || narrative.pov_style || narrative.pov || narrative.time_handling) && (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-4">
          <h4 className="text-xs font-medium text-slate-500 mb-2">叙事结构</h4>
          <div className="flex flex-wrap gap-3 text-sm text-slate-300">
            {narrative.structure && <span>结构: <strong className="text-cyan-400">{String(narrative.structure)}</strong></span>}
            {(narrative.pov_style || narrative.pov) && <span>视角: <strong className="text-cyan-400">{String(narrative.pov_style ?? narrative.pov)}</strong></span>}
            {narrative.time_handling && <span>时间: <strong className="text-cyan-400">{String(narrative.time_handling)}</strong></span>}
          </div>
        </div>
      )}

      {highlights.length > 0 && (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-4">
          <h4 className="text-xs font-medium text-slate-500 mb-2">亮点</h4>
          <div className="space-y-1.5">
            {highlights.map(h => <p key={h} className="text-xs text-slate-300 leading-relaxed">• {h}</p>)}
          </div>
        </div>
      )}

      {goodFor.length > 0 && (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-4">
          <h4 className="text-xs font-medium text-slate-500 mb-2">适合参考</h4>
          <div className="flex flex-wrap gap-1.5">
            {goodFor.map(g => <span key={g} className="text-xs px-2 py-1 rounded bg-cyan-500/10 text-cyan-400">{g}</span>)}
          </div>
        </div>
      )}

      <RemainingFields data={d} consumed={['material_id', 'genre', 'sub_genre', 'theme', 'themes', 'tone', 'tones', 'narrative', 'style', 'tropes', 'good_for', 'highlights']} />
    </div>
  )
}

/* ── Worldbuilding ────────────────────────────────────── */

const WB_LABELS: Record<string, string> = {
  power_system: '力量体系', geography: '地理空间',
  factions: '势力组织', factions_world: '势力组织',
  society: '社会背景', background: '社会背景',
  economy: '经济体系', culture: '文化', history: '历史',
  lore: '背景传说', rules_of_world: '世界规则',
  technology: '科技体系', magic_system: '魔法体系',
  religion: '宗教信仰', politics: '政治格局',
  races: '种族设定', languages: '语言体系',
}

function WorldbuildingTab({ id }: { id: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['worldbuilding', id],
    queryFn: () => api.getWorldbuilding(id),
  })

  if (isLoading) return <Skeleton />
  if (isError || !data) return <p className="text-sm text-slate-500">暂无世界观数据</p>

  const d = data as Record<string, unknown>
  const keys = Object.keys(d).filter(k => k !== 'material_id')

  if (keys.length === 0) return <p className="text-sm text-slate-500">暂无世界观数据（仅有 material_id）</p>

  return (
    <div className="space-y-4">
      {keys.map(k => renderWbSection(WB_LABELS[k] ?? k.replace(/_/g, ' '), d[k]))}
    </div>
  )
}

function renderWbSection(title: string, value: unknown) {
  if (!value) return null
  if (typeof value === 'string') {
    return (
      <div key={title} className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
        <h3 className="text-sm font-medium text-slate-400 mb-2">{title}</h3>
        <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap">{value}</p>
      </div>
    )
  }
  if (Array.isArray(value)) {
    return (
      <div key={title} className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
        <h3 className="text-sm font-medium text-slate-400 mb-2">{title}</h3>
        <div className="space-y-2">
          {value.map((item, i) => {
            if (typeof item === 'string') return <p key={i} className="text-xs text-slate-300">{item}</p>
            if (typeof item === 'object' && item !== null) {
              const obj = item as Record<string, unknown>
              const name = obj.name ?? obj.title ?? obj.label ?? ''
              const desc = obj.description ?? obj.desc ?? obj.detail ?? ''
              return (
                <div key={i} className="bg-slate-800/40 rounded-lg p-3">
                  {name && <p className="text-xs font-medium text-slate-200">{String(name)}</p>}
                  {desc && <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">{String(desc)}</p>}
                  {Object.entries(obj).filter(([k]) => !['name', 'title', 'label', 'description', 'desc', 'detail'].includes(k)).map(([k, v]) => (
                    <p key={k} className="text-xs text-slate-500 mt-0.5"><span className="text-slate-600">{k}:</span> {typeof v === 'object' ? JSON.stringify(v) : String(v)}</p>
                  ))}
                </div>
              )
            }
            return <p key={i} className="text-xs text-slate-400">{JSON.stringify(item)}</p>
          })}
        </div>
      </div>
    )
  }
  if (typeof value === 'object' && value !== null) {
    const obj = value as Record<string, unknown>
    return (
      <div key={title} className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
        <h3 className="text-sm font-medium text-slate-400 mb-2">{title}</h3>
        <div className="space-y-1">
          {Object.entries(obj).map(([k, v]) => (
            <div key={k}>
              {typeof v === 'string' ? (
                <p className="text-xs"><span className="text-slate-500">{k}:</span> <span className="text-slate-300">{v}</span></p>
              ) : Array.isArray(v) ? (
                <div className="mb-1">
                  <p className="text-xs text-slate-500">{k}:</p>
                  <div className="flex flex-wrap gap-1 mt-0.5">
                    {v.map((item, j) => <span key={j} className="text-xs px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400">{typeof item === 'string' ? item : JSON.stringify(item)}</span>)}
                  </div>
                </div>
              ) : (
                <p className="text-xs"><span className="text-slate-500">{k}:</span> <span className="text-slate-300">{JSON.stringify(v)}</span></p>
              )}
            </div>
          ))}
        </div>
      </div>
    )
  }
  return null
}

/* ── Stats ────────────────────────────────────────────── */

function normalizeStats(raw: Record<string, unknown>) {
  const basic = (raw.basic ?? raw.basic_stats ?? {}) as Record<string, number>

  const sceneDist = (raw.scene_type_distribution ?? []) as { type: string; count: number; ratio: number }[]
  const emotionDist = (raw.emotion_distribution ?? []) as { emotion: string; count: number }[]

  const oldPacing = (raw.pacing ?? {}) as Record<string, unknown>
  const tensionRaw = raw.tension_stats as Record<string, number> | undefined
  const pacing = {
    tension_distribution: oldPacing.tension_distribution as Record<string, number> | undefined,
    avg_tension: oldPacing.avg_tension ?? tensionRaw?.avg_tension,
    high_tension_scenes: oldPacing.high_tension_scenes ?? tensionRaw?.high_tension_count,
  }

  let top10: Record<string, number> = {}
  const cs = raw.character_stats
  if (cs && typeof cs === 'object' && !Array.isArray(cs)) {
    top10 = ((cs as Record<string, unknown>).top_10 ?? {}) as Record<string, number>
  } else if (Array.isArray(cs)) {
    for (const c of cs.slice(0, 10)) {
      const item = c as Record<string, unknown>
      if (item.name) top10[String(item.name)] = Number(item.scene_count ?? 0)
    }
  }

  const foreshadow = (raw.foreshadowing_stats ?? {}) as Record<string, unknown>

  const oldTurning = (raw.turning_points ?? {}) as Record<string, unknown>
  const turningPoints = oldTurning.key_turning_points as { chapter: number; event: string }[] | undefined

  const oldTech = (raw.technique_stats ?? {}) as Record<string, unknown>
  const techniques = oldTech.techniques_used as string[] | undefined

  const pacingAnalysis = raw.pacing_analysis as { total_acts?: number; act_structure?: { act: string; chapters: string; scene_count: number; avg_tension: number }[] } | undefined
  const structureAssess = raw.structure_assessment as Record<string, string> | undefined

  return { basic, sceneDist, emotionDist, pacing, top10, foreshadow, turningPoints, techniques, pacingAnalysis, structureAssess }
}

function StatsTab({ id }: { id: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['material-stats', id],
    queryFn: () => api.getMaterialStats(id),
  })

  if (isLoading) return <Skeleton />
  if (isError || !data) return <p className="text-sm text-slate-500">暂无统计数据</p>

  const { basic, sceneDist, emotionDist, pacing, top10, foreshadow, turningPoints, techniques, pacingAnalysis, structureAssess } = normalizeStats(data as Record<string, unknown>)

  const tensionDist = pacing.tension_distribution ?? {}
  const tensionData = Object.entries(tensionDist).map(([k, v]) => ({ tension: Number(k), count: v })).sort((a, b) => a.tension - b.tension)

  const tensionOption = tensionData.length > 0 ? {
    tooltip: { trigger: 'axis' as const },
    xAxis: { type: 'category' as const, data: tensionData.map(t => `T${t.tension}`), axisLabel: { color: '#94a3b8' } },
    yAxis: { type: 'value' as const, axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: '#1e293b' } } },
    series: [{ type: 'bar', data: tensionData.map(t => t.count), itemStyle: { color: '#f59e0b', borderRadius: [4, 4, 0, 0] } }],
    grid: { top: 20, bottom: 30, left: 45, right: 15 },
  } : null

  const distOption = sceneDist.length > 0 ? {
    tooltip: { trigger: 'item' as const },
    series: [{
      type: 'pie', radius: ['35%', '65%'], avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#020617', borderWidth: 2 },
      label: { color: '#94a3b8', fontSize: 11 },
      data: sceneDist.slice(0, 12).map(s => ({ name: s.type, value: s.count })),
    }],
  } : null

  return (
    <div className="space-y-4">
      {/* Basic numbers */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard value={basic.total_chapters} label="总章节" />
        <StatCard value={basic.total_scenes} label="总场景" />
        <StatCard value={basic.avg_scenes_per_chapter?.toFixed(2)} label="场景/章" />
        {pacing.avg_tension !== undefined && <StatCard value={Number(pacing.avg_tension).toFixed(1)} label="平均张力" />}
      </div>

      {/* Tension distribution */}
      {tensionOption && (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium text-slate-400">张力分布</h3>
            {pacing.high_tension_scenes !== undefined && (
              <span className="text-xs text-amber-400">高张力场景: {String(pacing.high_tension_scenes)}</span>
            )}
          </div>
          <ReactECharts option={tensionOption} style={{ height: 200 }} theme="dark" />
        </div>
      )}

      {/* Scene type distribution */}
      {distOption && (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
          <h3 className="text-sm font-medium text-slate-400 mb-2">场景类型分布</h3>
          <ReactECharts option={distOption} style={{ height: 280 }} theme="dark" />
        </div>
      )}

      {/* Emotion distribution */}
      {emotionDist.length > 0 && (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
          <h3 className="text-sm font-medium text-slate-400 mb-3">情绪分布</h3>
          <div className="space-y-1.5">
            {emotionDist.map(e => {
              const maxCount = emotionDist[0]?.count ?? 1
              return (
                <div key={e.emotion} className="flex items-center gap-2 text-xs">
                  <span className="w-14 text-slate-400 text-right shrink-0">{e.emotion}</span>
                  <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500/50 rounded-full" style={{ width: `${(e.count / maxCount) * 100}%` }} />
                  </div>
                  <span className="w-10 text-slate-500 text-right">{e.count}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Top characters */}
      {Object.keys(top10).length > 0 && (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
          <h3 className="text-sm font-medium text-slate-400 mb-3">出场人物 Top 10</h3>
          <div className="space-y-1.5">
            {Object.entries(top10).map(([name, count], i) => {
              const max = Object.values(top10)[0] ?? 1
              return (
                <div key={name} className="flex items-center gap-2 text-xs">
                  <span className="w-4 text-slate-600 text-right shrink-0">{i + 1}</span>
                  <span className="w-20 text-slate-300 shrink-0 truncate">{name}</span>
                  <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-violet-500/50 rounded-full" style={{ width: `${(count / max) * 100}%` }} />
                  </div>
                  <span className="w-10 text-slate-500 text-right">{count}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Turning points */}
      {turningPoints && turningPoints.length > 0 && (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
          <h3 className="text-sm font-medium text-slate-400 mb-3">关键转折点</h3>
          <div className="relative ml-3 border-l border-slate-800 space-y-0">
            {turningPoints.map((tp, i) => (
              <div key={i} className="relative pl-5 pb-3 last:pb-0">
                <div className="absolute left-0 top-1 w-2 h-2 -translate-x-[5px] rounded-full bg-rose-500" />
                <p className="text-xs text-slate-300">{tp.event}</p>
                <p className="text-[10px] text-slate-600">Ch.{tp.chapter}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Foreshadowing */}
      {Object.keys(foreshadow).length > 0 && (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
          <h3 className="text-sm font-medium text-slate-400 mb-2">钩子统计</h3>
          <div className="flex gap-6 text-sm flex-wrap">
            {foreshadow.plant_scenes !== undefined && <span className="text-slate-400">埋设: <strong className="text-amber-400">{String(foreshadow.plant_scenes)}</strong></span>}
            {foreshadow.payoff_scenes !== undefined && <span className="text-slate-400">回收: <strong className="text-emerald-400">{String(foreshadow.payoff_scenes)}</strong></span>}
            {foreshadow.total_foreshadowing !== undefined && <span className="text-slate-400">总数: <strong className="text-amber-400">{String(foreshadow.total_foreshadowing)}</strong></span>}
            {foreshadow.high_confidence !== undefined && <span className="text-slate-400">高置信: <strong className="text-emerald-400">{String(foreshadow.high_confidence)}</strong></span>}
            {foreshadow.medium_confidence !== undefined && <span className="text-slate-400">中置信: <strong className="text-blue-400">{String(foreshadow.medium_confidence)}</strong></span>}
          </div>
        </div>
      )}

      {/* Techniques */}
      {techniques && techniques.length > 0 && (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
          <h3 className="text-sm font-medium text-slate-400 mb-2">写作技法</h3>
          <div className="flex flex-wrap gap-1.5">
            {techniques.map(t => <span key={t} className="text-xs px-2 py-1 rounded bg-cyan-500/10 text-cyan-400">{t}</span>)}
          </div>
        </div>
      )}

      {/* Pacing analysis (new schema) */}
      {pacingAnalysis?.act_structure && pacingAnalysis.act_structure.length > 0 && (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
          <h3 className="text-sm font-medium text-slate-400 mb-3">节奏分析 ({pacingAnalysis.total_acts ?? pacingAnalysis.act_structure.length} 幕)</h3>
          <div className="space-y-2">
            {pacingAnalysis.act_structure.map((act, i) => (
              <div key={i} className="flex items-center gap-3 text-xs bg-slate-800/40 rounded-lg p-2.5">
                <span className="text-slate-300 font-medium shrink-0 w-40 truncate">{act.act}</span>
                <span className="text-slate-500 shrink-0">Ch.{act.chapters}</span>
                <span className="text-slate-500 shrink-0">{act.scene_count} 场景</span>
                <span className="text-amber-400 shrink-0">T{act.avg_tension}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Structure assessment (new schema) */}
      {structureAssess && Object.keys(structureAssess).length > 0 && (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
          <h3 className="text-sm font-medium text-slate-400 mb-3">结构评估</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {Object.entries(structureAssess).map(([k, v]) => (
              <div key={k} className="text-xs bg-slate-800/40 rounded-lg p-2.5">
                <span className="text-slate-500">{k.replace(/_/g, ' ')}: </span>
                <span className="text-slate-300">{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Scene type detail bars */}
      {sceneDist.length > 0 && (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
          <h3 className="text-sm font-medium text-slate-400 mb-3">场景类型明细</h3>
          <div className="space-y-1.5">
            {sceneDist.map(s => (
              <div key={s.type} className="flex items-center gap-2 text-xs">
                <span className="w-20 text-slate-400 text-right shrink-0">{s.type}</span>
                <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-amber-500/50 rounded-full" style={{ width: `${s.ratio * 100}%` }} />
                </div>
                <span className="w-10 text-slate-500 text-right">{s.count}</span>
                <span className="w-12 text-slate-600 text-right">{(s.ratio * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({ value, label }: { value: unknown; label: string }) {
  if (value === undefined || value === null) return null
  return (
    <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-4 text-center">
      <p className="text-2xl font-bold">{String(value)}</p>
      <p className="text-xs text-slate-500 mt-1">{label}</p>
    </div>
  )
}

/* ── Scenes ───────────────────────────────────────────── */

function ScenesTab({ id }: { id: string }) {
  const [page, setPage] = useState(1)
  const limit = 30

  const { data, isLoading } = useQuery({
    queryKey: ['scenes', id, page],
    queryFn: () => api.getScenes(id, page, limit),
  })

  if (isLoading) return <Skeleton />
  if (!data || data.scenes.length === 0) return <p className="text-sm text-slate-500">暂无场景数据</p>

  const totalPages = Math.ceil(data.total / limit)

  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-500">共 {data.total} 个场景，第 {page}/{totalPages} 页</p>
      <div className="space-y-2">
        {data.scenes.map((s: SceneItem) => <SceneRow key={s.scene_id} scene={s} />)}
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="p-1.5 rounded hover:bg-slate-800 disabled:opacity-30 transition-colors">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm text-slate-500 min-w-[80px] text-center">{page} / {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} className="p-1.5 rounded hover:bg-slate-800 disabled:opacity-30 transition-colors">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  )
}

function SceneRow({ scene }: { scene: SceneItem }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="rounded-lg bg-slate-900/80 border border-slate-800/60 overflow-hidden">
      <button onClick={() => setOpen(!open)} className="w-full text-left p-3 hover:bg-white/[0.02] transition-colors">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs text-slate-600 font-mono shrink-0">{scene.scene_id}</span>
          <span className="text-sm font-medium truncate">{scene.title}</span>
          <span className="ml-auto text-xs px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 shrink-0">T{scene.tension}</span>
        </div>
        <p className="text-xs text-slate-500 truncate">{scene.chapter}</p>
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-2 animate-fade-in border-t border-slate-800/40 pt-2">
          <p className="text-xs text-slate-400 leading-relaxed">{scene.summary}</p>
          {scene.characters && scene.characters.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {scene.characters.map(c => <span key={c} className="text-xs px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400">{c}</span>)}
            </div>
          )}
          {scene.tags && Object.keys(scene.tags).length > 0 && (
            <div className="flex flex-wrap gap-1">
              {Object.entries(scene.tags).flatMap(([dim, vals]) =>
                (vals as string[]).map(v => {
                  const c = TAG_COLORS[dim]
                  return <span key={`${dim}-${v}`} className={cn('text-xs px-1.5 py-0.5 rounded', c?.bg ?? 'bg-slate-700', c?.text ?? 'text-slate-400')}>{v}</span>
                })
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ── Shared ───────────────────────────────────────────── */

function Skeleton() {
  return <div className="h-48 rounded-xl bg-slate-900/50 animate-pulse" />
}


function asArr(v: unknown): string[] {
  if (Array.isArray(v)) return v.map(String)
  if (typeof v === 'string') return [v]
  return []
}

function asObjArr(v: unknown): Record<string, unknown>[] {
  if (Array.isArray(v)) return v.filter(x => x && typeof x === 'object') as Record<string, unknown>[]
  return []
}

function RemainingFields({ data, consumed }: { data: Record<string, unknown>; consumed: string[] }) {
  const remaining = Object.entries(data).filter(([k, v]) => !consumed.includes(k) && v != null && v !== '')
  if (remaining.length === 0) return null

  return (
    <>
      {remaining.map(([key, value]) => {
        const label = key.replace(/_/g, ' ')
        if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
          return (
            <div key={key} className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-4">
              <h4 className="text-xs font-medium text-slate-500 mb-2">{label}</h4>
              <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{String(value)}</p>
            </div>
          )
        }
        if (Array.isArray(value)) {
          const flat = value.every(v => typeof v === 'string' || typeof v === 'number')
          return (
            <div key={key} className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-4">
              <h4 className="text-xs font-medium text-slate-500 mb-2">{label}</h4>
              {flat ? (
                <div className="flex flex-wrap gap-1.5">
                  {value.map((v, i) => <span key={i} className="text-xs px-2 py-1 rounded bg-slate-800 text-slate-300">{String(v)}</span>)}
                </div>
              ) : (
                <div className="space-y-2">
                  {value.map((v, i) => {
                    if (typeof v === 'object' && v !== null) {
                      const obj = v as Record<string, unknown>
                      const name = obj.name ?? obj.title ?? obj.label ?? ''
                      const desc = obj.description ?? obj.desc ?? ''
                      return (
                        <div key={i} className="bg-slate-800/40 rounded-lg p-3">
                          {name && <p className="text-xs font-medium text-slate-200">{String(name)}</p>}
                          {desc && <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">{String(desc)}</p>}
                          {Object.entries(obj).filter(([k]) => !['name', 'title', 'label', 'description', 'desc'].includes(k)).map(([k, val]) => (
                            <p key={k} className="text-xs text-slate-500 mt-0.5"><span className="text-slate-600">{k}:</span> {typeof val === 'object' ? JSON.stringify(val) : String(val)}</p>
                          ))}
                        </div>
                      )
                    }
                    return <p key={i} className="text-xs text-slate-400">{String(v)}</p>
                  })}
                </div>
              )}
            </div>
          )
        }
        if (typeof value === 'object' && value !== null) {
          const obj = value as Record<string, unknown>
          return (
            <div key={key} className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-4">
              <h4 className="text-xs font-medium text-slate-500 mb-2">{label}</h4>
              <div className="space-y-1">
                {Object.entries(obj).map(([k, v]) => (
                  <div key={k} className="text-xs">
                    <span className="text-slate-500">{k}:</span>{' '}
                    <span className="text-slate-300">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )
        }
        return null
      })}
    </>
  )
}
