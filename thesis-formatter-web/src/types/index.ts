// Task types
export interface TaskStatus {
  id: string
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'fixing' | 'fixed'
  created_at: string
  updated_at?: string
  issue_count?: number
  fix_available?: boolean
  error_message?: string
}

export interface IssueLocation {
  page?: number
  paragraph?: number
  section?: number
}

export interface Issue {
  id: string
  severity: 'error' | 'warning' | 'info'
  category: string
  location: IssueLocation
  rule_id?: string
  current_value: string
  expected_value: string
  suggestion?: string
  is_fixed: boolean
}

export interface ReportSummary {
  total_issues: number
  error_count: number
  warning_count: number
  info_count: number
  categories: Record<string, number>
  score?: number
}

export interface TaskReport {
  task_id: string
  summary: ReportSummary
  issues: Issue[]
  rules_applied: Record<string, unknown>[]
  metadata: Record<string, unknown>
}

// Rule types
export interface RuleData {
  school_name?: string
  thesis_type?: 'bachelor' | 'master' | 'doctor'
  page_margin?: Record<string, string>
  font?: Record<string, string>
  font_size?: Record<string, string>
  line_spacing?: Record<string, string>
  paragraph_spacing?: Record<string, Record<string, string>>
  heading_style?: Record<string, Record<string, unknown>>
  page_number?: Record<string, unknown>
  references?: Record<string, unknown>
}

export interface Rule {
  id: string
  name: string
  source: 'ai_parsed' | 'manual' | 'template'
  rule_data: RuleData
  school_name?: string
  is_active: boolean
  created_at: string
}

// Template types
export interface Template {
  id: string
  school_name: string
  thesis_type: 'bachelor' | 'master' | 'doctor'
  description?: string
  usage_count: number
  created_at: string
}

// Model config types
export interface ModelConfig {
  id: string
  name: string
  provider: string
  base_url: string
  model_name: string
  is_default: boolean
  priority: number
  created_at: string
}

export interface ModelConfigCreate {
  name: string
  api_key: string
  base_url: string
  model_name: string
  is_default?: boolean
}

// Change types
export interface ChangeRecord {
  id: string
  category: string
  location: IssueLocation
  before_value: string
  after_value: string
  risk_level: 'low' | 'medium' | 'high'
  created_at: string
}

export interface ChangeLog {
  task_id: string
  total_changes: number
  changes: ChangeRecord[]
}
