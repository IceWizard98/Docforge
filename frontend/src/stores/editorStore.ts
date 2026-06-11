import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useEditorStore = defineStore('editor', () => {
  const activeSectionId = ref<string | null>(null)
  const expandedSections = ref<Set<string>>(new Set())
  const showOutline = ref(true)
  const showAssistant = ref(true)
  const selectedText = ref<string | null>(null)

  function isExpanded(id: string): boolean {
    return expandedSections.value.has(id)
  }

  function toggleSection(id: string) {
    const newSet = new Set(expandedSections.value)
    if (newSet.has(id)) {
      newSet.delete(id)
    } else {
      newSet.add(id)
    }
    expandedSections.value = newSet
  }

  function expandAll(sectionIds: string[]) {
    expandedSections.value = new Set(sectionIds)
  }

  function collapseAll() {
    expandedSections.value = new Set()
  }

  function setActiveSection(id: string | null) {
    activeSectionId.value = id
  }

  function toggleOutline() {
    showOutline.value = !showOutline.value
  }

  function toggleAssistant() {
    showAssistant.value = !showAssistant.value
  }

  return {
    activeSectionId,
    expandedSections,
    showOutline,
    showAssistant,
    selectedText,
    isExpanded,
    toggleSection,
    expandAll,
    collapseAll,
    setActiveSection,
    toggleOutline,
    toggleAssistant,
  }
})
