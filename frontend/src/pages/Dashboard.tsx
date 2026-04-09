import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { BookOpen, Film, Users, Tag } from 'lucide-react'
import ReactECharts from 'echarts-for-react'

function StatCard({ icon: Icon, label, value, color }: {
  icon: React.ElementType; label: string; value: number | string; color: string
}) {
  return (
    <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5 animate-fade-in">
      <div className="flex items-center gap-3 mb-3">
        <div className={`p-2 rounded-lg ${color}`}>
          <Icon className="w-4 h-4" />
        </div>
        <span className="text-sm text-slate-400">{label}</span>
      </div>
      <p className="text-2xl font-bold tracking-tight">{value}</p>
    </div>
  )
}

export default function Dashboard() {
  const { data: stats, isLoading, isError } = useQuery({
    queryKey: ['stats'],
    queryFn: api.getStats,
  })

  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <h1 className="text-xl font-semibold">总览</h1>
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-28 rounded-xl bg-slate-900/50 animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  if (isError || !stats) {
    return (
      <div className="p-6 space-y-6">
        <h1 className="text-xl font-semibold">总览</h1>
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-8 text-center">
          <p className="text-sm text-slate-500">暂无统计数据。请先添加小说素材并运行 Pipeline。</p>
        </div>
      </div>
    )
  }

  const sceneTypeOption = {
    tooltip: { trigger: 'item' as const },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#020617', borderWidth: 2 },
      label: { color: '#94a3b8', fontSize: 11 },
      data: stats.top_scene_types.slice(0, 10).map(t => ({
        name: t.value, value: t.count,
      })),
    }],
  }

  const emotionOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 80, right: 20, top: 10, bottom: 30 },
    xAxis: { type: 'value' as const, axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: '#1e293b' } } },
    yAxis: {
      type: 'category' as const,
      data: stats.top_emotions.slice(0, 10).map(e => e.value).reverse(),
      axisLabel: { color: '#94a3b8', fontSize: 11 },
    },
    series: [{
      type: 'bar',
      data: stats.top_emotions.slice(0, 10).map(e => e.count).reverse(),
      itemStyle: { color: '#f59e0b', borderRadius: [0, 4, 4, 0] },
      barWidth: 16,
    }],
  }

  const tensionOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 40, right: 20, top: 10, bottom: 30 },
    xAxis: {
      type: 'category' as const,
      data: stats.tension_distribution.map(t => `${t.tension}`),
      axisLabel: { color: '#94a3b8' },
    },
    yAxis: { type: 'value' as const, axisLabel: { color: '#64748b' }, splitLine: { lineStyle: { color: '#1e293b' } } },
    series: [{
      type: 'bar',
      data: stats.tension_distribution.map(t => t.count),
      itemStyle: {
        color: (p: { dataIndex: number }) => {
          const colors = ['#22d3ee', '#38bdf8', '#f59e0b', '#f97316', '#ef4444']
          return colors[p.dataIndex] || '#64748b'
        },
        borderRadius: [4, 4, 0, 0],
      },
      barWidth: 36,
    }],
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <h1 className="text-xl font-semibold">总览</h1>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={BookOpen} label="小说数量" value={stats.novels} color="bg-amber-500/15 text-amber-400" />
        <StatCard icon={Film} label="场景数量" value={stats.scenes} color="bg-blue-500/15 text-blue-400" />
        <StatCard icon={Users} label="人物数量" value={stats.characters} color="bg-violet-500/15 text-violet-400" />
        <StatCard icon={Tag} label="标签记录" value={stats.tag_records.toLocaleString()} color="bg-emerald-500/15 text-emerald-400" />
      </div>

      {stats.per_novel.length > 0 && (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
          <h2 className="text-sm font-medium text-slate-400 mb-3">各小说场景数</h2>
          <div className="space-y-2">
            {stats.per_novel.map(n => (
              <div key={n.material_id} className="flex items-center gap-3">
                <span className="text-sm flex-1 truncate">{n.name}</span>
                <div className="w-48 h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-amber-500/60 rounded-full"
                    style={{ width: `${Math.min(100, (n.scenes / Math.max(...stats.per_novel.map(x => x.scenes))) * 100)}%` }}
                  />
                </div>
                <span className="text-sm text-slate-400 w-16 text-right">{n.scenes}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
          <h2 className="text-sm font-medium text-slate-400 mb-3">场景类型分布</h2>
          <ReactECharts option={sceneTypeOption} style={{ height: 280 }} theme="dark" />
        </div>
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
          <h2 className="text-sm font-medium text-slate-400 mb-3">情绪分布 TOP 10</h2>
          <ReactECharts option={emotionOption} style={{ height: 280 }} theme="dark" />
        </div>
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-5">
          <h2 className="text-sm font-medium text-slate-400 mb-3">张力分布 (1-5)</h2>
          <ReactECharts option={tensionOption} style={{ height: 280 }} theme="dark" />
        </div>
      </div>
    </div>
  )
}
