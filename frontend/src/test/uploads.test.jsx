import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

// The upload helpers are unit-tested next to themselves (src/utils/upload*.test.js);
// here they are mocked so no test ever touches the network.
// Same shape as the uploadPdf mock below: stub the function, keep the real
// `UploadTooLargeError` and `IMAGE_MAX_BYTES`. The components branch on that
// class, so a bare factory leaves it undefined and every failure path throws
// inside its own catch.
vi.mock('../utils/uploadImage', async (importOriginal) => ({
  ...(await importOriginal()),
  uploadImage: vi.fn(),
}));
vi.mock('../utils/uploadPdf', async (importOriginal) => ({
  ...(await importOriginal()),
  uploadPdf: vi.fn(),
}));

import { uploadImage, UploadRateLimitedError, UploadTooLargeError } from '../utils/uploadImage';
import { uploadPdf, PDF_MAX_BYTES } from '../utils/uploadPdf';
import ImageUpload from '../components/ImageUpload';
import PdfUpload from '../components/PdfUpload';
import en from '../i18n/locales/en.json';
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
    uploadImage.mockResolvedValue({
      publicId: 'oiueei/things/abc',
      url: 'https://bucket.your-domain.test/abc.jpg',
    });
    const onChange = vi.fn();
    const { container } = render(
      <ImageUpload id="thumb" label="Thumbnail" onChange={onChange} folder="oiueei/things" />
    );

    pick(container, photo());

    await waitFor(() => expect(onChange).toHaveBeenCalledWith('oiueei/things/abc'));
    expect(uploadImage).toHaveBeenCalledWith(expect.any(File), 'oiueei/things');

    const preview = await screen.findByAltText('Image preview');
    expect(preview).toHaveAttribute('src', 'https://bucket.your-domain.test/abc.jpg');
    // The picker gives way to the preview — you replace by removing first.
    expect(fileInput(container)).toBeNull();
  });

  test('an already-saved image previews without any upload', () => {
    const { container } = render(
      <ImageUpload
        id="thumb"
        label="Thumbnail"
        onChange={vi.fn()}
        currentUrl="https://bucket.your-domain.test/saved.jpg"
      />
    );

    expect(screen.getByAltText('Image preview')).toHaveAttribute(
      'src',
      'https://bucket.your-domain.test/saved.jpg'
    );
    expect(uploadImage).not.toHaveBeenCalled();
    expect(fileInput(container)).toBeNull();
  });

  test('Remove clears the value and brings the picker back', () => {
    const onChange = vi.fn();
    const { container } = render(
      <ImageUpload
        id="thumb"
        label="Thumbnail"
        onChange={onChange}
        currentUrl="https://bucket.your-domain.test/saved.jpg"
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Remove' }));

    expect(onChange).toHaveBeenCalledWith('');
    expect(screen.queryByAltText('Image preview')).toBeNull();
    expect(fileInput(container)).not.toBeNull();
  });

  test('a new saved image replaces the one on screen', async () => {
    // The parent loads its data *after* this mounts, and can load a different
    // thing later, so the preview follows `currentUrl` when it changes — but not
    // over an upload or a removal this component owns, which is the whole reason
    // the preview is state and not the prop.
    const { rerender } = render(
      <ImageUpload id="thumb" label="Thumbnail" onChange={vi.fn()} currentUrl="" />
    );
    expect(screen.queryByAltText('Image preview')).toBeNull();

    rerender(
      <ImageUpload
        id="thumb"
        label="Thumbnail"
        onChange={vi.fn()}
        currentUrl="https://bucket.your-domain.test/first.jpg"
      />
    );
    expect(screen.getByAltText('Image preview')).toHaveAttribute(
      'src',
      'https://bucket.your-domain.test/first.jpg'
    );

    rerender(
      <ImageUpload
        id="thumb"
        label="Thumbnail"
        onChange={vi.fn()}
        currentUrl="https://bucket.your-domain.test/second.jpg"
      />
    );
    expect(screen.getByAltText('Image preview')).toHaveAttribute(
      'src',
      'https://bucket.your-domain.test/second.jpg'
    );
  });

  test('a re-render with the same saved image does not undo a removal', async () => {
    // The parent re-renders for its own reasons — a sibling field changing, a
    // toast opening — and each one must not put back the photo the owner just
    // took off, which is exactly what re-reading the prop every render would do.
    const props = {
      id: 'thumb',
      label: 'Thumbnail',
      onChange: vi.fn(),
      currentUrl: 'https://bucket.your-domain.test/saved.jpg',
    };
    const { rerender, container } = render(<ImageUpload {...props} />);

    fireEvent.click(screen.getByRole('button', { name: 'Remove' }));
    rerender(<ImageUpload {...props} />);

    expect(screen.queryByAltText('Image preview')).toBeNull();
    expect(fileInput(container)).not.toBeNull();
  });

  test('a failed upload shows the error and reports no value', async () => {
    uploadImage.mockRejectedValue(new Error('upload_failed'));
    const onChange = vi.fn();
    const { container } = render(<ImageUpload id="thumb" label="Thumbnail" onChange={onChange} />);

    pick(container, photo());

    expect(await screen.findByText('Upload failed. Please try again.')).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.queryByAltText('Image preview')).toBeNull();
  });

  test('an oversized image says so, rather than "upload failed"', async () => {
    // The whole difference this makes: one of these two is something the person
    // can act on, and telling them apart is why `uploadImage` throws a class
    // and not a string. `PdfUpload` has always done this; the image path met the
    // server's cap with a shrug.
    uploadImage.mockRejectedValue(new UploadTooLargeError());
    const onChange = vi.fn();
    const { container } = render(<ImageUpload id="thumb" label="Thumbnail" onChange={onChange} />);

    pick(container, photo());

    expect(await screen.findByText(/The image is too large \(max 10 MB\)/)).toBeInTheDocument();
    expect(screen.queryByText('Upload failed. Please try again.')).toBeNull();
    expect(onChange).not.toHaveBeenCalled();
  });

  test('an hour\'s allowance used up says to wait, rather than "upload failed"', async () => {
    uploadImage.mockRejectedValue(new UploadRateLimitedError());
    const onChange = vi.fn();
    const { container } = render(<ImageUpload id="thumb" label="Thumbnail" onChange={onChange} />);

    pick(container, photo());

    expect(
      await screen.findByText(
        "You've reached the limit of 120 photos an hour. Try again in a while."
      )
    ).toBeInTheDocument();
    expect(screen.queryByText('Upload failed. Please try again.')).toBeNull();
    expect(onChange).not.toHaveBeenCalled();
  });
});

// ════════════════════════════════════════════════════════════════════════
// PdfUpload — the collection welcome document
// ════════════════════════════════════════════════════════════════════════
describe('PdfUpload', () => {
  test('offers a .pdf-only picker with the generic add-file label', () => {
    const { container } = render(
      <PdfUpload id="doc" label="Welcome document" onChange={vi.fn()} />
    );

    expect(fileInput(container)).toHaveAttribute('accept', '.pdf,application/pdf');
    // A document is not an image: the label must not be the photo one.
    expect(screen.getByText(en.upload.addFileGeneric)).toBeInTheDocument();
    expect(screen.queryByText(en.upload.addFile)).toBeNull();
  });

  // The *inline* size guard. It is no longer the only cap — the byte count is
  // signed into the upload ticket and `UploadTicketView` refuses anything over
  // `DOCUMENT_MAX_BYTES`, so a client that skipped this check would be turned
  // away by the bucket. What this protects is the refusal happening *here*:
  // instantly, with a message next to the field, instead of after a round trip.
  // Keep `PDF_MAX_BYTES` and the server's limit equal.
  test('a file over 5 MB is refused inline and never uploaded', async () => {
    const onChange = vi.fn();
    const { container } = render(
      <PdfUpload id="doc" label="Welcome document" onChange={onChange} />
    );

    pick(container, pdf(PDF_MAX_BYTES + 1));

    expect(await screen.findByText('The file is too large (max 5 MB).')).toBeInTheDocument();
    expect(uploadPdf).not.toHaveBeenCalled();
    expect(onChange).not.toHaveBeenCalled();
  });

  test('a file exactly at the cap is accepted', async () => {
    uploadPdf.mockResolvedValue({
      publicId: 'oiueei/documents/abc',
      url: 'https://bucket.your-domain.test/abc.pdf',
    });
    const onChange = vi.fn();
    const { container } = render(
      <PdfUpload id="doc" label="Welcome document" onChange={onChange} />
    );

    pick(container, pdf(PDF_MAX_BYTES));

    await waitFor(() => expect(onChange).toHaveBeenCalledWith('oiueei/documents/abc'));
    expect(uploadPdf).toHaveBeenCalledWith(expect.any(File), 'oiueei/documents');
    expect(screen.getByRole('link', { name: 'View the document' })).toBeInTheDocument();
  });

  test('a ticket refused for the hour says to wait, not that the file is wrong', async () => {
    uploadPdf.mockRejectedValue(new UploadRateLimitedError());
    const onChange = vi.fn();
    const { container } = render(
      <PdfUpload id="doc" label="Welcome document" onChange={onChange} />
    );

    pick(container, pdf(1024));

    expect(
      await screen.findByText(
        "You've reached the limit of 10 documents an hour. Try again in a while."
      )
    ).toBeInTheDocument();
    expect(screen.queryByText('Upload failed. Please try again.')).toBeNull();
    expect(onChange).not.toHaveBeenCalled();
  });

  test('a saved document shows the view link, and Remove clears it', () => {
    const onChange = vi.fn();
    const { container } = render(
      <PdfUpload
        id="doc"
        label="Welcome document"
        onChange={onChange}
        currentUrl="https://bucket.your-domain.test/welcome.pdf"
      />
    );

    expect(screen.getByRole('link', { name: 'View the document' })).toHaveAttribute(
      'href',
      'https://bucket.your-domain.test/welcome.pdf'
    );
    expect(fileInput(container)).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Remove' }));

    expect(onChange).toHaveBeenCalledWith('');
    expect(screen.queryByRole('link', { name: 'View the document' })).toBeNull();
    expect(fileInput(container)).not.toBeNull();
  });

  test('a new saved document replaces the link, and a re-render does not undo a removal', async () => {
    const props = {
      id: 'doc',
      label: 'Welcome document',
      onChange: vi.fn(),
      currentUrl: 'https://bucket.your-domain.test/first.pdf',
    };
    const { rerender } = render(<PdfUpload {...props} />);
    expect(screen.getByRole('link', { name: /view/i })).toHaveAttribute(
      'href',
      'https://bucket.your-domain.test/first.pdf'
    );

    rerender(<PdfUpload {...props} currentUrl="https://bucket.your-domain.test/second.pdf" />);
    expect(screen.getByRole('link', { name: /view/i })).toHaveAttribute(
      'href',
      'https://bucket.your-domain.test/second.pdf'
    );

    fireEvent.click(screen.getByRole('button', { name: 'Remove' }));
    rerender(<PdfUpload {...props} currentUrl="https://bucket.your-domain.test/second.pdf" />);
    expect(screen.queryByRole('link', { name: /view/i })).toBeNull();
  });

  test('a failed upload shows the error and reports no value', async () => {
    uploadPdf.mockRejectedValue(new Error('upload_failed'));
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
  const item = (n) => ({ publicId: `p${n}`, url: `https://bucket.your-domain.test/p${n}.jpg` });

  test('an added photo is appended to the existing items', async () => {
    uploadImage.mockResolvedValue({
      publicId: 'p2',
      url: 'https://bucket.your-domain.test/p2.jpg',
    });
    const onChange = vi.fn();
    const { container } = render(<GalleryUpload items={[item(1)]} onChange={onChange} />);

    pick(container, photo());

    await waitFor(() => expect(onChange).toHaveBeenCalledWith([item(1), item(2)]));
    expect(uploadImage).toHaveBeenCalledWith(expect.any(File), 'oiueei/things');
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
    uploadImage.mockResolvedValue({
      publicId: 'p8',
      url: 'https://bucket.your-domain.test/p8.jpg',
    });
    const items = Array.from({ length: 7 }, (_, i) => item(i));
    const onChange = vi.fn();
    const { container } = render(<GalleryUpload items={items} onChange={onChange} />);

    pick(container, photo('a.jpg'), photo('b.jpg'), photo('c.jpg'));

    await waitFor(() => expect(onChange).toHaveBeenCalledWith([...items, item(8)]));
    expect(uploadImage).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('Maximum 8 photos.')).toBeInTheDocument();
  });

  // The loop is not atomic: whatever uploaded before the failure is kept, so the
  // user doesn't lose good photos to one bad one.
  test('a mid-batch failure keeps the photos that made it and shows the error', async () => {
    uploadImage
      .mockResolvedValueOnce({ publicId: 'p1', url: 'https://bucket.your-domain.test/p1.jpg' })
      .mockRejectedValueOnce(new Error('upload_failed'));
    const onChange = vi.fn();
    const { container } = render(<GalleryUpload items={[]} onChange={onChange} />);

    pick(container, photo('a.jpg'), photo('b.jpg'));

    expect(await screen.findByText('Upload failed. Please try again.')).toBeInTheDocument();
    expect(onChange).toHaveBeenCalledWith([item(1)]);
  });

  test('one oversized photo mid-batch keeps the rest and says which problem it was', async () => {
    // Both halves matter here. The batch is not atomic, so the photos that made
    // it are kept — and the message has to name the size, because that is the
    // one failure the person can fix by picking a different file.
    uploadImage
      .mockResolvedValueOnce({ publicId: 'p1', url: 'https://bucket.your-domain.test/p1.jpg' })
      .mockRejectedValueOnce(new UploadTooLargeError());
    const onChange = vi.fn();
    const { container } = render(<GalleryUpload items={[]} onChange={onChange} />);

    pick(container, photo('a.jpg'), photo('b.jpg'));

    expect(await screen.findByText(/The image is too large \(max 10 MB\)/)).toBeInTheDocument();
    expect(screen.queryByText('Upload failed. Please try again.')).toBeNull();
    expect(onChange).toHaveBeenCalledWith([item(1)]);
  });

  test("the hour's allowance running out mid-batch keeps the photos that made it and says to wait", async () => {
    uploadImage
      .mockResolvedValueOnce({ publicId: 'p1', url: 'https://bucket.your-domain.test/p1.jpg' })
      .mockRejectedValueOnce(new UploadRateLimitedError());
    const onChange = vi.fn();
    const { container } = render(<GalleryUpload items={[]} onChange={onChange} />);

    pick(container, photo('a.jpg'), photo('b.jpg'));

    expect(
      await screen.findByText(
        "You've reached the limit of 120 photos an hour. Try again in a while."
      )
    ).toBeInTheDocument();
    expect(screen.queryByText('Upload failed. Please try again.')).toBeNull();
    expect(onChange).toHaveBeenCalledWith([item(1)]);
  });

  test('a single failed upload reports nothing', async () => {
    uploadImage.mockRejectedValue(new Error('upload_failed'));
    const onChange = vi.fn();
    const { container } = render(<GalleryUpload items={[]} onChange={onChange} />);

    pick(container, photo());

    expect(await screen.findByText('Upload failed. Please try again.')).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });
});
