<script setup lang="ts">
import { computed } from 'vue'
import { Bot, User, Check, X, ExternalLink } from '@lucide/vue'
import type { ChatMessageResponse, ChatActionPayload, PatchPayload, SourceRef } from '@/types/document'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps<{
  message: ChatMessageResponse
}>()

const emit = defineEmits<{
  action: [action: ChatActionPayload]
}>()

const isUser = computed(() => props.message.role === 'user')
const hasActions = computed(() => (props.message.actions?.length || 0) > 0)
const hasPatches = computed(() => (props.message.patches?.length || 0) > 0)
const hasSources = computed(() => (props.message.sources?.length || 0) > 0)

const renderedContent = computed(() => {
  const text = props.message.content || ''
  if (!text) return ''
  const raw = marked.parse(text, { async: false }) as string
  return DOMPurify.sanitize(raw)
})

function handleAction(action: ChatActionPayload) {
  emit('action', action)
}
</script>

<template>
  <div
    class="flex gap-3"
    :class="isUser ? 'flex-row-reverse' : 'flex-row'"
  >
    <!-- Avatar -->
    <div
      class="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center"
      :class="isUser ? 'bg-primary/15' : 'bg-secondary/15'"
    >
      <User v-if="isUser" class="w-3.5 h-3.5 text-primary" />
      <Bot v-else class="w-3.5 h-3.5 text-secondary" />
    </div>

    <!-- Content -->
    <div class="flex flex-col max-w-[80%]" :class="isUser ? 'items-end' : 'items-start'">
      <div
        class="px-3 py-2 rounded-lg text-sm leading-relaxed"
        :class="isUser ? 'bg-primary text-white rounded-tr-sm' : 'bg-surface border border-primary/10 rounded-tl-sm'"
      >
        <div
          v-if="isUser"
          class="whitespace-pre-wrap text-white"
        >
          {{ message.content }}
        </div>
        <div
          v-else
          class="prose prose-sm max-w-none text-foreground prose-headings:text-foreground prose-a:text-primary prose-code:bg-primary/10 prose-code:text-primary prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-surface prose-pre:border prose-pre:border-primary/10 prose-li:text-foreground prose-strong:text-foreground"
          v-html="renderedContent"
        />
      </div>

      <!-- Action buttons -->
      <div v-if="hasActions" class="flex flex-wrap gap-2 mt-2">
        <button
          v-for="(act, idx) in message.actions"
          :key="'action_' + idx"
          class="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md bg-primary/10 text-primary hover:bg-primary/15 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          @click="handleAction(act)"
        >
          <Check class="w-3 h-3" />
          {{ act.label }}
        </button>
      </div>

      <!-- Patch preview -->
      <div v-if="hasPatches" class="mt-2 w-full">
        <div
          v-for="patch in message.patches"
          :key="patch.sectionId"
          class="px-2.5 py-1.5 rounded-md bg-cta/10 border border-cta/20 text-xs text-foreground/70"
        >
          <span class="text-cta font-medium">Patch:</span>
          Section {{ patch.sectionId }} — {{ patch.operations.length }} operations
        </div>
      </div>

      <!-- Source citations -->
      <div v-if="hasSources" class="flex flex-wrap gap-1.5 mt-2">
        <span
          v-for="src in message.sources"
          :key="src.sourceDocId"
          class="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium rounded-full bg-primary/5 text-primary/60 border border-primary/10"
        >
          <ExternalLink class="w-2.5 h-2.5" />
          {{ src.title }}
        </span>
      </div>
    </div>
  </div>
</template>
