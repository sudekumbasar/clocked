import { useEffect, useId, useMemo } from "preact/hooks";
import type { StampView } from "../stamp";

interface Props {
  photo: Blob;
  stamp: StampView;
  /** "large" on the discovery and item pages; "small" in the collection. */
  size: "large" | "small";
  animate?: boolean;
  alt?: string;
}

/** A blob URL for a photo, released when the photo changes or the screen closes. */
export function usePhotoUrl(photo: Blob): string {
  const url = useMemo(() => URL.createObjectURL(photo), [photo]);
  useEffect(() => () => URL.revokeObjectURL(url), [url]);
  return url;
}

/** Worn ink: speckles where the rubber did not quite touch the paper. */
function WornInk({ id }: { id: string }) {
  return (
    <filter id={id} x="-5%" y="-5%" width="110%" height="110%">
      <feTurbulence type="fractalNoise" baseFrequency="1.1" numOctaves="2" seed="4" result="noise" />
      <feColorMatrix in="noise" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  -1 0 0 0 1.45" result="worn" />
      <feComposite in="SourceGraphic" in2="worn" operator="in" />
    </filter>
  );
}

/** A London postmark: the dated circle with wavy cancel lines beside it. */
function Postmark({ stamp, animate }: { stamp: StampView; animate: boolean }) {
  const ink = `ink-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  return (
    <svg class={`postmark ${animate ? "thump" : ""}`} viewBox="0 0 240 120" style={{ color: stamp.ink }} aria-hidden="true">
      <defs><WornInk id={ink} /></defs>
      <g filter={`url(#${ink})`}>
        <g fill="none" stroke="currentColor">
          <circle cx="60" cy="60" r="52" stroke-width="4" />
          <circle cx="60" cy="60" r="38" stroke-width="1.6" />
          <path
            d="M118 34 q15 -10 30 0 t30 0 t30 0 t30 0 M118 52 q15 -10 30 0 t30 0 t30 0 t30 0 M118 70 q15 -10 30 0 t30 0 t30 0 t30 0 M118 88 q15 -10 30 0 t30 0 t30 0 t30 0"
            stroke-width="3.2"
          />
        </g>
        <g fill="currentColor" text-anchor="middle" class="postmark-text">
          <text x="60" y="51" font-size="12" letter-spacing="2">LONDON</text>
          <text x="60" y="69" font-size="13">{stamp.postmarkDate}</text>
          <text x="60" y="85" font-size="10" letter-spacing="2">{"★".repeat(stamp.stars)}</text>
        </g>
      </g>
    </svg>
  );
}

/** The small cancellation on a stamp in the collection: a ring with two bars. */
function Cancel({ stamp }: { stamp: StampView }) {
  const ink = `ink-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  return (
    <svg class="cancel" viewBox="0 0 100 100" style={{ color: stamp.ink }} aria-hidden="true">
      <defs><WornInk id={ink} /></defs>
      <g filter={`url(#${ink})`} fill="none" stroke="currentColor">
        <circle cx="50" cy="50" r="44" stroke-width="6" />
        <path d="M14 40 h72 M14 60 h72" stroke-width="4" />
      </g>
    </svg>
  );
}

/** The player's own photo as a perforated postage stamp. The photo stays fully visible. */
export function PostageStamp({ photo, stamp, size, animate = false, alt = "" }: Props) {
  const url = usePhotoUrl(photo);
  return (
    <figure class={`postage ${size} ${animate ? "drop" : ""}`} style={{ "--tilt": `${stamp.tilt}deg` }}>
      <div class="perforated">
        <div class="stamp-face">
          <img src={url} alt={alt} />
          {size === "large" && <span class="denomination" aria-label={`${stamp.stars} star`}>{"★".repeat(stamp.stars)}</span>}
          <figcaption>
            <b>{stamp.name}</b>
            {size === "large" && <span>{stamp.category}</span>}
          </figcaption>
        </div>
      </div>
      {size === "large" ? <Postmark stamp={stamp} animate={animate} /> : <Cancel stamp={stamp} />}
    </figure>
  );
}
