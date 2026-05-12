import { create } from 'zustand'
import type { TaskStatus, TaskReport } from '@/types'
import { getTaskStatus, getTaskReport } from '@/services/taskApi'

const POLL_INTERVAL = 3000

interface TaskState {
  currentTaskId: string | null
  taskStatus: TaskStatus | null
  report: TaskReport | null
  isPolling: boolean
  /** 内部轮询定时器引用 */
  _pollTimer: ReturnType<typeof setInterval> | null

  // Actions
  setCurrentTaskId: (id: string | null) => void
  setTaskStatus: (status: TaskStatus | null) => void
  setReport: (report: TaskReport | null) => void
  startPolling: (taskId: string) => void
  stopPolling: () => void
  reset: () => void
}

export const useTaskStore = create<TaskState>((set, get) => ({
  currentTaskId: null,
  taskStatus: null,
  report: null,
  isPolling: false,
  _pollTimer: null,

  setCurrentTaskId: (id) => set({ currentTaskId: id }),

  setTaskStatus: (status) => set({ taskStatus: status }),

  setReport: (report) => set({ report }),

  startPolling: (taskId: string) => {
    // 如果已有轮询在进行，先清除
    const existing = get()._pollTimer
    if (existing) {
      clearInterval(existing)
    }

    set({ currentTaskId: taskId, isPolling: true })

    const poll = async () => {
      try {
        const status = await getTaskStatus(taskId)
        set({ taskStatus: status })

        // 当任务完成或失败时，停止轮询并拉取报告
        if (status.status === 'completed' || status.status === 'failed') {
          get().stopPolling()

          if (status.status === 'completed') {
            try {
              const report = await getTaskReport(taskId)
              set({ report })
            } catch {
              // 报告拉取失败不影响主流程
            }
          }
        }
      } catch {
        // 网络错误不中断轮询，继续尝试
      }
    }

    // 立即执行一次，然后每 3 秒轮询
    poll()
    const timer = setInterval(poll, POLL_INTERVAL)
    set({ _pollTimer: timer })
  },

  stopPolling: () => {
    const timer = get()._pollTimer
    if (timer) {
      clearInterval(timer)
    }
    set({ isPolling: false, _pollTimer: null })
  },

  reset: () => {
    const timer = get()._pollTimer
    if (timer) {
      clearInterval(timer)
    }
    set({
      currentTaskId: null,
      taskStatus: null,
      report: null,
      isPolling: false,
      _pollTimer: null,
    })
  },
}))
