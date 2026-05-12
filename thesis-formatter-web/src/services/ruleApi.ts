import api from '@/services/api'
import type { Rule, Template } from '@/types'

/**
 * 解析规范文件
 */
export async function parseSpecFile(
  file: File,
  modelId?: string,
): Promise<Rule[]> {
  const formData = new FormData()
  formData.append('spec_file', file)
  if (modelId) {
    formData.append('model_id', modelId)
  }

  const { data } = await api.post<Rule[]>('/api/v1/rules/parse', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/**
 * 获取规则列表
 */
export async function listRules(schoolName?: string): Promise<Rule[]> {
  const params: Record<string, string> = {}
  if (schoolName) {
    params.school_name = schoolName
  }

  const { data } = await api.get<Rule[]>('/api/v1/rules', { params })
  return data
}

/**
 * 获取模板列表
 */
export async function listTemplates(
  schoolName?: string,
  thesisType?: string,
): Promise<Template[]> {
  const params: Record<string, string> = {}
  if (schoolName) {
    params.school_name = schoolName
  }
  if (thesisType) {
    params.thesis_type = thesisType
  }

  const { data } = await api.get<Template[]>('/api/v1/templates', { params })
  return data
}
