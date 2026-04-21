import { clsx } from 'clsx'
import type { ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const TAG_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  event_type:      { bg: 'bg-rose-500/15', text: 'text-rose-400', label: '事件类型' },
  conflict:        { bg: 'bg-rose-500/15', text: 'text-rose-400', label: '冲突类型' },
  stakes:          { bg: 'bg-rose-500/15', text: 'text-rose-400', label: '赌注' },
  relationship:    { bg: 'bg-violet-500/15', text: 'text-violet-400', label: '人物关系' },
  interaction:     { bg: 'bg-violet-500/15', text: 'text-violet-400', label: '互动方式' },
  power_dynamic:   { bg: 'bg-violet-500/15', text: 'text-violet-400', label: '权力位差' },
  character_moment: { bg: 'bg-violet-500/15', text: 'text-violet-400', label: '弧光时刻' },
  moral_spectrum:  { bg: 'bg-violet-500/15', text: 'text-violet-400', label: '道德光谱' },
  emotion:         { bg: 'bg-amber-500/15', text: 'text-amber-400', label: '情绪基调' },
  reader_effect:   { bg: 'bg-amber-500/15', text: 'text-amber-400', label: '读者感受' },
  plot_stage:      { bg: 'bg-blue-500/15', text: 'text-blue-400', label: '剧情阶段' },
  plot_function:   { bg: 'bg-blue-500/15', text: 'text-blue-400', label: '情节功能' },
  pacing:          { bg: 'bg-blue-500/15', text: 'text-blue-400', label: '节奏型' },
  technique:       { bg: 'bg-emerald-500/15', text: 'text-emerald-400', label: '叙事技法' },
  dialogue_type:   { bg: 'bg-emerald-500/15', text: 'text-emerald-400', label: '对话类型' },
  pov:             { bg: 'bg-emerald-500/15', text: 'text-emerald-400', label: '视角' },
  info_delivery:   { bg: 'bg-emerald-500/15', text: 'text-emerald-400', label: '信息投放' },
  setting:         { bg: 'bg-cyan-500/15', text: 'text-cyan-400', label: '空间类型' },
  scale:           { bg: 'bg-cyan-500/15', text: 'text-cyan-400', label: '人数规模' },
  time_weather:    { bg: 'bg-cyan-500/15', text: 'text-cyan-400', label: '时间天气' },
}

export const STATUS_MAP: Record<string, { label: string; color: string }> = {
  raw:      { label: '未处理', color: 'bg-slate-500/20 text-slate-400' },
  outlined: { label: '已分析', color: 'bg-blue-500/20 text-blue-400' },
  tagged:   { label: '已标签', color: 'bg-violet-500/20 text-violet-400' },
  complete: { label: '已完成', color: 'bg-emerald-500/20 text-emerald-400' },
  refined:  { label: '已精调', color: 'bg-amber-500/20 text-amber-400' },
}

export const TAG_LAYERS = [
  { id: 'content', label: 'A. 内容层', dims: ['event_type', 'conflict', 'stakes'] },
  { id: 'people', label: 'B. 人物层', dims: ['relationship', 'interaction', 'power_dynamic', 'character_moment', 'moral_spectrum'] },
  { id: 'emotion', label: 'C. 情感层', dims: ['emotion', 'reader_effect'] },
  { id: 'structure', label: 'D. 结构层', dims: ['plot_stage', 'plot_function', 'pacing'] },
  { id: 'technique', label: 'E. 技法层', dims: ['technique', 'dialogue_type', 'pov', 'info_delivery'] },
  { id: 'setting', label: 'F. 物理层', dims: ['setting', 'scale', 'time_weather'] },
]