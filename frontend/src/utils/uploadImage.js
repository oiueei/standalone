import { apiFetch } from '../services/api';
import { resizeImage } from './resizeImage';

/**
 * Resize an image File client-side (≤1216px) and upload it to Cloudinary via a
 * short-lived server-signed signature. Returns the Cloudinary `{ publicId, url }`.
 * Throws on signature/upload failure.
 *
 * Extracted from the inline flow in ImageUpload / GalleryUpload so the CSV/ZIP
 * bulk import can reuse the exact same secure upload path (the server signs every
 * parameter, including the public_id, so the client can't tamper with them).
 */
export async function uploadImageToCloudinary(original, folder = 'oiueei/things') {
  const file = await resizeImage(original);

  const sigRes = await apiFetch('/api/v1/upload/signature/', {
    method: 'POST',
    body: JSON.stringify({ folder }),
  });
  if (!sigRes.ok) throw new Error('signature_failed');
  const {
    signature,
    timestamp,
    api_key,
    cloud_name,
    folder: signedFolder,
    public_id,
    allowed_formats,
    resource_type,
  } = await sigRes.json();

  // Send back exactly the server-signed parameters — changing any of them would
  // break the signature.
  const formData = new FormData();
  formData.append('file', file);
  formData.append('api_key', api_key);
  formData.append('timestamp', String(timestamp));
  formData.append('signature', signature);
  formData.append('folder', signedFolder);
  formData.append('public_id', public_id);
  formData.append('allowed_formats', allowed_formats);

  const uploadRes = await fetch(
    `https://api.cloudinary.com/v1_1/${cloud_name}/${resource_type}/upload`,
    { method: 'POST', body: formData }
  );
  if (!uploadRes.ok) throw new Error('upload_failed');
  const data = await uploadRes.json();
  return { publicId: data.public_id, url: data.secure_url };
}
