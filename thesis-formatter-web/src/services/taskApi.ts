import api from '@/services/api'
import type { TaskStatus, TaskReport, ChangeLog } from '@/types'

/**
 * 创建格式化任务
 */
export async function createTask(
  thesisFile: File,
  specFile?: File,
  templateId?: string,
  modelId?: string,
): Promise<TaskStatus> {
  const formData = new FormData()
  formData.append('thesis_file', thesisFile)
  if (specFile) {
    formData.append('spec_file', specFile)
  }
  if (templateId) {
    formData.append('template_id', templateId)
  }
  if (modelId) {
    formData.append('model_id', modelId)
  }

  const { data } = await api.post<TaskStatus>('/api/v1/tasks', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/**
 * 查询任务状态
 */
export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  const { data } = await api.get<TaskStatus>(`/api/v1/tasks/${taskId}`)
  return data
}

/**
 * 获取任务报告
 */
export async function getTaskReport(taskId: string): Promise<TaskReport> {
  const { data } = await api.get<TaskReport>(`/api/v1/tasks/${taskId}/report`)
  return data
}

/**
 * 修复任务中的问题
 */
export async function fixTask(
  taskId: string,
  issueIds?: string[],
): Promise<TaskStatus> {
  const { data } = await api.post<TaskStatus>(
    `/api/v1/tasks/${taskId}/fix`,
    issueIds ? { issue_ids: issueIds } : undefined,
  )
  return data
}

/**
 * 获取修复后文档的下载链接
 */
export async function downloadFixedDoc(taskId: string): Promise<string> {
  const { data } = await api.get<{ download_url: string }>(
    `/api/v1/tasks/${taskId}/download`,
  )
  return data.download_url
}

/**
 * 获取任务变更日志
 */
export async function getChangelog(taskId: string): Promise<ChangeLog> {
  const { data } = await api.get<ChangeLog>(
    `/api/v1/tasks/${taskId}/changelog`,
  )
  return data
}
