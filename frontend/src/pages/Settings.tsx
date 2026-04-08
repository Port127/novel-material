import { useState, useEffect } from 'react'
import { Settings as SettingsIcon, Eye, EyeOff, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/api/client'

interface LlmConfig {
  apiUrl: string
  apiKey: string
  model: string
}

const STORAGE_KEY = 'novel-material-llm-config'

function loadConfig(): LlmConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : { apiUrl: '', apiKey: '', model: '' }
  } catch {
    return { apiUrl: '', apiKey: '', model: '' }
  }
}

export default function Settings() {
  const [config, setConfig] = useState<LlmConfig>(loadConfig)
  const [showKey, setShowKey] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testStatus, setTestStatus] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle')

  useEffect(() => { setSaved(false) }, [config])

  const handleSave = async () => {
    setSaving(true)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
    try {
      await api.saveLlmSettings({
        base_url: config.apiUrl,
        api_key: config.apiKey,
        model: config.model,
      })
    } catch { /* backend save is best-effort */ }
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleTest = async () => {
    if (!config.apiUrl || !config.apiKey) return
    setTestStatus('loading')
    try {
      const BASE = import.meta.env.DEV ? 'http://127.0.0.1:8000/api' : '/api'
      const res = await fetch(`${BASE}/llm/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ base_url: config.apiUrl, api_key: config.apiKey, model: config.model }),
      })
      const data = await res.json()
      setTestStatus(data.ok ? 'ok' : 'error')
    } catch {
      setTestStatus('error')
    }
    setTimeout(() => setTestStatus('idle'), 3000)
  }

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-2">
        <SettingsIcon className="w-5 h-5 text-slate-400" />
        <h1 className="text-xl font-semibold">设置</h1>
      </div>

      <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-6 space-y-5">
        <h2 className="text-sm font-medium text-slate-300">LLM API 配置</h2>
        <p className="text-xs text-slate-500">
          配置第三方大模型 API 接入，用于 Pipeline 中的场景分析、标签生成等任务。保存后同步到后端。
        </p>

        <div>
          <label className="text-xs text-slate-500 block mb-1.5">API Base URL</label>
          <input value={config.apiUrl}
            onChange={e => setConfig(c => ({ ...c, apiUrl: e.target.value }))}
            placeholder="https://api.openai.com/v1"
            className="w-full text-sm bg-slate-950 border border-slate-800 rounded-lg px-3 py-2.5 focus:outline-none focus:border-amber-500/50 placeholder:text-slate-700" />
        </div>

        <div>
          <label className="text-xs text-slate-500 block mb-1.5">API Key</label>
          <div className="relative">
            <input type={showKey ? 'text' : 'password'} value={config.apiKey}
              onChange={e => setConfig(c => ({ ...c, apiKey: e.target.value }))}
              placeholder="sk-..."
              className="w-full text-sm bg-slate-950 border border-slate-800 rounded-lg px-3 py-2.5 pr-10 focus:outline-none focus:border-amber-500/50 placeholder:text-slate-700" />
            <button onClick={() => setShowKey(!showKey)}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-600 hover:text-slate-400">
              {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <div>
          <label className="text-xs text-slate-500 block mb-1.5">模型名称</label>
          <input value={config.model}
            onChange={e => setConfig(c => ({ ...c, model: e.target.value }))}
            placeholder="gpt-4o / claude-3-opus / ..."
            className="w-full text-sm bg-slate-950 border border-slate-800 rounded-lg px-3 py-2.5 focus:outline-none focus:border-amber-500/50 placeholder:text-slate-700" />
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button onClick={handleSave} disabled={saving}
            className={cn(
              'px-5 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5',
              saved ? 'bg-emerald-500/20 text-emerald-400'
                : 'bg-amber-500 text-slate-950 hover:bg-amber-400',
            )}>
            {saving ? <><Loader2 className="w-4 h-4 animate-spin" /> 保存中</>
              : saved ? <><CheckCircle className="w-4 h-4" /> 已保存</>
              : '保存配置'}
          </button>

          <button onClick={handleTest}
            disabled={!config.apiUrl || !config.apiKey || testStatus === 'loading'}
            className="px-4 py-2 rounded-lg text-sm border border-slate-700 text-slate-400 hover:text-slate-200 hover:border-slate-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
            {testStatus === 'loading' ? '测试中...' : '测试连接'}
          </button>

          {testStatus === 'ok' && (
            <span className="text-xs text-emerald-400 flex items-center gap-1">
              <CheckCircle className="w-3.5 h-3.5" /> 连接成功
            </span>
          )}
          {testStatus === 'error' && (
            <span className="text-xs text-red-400 flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5" /> 连接失败
            </span>
          )}
        </div>
      </div>

      <div className="rounded-xl bg-slate-900/80 border border-slate-800/60 p-6 space-y-3">
        <h2 className="text-sm font-medium text-slate-300">后端服务</h2>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          API 服务: http://localhost:8000
        </div>
        <p className="text-xs text-slate-600">
          启动后端: <code className="bg-slate-800 px-1.5 py-0.5 rounded text-slate-400">cd backend && python main.py</code>
        </p>
      </div>
    </div>
  )
}
