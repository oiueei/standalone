const MAX_PX = 1216;

/**
 * Downscale an image File to fit within `maxPx` on its longest edge, preserving
 * aspect ratio. Returns the original File untouched when it is already small
 * enough (or if it isn't a raster image the browser can decode).
 *
 * Shared by ImageUpload (single) and GalleryUpload (multi) so the client-side
 * resize behaviour stays identical across both.
 */
export function resizeImage(file, maxPx = MAX_PX) {
  return new Promise((resolve) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      if (img.width <= maxPx && img.height <= maxPx) {
        resolve(file);
        return;
      }
      const scale = maxPx / Math.max(img.width, img.height);
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
      canvas.toBlob((blob) => resolve(new File([blob], file.name, { type: file.type })), file.type);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(file);
    };
    img.src = url;
  });
}
