<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Upload } from '@lucide/vue'

const emit = defineEmits<{
  dropped: [file: File]
}>()

const active = ref(false)
let dragCounter = 0

function onDragEnter(e: DragEvent) {
  e.preventDefault()
  dragCounter++
  if (dragCounter === 1) active.value = true
}

function onDragOver(e: DragEvent) {
  e.preventDefault()
}

function onDragLeave(_e: DragEvent) {
  dragCounter--
  if (dragCounter <= 0) {
    dragCounter = 0
    active.value = false
  }
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  dragCounter = 0
  active.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) emit('dropped', file)
}

onMounted(() => {
  document.addEventListener('dragenter', onDragEnter)
  document.addEventListener('dragover', onDragOver)
  document.addEventListener('dragleave', onDragLeave)
  document.addEventListener('drop', onDrop)
})

onUnmounted(() => {
  document.removeEventListener('dragenter', onDragEnter)
  document.removeEventListener('dragover', onDragOver)
  document.removeEventListener('dragleave', onDragLeave)
  document.removeEventListener('drop', onDrop)
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="active"
      class="fixed inset-0 z-[100] flex items-center justify-center bg-primary/5 backdrop-blur-[2px]"
    >
      <div class="rounded-2xl border-2 border-dashed border-primary/50 bg-card/95 p-10 text-center shadow-2xl max-w-sm mx-4">
        <Upload class="w-12 h-12 text-primary mx-auto mb-4" />
        <p class="text-lg font-semibold text-foreground">Rilascia il file qui</p>
        <p class="text-sm text-foreground/50 mt-1">PDF, DOCX, TXT, MD</p>
      </div>
    </div>
  </Teleport>
</template>
