import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload as UploadIcon, FileText, Loader2, CheckCircle2, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/api/client'

type Status = 'idle' | 'uploading' | 'success' | 'error'

export default function Upload() {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [author, setAuthor] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [result, setResult] = useState<{ material_id: string; name: string } | null>(null)
  const [error, setError] = useState('')
  const [dragOver, setDragOver] = useState(false)

  const handleFile = (f: File) => {
    setFile(f)
    if (!name) setName(f.name.replace(/\.[^.]+$/, ''))
    setStatus('idle')
    setError('')
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  const handleUpload = async () => {
    if (!file) return
    setStatus('uploading')
    setError('')
    try {
      const res = await api.uploadNovel(file, name || undefined, author || undefined)
      setResult(res)
      setStatus('success')
    } catch (e) {
      setError(e instanceof Error ? e.message : '上传失败')
      setStatus('error')
    }
  }

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <h1 className="text-lg font-semibold">上传小说</h1>

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={cn(
          'border-2 border-dashed rounded-xl p-12 flex flex-col items-center gap-3 cursor-pointer transition-colors',
          dragOver ? 'border-amber-500 bg-amber-500/5' : 'border-slate-800 hover:border-slate-600',
        )}
      >
        <UploadIcon className="w-10 h-10 text-slate-600" />
        {file ? (
          <div className="flex items-center gap-2 text-sm">
            <FileText className="w-4 h-4 text-amber-400" />
            <span className="text-slate-300">{file.name}</span>
            <span className="text-slate-600">({(file.size / 1024 / 1024).toFixed(1)} MB)</span>
          </div>
        ) : (
          <>
            <p className="text-sm text-slate-400">拖拽文件到此处，或点击选择</p>
            <p className="text-xs text-slate-600">支持 .txt .md .epub</p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept=".txt,.md,.epub"
          className="hidden"
          onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
        />
      </div>

      {/* Metadata */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-xs text-slate-500 block mb-1">书名</label>
          <input value={name} onChange={e => setName(e.target.value)} placeholder="自动从文件名获取"
            className="w-full text-sm bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 focus:outline-none focus:border-amber-500/50" />
        </div>
        <div>
          <label className="text-xs text-slate-500 block mb-1">作者</label>
          <input value={author} onChange={e => setAuthor(e.target.value)} placeholder="可选"
            className="w-full text-sm bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 focus:outline-none focus:border-amber-500/50" />
        </div>
      </div>

      {/* Upload button */}
      <button
        onClick={handleUpload}
        disabled={!file || status === 'uploading'}
        className={cn(
          'w-full py-3 rounded-lg text-sm font-medium flex items-center justify-center gap-2 transition-colors',
          file && status !== 'uploading'
            ? 'bg-amber-500 text-slate-950 hover:bg-amber-400'
            : 'bg-slate-800 text-slate-500 cursor-not-allowed',
        )}
      >
        {status === 'uploading' ? (
          <><Loader2 className="w-4 h-4 animate-spin" /> 上传中...</>
        ) : (
          <><UploadIcon className="w-4 h-4" /> 上传</>
        )}
      </button>

      {/* Result */}
      {status === 'success' && result && (
        <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-4 space-y-3 animate-fade-in">
          <div className="flex items-center gap-2 text-emerald-400">
            <CheckCircle2 className="w-5 h-5" />
            <span className="text-sm font-medium">上传成功</span>
          </div>
          <p className="text-sm text-slate-300">
            素材 ID: <code className="text-amber-400">{result.material_id}</code>
          </p>
          <div className="flex gap-2">
            <button onClick={() => navigate(`/materials/${result.material_id}`)}
              className="text-sm px-4 py-1.5 rounded-lg bg-amber-500 text-slate-950 hover:bg-amber-400 transition-colors">
              查看素材
            </button>
            <button onClick={() => { setFile(null); setName(''); setAuthor(''); setResult(null); setStatus('idle') }}
              className="text-sm px-4 py-1.5 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors">
              继续上传
            </button>
          </div>
        </div>
      )}

      {status === 'error' && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/20 p-4 flex items-center gap-2 animate-fade-in">
          <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
          <p className="text-sm text-red-300">{error}</p>
        </div>
      )}
    </div>
  )
}
