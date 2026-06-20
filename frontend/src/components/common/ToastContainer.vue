<script setup lang="ts">
import { CheckCircle, XCircle, Info, AlertTriangle, X } from '@lucide/vue'
import { useToast } from '@/composables/useToast'

const { toasts, dismiss } = useToast()

const iconMap = {
  success: CheckCircle,
  error: XCircle,
  info: Info,
  warning: AlertTriangle,
}

const colorMap = {
  success: 'border-cta/30 bg-cta/10 text-cta',
  error: 'border-danger/30 bg-danger/10 text-danger',
  info: 'border-primary/30 bg-primary/10 text-primary',
  warning: 'border-warning/30 bg-warning/10 text-warning',
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="toasts.length"
      class="fixed bottom-4 right-4 z-[10000] flex flex-col-reverse gap-2 max-w-sm"
      aria-live="polite"
      aria-label="Notifiche"
    >
      <TransitionGroup
        enter-active-class="transition duration-300 ease-out"
        enter-from-class="opacity-0 translate-y-4 scale-95"
        enter-to-class="opacity-100 translate-y-0 scale-100"
        leave-active-class="transition duration-200 ease-in"
        leave-from-class="opacity-100 translate-y-0 scale-100"
        leave-to-class="opacity-0 translate-y-2 scale-95"
      >
        <div
          v-for="toast in toasts"
          :key="toast.id"
          :class="colorMap[toast.type]"
          class="flex items-start gap-2.5 px-4 py-3 rounded-lg border shadow-lg bg-card/95 backdrop-blur-sm"
          role="alert"
        >
          <component :is="iconMap[toast.type]" class="w-4 h-4 flex-shrink-0 mt-0.5" />
          <p class="text-sm flex-1">{{ toast.message }}</p>
          <button
            class="flex-shrink-0 p-0.5 rounded hover:bg-foreground/5 transition-colors cursor-pointer opacity-50 hover:opacity-100"
            @click="dismiss(toast.id)"
            aria-label="Chiudi notifica"
          >
            <X class="w-3.5 h-3.5" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>
