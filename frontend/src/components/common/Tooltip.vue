<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'

const props = withDefaults(defineProps<{
  text: string
  position?: 'top' | 'bottom' | 'left' | 'right'
  delay?: number
}>(), {
  position: 'top',
  delay: 300,
})

const visible = ref(false)
const triggerRef = ref<HTMLElement>()
const tooltipStyle = ref<Record<string, string>>({})
let timer: ReturnType<typeof setTimeout> | null = null
let hideTimer: ReturnType<typeof setTimeout> | null = null

const arrowClass = computed(() => {
  switch (props.position) {
    case 'bottom': return 'border-t-0 border-b-foreground/90 -top-1.5 left-1/2 -translate-x-1/2'
    case 'left': return 'border-r-0 border-l-foreground/90 -right-1.5 top-1/2 -translate-y-1/2'
    case 'right': return 'border-l-0 border-r-foreground/90 -left-1.5 top-1/2 -translate-y-1/2'
    default: return 'border-b-0 border-t-foreground/90 -bottom-1.5 left-1/2 -translate-x-1/2'
  }
})

async function show() {
  if (hideTimer) { clearTimeout(hideTimer); hideTimer = null }
  if (timer) clearTimeout(timer)
  timer = setTimeout(async () => {
    visible.value = true
    await nextTick()
    updatePosition()
  }, props.delay)
}

function hide() {
  if (timer) { clearTimeout(timer); timer = null }
  hideTimer = setTimeout(() => {
    visible.value = false
  }, 100)
}

function updatePosition() {
  if (!triggerRef.value) return
  const rect = triggerRef.value.getBoundingClientRect()
  const style: Record<string, string> = {}

  switch (props.position) {
    case 'bottom':
      style.top = `${rect.bottom + 6}px`
      style.left = `${rect.left + rect.width / 2}px`
      style.transform = 'translateX(-50%)'
      break
    case 'left':
      style.top = `${rect.top + rect.height / 2}px`
      style.left = `${rect.left - 8}px`
      style.transform = 'translate(-100%, -50%)'
      break
    case 'right':
      style.top = `${rect.top + rect.height / 2}px`
      style.left = `${rect.right + 8}px`
      style.transform = 'translateY(-50%)'
      break
    default: // top
      style.top = `${rect.top - 6}px`
      style.left = `${rect.left + rect.width / 2}px`
      style.transform = 'translate(-50%, -100%)'
      break
  }

  tooltipStyle.value = style
}
</script>

<template>
  <span
    ref="triggerRef"
    class="inline-flex"
    @mouseenter="show"
    @mouseleave="hide"
    @focusin="show"
    @focusout="hide"
  >
    <slot />
  </span>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="visible"
        class="fixed z-[9999] px-2.5 py-1.5 text-xs font-medium text-surface rounded-md shadow-lg pointer-events-none max-w-[220px] text-center leading-relaxed"
        style="background-color: var(--color-foreground)"
        :style="tooltipStyle"
      >
        {{ text }}
      </div>
    </Transition>
  </Teleport>
</template>
