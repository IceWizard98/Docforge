import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useEditorStore } from '../editorStore'

describe('editorStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('initializes with outline and assistant visible', () => {
    const store = useEditorStore()
    expect(store.showOutline).toBe(true)
    expect(store.showAssistant).toBe(true)
  })

  it('toggles outline sidebar', () => {
    const store = useEditorStore()
    expect(store.showOutline).toBe(true)
    store.toggleOutline()
    expect(store.showOutline).toBe(false)
    store.toggleOutline()
    expect(store.showOutline).toBe(true)
  })

  it('toggles assistant sidebar', () => {
    const store = useEditorStore()
    expect(store.showAssistant).toBe(true)
    store.toggleAssistant()
    expect(store.showAssistant).toBe(false)
    store.toggleAssistant()
    expect(store.showAssistant).toBe(true)
  })

  it('starts with no active section', () => {
    const store = useEditorStore()
    expect(store.activeSectionId).toBeNull()
  })

  it('sets active section', () => {
    const store = useEditorStore()
    store.setActiveSection('section-1')
    expect(store.activeSectionId).toBe('section-1')
    store.setActiveSection(null)
    expect(store.activeSectionId).toBeNull()
  })

  it('expands and collapses sections', () => {
    const store = useEditorStore()
    expect(store.isExpanded('section-1')).toBe(false)
    store.toggleSection('section-1')
    expect(store.isExpanded('section-1')).toBe(true)
    store.toggleSection('section-1')
    expect(store.isExpanded('section-1')).toBe(false)
  })

  it('maintains separate expand state for different sections', () => {
    const store = useEditorStore()
    store.toggleSection('section-1')
    store.toggleSection('section-2')
    expect(store.isExpanded('section-1')).toBe(true)
    expect(store.isExpanded('section-2')).toBe(true)
    store.toggleSection('section-1')
    expect(store.isExpanded('section-1')).toBe(false)
    expect(store.isExpanded('section-2')).toBe(true)
  })

  it('expandAll sets all sections as expanded', () => {
    const store = useEditorStore()
    store.expandAll(['a', 'b', 'c'])
    expect(store.isExpanded('a')).toBe(true)
    expect(store.isExpanded('b')).toBe(true)
    expect(store.isExpanded('c')).toBe(true)
    expect(store.isExpanded('d')).toBe(false)
  })

  it('collapseAll removes all expanded sections', () => {
    const store = useEditorStore()
    store.expandAll(['a', 'b'])
    store.collapseAll()
    expect(store.isExpanded('a')).toBe(false)
    expect(store.isExpanded('b')).toBe(false)
  })
})
