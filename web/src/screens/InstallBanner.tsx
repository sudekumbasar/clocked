import { useEffect, useState } from "preact/hooks";
import { canPromptInstall, isIos, isStandalone, onInstallAvailable, promptInstall } from "../persist";

const DISMISSED_KEY = "clocked.installBannerDismissed";

function wasDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
}

/** Shown after the first discovery, unless the app already runs from the home screen. */
export function InstallBanner() {
  const [hidden, setHidden] = useState(isStandalone() || wasDismissed());
  const [canPrompt, setCanPrompt] = useState(canPromptInstall());
  useEffect(() => onInstallAvailable(() => setCanPrompt(true)), []);

  if (hidden) return null;

  function dismiss() {
    try {
      localStorage.setItem(DISMISSED_KEY, "1");
    } catch {
      // Private browsing: the banner simply comes back next time.
    }
    setHidden(true);
  }

  return (
    <aside class="install">
      <p>
        <strong>Keep your collection safe.</strong>{" "}
        {isIos()
          ? "Add Clocked to your Home Screen: tap the Share button, then “Add to Home Screen”."
          : canPrompt
            ? "Add Clocked to your Home Screen so your finds are kept."
            : "Add Clocked to your Home Screen from your browser’s menu so your finds are kept."}
      </p>
      <div class="install-actions">
        {canPrompt && !isIos() && (
          <button class="pill light" onClick={() => promptInstall().then(dismiss)}>
            Add to Home Screen
          </button>
        )}
        <button class="pill" onClick={dismiss}>
          Not now
        </button>
      </div>
    </aside>
  );
}
