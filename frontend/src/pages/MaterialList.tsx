import { useQuery } from '@tanstack/react-query'
import { useNavigate, Link } from 'react-router-dom'
import { api } from '@/api/client'
import { BookOpen, Film, Calendar, Upload } from 'lucide-react'
import { cn, STATUS_MAP } from '@/lib/utils'

export default function MaterialList() {
  const navigate = useNavigate()
  const { data: materials, isLoading, isError } = useQuery({
    queryKey: ['materials'],
    queryFn: api.listMaterials,
  })

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">素材库</h1>
        <span className="text-sm text-slate-500">{materials?.length ?? 0} 部小说</span>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-44 rounded-xl bg-slate-900/50 animate-pulse" />
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-8 text-center">
          <p className="text-sm text-slate-500">加载失败，请检查后端服务是否运行。</p>
        </div>
      ) : !materials || materials.length === 0 ? (
        <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-12 text-center space-y-3">
          <BookOpen className="w-10 h-10 mx-auto text-slate-700" />
          <p className="text-sm text-slate-500">暂无素材</p>
          <Link to="/upload" className="inline-flex items-center gap-1.5 text-sm text-amber-400 hover:text-amber-300 transition-colors">
            <Upload className="w-3.5 h-3.5" /> 上传第一部小说
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {materials.map(m => {
            const status = STATUS_MAP[m.status] ?? STATUS_MAP.raw
            return (
              <button
                key={m.id}
                onClick={() => navigate(`/materials/${m.id}`)}
                className={cn(
                  'text-left rounded-xl bg-slate-900/80 border border-slate-800/60 p-5',
                  'hover:border-amber-500/30 hover:bg-slate-900 transition-all',
                  'animate-fade-in group',
                )}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <BookOpen className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                    <h3 className="font-medium text-sm leading-tight group-hover:text-amber-400 transition-colors">
                      {m.name}
                    </h3>
                  </div>
                  <span className={cn('text-xs px-2 py-0.5 rounded-full shrink-0 ml-2', status.color)}>
                    {status.label}
                  </span>
                </div>

                <p className="text-xs text-slate-500 mb-4">{m.author}</p>

                <div className="flex items-center gap-4 text-xs text-slate-500">
                  <span className="flex items-center gap-1">
                    <Film className="w-3 h-3" />
                    {m.event_count} 事件
                  </span>
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3 h-3" />
                    {m.added}
                  </span>
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
