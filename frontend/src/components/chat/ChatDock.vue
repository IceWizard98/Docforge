<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Send, Bot, Loader2, Paperclip, Plus, ChevronDown, Pencil, Trash2, ArrowUp, FileText, Upload } from '@lucide/vue'
import ChatMessage from './ChatMessage.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ErrorMessage from '@/components/common/ErrorMessage.vue'
import { useEditorContext } from '@/composables/useEditorContext'
import { useChatStore } from '@/stores/chatStore'
import { useDocumentStore } from '@/stores/documentStore'
import { promoteDraft } from '@/api/client'
import { useToast } from '@/composables/useToast'
import type { ChatActionPayload, SourceRef, ChatMessageResponse } from '@/types/document'
import type { Editor } from '@tiptap/core'
import { MessageSquare } from '@lucide/vue'

const props = defineProps<{
  editor: { value: Editor | null }
  documentId: string
}>()

const inputText = ref('')
const router = useRouter()
const toast = useToast()
const chatStore = useChatStore()
const documentStore = useDocumentStore()
const attachedFiles = ref<File[]>([])
const sessionsOpen = ref(false)
const renamingSessionId = ref<string | null>(null)
const renameText = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)

const { context } = useEditorContext(props.editor)

const messagesContainer = ref<HTMLElement | null>(null)
const inputTextareaRef = ref<HTMLTextAreaElement | null>(null)

function autoGrowTextarea() {
  const el = inputTextareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 400) + 'px'
}

const activeSessionTitle = computed(() => {
  if (!chatStore.sessionId) return ''
  const s = chatStore.sessions.find((s) => s.id === chatStore.sessionId)
  return s?.title || 'Chat'
})

function scrollToBottom() {
  const el = messagesContainer.value
  if (!el) return
  el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
}

watch(() => chatStore.messages.length, async () => {
  await nextTick()
  if (!messagesContainer.value) return
  const el = messagesContainer.value
  const threshold = 100
  const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
  if (isNearBottom) {
    scrollToBottom()
  }
})

async function send() {
  const text = inputText.value.trim()
  if ((!text && attachedFiles.value.length === 0) || chatStore.isSending || chatStore.sessionLoading) return

  inputText.value = ''
  await nextTick()
  if (inputTextareaRef.value) {
    inputTextareaRef.value.style.height = ''
  }

  chatStore.pushMessage({
    id: `msg_${Date.now()}`,
    role: 'user',
    content: text || '(file allegato)',
    created_at: new Date().toISOString(),
  } as ChatMessageResponse)

  await nextTick()
  scrollToBottom()

  let response: ChatMessageResponse | null = null
  if (attachedFiles.value.length > 0) {
    response = await chatStore.sendWithFiles(text, [...attachedFiles.value], context.value, props.documentId)
    attachedFiles.value = []
  } else {
    response = await chatStore.sendMessage(text, context.value, props.documentId)
  }

  handleAssistantResponse(response)
  await chatStore.loadSessions(props.documentId, false)

  await nextTick()
  scrollToBottom()
}

async function handleAction(action: ChatActionPayload) {
  let contextMessage = ''
  const actionType = action.action

  if (actionType === 'draft_ready') {
    const docContent = action.payload?.document_content
    if (docContent) {
      documentStore.setContent(docContent as Record<string, unknown>)
      documentStore.saveContent(docContent as Record<string, unknown>)
    }
    if (action.payload?.draft_id) {
      chatStore.setCurrentDraftId(action.payload.draft_id as string)
    }
    chatStore.pushMessage({
      id: `draft_${Date.now()}`,
      role: 'assistant',
      content: `**${action.payload?.title || 'Documento'}** (${action.payload?.section_count || 0} sezioni) scritto nell'editor.`,
      created_at: new Date().toISOString(),
    } as ChatMessageResponse)
    return
  }

  if (actionType === 'section_created' || actionType === 'clause_inserted' || actionType === 'section_rewritten') {
    const docContent = action.payload?.document_content
    if (docContent) {
      documentStore.setContent(docContent as Record<string, unknown>)
      documentStore.saveContent(docContent as Record<string, unknown>)
    }
    chatStore.pushMessage({
      id: `edit_${Date.now()}`,
      role: 'assistant',
      content: action.label || 'Documento modificato.',
      created_at: new Date().toISOString(),
    } as ChatMessageResponse)
    return
  }

  // 'patches_proposed' is rendered as a granular PatchReviewCard (per-operation
  // accept/reject + apply); it does not flow through handleAction.

  if (actionType === 'suggest_draft') {
    contextMessage = 'Genera un documento completo con tutte le sezioni. Includi il contenuto COMPLETO per ogni sezione, non solo i titoli. Usa action type: draft.'
  } else if (actionType === 'suggest_patches') {
    contextMessage = 'Proponi modifiche al documento.'
  } else if (actionType === 'validate') {
    contextMessage = 'Valida il documento.'
  } else {
    contextMessage = action.label || `Esegui azione: ${actionType}`
  }

  chatStore.pushMessage({
    id: `action_${Date.now()}`,
    role: 'user',
    content: contextMessage,
    created_at: new Date().toISOString(),
  } as ChatMessageResponse)

  await nextTick()
  scrollToBottom()

  const response = await chatStore.sendMessage(contextMessage, context.value, props.documentId)
  handleAssistantResponse(response)
  await chatStore.loadSessions(props.documentId, false)
}

async function handlePromote() {
  const draftId = chatStore.currentDraftId
  if (!draftId || chatStore.promoting) return
  chatStore.promoting = true
  try {
    const doc = await promoteDraft(draftId)
    chatStore.setCurrentDraftId(null)
    toast.success('Bozza promossa a documento definitivo')
    router.push(`/documents/${doc.id}`)
  } catch (e: any) {
    toast.error(e?.response?.data?.detail || e.message || 'Errore durante la promozione della bozza')
  } finally {
    chatStore.promoting = false
  }
}

// Result actions the agent already executed server-side; apply them to the
// editor immediately so the document reflects the change without a manual click.
const AUTO_APPLY_ACTIONS = ['draft_ready', 'section_created', 'clause_inserted', 'section_rewritten']

function handleAssistantResponse(response: ChatMessageResponse | null) {
  if (response?.role === 'assistant') {
    chatStore.pushMessage({
      id: response.id,
      role: 'assistant',
      content: response.content,
      actions: response.actions as ChatActionPayload[] | undefined,
      sources: response.sources || [],
      created_at: response.created_at,
    } as ChatMessageResponse)

    for (const action of (response.actions as ChatActionPayload[] | undefined) || []) {
      if (AUTO_APPLY_ACTIONS.includes(action.action) && action.payload?.document_content) {
        documentStore.setContent(action.payload.document_content as Record<string, unknown>)
        documentStore.saveContent(action.payload.document_content as Record<string, unknown>)
        if (action.action === 'draft_ready' && action.payload?.draft_id) {
          chatStore.setCurrentDraftId(action.payload.draft_id as string)
        }
      }
    }
  }
}

async function onPatchApplied() {
  await documentStore.fetchDocument(props.documentId)
}

function handleRetry() {
  chatStore.setError(null)
  chatStore.loadSessions(props.documentId)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

async function loadSessions() {
  await chatStore.loadSessions(props.documentId)
}

async function selectSession(sid: string) {
  sessionsOpen.value = false
  if (sid === chatStore.sessionId) return
  await chatStore.selectSession(sid)
}

async function newSession() {
  sessionsOpen.value = false
  chatStore.newSession()
  await chatStore.ensureSession(props.documentId)
}

function startRename(sid: string, currentTitle: string) {
  renamingSessionId.value = sid
  renameText.value = currentTitle || ''
}

async function finishRename(sid: string) {
  const title = renameText.value.trim()
  if (title && title !== chatStore.sessions.find((s) => s.id === sid)?.title) {
    await chatStore.renameSession(sid, title)
  }
  renamingSessionId.value = null
  renameText.value = ''
}

function cancelRename() {
  renamingSessionId.value = null
  renameText.value = ''
}

async function confirmDeleteSession(id: string) {
  if (!window.confirm('Eliminare questa sessione chat?')) return
  await chatStore.deleteSession(id)
}

function openFilePicker() {
  fileInputRef.value?.click()
}

function handleFilesSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  attachedFiles.value = [...attachedFiles.value, ...files]
  input.value = ''
}

function removeFile(index: number) {
  attachedFiles.value.splice(index, 1)
}

// Drag & drop support
const isDragging = ref(false)
let dragCounter = 0

function onDragEnter(_e: DragEvent) {
  dragCounter++
  if (dragCounter === 1) isDragging.value = true
}

function onDragLeaveContainer() {
  dragCounter--
  if (dragCounter <= 0) {
    dragCounter = 0
    isDragging.value = false
  }
}

function onDropHandler(e: DragEvent) {
  dragCounter = 0
  isDragging.value = false
  const files = Array.from(e.dataTransfer?.files || [])
  if (files.length > 0) {
    attachedFiles.value = [...attachedFiles.value, ...files]
  }
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

onMounted(() => {
  chatStore.loadSessions(props.documentId)
})
</script>

<template>
  <div
    class="flex flex-col min-h-0 flex-1 bg-surface overflow-hidden"
    @dragover.prevent
    @dragenter="onDragEnter"
    @dragleave="onDragLeaveContainer"
    @drop.prevent="onDropHandler"
  >
    <!-- Drop zone overlay -->
    <div
      v-if="isDragging"
      class="absolute inset-0 z-20 flex items-center justify-center rounded-lg border-2 border-dashed border-primary/50 bg-primary/5 backdrop-blur-[1px]"
    >
      <div class="text-center">
        <Upload class="w-8 h-8 text-primary mx-auto mb-2" />
        <p class="text-sm font-medium text-foreground">Rilascia i file per allegarli</p>
        <p class="text-xs text-foreground/50 mt-1">PDF, DOCX, TXT, MD</p>
      </div>
    </div>
    <!-- Minimal header -->
    <div class="flex items-center gap-2 px-4 py-2.5 border-b border-primary/10 shrink-0">
      <div class="relative flex-1 min-w-0">
        <button
          class="w-full flex items-center gap-1.5 text-sm font-semibold text-foreground truncate hover:text-primary transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          @click="sessionsOpen = !sessionsOpen"
        >
          <Bot class="w-4 h-4 text-primary flex-shrink-0" />
          <span class="truncate">{{ activeSessionTitle || 'Assistant' }}</span>
          <ChevronDown class="w-3.5 h-3.5 flex-shrink-0 ml-auto" />
        </button>
        <!-- Promote to Document button -->
        <button
          v-if="chatStore.currentDraftId"
          class="w-full mt-1.5 inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-cta text-white hover:bg-cta/90 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-cta focus-visible:outline-none disabled:opacity-60 disabled:cursor-not-allowed"
          :disabled="chatStore.promoting"
          @click.stop="handlePromote"
        >
          <Loader2 v-if="chatStore.promoting" class="w-3.5 h-3.5 animate-spin" />
          <FileText v-else class="w-3.5 h-3.5" />
          {{ chatStore.promoting ? 'Promozione...' : 'Promuovi a Documento' }}
        </button>

        <div
          v-if="sessionsOpen"
          class="absolute top-full left-0 right-0 mt-1 bg-card border border-primary/10 rounded-lg shadow-lg z-30 max-h-64 overflow-y-auto"
          @keydown.escape="sessionsOpen = false"
        >
          <div class="p-1.5">
            <button
              class="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-primary/8 rounded-md transition-colors duration-150 cursor-pointer"
              @click="newSession"
            >
              <Plus class="w-4 h-4" />
              Nuova chat
            </button>
            <div class="border-t border-primary/5 my-1" />
            <div v-if="chatStore.sessionLoading" class="flex items-center justify-center py-3">
              <Loader2 class="w-4 h-4 animate-spin text-foreground/40" />
            </div>
            <div v-for="s in chatStore.sessions" :key="s.id" class="group relative">
              <button
                class="w-full flex items-center gap-2 px-3 py-2 text-sm text-left rounded-md transition-colors duration-150 cursor-pointer"
                :class="s.id === chatStore.sessionId ? 'bg-primary/10 text-primary' : 'text-foreground hover:bg-primary/8'"
                @click="selectSession(s.id)"
                @dblclick="startRename(s.id, s.title)"
              >
                <div class="flex-1 min-w-0">
                  <template v-if="renamingSessionId === s.id">
                    <input
                      v-model="renameText"
                      class="w-full text-sm bg-surface border border-primary/20 rounded px-1.5 py-0.5 text-foreground outline-none focus-visible:ring-2 focus-visible:ring-primary"
                      @click.stop
                      @keydown.enter.stop="finishRename(s.id)"
                      @keydown.escape.stop="cancelRename"
                      @blur="finishRename(s.id)"
                    />
                  </template>
                  <template v-else>
                    <p class="text-sm truncate">{{ s.title || 'Senza titolo' }}</p>
                    <p v-if="s.last_message_preview" class="text-[11px] text-foreground/40 truncate mt-0.5">
                      {{ s.last_message_preview }}
                    </p>
                  </template>
                </div>
                <Pencil
                  class="w-3 h-3 text-foreground/30 hover:text-foreground/60 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                  @click.stop="startRename(s.id, s.title)"
                />
                <Trash2
                  class="w-3 h-3 text-foreground/30 hover:text-danger flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                  @click.stop="confirmDeleteSession(s.id)"
                />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Messages — takes all available space -->
    <div ref="messagesContainer" class="flex-1 overflow-y-auto px-4 py-4 space-y-5 min-h-0">
      <EmptyState
        v-if="chatStore.messages.length === 0 && !chatStore.isSending && !chatStore.error && !chatStore.sessionLoading"
        :icon="MessageSquare"
        title="Descrivi il documento che vuoi creare o la modifica che ti serve"
        description="L'assistente puo scrivere interi documenti, aggiungere sezioni, inserire clausole e molto altro."
      />

      <LoadingSpinner v-if="(chatStore.isSending || chatStore.sessionLoading) && chatStore.messages.length === 0" />

      <ErrorMessage
        v-if="chatStore.error && chatStore.messages.length === 0"
        :message="chatStore.error"
        retry-label="Riprova"
        @retry="handleRetry"
      />

      <template v-for="msg in chatStore.messages" :key="msg.id">
        <ChatMessage :message="msg" @action="handleAction" @patch-applied="onPatchApplied" />
      </template>

      <div v-if="chatStore.isSending && chatStore.messages.length > 0" class="flex items-center gap-2 text-xs text-foreground/40 pl-10">
        <Loader2 class="w-3 h-3 animate-spin" />
        <span>Sta scrivendo...</span>
      </div>
    </div>

    <!-- Perplexity-style input area -->
    <div class="border-t border-primary/10 bg-surface p-3 shrink-0">
      <!-- File chips -->
      <div v-if="attachedFiles.length > 0" class="flex flex-wrap gap-1.5 mb-2">
        <div
          v-for="(file, idx) in attachedFiles"
          :key="idx"
          class="inline-flex items-center gap-1 px-2 py-1 text-xs bg-primary/5 border border-primary/10 rounded-md"
        >
          <Paperclip class="w-3 h-3 text-primary/60" />
          <span class="text-foreground/70 truncate max-w-[100px]">{{ file.name }}</span>
          <button class="ml-0.5 text-foreground/40 hover:text-danger transition-colors cursor-pointer" @click="removeFile(idx)">&times;</button>
        </div>
      </div>

      <!-- Input container — Perplexity style -->
      <div class="relative rounded-xl border border-primary/20 bg-card shadow-sm focus-within:border-primary/40 focus-within:shadow-md transition-all duration-200">
        <textarea
          ref="inputTextareaRef"
          v-model="inputText"
          class="w-full min-h-[90px] max-h-[360px] px-4 pt-3.5 pb-14 text-sm bg-transparent text-foreground placeholder-foreground/40 resize-none focus:outline-none"
          placeholder="Descrivi il documento che vuoi creare o la modifica da fare..."
          rows="3"
          :disabled="chatStore.isSending"
          aria-label="Messaggio per l'assistente"
          @keydown="handleKeydown"
          @input="autoGrowTextarea"
        />

        <!-- Bottom action bar — with background gradient to prevent text overlap -->
        <div class="absolute bottom-0 left-0 right-0 px-3 pb-2 pt-6 rounded-b-xl bg-gradient-to-t from-card via-card/95 to-transparent">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-1">
              <input
                ref="fileInputRef"
                type="file"
                accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg"
                class="hidden"
                multiple
                @change="handleFilesSelected"
              />
              <button
                class="p-1.5 rounded-lg text-foreground/40 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer"
                aria-label="Allega file"
                @click="openFilePicker"
              >
                <Paperclip class="w-4 h-4" />
              </button>
            </div>

            <div class="flex items-center gap-2">
              <span v-if="inputText.trim()" class="text-[10px] text-foreground/30 hidden sm:inline tabular-nums">
                Invio per mandare &middot; Shift+Invio per nuova riga
              </span>
              <button
                class="p-1.5 rounded-lg bg-primary text-white hover:bg-primary-light transition-colors duration-150 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer shadow-sm"
                :disabled="(!inputText.trim() && attachedFiles.length === 0) || chatStore.isSending"
                aria-label="Invia messaggio"
                @click="send"
              >
                <ArrowUp class="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
