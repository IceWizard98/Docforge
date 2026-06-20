<script setup lang="ts">
import { ref, computed } from 'vue'
import { Check, X, GitPullRequestArrow, Loader2 } from '@lucide/vue'
import { acceptPatchOperation, rejectPatchOperation, applyPatchSet } from '@/api/client'
import { useToast } from '@/composables/useToast'

interface PatchOperation {
  id: string
  operation: string
  target_section?: string | null
  target_path?: string[] | null
  content?: unknown
  rationale?: string | null
}

const props = defineProps<{
  patchSetId: string
  summary?: string
  operations: PatchOperation[]
}>()

const emit = defineEmits<{ applied: [] }>()

const { error: toastError, success } = useToast()

// Per-operation review state: 'pending' | 'accepted' | 'rejected'.
const statuses = ref<Record<string, string>>(
  Object.fromEntries(props.operations.map((op) => [op.id, 'pending'])),
)
const busy = ref<string | null>(null)
const applying = ref(false)
const applied = ref(false)

const acceptedCount = computed(
  () => Object.values(statuses.value).filter((s) => s === 'accepted').length,
)
const decided = computed(
  () => Object.values(statuses.value).every((s) => s !== 'pending'),
)

const OP_LABELS: Record<string, string> = {
  insert: 'Inserisci',
  replace: 'Sostituisci',
  delete: 'Elimina',
}

function opLabel(op: PatchOperation): string {
  return OP_LABELS[op.operation] || op.operation
}

function preview(content: unknown): string {
  if (content == null) return ''
  if (typeof content === 'string') return content
  // ProseMirror-ish { content: [...] } → flatten text nodes.
  const extract = (node: any): string => {
    if (!node || typeof node !== 'object') return ''
    if (node.type === 'text') return node.text || ''
    if (Array.isArray(node.content)) return node.content.map(extract).join('')
    return ''
  }
  const c = content as any
  if (Array.isArray(c?.content)) return c.content.map(extract).join(' ')
  try {
    return JSON.stringify(content).slice(0, 300)
  } catch {
    return ''
  }
}

function extractErr(e: any): string {
  return e?.response?.data?.detail || e?.message || 'Operazione fallita'
}

async function accept(op: PatchOperation) {
  busy.value = op.id
  try {
    await acceptPatchOperation(props.patchSetId, op.id)
    statuses.value[op.id] = 'accepted'
  } catch (e: any) {
    toastError(extractErr(e))
  } finally {
    busy.value = null
  }
}

async function reject(op: PatchOperation) {
  busy.value = op.id
  try {
    await rejectPatchOperation(props.patchSetId, op.id)
    statuses.value[op.id] = 'rejected'
  } catch (e: any) {
    toastError(extractErr(e))
  } finally {
    busy.value = null
  }
}

async function apply() {
  if (acceptedCount.value === 0 || applying.value) return
  applying.value = true
  try {
    await applyPatchSet(props.patchSetId)
    applied.value = true
    success('Modifiche applicate al documento')
    emit('applied')
  } catch (e: any) {
    toastError(extractErr(e))
  } finally {
    applying.value = false
  }
}
</script>

<template>
  <div class="mt-2 w-full rounded-lg border border-cta/30 bg-cta/5 overflow-hidden">
    <div class="flex items-center gap-2 px-3 py-2 border-b border-cta/20 bg-cta/10">
      <GitPullRequestArrow class="w-4 h-4 text-cta" />
      <span class="text-xs font-semibold text-foreground">Modifiche proposte</span>
      <span class="ml-auto text-[10px] text-foreground/50">{{ operations.length }} operazioni</span>
    </div>

    <p v-if="summary" class="px-3 pt-2 text-xs text-foreground/70">{{ summary }}</p>

    <ul class="divide-y divide-cta/10">
      <li v-for="op in operations" :key="op.id" class="px-3 py-2">
        <div class="flex items-start gap-2">
          <span class="text-[10px] font-medium px-1.5 py-0.5 rounded bg-primary/10 text-primary shrink-0">
            {{ opLabel(op) }}
          </span>
          <div class="min-w-0 flex-1">
            <div v-if="op.target_section" class="text-[10px] text-foreground/40 font-mono">
              {{ op.target_section }}
            </div>
            <div class="text-xs text-foreground/80 whitespace-pre-wrap break-words line-clamp-4">
              {{ preview(op.content) || '—' }}
            </div>
            <div v-if="op.rationale" class="text-[10px] text-foreground/40 italic mt-0.5">
              {{ op.rationale }}
            </div>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <template v-if="statuses[op.id] === 'pending'">
              <button
                class="p-1 rounded text-foreground/50 hover:text-cta hover:bg-cta/10 disabled:opacity-40"
                title="Accetta" :disabled="busy === op.id" @click="accept(op)"
              >
                <Loader2 v-if="busy === op.id" class="w-3.5 h-3.5 animate-spin" />
                <Check v-else class="w-3.5 h-3.5" />
              </button>
              <button
                class="p-1 rounded text-foreground/50 hover:text-danger hover:bg-danger/10 disabled:opacity-40"
                title="Rifiuta" :disabled="busy === op.id" @click="reject(op)"
              >
                <X class="w-3.5 h-3.5" />
              </button>
            </template>
            <span v-else-if="statuses[op.id] === 'accepted'" class="text-[10px] font-medium text-cta">Accettata</span>
            <span v-else class="text-[10px] font-medium text-danger">Rifiutata</span>
          </div>
        </div>
      </li>
    </ul>

    <div class="flex items-center gap-2 px-3 py-2 border-t border-cta/20">
      <span class="text-[10px] text-foreground/50">{{ acceptedCount }} accettate</span>
      <button
        class="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md bg-cta text-white hover:opacity-90 disabled:opacity-40"
        :disabled="acceptedCount === 0 || applying || applied"
        @click="apply"
      >
        <Loader2 v-if="applying" class="w-3 h-3 animate-spin" />
        <Check v-else class="w-3 h-3" />
        {{ applied ? 'Applicate' : 'Applica accettate' }}
      </button>
    </div>
  </div>
</template>
