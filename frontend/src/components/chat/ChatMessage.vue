<script setup lang="ts">
import { computed } from 'vue'
import { Bot, User, Check, ExternalLink, Info, AlertTriangle } from '@lucide/vue'
import type { ChatMessageResponse, ChatActionPayload, SourceRef } from '@/types/document'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import PatchReviewCard from './PatchReviewCard.vue'

const props = defineProps<{
  message: ChatMessageResponse
}>()

const emit = defineEmits<{
  action: [action: ChatActionPayload]
  patchApplied: []
}>()

const isUser = computed(() => props.message.role === 'user')
// Result actions already applied automatically by ChatDock.handleAssistantResponse —
// must NOT also be rendered as clickable buttons (would double-apply).
const AUTO_APPLIED = ['draft_ready', 'section_created', 'clause_inserted', 'section_rewritten']
// Surgical patch proposals get a granular review card; everything else is a button.
const patchActions = computed(
  () => (props.message.actions || []).filter((a) => a.action === 'patches_proposed'),
)
const buttonActions = computed(
  () => (props.message.actions || []).filter(
    (a) => a.action !== 'patches_proposed' && !AUTO_APPLIED.includes(a.action),
  ),
)
const hasSources = computed(() => (props.message.sources?.length || 0) > 0)
const intentSummary = computed(() => (isUser.value ? '' : props.message.intentSummary || ''))
// Only missing/ambiguous slots are surfaced — the things the user still needs to
// provide so the AI doesn't invent them.
const missingSlots = computed(() =>
  (props.message.slotStatus || []).filter((s) => s.status === 'missing' || s.status === 'ambiguous'),
)

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
      <div v-if="buttonActions.length" class="flex flex-wrap gap-2 mt-2">
        <button
          v-for="(act, idx) in buttonActions"
          :key="'action_' + idx"
          class="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md bg-primary/10 text-primary hover:bg-primary/15 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          @click="handleAction(act)"
        >
          <Check class="w-3 h-3" />
          {{ act.label }}
        </button>
      </div>

      <!-- Granular patch review -->
      <PatchReviewCard
        v-for="(act, idx) in patchActions"
        :key="'patch_' + idx"
        :patch-set-id="(act.payload?.patch_set_id as string)"
        :summary="(act.payload?.summary as string)"
        :operations="(act.payload?.operations as any[]) || []"
        @applied="emit('patchApplied')"
      />

      <!-- Transparency: what the AI understood + sources used -->
      <div
        v-if="intentSummary"
        class="flex items-start gap-1.5 mt-2 text-[11px] text-foreground/60"
      >
        <Info class="w-3 h-3 mt-0.5 shrink-0 text-secondary" />
        <span>{{ intentSummary }}</span>
      </div>

      <!-- Missing / ambiguous slots: what the user still needs to provide -->
      <div v-if="missingSlots.length" class="mt-2 w-full">
        <div class="flex items-center gap-1 text-[11px] font-medium text-warning mb-1">
          <AlertTriangle class="w-3 h-3" />
          Informazioni mancanti
        </div>
        <div class="flex flex-wrap gap-1">
          <span
            v-for="slot in missingSlots"
            :key="slot.slotId"
            class="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium rounded-full border"
            :class="slot.status === 'ambiguous'
              ? 'bg-warning/10 text-warning border-warning/20'
              : 'bg-danger/5 text-danger/80 border-danger/15'"
            :title="slot.status === 'ambiguous' ? 'Ambiguo nelle fonti' : 'Non trovato nelle fonti'"
          >
            {{ slot.label }}
          </span>
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
