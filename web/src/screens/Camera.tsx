import { useEffect, useRef, useState } from "preact/hooks";
import type { ComponentChildren } from "preact";
import { CAMERA_DENIED_MESSAGE, capture, startCamera, stopCamera } from "../camera";
import { usePhotoUrl } from "./PostageStamp";

interface Props {
  busy: boolean;
  message: string | null;
  canRetry: boolean;
  /** The newest stamp's photo, shown small in the corner; tapping it opens the album. */
  latestPhoto: Blob | null;
  onPhoto: (photo: Blob) => void;
  onRetry: () => void;
  onOpenCollection: () => void;
  onOpenMap: () => void;
  onHome: () => void;
  /** Development builds only: saved-photo picker and reset. */
  testTools?: ComponentChildren;
}

function LatestStamp({ photo, onOpen }: { photo: Blob; onOpen: () => void }) {
  const url = usePhotoUrl(photo);
  return (
    <button class="latest-stamp" onClick={onOpen} aria-label="My stamps">
      <img src={url} alt="" />
    </button>
  );
}

export function CameraScreen(props: Props) {
  const video = useRef<HTMLVideoElement>(null);
  const [cameraError, setCameraError] = useState<string | null>(null);

  useEffect(() => {
    let stream: MediaStream | null = null;
    let closed = false;
    startCamera(video.current!)
      .then((s) => {
        stream = s;
        // The screen may have closed while the camera was starting: turn it off again.
        if (closed) stopCamera(s);
      })
      .catch(() => setCameraError(CAMERA_DENIED_MESSAGE));
    return () => {
      closed = true;
      stopCamera(stream);
      if (video.current) video.current.srcObject = null;
    };
  }, []);

  async function shoot() {
    if (props.busy || !video.current?.videoWidth) return;
    props.onPhoto(await capture(video.current));
  }

  return (
    <main class="camera">
      <video ref={video} class="viewfinder" playsInline muted autoPlay />
      {cameraError && !props.busy && <p class="camera-error">{cameraError}</p>}

      <div class="stamp-frame" aria-hidden="true" />
      <p class="frame-hint" aria-hidden="true">Frame it like a stamp</p>

      <header class="topbar">
        <button class="pill" onClick={props.onHome}>
          ← Home
        </button>
        <button class="pill" onClick={props.onOpenMap}>
          Map
        </button>
      </header>

      {props.busy && <div class="looking">Looking…</div>}

      {props.message && !props.busy && (
        <div class="toast" role="status">
          <p>{props.message}</p>
          {props.canRetry && (
            <button class="pill light" onClick={props.onRetry}>
              Retry
            </button>
          )}
        </div>
      )}

      <footer class="controls">
        {props.testTools}
        {props.latestPhoto && <LatestStamp photo={props.latestPhoto} onOpen={props.onOpenCollection} />}
        <button
          class="shutter"
          aria-label="Take photo"
          disabled={props.busy || cameraError !== null}
          onClick={shoot}
        />
      </footer>
    </main>
  );
}
