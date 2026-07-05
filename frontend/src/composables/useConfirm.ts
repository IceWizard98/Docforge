import { ref } from 'vue'

export interface ConfirmOptions {
  title?: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  /** destructive actions get a danger-styled confirm button */
  danger?: boolean
}

interface ConfirmState extends ConfirmOptions {
  open: boolean
}

const state = ref<ConfirmState>({ open: false, message: '' })
let resolver: ((ok: boolean) => void) | null = null

/**
 * Promise-based confirmation backed by a Vue dialog (ConfirmDialog.vue mounted
 * once at the app root) — replaces native window.confirm, which blocks the event
 * loop and can't be themed. Usage: `if (!(await confirm({ message: '…' }))) return`.
 */
export function useConfirm() {
  function confirm(opts: ConfirmOptions): Promise<boolean> {
    // Resolve any dialog still pending (defensive) before opening a new one.
    if (resolver) resolver(false)
    state.value = { ...opts, open: true }
    return new Promise<boolean>((resolve) => {
      resolver = resolve
    })
  }

  function respond(ok: boolean) {
    state.value = { ...state.value, open: false }
    if (resolver) {
      resolver(ok)
      resolver = null
    }
  }

  return { state, confirm, respond }
}
