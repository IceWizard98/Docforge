/**
 * Trigger a browser "save file" for a Blob. Single copy so any browser-compat or
 * leak fix (anchor lifecycle, delayed revoke) applies to every download path
 * instead of drifting between the export dialog and the source library.
 */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
