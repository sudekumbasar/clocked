/**
 * Keeping the collection safe (PRODUCT.md, "Technical shape"). Safari may delete a site's
 * data after about 7 days without a visit unless it was added to the home screen, so:
 * ask for persistent storage, and suggest adding the app to the home screen.
 */

export async function requestPersistentStorage(): Promise<boolean> {
  if (!navigator.storage?.persist) return false;
  if (await navigator.storage.persisted()) return true;
  return navigator.storage.persist();
}

export function isStandalone(): boolean {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

export function isIos(): boolean {
  const ua = navigator.userAgent;
  return /iPhone|iPad|iPod/.test(ua) || (ua.includes("Macintosh") && navigator.maxTouchPoints > 1);
}

/** Chrome on Android offers an install prompt we can trigger from our own button. */
export interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>;
}

let deferredPrompt: InstallPromptEvent | null = null;
const listeners = new Set<() => void>();

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredPrompt = event as InstallPromptEvent;
  listeners.forEach((listener) => listener());
});

export function canPromptInstall(): boolean {
  return deferredPrompt !== null;
}

export function onInstallAvailable(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export async function promptInstall(): Promise<void> {
  await deferredPrompt?.prompt();
  deferredPrompt = null;
}

export function vibrate(): void {
  // Android only; iPhone browsers do not support vibration.
  navigator.vibrate?.([60, 40, 140]);
}
