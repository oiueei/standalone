import { apiFetch } from '../services/api';

// The collection welcome doc: PDF only, 5 MB. `max_file_size` isn't a signable
// Cloudinary upload parameter (signing it broke every document upload — S3), so
// this client check is the only size cap there is.
export const PDF_MAX_BYTES = 5 * 1024 * 1024;

/**
 * Upload a PDF to Cloudinary through a short-lived server-signed signature —
 * the same secure path as `uploadImageToCloudinary` (the server signs every
 * parameter, including the public_id, so the client can't tamper with them),
 * with `kind: 'document'` so the signature only accepts a PDF. No resize: a
 * document is not a photo. Returns the Cloudinary `{ publicId, url }`.
 */
export async function uploadPdfToCloudinary(file, folder = 'oiueei/documents') {
  const sigRes = await apiFetch('/api/v1/upload/signature/', {
    method: 'POST',
    body: JSON.stringify({ folder, kind: 'document' }),
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

  // A PDF is a page-based image to Cloudinary, so it uploads (and is delivered)
  // under resource_type=image like every other asset.
  const uploadRes = await fetch(
    `https://api.cloudinary.com/v1_1/${cloud_name}/${resource_type}/upload`,
    { method: 'POST', body: formData }
  );
  if (!uploadRes.ok) throw new Error('upload_failed');
  const data = await uploadRes.json();
  return { publicId: data.public_id, url: data.secure_url };
}
