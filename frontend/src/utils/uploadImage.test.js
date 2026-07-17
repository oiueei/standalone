import { describe, test, expect, beforeEach, afterEach, vi } from 'vitest';

vi.mock('../services/api', () => ({ apiFetch: vi.fn() }));
// The scaling itself is covered by resizeImage.test.js; here it only has to run
// first and hand its output to the upload.
vi.mock('./resizeImage', () => ({ resizeImage: vi.fn() }));

import { apiFetch } from '../services/api';
import { resizeImage } from './resizeImage';
import { uploadImageToCloudinary } from './uploadImage';

// What the server signs (core/views/upload.py): every parameter, including the
// public_id and the folder, so the client can only echo them back.
const SIGNATURE = {
  signature: 'sig-abc',
  timestamp: 1720000000,
  api_key: 'key-123',
  cloud_name: 'demo-cloud',
  folder: 'oiueei/things',
  public_id: 'oiueei/things/server-generated',
  allowed_formats: 'jpg,jpeg,png,webp,gif,heic,heif,avif,bmp,tif,tiff',
  resource_type: 'image',
};

const UPLOADED = {
  public_id: 'oiueei/things/server-generated',
  secure_url: 'https://res.cloudinary.com/demo-cloud/image/upload/v1/server-generated.jpg',
};

function jsonResponse(data, ok = true) {
  return { ok, status: ok ? 200 : 400, json: () => Promise.resolve(data) };
}

const photo = () => new File(['original bytes'], 'photo.jpg', { type: 'image/jpeg' });

let fetchMock;
let resized;

beforeEach(() => {
  vi.clearAllMocks();
  resized = new File(['smaller bytes'], 'photo.jpg', { type: 'image/jpeg' });
  resizeImage.mockResolvedValue(resized);
  apiFetch.mockResolvedValue(jsonResponse(SIGNATURE));
  fetchMock = vi.fn(() => Promise.resolve(jsonResponse(UPLOADED)));
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('uploadImageToCloudinary', () => {
  test('resizes first, then uploads the resized file with the signed parameters', async () => {
    const original = photo();

    const result = await uploadImageToCloudinary(original);

    expect(resizeImage).toHaveBeenCalledWith(original);
    expect(apiFetch).toHaveBeenCalledWith('/api/v1/upload/signature/', {
      method: 'POST',
      body: JSON.stringify({ folder: 'oiueei/things' }),
    });

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe('https://api.cloudinary.com/v1_1/demo-cloud/image/upload');
    expect(options.method).toBe('POST');

    // What goes up is the resize output, never the original.
    const sent = options.body;
    expect(sent.get('file')).toBe(resized);
    // Every signed parameter is echoed back verbatim — changing any breaks the
    // signature, so this is the contract with the server.
    expect(sent.get('api_key')).toBe('key-123');
    expect(sent.get('timestamp')).toBe('1720000000');
    expect(sent.get('signature')).toBe('sig-abc');
    expect(sent.get('folder')).toBe('oiueei/things');
    expect(sent.get('public_id')).toBe('oiueei/things/server-generated');
    expect(sent.get('allowed_formats')).toBe(SIGNATURE.allowed_formats);

    expect(result).toEqual({ publicId: UPLOADED.public_id, url: UPLOADED.secure_url });
  });

  test('asks for a signature on the caller-chosen folder', async () => {
    await uploadImageToCloudinary(photo(), 'oiueei/users');

    expect(apiFetch).toHaveBeenCalledWith('/api/v1/upload/signature/', {
      method: 'POST',
      body: JSON.stringify({ folder: 'oiueei/users' }),
    });
  });

  test('throws signature_failed and uploads nothing when the server refuses to sign', async () => {
    apiFetch.mockResolvedValue(jsonResponse({ detail: 'no' }, false));

    await expect(uploadImageToCloudinary(photo())).rejects.toThrow('signature_failed');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test('throws upload_failed when Cloudinary rejects the upload', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ error: 'nope' }, false));

    await expect(uploadImageToCloudinary(photo())).rejects.toThrow('upload_failed');
  });
});
