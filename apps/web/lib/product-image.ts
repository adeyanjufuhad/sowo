// Product pictures. A vendor picks a photo from their phone; it is shrunk here, in the browser, before it is sent,
// so a 4 MB camera shot becomes a JPEG of a couple of hundred kilobytes and uploads quickly on mobile data.

/** Where the browser loads a product's picture from. Uploaded pictures are served by the API, through the proxy. */
export function productImageSrc(imageUrl: string | undefined | null): string | null {
  const url = (imageUrl ?? "").trim();
  if (!url) return null;
  return url.startsWith("/product-images/") ? `/api/proxy${url}` : url;
}

const MAX_SIDE = 1000;
const QUALITY = 0.85;

/** The picture, at most 1000 px on its longest side, as base64 JPEG (without the "data:" prefix). */
export async function shrinkImage(file: File): Promise<string> {
  if (!file.type.startsWith("image/")) throw new Error("not an image");
  const bitmap = await createImageBitmap(file); // also turns phone photos the right way up
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(bitmap.width * scale));
  canvas.height = Math.max(1, Math.round(bitmap.height * scale));
  const context = canvas.getContext("2d");
  if (!context) throw new Error("no canvas");
  context.fillStyle = "#fff"; // JPEG has no transparency: see-through PNGs go on white, not black
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", QUALITY));
  if (!blob) throw new Error("couldn't encode");
  const dataUrl = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
  return dataUrl.slice(dataUrl.indexOf(",") + 1);
}
