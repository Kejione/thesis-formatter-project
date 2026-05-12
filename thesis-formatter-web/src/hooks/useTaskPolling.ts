import { useEffect, useState } from 'react'
import { useTaskStore } from '@/store/taskStore'
import type { TaskStatus, TaskReport } from '@/types'

interface UseTaskPollingResult {
  taskStatus: TaskStatus | null
  report: TaskReport | null
  isPolling: boolean
  error: string | null
}

/**
 * 自定义 Hook：封装任务轮询逻辑
 *
 * 在组件挂载时自动开始轮询，卸载时自动停止。
 *
 * @param taskId - 要轮询的任务 ID，为空时不会启动轮询
 */
export function useTaskPolling(taskId: string | null): UseTaskPollingResult {
  const { taskStatus, report, isPolling, startPolling, stopPolling } =
    useTaskStore()

  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!taskId) {
      stopPolling()
      return
    }

    setError(null)
    startPolling(taskId)

    return () => {
      stopPolling()
    }
  }, [taskId, startPolling, stopPolling])

  // 监听 taskStatus 变化，检测失败状态以设置 error
  useEffect(() => {
    if (taskStatus?.status === 'failed') {
      setError(
        taskStatus.error_message ?? '任务执行失败，请查看详情或重试。',
      )
    }
  }, [taskStatus])

  return { taskStatus, report, isPolling, error }
}
