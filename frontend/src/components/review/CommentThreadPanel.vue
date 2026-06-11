<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { format } from 'date-fns'
import { MessageSquare, Check, Reply, X } from '@lucide/vue'
import { listComments, createComment, resolveComment } from '@/api/client'
import type { Comment } from '@/types/document'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

function formatDate(iso: string) {
  try {
    return format(new Date(iso), 'MMM d, HH:mm')
  } catch {
    return iso
  }
}

const props = defineProps<{
  documentId: string
}>()

const emit = defineEmits<{
  close: []
}>()

const comments = ref<Comment[]>([])
const loading = ref(false)
const showResolved = ref(false)
const newCommentText = ref('')
const replyTexts = ref<Record<string, string>>({})
const submitting = ref(false)

onMounted(async () => {
  if (!props.documentId) return
  loading.value = true
  try {
    comments.value = await listComments(props.documentId)
  } catch (e) {
    console.error('Failed to load comments', e)
  } finally {
    loading.value = false
  }
})

const threads = computed(() => {
  const roots = comments.value.filter((c) => !c.thread_id)
  return roots.map((root) => ({
    ...root,
    replies: comments.value.filter((c) => c.thread_id === root.id),
  }))
})

const activeThreads = computed(() => threads.value.filter((t) => !t.resolved))
const resolvedThreads = computed(() => threads.value.filter((t) => t.resolved))

async function handleResolve(commentId: string) {
  try {
    const updated = await resolveComment(commentId)
    comments.value = comments.value.map((c) =>
      c.id === commentId ? { ...c, resolved: updated.resolved } : c,
    )
  } catch (e) {
    console.error('Failed to resolve comment', e)
  }
}

async function handleAddReply(threadId: string) {
  const text = replyTexts.value[threadId]?.trim()
  if (!text || submitting.value) return
  submitting.value = true
  try {
    const created = await createComment(props.documentId, text, threadId)
    comments.value.push(created)
    replyTexts.value[threadId] = ''
  } catch (e) {
    console.error('Failed to add reply', e)
  } finally {
    submitting.value = false
  }
}

async function handleAddComment() {
  const text = newCommentText.value?.trim()
  if (!text || submitting.value || !props.documentId) return
  submitting.value = true
  try {
    const created = await createComment(props.documentId, text)
    comments.value.push(created)
    newCommentText.value = ''
  } catch (e) {
    console.error('Failed to add comment', e)
  } finally {
    submitting.value = false
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
        {{ activeThreads.length }} active
      </span>
      <button
        class="p-1 rounded text-foreground/40 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
        aria-label="Close comments"
        @click="emit('close')"
      >
        <X class="w-4 h-4" />
      </button>
    </div>

    <!-- New comment input -->
    <div class="px-4 py-2 border-b border-primary/10">
      <div class="flex gap-2">
        <input
          v-model="newCommentText"
          class="flex-1 px-2 py-1.5 text-sm bg-white border border-primary/10 rounded-md text-foreground placeholder-foreground/40 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          placeholder="Add a comment..."
          @keydown.enter="handleAddComment"
        />
        <button
          class="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none disabled:opacity-40"
          :disabled="!newCommentText.trim() || submitting"
          @click="handleAddComment"
        >
          <MessageSquare class="w-4 h-4" />
        </button>
      </div>
    </div>

    <!-- Comments list -->
    <div class="flex-1 overflow-y-auto">
      <!-- Loading -->
      <div v-if="loading" class="flex items-center justify-center py-8">
        <LoadingSpinner />
      </div>

      <!-- Empty state -->
      <EmptyState
        v-else-if="comments.length === 0"
        title="No comments"
        description="Add a comment to start a discussion"
      />

      <!-- Active threads -->
      <div v-for="thread in activeThreads" :key="thread.id" class="border-b border-primary/5">
        <div class="px-4 py-3">
          <div class="flex items-start gap-2">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-xs font-medium text-foreground">{{ thread.author }}</span>
                <span class="text-[10px] text-foreground/40">{{ formatDate(thread.created_at) }}</span>
              </div>
              <p class="text-sm text-foreground/80">{{ thread.content }}</p>
            </div>
            <button
              class="p-1 rounded text-cta hover:bg-cta/10 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
              title="Resolve"
              @click="handleResolve(thread.id)"
            >
              <Check class="w-3.5 h-3.5" />
            </button>
          </div>

          <!-- Replies -->
          <div v-if="thread.replies.length > 0" class="ml-4 mt-2 space-y-2">
            <div
              v-for="reply in thread.replies"
              :key="reply.id"
              class="border-l-2 border-primary/10 pl-3"
            >
              <div class="flex items-center gap-2 mb-0.5">
                <span class="text-[11px] font-medium text-foreground/60">{{ reply.author }}</span>
                <span class="text-[10px] text-foreground/40">{{ formatDate(reply.created_at) }}</span>
              </div>
              <p class="text-xs text-foreground/70">{{ reply.content }}</p>
            </div>
          </div>

          <!-- Reply input -->
          <div class="mt-2 flex gap-2">
            <input
              v-model="replyTexts[thread.id]"
              class="flex-1 px-2 py-1 text-xs bg-white border border-primary/10 rounded-md text-foreground placeholder-foreground/40 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
              placeholder="Write a reply..."
              @keydown.enter="handleAddReply(thread.id)"
            />
            <button
              class="p-1 rounded text-primary hover:bg-primary/10 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none disabled:opacity-40"
              :disabled="!replyTexts[thread.id]?.trim() || submitting"
              @click="handleAddReply(thread.id)"
            >
              <Reply class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      <!-- Resolved toggle -->
      <button
        v-if="resolvedThreads.length > 0"
        class="w-full px-4 py-2 text-xs font-medium text-foreground/40 hover:text-primary hover:bg-primary/5 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
        @click="showResolved = !showResolved"
      >
        {{ showResolved ? 'Hide' : 'Show' }} resolved ({{ resolvedThreads.length }})
      </button>

      <!-- Resolved comments -->
      <div v-if="showResolved && resolvedThreads.length > 0">
        <div
          v-for="thread in resolvedThreads"
          :key="thread.id"
          class="px-4 py-2 opacity-50"
        >
          <div class="flex items-center gap-2">
            <span class="text-xs text-foreground/50 line-through">{{ thread.author }}</span>
            <span class="text-[10px] text-cta">Resolved</span>
          </div>
          <p class="text-xs text-foreground/40 line-through">{{ thread.content }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
