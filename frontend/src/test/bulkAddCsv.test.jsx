import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import JSZip from 'jszip';

vi.mock('../services/api', () => ({ apiFetch: vi.fn() }));
// The signed Cloudinary path is covered in src/utils/uploadImage.test.js; here it
// only has to receive the right File and hand back a public_id.
vi.mock('../utils/uploadImage', () => ({ uploadImageToCloudinary: vi.fn() }));

import { apiFetch } from '../services/api';
import { uploadImageToCloudinary } from '../utils/uploadImage';
import BulkAddCsv from '../components/BulkAddCsv';

const fileInput = (container) => container.querySelector('input[type="file"]');
const pick = (container, file) => fireEvent.change(fileInput(container), { target: { files: [file] } });

const csvFile = (text) => new File([text], 'things.csv', { type: 'text/csv' });

// A real ZIP, built here rather than mocked: the component's own JSZip read is
// half of what the ZIP path does.
async function zipFile(entries) {
  const zip = new JSZip();
  for (const [name, content] of Object.entries(entries)) zip.file(name, content);
  const blob = await zip.generateAsync({ type: 'blob' });
  return new File([blob], 'things.zip', { type: 'application/zip' });
}

function jsonResponse(data, ok = true, status = ok ? 200 : 400) {
  return { ok, status, json: () => Promise.resolve(data) };
}

const renderBulkAdd = (onImported = vi.fn()) => ({
  onImported,
  ...render(<BulkAddCsv collectionCode="COL001" onImported={onImported} />),
});

beforeEach(() => {
  vi.clearAllMocks();
  apiFetch.mockResolvedValue(jsonResponse({ created: 0 }));
});

describe('BulkAddCsv — plain CSV', () => {
  test('parses, previews, and imports the mapped rows', async () => {
    apiFetch.mockResolvedValue(jsonResponse({ created: 2 }));
    const { container, onImported } = renderBulkAdd();

    pick(container, csvFile('headline,type,fee\nCazo de acero,RENT_THING,1\nSartén,SELL_THING,3'));

    expect(await screen.findByText('Preview (2)')).toBeInTheDocument();
    expect(screen.getByText('Cazo de acero — Rental · 1')).toBeInTheDocument();
    expect(screen.getByText('Sartén — Sale · 3')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Add 2 items'));

    await waitFor(() => expect(onImported).toHaveBeenCalledWith(2));
    expect(apiFetch).toHaveBeenCalledWith('/api/v1/collections/COL001/things/bulk/', {
      method: 'POST',
      body: JSON.stringify({
        rows: [
          { type: 'RENT_THING', headline: 'Cazo de acero', fee: '1' },
          { type: 'SELL_THING', headline: 'Sartén', fee: '3' },
        ],
      }),
    });
  });

  test('a tags cell is split on the pipe and previewed', async () => {
    const { container } = renderBulkAdd();

    pick(container, csvFile('headline,tags\nCazo,Cocina|Vintage'));

    expect(await screen.findByText('Cazo · Cocina, Vintage')).toBeInTheDocument();
  });
});

// Client-side guards. Each must stop the import before any request goes out.
describe('BulkAddCsv — guards', () => {
  test('refuses more than 100 rows', async () => {
    const { container } = renderBulkAdd();
    const rows = Array.from({ length: 101 }, (_, i) => `Thing ${i}`).join('\n');

    pick(container, csvFile(`headline\n${rows}`));

    expect(await screen.findByText('You can import up to 100 items at once.')).toBeInTheDocument();
    expect(screen.queryByText(/^Preview/)).toBeNull();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  test('refuses a row with no headline', async () => {
    const { container } = renderBulkAdd();

    pick(container, csvFile('headline,type\nCazo,GIFT_THING\n,SELL_THING'));

    expect(await screen.findByText('Every row needs a headline.')).toBeInTheDocument();
    expect(screen.queryByText(/^Preview/)).toBeNull();
  });

  test('refuses an empty file', async () => {
    const { container } = renderBulkAdd();

    pick(container, csvFile('headline\n'));

    expect(await screen.findByText('No rows found in that file.')).toBeInTheDocument();
  });
});

describe('BulkAddCsv — ZIP', () => {
  test('uploads each referenced photo and sends its public_id as the thumbnail', async () => {
    uploadImageToCloudinary.mockResolvedValue({ publicId: 'oiueei/things/cazo' });
    apiFetch.mockResolvedValue(jsonResponse({ created: 1 }));
    const { container, onImported } = renderBulkAdd();

    pick(container, await zipFile({ 'things.csv': 'headline,photo\nCazo,cazo.jpg', 'cazo.jpg': 'fake-jpeg-bytes' }));

    expect(await screen.findByText('Preview (1)')).toBeInTheDocument();
    expect(screen.getByText('Cazo · 📷 cazo.jpg')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Add 1 items'));

    await waitFor(() => expect(onImported).toHaveBeenCalledWith(1));

    // The photo travels the same signed upload path as any other image.
    expect(uploadImageToCloudinary).toHaveBeenCalledTimes(1);
    const [uploaded, folder] = uploadImageToCloudinary.mock.calls[0];
    expect(uploaded.name).toBe('cazo.jpg');
    expect(uploaded.type).toBe('image/jpeg');
    expect(folder).toBe('oiueei/things');

    // The filename is swapped for the public_id Cloudinary returned.
    expect(apiFetch).toHaveBeenCalledWith('/api/v1/collections/COL001/things/bulk/', {
      method: 'POST',
      body: JSON.stringify({ rows: [{ headline: 'Cazo', thumbnail: 'oiueei/things/cazo' }] }),
    });
  });

  test('refuses a ZIP whose CSV names a photo the ZIP does not carry', async () => {
    const { container } = renderBulkAdd();

    pick(container, await zipFile({ 'things.csv': 'headline,photo\nCazo,cazo.jpg' }));

    expect(
      await screen.findByText('These photos are named in the CSV but missing from the ZIP: cazo.jpg')
    ).toBeInTheDocument();
    expect(screen.queryByText(/^Preview/)).toBeNull();
  });

  test('refuses a ZIP with no CSV in it', async () => {
    const { container } = renderBulkAdd();

    pick(container, await zipFile({ 'cazo.jpg': 'fake-jpeg-bytes' }));

    expect(await screen.findByText('The ZIP must contain a CSV file.')).toBeInTheDocument();
  });

  test('a failed photo upload stops the import and says so', async () => {
    uploadImageToCloudinary.mockRejectedValue(new Error('upload_failed'));
    const { container, onImported } = renderBulkAdd();

    pick(container, await zipFile({ 'things.csv': 'headline,photo\nCazo,cazo.jpg', 'cazo.jpg': 'fake-jpeg-bytes' }));
    fireEvent.click(await screen.findByText('Add 1 items'));

    expect(
      await screen.findByText("Some photos couldn't be uploaded. Check the images and try again.")
    ).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
    expect(onImported).not.toHaveBeenCalled();
  });
});

// The import is atomic server-side, so a rejection means nothing was created —
// the user has to be told which rows to fix.
describe('BulkAddCsv — server rejections', () => {
  test('surfaces the error detail from a 400', async () => {
    apiFetch.mockResolvedValue(jsonResponse({ error: 'Tag "Cocina" is not in this collection.' }, false));
    const { container, onImported } = renderBulkAdd();

    pick(container, csvFile('headline\nCazo'));
    fireEvent.click(await screen.findByText('Add 1 items'));

    expect(await screen.findByText('Tag "Cocina" is not in this collection.')).toBeInTheDocument();
    expect(onImported).not.toHaveBeenCalled();
  });

  test('names the offending rows, numbered as the preview shows them', async () => {
    apiFetch.mockResolvedValue(jsonResponse({ errors: [{ row: 0 }, { row: 2 }] }, false));
    const { container } = renderBulkAdd();

    pick(container, csvFile('headline\nCazo\nSartén\nOlla'));
    fireEvent.click(await screen.findByText('Add 3 items'));

    // The server counts rows from 0, the preview list from 1.
    expect(
      await screen.findByText("These rows couldn't be imported (check their columns): 1, 3")
    ).toBeInTheDocument();
  });

  test('surfaces a rate limit', async () => {
    apiFetch.mockResolvedValue(jsonResponse({}, false, 429));
    const { container } = renderBulkAdd();

    pick(container, csvFile('headline\nCazo'));
    fireEvent.click(await screen.findByText('Add 1 items'));

    expect(
      await screen.findByText('Too many attempts — please wait a moment and try again.')
    ).toBeInTheDocument();
  });

  test('surfaces a dropped connection', async () => {
    apiFetch.mockRejectedValue(new Error('network down'));
    const { container } = renderBulkAdd();

    pick(container, csvFile('headline\nCazo'));
    fireEvent.click(await screen.findByText('Add 1 items'));

    expect(await screen.findByText('Connection error.')).toBeInTheDocument();
  });
});
