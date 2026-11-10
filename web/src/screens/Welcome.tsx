interface Props {
  onStart: () => void;
}

const STEPS = [
  ["Take the photo you'd take anyway", "Big Ben, a red bus, your local pub, the pelicans in St James's Park."],
  ["We recognise it", "For places, we also check you're really there."],
  ["It becomes a stamp", "Your photo joins your album with a London postmark and a fact about the place."],
];

/** PRODUCT.md, "Screens", 0, "First open": shown once on this device. */
export function WelcomeScreen({ onStart }: Props) {
  return (
    <main class="welcome paper">
      <span class="mono-label">Welcome</span>
      <h1 class="welcome-title">Collect London, one stamp at a time</h1>
      <ol class="steps">
        {STEPS.map(([title, text], index) => (
          <li key={title}>
            <span class="step-number">{index + 1}</span>
            <span>
              <b>{title}</b>
              <span>{text}</span>
            </span>
          </li>
        ))}
      </ol>
      <p class="welcome-note">
        <b>We'll ask for your camera and location.</b> Location only checks you're at a place and shows the map. We
        don't keep it.
      </p>
      <button class="primary" onClick={onStart}>
        Start collecting
      </button>
    </main>
  );
}
