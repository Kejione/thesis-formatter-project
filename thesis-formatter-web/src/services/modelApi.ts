import api from '@/services/api'
import type { ModelConfig, ModelConfigCreate } from '@/types'

/**
 * 获取已配置的模型列表
 */
export async function listModels(): Promise<ModelConfig[]> {
  const { data } = await api.get<ModelConfig[]>('/api/v1/models')
  return data
}

/**
 * 配置新模型
 */
export async function configureModel(
  data: ModelConfigCreate,
): Promise<ModelConfig> {
  const { data: result } = await api.post<ModelConfig>(
    '/api/v1/models/config',
    data,
  )
  return result
}

/**
 * 更新已有模型配置
 */
export async function updateModel(
  modelId: string,
  data: ModelConfigCreate,
): Promise<ModelConfig> {
  const { data: result } = await api.put<ModelConfig>(
    `/api/v1/models/${modelId}`,
    data,
  )
  return result
}

/**
 * 删除模型配置
 */
export async function deleteModel(modelId: string): Promise<void> {
  await api.delete(`/api/v1/models/${modelId}`)
}

/**
 * 测试模型连通性
 */
export async function testModel(modelId: string): Promise<{ success: boolean; message: string }> {
  const { data } = await api.post<{ success: boolean; message: string }>(
    `/api/v1/models/${modelId}/test`,
  )
  return data
}
