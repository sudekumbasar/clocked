/** The live camera inside the page (PRODUCT.md: no file picker, no gallery). */

/** The server downscales to this anyway; sending less is faster on a phone connection. */
export const MAX_LONG_EDGE = 1568;
const JPEG_QUALITY = 0.85;

export const CAMERA_DENIED_MESSAGE = "Camera access is needed to discover items.";

export async function startCamera(video: HTMLVideoElement): Promise<MediaStream> {
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1440 } },
    audio: false,
  });
  video.srcObject = stream;
  await video.play();
  return stream;
}

export function stopCamera(stream: MediaStream | null): void {
  stream?.getTracks().forEach((track) => track.stop());
}

/** Size that fits within the long-edge limit, keeping the aspect ratio. */
export function fitWithin(width: number, height: number, maxEdge = MAX_LONG_EDGE) {
  const scale = Math.min(1, maxEdge / Math.max(width, height));
  return { width: Math.round(width * scale), height: Math.round(height * scale) };
}

/** Draw a bitmap or video frame to a JPEG. */
export async function toJpeg(
  source: CanvasImageSource,
  width: number,
  height: number,
): Promise<Blob> {
  const size = fitWithin(width, height);
  const canvas = document.createElement("canvas");
  canvas.width = size.width;
  canvas.height = size.height;
  canvas.getContext("2d")!.drawImage(source, 0, 0, size.width, size.height);
  return new Promise((resolve, reject) =>
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("capture failed"))), "image/jpeg", JPEG_QUALITY),
  );
}

export function capture(video: HTMLVideoElement): Promise<Blob> {
  return toJpeg(video, video.videoWidth, video.videoHeight);
}
