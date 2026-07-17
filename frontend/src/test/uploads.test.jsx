import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

// The Cloudinary helpers are unit-tested next to themselves (src/utils/upload*.test.js);
// here they are mocked so no test ever touches the network.
vi.mock('../utils/uploadImage', () => ({ uploadImageToCloudinary: vi.fn() }));
vi.mock('../utils/uploadPdf', async (importOriginal) => ({
  ...(await importOriginal()),
  uploadPdfToCloudinary: vi.fn(),
}));

import { uploadImageToCloudinary } from '../utils/uploadImage';
import { uploadPdfToCloudinary, PDF_MAX_BYTES } from '../utils/uploadPdf';
import ImageUpload from '../components/ImageUpload';
import PdfUpload from '../components/PdfUpload';
import GalleryUpload from '../components/GalleryUpload';

// HDS FileInput hides a real <input type="file"> behind its own button, and
// validates `accept` against the File's name/type before calling onChange — so
// the fixtures below must look like the real thing.
const fileInput = (container) => container.querySelector('input[type="file"]');
const pick = (container, ...files) => fireEvent.change(fileInput(container), { target: { files } });

const photo = (name = 'photo.jpg') => new File(['bytes'], name, { type: 'image/jpeg' });

function pdf(size = 1024) {
  const file = new File(['%PDF-1.4'], 'welcome.pdf', { type: 'application/pdf' });
  // Faking the size beats allocating 5 MB of test data to cross the cap.
  Object.defineProperty(file, 'size', { value: size });
  return file;
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ════════════════════════════════════════════════════════════════════════
// ImageUpload — the single-image surface (thing thumbnail, profile photo)
// ════════════════════════════════════════════════════════════════════════
describe('ImageUpload', () => {
  test('a picked image is uploaded, previewed, and its public_id reported', async () => {
    uploadImageToCloudinary.mockResolvedValue({
      publicId: 'oiueei/things/abc',
      url: 'https://res.cloudinary.com/demo/abc.jpg',
    });
    const onChange = vi.fn();
    const { container } = render(
      <ImageUpload id="thumb" label="Thumbnail" onChange={onChange} folder="oiueei/things" />
    );

    pick(container, photo());

    await waitFor(() => expect(onChange).toHaveBeenCalledWith('oiueei/things/abc'));
    expect(uploadImageToCloudinary).toHaveBeenCalledWith(expect.any(File), 'oiueei/things');

    const preview = await screen.findByAltText('Image preview');
    expect(preview).toHaveAttribute('src', 'https://res.cloudinary.com/demo/abc.jpg');
    // The picker gives way to the preview — you replace by removing first.
    expect(fileInput(container)).toBeNull();
  });

  test('an already-saved image previews without any upload', () => {
    const { container } = render(
      <ImageUpload
        id="thumb"
        label="Thumbnail"
        onChange={vi.fn()}
        currentUrl="https://res.cloudinary.com/demo/saved.jpg"
      />
    );

    expect(screen.getByAltText('Image preview')).toHaveAttribute(
      'src',
      'https://res.cloudinary.com/demo/saved.jpg'
    );
    expect(uploadImageToCloudinary).not.toHaveBeenCalled();
    expect(fileInput(container)).toBeNull();
  });

  test('Remove clears the value and brings the picker back', () => {
    const onChange = vi.fn();
    const { container } = render(
      <ImageUpload
        id="thumb"
        label="Thumbnail"
        onChange={onChange}
        currentUrl="https://res.cloudinary.com/demo/saved.jpg"
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Remove' }));

    expect(onChange).toHaveBeenCalledWith('');
    expect(screen.queryByAltText('Image preview')).toBeNull();
    expect(fileInput(container)).not.toBeNull();
  });

  test('a failed upload shows the error and reports no value', async () => {
    uploadImageToCloudinary.mockRejectedValue(new Error('upload_failed'));
    const onChange = vi.fn();
    const { container } = render(<ImageUpload id="thumb" label="Thumbnail" onChange={onChange} />);

    pick(container, photo());

    expect(await screen.findByText('Upload failed. Please try again.')).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.queryByAltText('Image preview')).toBeNull();
  });
});

// ════════════════════════════════════════════════════════════════════════
// PdfUpload — the collection welcome document
// ════════════════════════════════════════════════════════════════════════
describe('PdfUpload', () => {
  test('offers a .pdf-only picker with the generic add-file label', () => {
    const { container } = render(<PdfUpload id="doc" label="Welcome document" onChange={vi.fn()} />);

    expect(fileInput(container)).toHaveAttribute('accept', '.pdf,application/pdf');
    // A document is not an image: the label must not be the photo one.
    expect(screen.getByText('Add file')).toBeInTheDocument();
    expect(screen.queryByText('Add a file')).toBeNull();
  });

  // THE size guard: `max_file_size` is not a signable Cloudinary parameter, so
  // this client check is the only cap on the welcome doc anywhere in the system.
  test('a file over 5 MB is refused inline and never uploaded', async () => {
    const onChange = vi.fn();
    const { container } = render(
      <PdfUpload id="doc" label="Welcome document" onChange={onChange} />
    );

    pick(container, pdf(PDF_MAX_BYTES + 1));

    expect(await screen.findByText('The file is too large (max 5 MB).')).toBeInTheDocument();
    expect(uploadPdfToCloudinary).not.toHaveBeenCalled();
    expect(onChange).not.toHaveBeenCalled();
  });

  test('a file exactly at the cap is accepted', async () => {
    uploadPdfToCloudinary.mockResolvedValue({
      publicId: 'oiueei/documents/abc',
      url: 'https://res.cloudinary.com/demo/abc.pdf',
    });
    const onChange = vi.fn();
    const { container } = render(
      <PdfUpload id="doc" label="Welcome document" onChange={onChange} />
    );

    pick(container, pdf(PDF_MAX_BYTES));

    await waitFor(() => expect(onChange).toHaveBeenCalledWith('oiueei/documents/abc'));
    expect(uploadPdfToCloudinary).toHaveBeenCalledWith(expect.any(File), 'oiueei/documents');
    expect(screen.getByRole('link', { name: 'View the document' })).toBeInTheDocument();
  });

  test('a saved document shows the view link, and Remove clears it', () => {
    const onChange = vi.fn();
    const { container } = render(
      <PdfUpload
        id="doc"
        label="Welcome document"
        onChange={onChange}
        currentUrl="https://res.cloudinary.com/demo/welcome.pdf"
      />
    );

    expect(screen.getByRole('link', { name: 'View the document' })).toHaveAttribute(
      'href',
      'https://res.cloudinary.com/demo/welcome.pdf'
    );
    expect(fileInput(container)).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Remove' }));

    expect(onChange).toHaveBeenCalledWith('');
    expect(screen.queryByRole('link', { name: 'View the document' })).toBeNull();
    expect(fileInput(container)).not.toBeNull();
  });

  test('a failed upload shows the error and reports no value', async () => {
    uploadPdfToCloudinary.mockRejectedValue(new Error('upload_failed'));
    const onChange = vi.fn();
    const { container } = render(
      <PdfUpload id="doc" label="Welcome document" onChange={onChange} />
    );

    pick(container, pdf());

    expect(await screen.findByText('Upload failed. Please try again.')).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });
});

// ════════════════════════════════════════════════════════════════════════
// GalleryUpload — a thing's extra photos, max 8
// ════════════════════════════════════════════════════════════════════════
describe('GalleryUpload', () => {
  const item = (n) => ({ publicId: `p${n}`, url: `https://res.cloudinary.com/demo/p${n}.jpg` });

  test('an added photo is appended to the existing items', async () => {
    uploadImageToCloudinary.mockResolvedValue({
      publicId: 'p2',
      url: 'https://res.cloudinary.com/demo/p2.jpg',
    });
    const onChange = vi.fn();
    const { container } = render(<GalleryUpload items={[item(1)]} onChange={onChange} />);

    pick(container, photo());

    await waitFor(() => expect(onChange).toHaveBeenCalledWith([item(1), item(2)]));
    expect(uploadImageToCloudinary).toHaveBeenCalledWith(expect.any(File), 'oiueei/things');
  });

  test('removing a thumbnail reports the list without it', () => {
    const onChange = vi.fn();
    render(<GalleryUpload items={[item(1), item(2)]} onChange={onChange} />);

    fireEvent.click(screen.getAllByRole('button', { name: 'Remove' })[0]);

    expect(onChange).toHaveBeenCalledWith([item(2)]);
  });

  test('at 8 photos the picker is disabled and says why', () => {
    const items = Array.from({ length: 8 }, (_, i) => item(i));
    const { container } = render(<GalleryUpload items={items} onChange={vi.fn()} />);

    expect(fileInput(container)).toBeDisabled();
    expect(screen.getByText('Maximum 8 photos.')).toBeInTheDocument();
  });

  // Selecting more than fits keeps what fits rather than dropping the lot.
  test('a selection over the cap uploads only what fits and flags the cap', async () => {
    uploadImageToCloudinary.mockResolvedValue({
      publicId: 'p8',
      url: 'https://res.cloudinary.com/demo/p8.jpg',
    });
    const items = Array.from({ length: 7 }, (_, i) => item(i));
    const onChange = vi.fn();
    const { container } = render(<GalleryUpload items={items} onChange={onChange} />);

    pick(container, photo('a.jpg'), photo('b.jpg'), photo('c.jpg'));

    await waitFor(() => expect(onChange).toHaveBeenCalledWith([...items, item(8)]));
    expect(uploadImageToCloudinary).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('Maximum 8 photos.')).toBeInTheDocument();
  });

  // The loop is not atomic: whatever uploaded before the failure is kept, so the
  // user doesn't lose good photos to one bad one.
  test('a mid-batch failure keeps the photos that made it and shows the error', async () => {
    uploadImageToCloudinary
      .mockResolvedValueOnce({ publicId: 'p1', url: 'https://res.cloudinary.com/demo/p1.jpg' })
      .mockRejectedValueOnce(new Error('upload_failed'));
    const onChange = vi.fn();
    const { container } = render(<GalleryUpload items={[]} onChange={onChange} />);

    pick(container, photo('a.jpg'), photo('b.jpg'));

    expect(await screen.findByText('Upload failed. Please try again.')).toBeInTheDocument();
    expect(onChange).toHaveBeenCalledWith([item(1)]);
  });

  test('a single failed upload reports nothing', async () => {
    uploadImageToCloudinary.mockRejectedValue(new Error('upload_failed'));
    const onChange = vi.fn();
    const { container } = render(<GalleryUpload items={[]} onChange={onChange} />);

    pick(container, photo());

    expect(await screen.findByText('Upload failed. Please try again.')).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });
});
