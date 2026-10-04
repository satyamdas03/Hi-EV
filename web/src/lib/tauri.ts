/**
 * Minimal bridge to Tauri native APIs when running inside the desktop shell.
 *
 * The same HUD works in a normal browser, so this file must not break when
 * `window.__TAURI__` is absent.
 */

export const IS_TAURI = typeof window !== 'undefined' && !!(window as any).__TAURI__

export async function showWindow(): Promise<void> {
  if (!IS_TAURI) return
  const tauri = (window as any).__TAURI__.window
  await tauri.getCurrentWindow().show()
  await tauri.getCurrentWindow().setFocus()
}

export async function hideWindow(): Promise<void> {
  if (!IS_TAURI) return
  const tauri = (window as any).__TAURI__.window
  await tauri.getCurrentWindow().hide()
}

export function onShortcutTriggered(callback: () => void): () => void {
  if (!IS_TAURI) return () => {}
  const tauri = (window as any).__TAURI__.event
  const unlisten = tauri.listen('ev:shortcut-triggered', callback)
  return unlisten
}
