import { ref } from 'vue'

export interface Toast {
  id: string
  type: 'success' | 'error' | 'info' | 'warning'
  message: string
  duration: number
}

const toasts = ref<Toast[]>([])
let counter = 0

function add(toast: Omit<Toast, 'id'>) {
  const id = `toast_${++counter}_${Date.now()}`
  const entry = { ...toast, id }
  toasts.value.push(entry)
  if (entry.duration > 0) {
    setTimeout(() => dismiss(id), entry.duration)
  }
  return id
}

function dismiss(id: string) {
  const idx = toasts.value.findIndex(t => t.id === id)
  if (idx !== -1) {
    toasts.value.splice(idx, 1)
  }
}

export function useToast() {
  return {
    toasts,
    toast(opts: { type?: Toast['type']; message: string; duration?: number }) {
      return add({
        type: opts.type || 'info',
        message: opts.message,
        duration: opts.duration ?? 3000,
      })
    },
    success(message: string, duration?: number) {
      return add({ type: 'success', message, duration: duration ?? 3000 })
    },
    error(message: string, duration?: number) {
      return add({ type: 'error', message, duration: duration ?? 5000 })
    },
    info(message: string, duration?: number) {
      return add({ type: 'info', message, duration: duration ?? 3000 })
    },
    warning(message: string, duration?: number) {
      return add({ type: 'warning', message, duration: duration ?? 4000 })
    },
    dismiss,
  }
}
