<script setup lang="ts">
import { watch, nextTick, ref } from 'vue'
import { AlertTriangle } from '@lucide/vue'
import { useConfirm } from '@/composables/useConfirm'

const { state, respond } = useConfirm()
const confirmBtn = ref<HTMLButtonElement | null>(null)

// Move focus to the confirm button when the dialog opens (keyboard + a11y).
watch(
  () => state.value.open,
  async (open) => {
    if (open) {
      await nextTick()
      confirmBtn.value?.focus()
    }
  },
)

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') respond(false)
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="state.open"
      class="fixed inset-0 z-[60] flex items-center justify-center bg-black/30 p-4"
      role="dialog"
      aria-modal="true"
      @click.self="respond(false)"
      @keydown="onKeydown"
    >
      <div class="w-full max-w-sm rounded-xl bg-surface p-5 md:p-6 shadow-xl border border-primary/10">
        <div class="flex items-start gap-3">
          <div
            v-if="state.danger"
            class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-danger/10 text-danger"
          >
            <AlertTriangle class="h-5 w-5" />
          </div>
          <div class="min-w-0">
            <h2 v-if="state.title" class="text-base font-semibold text-foreground">
              {{ state.title }}
            </h2>
            <p class="text-sm text-foreground/70" :class="{ 'mt-1': state.title }">
              {{ state.message }}
            </p>
          </div>
        </div>

        <div class="mt-6 flex justify-end gap-2">
          <button
            type="button"
            class="rounded-lg px-4 py-2 text-sm font-medium text-foreground/70 hover:bg-primary/8 transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
            @click="respond(false)"
          >
            {{ state.cancelLabel || 'Annulla' }}
          </button>
          <button
            ref="confirmBtn"
            type="button"
            class="rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors cursor-pointer focus-visible:ring-2 focus-visible:outline-none"
            :class="state.danger
              ? 'bg-danger hover:bg-danger/90 focus-visible:ring-danger'
              : 'bg-primary hover:bg-primary-light focus-visible:ring-primary'"
            @click="respond(true)"
          >
            {{ state.confirmLabel || 'Conferma' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
