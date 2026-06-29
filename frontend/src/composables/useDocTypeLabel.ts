import { useI18n } from 'vue-i18n'

// Canonical doc types (mirror backend core/doc_types.py CANONICAL_DOC_TYPES).
export const CANONICAL_DOC_TYPES = [
  'contract',
  'nda',
  'company_profile',
  'service_sheet',
  'technical_doc',
  'other',
] as const

// Single source of truth for localizing a source/document doc_type badge.
// Unknown values fall back to the raw string.
export function useDocTypeLabel() {
  const { t } = useI18n({ useScope: 'global' })
  return (dt?: string): string => {
    if (!dt) return t('docType.other')
    return (CANONICAL_DOC_TYPES as readonly string[]).includes(dt) ? t(`docType.${dt}`) : dt
  }
}
