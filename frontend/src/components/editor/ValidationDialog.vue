<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Loader2, X, ShieldCheck, ShieldAlert, AlertTriangle, Info, CircleAlert } from '@lucide/vue'
import { validateDocument, extractApiError, type ValidationReport, type ValidationIssue } from '@/api/client'

const props = defineProps<{ documentId: string }>()
const emit = defineEmits<{ close: [] }>()

const loading = ref(true)
const error = ref<string | null>(null)
const report = ref<ValidationReport | null>(null)

// Order + presentation per severity. Anything unexpected falls back to "info".
const SEVERITY = {
  error: { label: 'Errori', icon: CircleAlert, badge: 'bg-danger/10 text-danger', dot: 'bg-danger' },
  warning: { label: 'Avvisi', icon: AlertTriangle, badge: 'bg-warning/10 text-warning', dot: 'bg-warning' },
  info: { label: 'Note', icon: Info, badge: 'bg-primary/10 text-primary', dot: 'bg-primary' },
} as const
type Sev = keyof typeof SEVERITY
const ORDER: Sev[] = ['error', 'warning', 'info']

function sevOf(issue: ValidationIssue): Sev {
  return (issue.severity in SEVERITY ? issue.severity : 'info') as Sev
}

// Group by severity ourselves so the UI is robust whether or not the backend
// filled issues_grouped, and so ordering/labels stay under our control.
const grouped = computed<Array<{ sev: Sev; issues: ValidationIssue[] }>>(() => {
  const r = report.value
  if (!r) return []
  const buckets: Record<Sev, ValidationIssue[]> = { error: [], warning: [], info: [] }
  for (const issue of r.issues) buckets[sevOf(issue)].push(issue)
  return ORDER.filter((s) => buckets[s].length).map((sev) => ({ sev, issues: buckets[sev] }))
})

// il backend restituisce già una scala 0-100 (es. 100.0 = perfetto)
const scorePct = computed(() => Math.round(report.value?.score ?? 0))

async function run() {
  loading.value = true
  error.value = null
  try {
    report.value = await validateDocument(props.documentId)
  } catch (e: any) {
    error.value = extractApiError(e, 'Validazione fallita')
  } finally {
    loading.value = false
  }
}

onMounted(run)
</script>

<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
      @click.self="emit('close')"
    >
      <div class="w-full max-w-md rounded-xl bg-surface p-5 md:p-6 shadow-xl border border-primary/10 max-h-[85vh] overflow-y-auto">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold text-foreground flex items-center gap-2">
            <ShieldCheck class="h-5 w-5 text-primary" />
            Validazione documento
          </h2>
          <button
            class="p-1 rounded text-foreground/40 hover:text-foreground hover:bg-primary/8 transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
            aria-label="Chiudi"
            @click="emit('close')"
          >
            <X class="h-4 w-4" />
          </button>
        </div>

        <div v-if="loading" class="flex items-center justify-center gap-2 py-10 text-sm text-foreground/60">
          <Loader2 class="h-4 w-4 animate-spin text-primary" />
          Analisi in corso…
        </div>

        <div v-else-if="error" class="py-6 text-center">
          <p class="text-sm text-danger">{{ error }}</p>
          <button
            class="mt-3 rounded-lg border border-primary/15 px-3 py-1.5 text-sm font-medium text-foreground/70 hover:bg-primary/8 hover:text-primary transition-colors cursor-pointer"
            @click="run"
          >
            Riprova
          </button>
        </div>

        <template v-else-if="report">
          <!-- Score + esito -->
          <div class="flex items-center gap-4 rounded-lg border border-primary/10 bg-card px-4 py-3 mb-4">
            <div class="flex flex-col">
              <span class="text-3xl font-bold text-foreground leading-none">{{ scorePct }}</span>
              <span class="text-xs text-foreground/40 mt-1">Punteggio</span>
            </div>
            <span
              class="ml-auto inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
              :class="report.passed ? 'bg-cta/10 text-cta' : 'bg-danger/10 text-danger'"
            >
              <ShieldCheck v-if="report.passed" class="h-3.5 w-3.5" />
              <ShieldAlert v-else class="h-3.5 w-3.5" />
              {{ report.passed ? 'Superata' : 'Non superata' }}
            </span>
          </div>

          <p v-if="report.summary" class="text-sm text-foreground/60 mb-4">{{ report.summary }}</p>

          <div v-if="!grouped.length" class="flex flex-col items-center py-6 text-center">
            <ShieldCheck class="h-6 w-6 text-cta mb-2" />
            <p class="text-sm font-medium text-foreground/60">Nessun problema rilevato</p>
          </div>

          <div v-else class="space-y-4 max-h-72 overflow-y-auto">
            <section v-for="g in grouped" :key="g.sev">
              <h3 class="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-foreground/50 mb-2">
                <component :is="SEVERITY[g.sev].icon" class="h-3.5 w-3.5" />
                {{ SEVERITY[g.sev].label }}
                <span class="rounded-full px-1.5 py-0.5 text-[10px]" :class="SEVERITY[g.sev].badge">{{ g.issues.length }}</span>
              </h3>
              <ul class="space-y-1.5">
                <li
                  v-for="(issue, i) in g.issues"
                  :key="i"
                  class="flex items-start gap-2 rounded-lg border border-primary/10 bg-card px-3 py-2"
                >
                  <span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" :class="SEVERITY[g.sev].dot" />
                  <span class="text-sm text-foreground/80">{{ issue.message || issue.type }}</span>
                </li>
              </ul>
            </section>
          </div>
        </template>

        <div class="mt-5 flex justify-end">
          <button
            class="rounded-lg px-4 py-2 text-sm font-medium text-foreground/70 hover:bg-primary/8 transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
            @click="emit('close')"
          >
            Chiudi
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
