export interface Material {
  id: string
  type: string
  name: string
  author: string
  folder: string
  status: string
  added: string
  scene_count: number
  pipeline?: PipelineStatus
}

export interface PipelineStatus {
  mode?: string
  current_stage?: string
  stages_completed?: string[]
  chapters?: number
  scenes_processed?: string[]
  scenes_total_chapters?: number
  index_built?: boolean
  refined?: boolean
  stats_generated?: boolean
}

export interface MaterialDetail extends Material {
  material_id: string
  character_count?: number
  has_outline?: boolean
  has_worldbuilding?: boolean
  has_characters?: boolean
  has_tags?: boolean
  has_stats?: boolean
  has_scenes?: boolean
  formatted?: boolean
}

export interface DashboardStats {
  novels: number
  scenes: number
  characters: number
  tag_records: number
  per_novel: { material_id: string; name: string; scenes: number }[]
  top_scene_types: { value: string; count: number }[]
  top_emotions: { value: string; count: number }[]
  tension_distribution: { tension: number; count: number }[]
  top_techniques: { value: string; count: number }[]
}

export interface SceneItem {
  scene_id: string
  material_id?: string
  novel?: string
  chapter: string
  title: string
  summary: string
  tension: number
  pacing?: string
  pov?: string
  power_dynamic?: string
  moral_spectrum?: string
  plot_stage?: string
  scale?: string
  characters?: string[]
  tags?: Record<string, string[]>
  matched?: string[]
  score?: number
}

export interface ScenesResponse {
  total: number
  page: number
  limit: number
  scenes: SceneItem[]
}

export interface SceneSearchResponse {
  query: Record<string, string>
  total: number
  results: SceneItem[]
  relaxed: boolean
}

export interface CharacterItem {
  name: string
  novel: string
  material_id: string
  role: string
  archetype: string
  moral_spectrum: string
  arc_summary: string
  narrative_function: string
  psychology?: Record<string, string>
  appearance_count: number
}

export interface CharacterSearchResponse {
  total: number
  results: CharacterItem[]
}

export interface TextSearchResponse {
  query: string
  total: number
  results: SceneItem[]
}

export interface TagDimension {
  description: string
  values: string[]
}

export type TagDictionary = Record<string, TagDimension>

export type TagUsage = Record<string, { value: string; count: number }[]>

export interface PipelineStatusResponse {
  stages_completed: string[]
  running: boolean
  current_stage: string | null
  last_error: string | null
  updated_at: string | null
}
