<script setup lang="ts">
import { ref, computed } from 'vue'
import { MessageSquare, Check, Reply } from '@lucide/vue'
import type { Comment } from '@/types/document'
import EmptyState from '@/components/common/EmptyState.vue'

const props = defineProps<{
  comments: Comment[]
}>()

const emit = defineEmits<{
  resolve: [commentId: string]
  addReply: [commentId: string, text: string]
}>()

const showResolved = ref(false)
const replyTexts = ref<Record<string, string>>({})
const submittingReply = ref(false)

const activeComments = computed(() => props.comments.filter((c) => !c.resolved))
const resolvedComments = computed(() => props.comments.filter((c) => c.resolved))

function toggleShowResolved() {
  showResolved.value = !showResolved.value
}

async function handleAddReply(commentId: string) {
  const text = replyTexts.value[commentId]?.trim()
  if (!text || submittingReply.value) return
  submittingReply.value = true
  try {
    emit('addReply', commentId, text)
    replyTexts.value[commentId] = ''
  } finally {
    submittingReply.value = false
  }
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="flex items-center gap-2 px-4 py-3 border-b border-primary/10">
      <MessageSquare class="w-4 h-4 text-primary" />
      <h2 class="text-sm font-semibold text-foreground">Comments</h2>
      <span class="ml-auto text-[11px] text-foreground/40 font-medium">
        {{ activeComments.length }} active
      </span>
    </div>

    <!-- Comments list -->
    <div class="flex-1 overflow-y-auto">
      <!-- Empty state -->
      <EmptyState
        v-if="comments.length === 0"
        title="Nessun commento"
        description="Seleziona testo e aggiungi un commento per iniziare"
      />

      <!-- Active comments -->
      <div v-for="comment in activeComments" :key="comment.commentId" class="border-b border-primary/5">
        <div class="px-4 py-3">
          <div class="flex items-start gap-2">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-xs font-medium text-foreground">{{ comment.author }}</span>
                <span class="text-[10px] text-foreground/40">{{ comment.createdAt }}</span>
              </div>
              <p class="text-sm text-foreground/80">{{ comment.text }}</p>
            </div>
            <button
              class="p-1 rounded text-cta hover:bg-cta/10 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
              title="Resolve"
              @click="emit('resolve', comment.commentId)"
            >
              <Check class="w-3.5 h-3.5" />
            </button>
          </div>

          <!-- Replies -->
          <div v-if="comment.replies.length > 0" class="ml-4 mt-2 space-y-2">
            <div
              v-for="reply in comment.replies"
              :key="reply.replyId"
              class="border-l-2 border-primary/10 pl-3"
            >
              <div class="flex items-center gap-2 mb-0.5">
                <span class="text-[11px] font-medium text-foreground/60">{{ reply.author }}</span>
                <span class="text-[10px] text-foreground/40">{{ reply.createdAt }}</span>
              </div>
              <p class="text-xs text-foreground/70">{{ reply.text }}</p>
            </div>
          </div>

          <!-- Add reply -->
          <div class="mt-2 flex gap-2">
            <input
              v-model="replyTexts[comment.commentId]"
              class="flex-1 px-2 py-1 text-xs bg-white border border-primary/10 rounded-md text-foreground placeholder-foreground/40 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
              placeholder="Scrivi una risposta..."
              @keydown.enter="handleAddReply(comment.commentId)"
            />
            <button
              class="p-1 rounded text-primary hover:bg-primary/10 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
              @click="handleAddReply(comment.commentId)"
            >
              <Reply class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      <!-- Resolved toggle -->
      <button
        v-if="resolvedComments.length > 0"
        class="w-full px-4 py-2 text-xs font-medium text-foreground/40 hover:text-primary hover:bg-primary/5 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
        @click="toggleShowResolved"
      >
        {{ showResolved ? 'Hide' : 'Show' }} resolved ({{ resolvedComments.length }})
      </button>

      <!-- Resolved comments -->
      <div v-if="showResolved && resolvedComments.length > 0">
        <div
          v-for="comment in resolvedComments"
          :key="comment.commentId"
          class="px-4 py-2 opacity-50"
        >
          <div class="flex items-center gap-2">
            <span class="text-xs text-foreground/50 line-through">{{ comment.author }}</span>
            <span class="text-[10px] text-cta">Resolved</span>
          </div>
          <p class="text-xs text-foreground/40 line-through">{{ comment.text }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
