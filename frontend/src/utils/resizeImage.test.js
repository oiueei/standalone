import { describe, test, expect, beforeEach, afterEach, vi } from 'vitest';
import { resizeImage } from './resizeImage';

// jsdom decodes no images and implements no canvas, so both are stubbed here and
// only the scaling maths + File plumbing are actually under test.
let canvases;

function stubImage({ width, height, fail = false }) {
  class FakeImage {
    constructor() {
      this.width = width;
      this.height = height;
    }
    set src(value) {
      this._src = value;
      // A real decode never resolves on the setter's own stack.
      queueMicrotask(() => (fail ? this.onerror() : this.onload()));
    }
    get src() {
      return this._src;
    }
  }
  vi.stubGlobal('Image', FakeImage);
}

const jpeg = () => new File(['bytes'], 'photo.jpg', { type: 'image/jpeg' });

beforeEach(() => {
  canvases = [];
  URL.createObjectURL = vi.fn(() => 'blob:mock-url');
  URL.revokeObjectURL = vi.fn();
  const realCreateElement = document.createElement.bind(document);
  vi.spyOn(document, 'createElement').mockImplementation((tag, ...rest) => {
    if (tag !== 'canvas') return realCreateElement(tag, ...rest);
    const canvas = {
      width: 0,
      height: 0,
      getContext: vi.fn(() => ({ drawImage: vi.fn() })),
      toBlob: vi.fn((cb, type) => cb(new Blob(['resized'], { type }))),
    };
    canvases.push(canvas);
    return canvas;
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  delete URL.createObjectURL;
  delete URL.revokeObjectURL;
});

describe('resizeImage', () => {
  test('passes a small image through as the very same File', async () => {
    stubImage({ width: 800, height: 600 });
    const file = jpeg();

    await expect(resizeImage(file)).resolves.toBe(file);
    expect(canvases).toHaveLength(0);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
  });

  test('an image exactly at the cap is still a pass-through', async () => {
    stubImage({ width: 1216, height: 1216 });
    const file = jpeg();

    await expect(resizeImage(file)).resolves.toBe(file);
    expect(canvases).toHaveLength(0);
  });

  test('scales a landscape image to 1216 on its longest side, keeping the ratio', async () => {
    stubImage({ width: 2432, height: 1216 });

    const out = await resizeImage(jpeg());

    expect(canvases[0]).toMatchObject({ width: 1216, height: 608 });
    expect(out).toBeInstanceOf(File);
    expect(out.name).toBe('photo.jpg');
    expect(out.type).toBe('image/jpeg');
  });

  test('caps a portrait image on its height instead', async () => {
    stubImage({ width: 1000, height: 4000 });

    await resizeImage(jpeg());

    expect(canvases[0]).toMatchObject({ width: 304, height: 1216 });
  });

  test('honours a caller-supplied maxPx', async () => {
    stubImage({ width: 1000, height: 500 });

    await resizeImage(jpeg(), 500);

    expect(canvases[0]).toMatchObject({ width: 500, height: 250 });
  });

  // Anything the browser can't decode (a PDF picked by mistake, a corrupt file)
  // must come back untouched rather than reject — the caller uploads it as-is.
  test('returns the original when the browser cannot decode it', async () => {
    stubImage({ width: 0, height: 0, fail: true });
    const file = new File(['%PDF-1.4'], 'not-a-photo.pdf', { type: 'application/pdf' });

    await expect(resizeImage(file)).resolves.toBe(file);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
  });
});
