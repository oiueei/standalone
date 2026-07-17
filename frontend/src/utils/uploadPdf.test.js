import { describe, test, expect, beforeEach, afterEach, vi } from 'vitest';

vi.mock('../services/api', () => ({ apiFetch: vi.fn() }));

import { apiFetch } from '../services/api';
import { uploadPdfToCloudinary, PDF_MAX_BYTES } from './uploadPdf';

// Document-mode signature (core/views/upload.py): the folder is forced server-side
// and allowed_formats narrows to pdf alone.
const SIGNATURE = {
  signature: 'sig-doc',
  timestamp: 1720000000,
  api_key: 'key-123',
  cloud_name: 'demo-cloud',
  folder: 'oiueei/documents',
  public_id: 'oiueei/documents/server-generated',
  allowed_formats: 'pdf',
  resource_type: 'image',
};

const UPLOADED = {
  public_id: 'oiueei/documents/server-generated',
  secure_url: 'https://res.cloudinary.com/demo-cloud/image/upload/v1/welcome.pdf',
};

function jsonResponse(data, ok = true) {
  return { ok, status: ok ? 200 : 400, json: () => Promise.resolve(data) };
}

const pdf = () => new File(['%PDF-1.4'], 'welcome.pdf', { type: 'application/pdf' });

let fetchMock;

beforeEach(() => {
  vi.clearAllMocks();
  apiFetch.mockResolvedValue(jsonResponse(SIGNATURE));
  fetchMock = vi.fn(() => Promise.resolve(jsonResponse(UPLOADED)));
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('uploadPdfToCloudinary', () => {
  // max_file_size isn't signable, so this constant is the only size cap that
  // exists anywhere — PdfUpload is what enforces it.
  test('PDF_MAX_BYTES is 5 MB', () => {
    expect(PDF_MAX_BYTES).toBe(5 * 1024 * 1024);
  });

  test('asks for a document-kind signature and uploads with the signed parameters', async () => {
    const result = await uploadPdfToCloudinary(pdf());

    expect(apiFetch).toHaveBeenCalledWith('/api/v1/upload/signature/', {
      method: 'POST',
      body: JSON.stringify({ folder: 'oiueei/documents', kind: 'document' }),
    });

    const [url, options] = fetchMock.mock.calls[0];
    // A PDF is a page-based image to Cloudinary, so it rides the signed
    // resource_type (image) like every other asset — not a raw/document type.
    expect(url).toBe('https://api.cloudinary.com/v1_1/demo-cloud/image/upload');
    expect(options.method).toBe('POST');

    const sent = options.body;
    expect(sent.get('file').name).toBe('welcome.pdf');
    expect(sent.get('api_key')).toBe('key-123');
    expect(sent.get('timestamp')).toBe('1720000000');
    expect(sent.get('signature')).toBe('sig-doc');
    expect(sent.get('folder')).toBe('oiueei/documents');
    expect(sent.get('public_id')).toBe('oiueei/documents/server-generated');
    expect(sent.get('allowed_formats')).toBe('pdf');

    expect(result).toEqual({ publicId: UPLOADED.public_id, url: UPLOADED.secure_url });
  });

  test('asks for a signature on the caller-chosen folder', async () => {
    await uploadPdfToCloudinary(pdf(), 'oiueei/things');

    expect(apiFetch).toHaveBeenCalledWith('/api/v1/upload/signature/', {
      method: 'POST',
      body: JSON.stringify({ folder: 'oiueei/things', kind: 'document' }),
    });
  });

  test('throws signature_failed and uploads nothing when the server refuses to sign', async () => {
    apiFetch.mockResolvedValue(jsonResponse({ detail: 'no' }, false));

    await expect(uploadPdfToCloudinary(pdf())).rejects.toThrow('signature_failed');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test('throws upload_failed when Cloudinary rejects the upload', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ error: 'nope' }, false));

    await expect(uploadPdfToCloudinary(pdf())).rejects.toThrow('upload_failed');
  });
});
