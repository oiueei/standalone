import { render, screen, fireEvent, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';

window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import { invalidateMe } from '../hooks/useCapabilities';
import RequestSuccess from '../components/request/RequestSuccess';
import declarePalette from './declarePalette';
import { settle } from './settle';

/**
 * After a loan, a rental or a reservation the request page says it went through and
 * offers the way back. When the account is still blank (no name, or neither age nor
 * postal code) it first offers to complete the profile, coming back to the thing after.
 * The account is read from the shared `/auth/me/`; until that answers, and if it never
 * does, the page is what it was.
 */
const BACK = '/library/COL001/things/THG001';

const me = (extra = {}) => ({
  name: 'Lili',
  age_range: 'GEN_X',
  postal_code: '08038',
  language: 'en',
  ...extra,
});

function answerMe(answer) {
  apiFetch.mockImplementation((url) =>
    url === '/api/v1/auth/me/' ? answer() : Promise.resolve({ ok: true, json: () => ({}) })
  );
}
const ok = (data) => () =>
  Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(data) });

function Where() {
  const { pathname, state } = useLocation();
  return (
    <div data-testid="where" data-state={JSON.stringify(state)}>
      {pathname}
    </div>
  );
}

function renderSuccess() {
  return render(
    <MemoryRouter initialEntries={['/request']}>
      <Where />
      <Routes>
        <Route
          path="/request"
          element={
            <RequestSuccess
              isReservation={false}
              headline="Drill"
              bookedWhen=""
              joinedGroup=""
              backPath={BACK}
              backLabel="Neighbourhood library"
            />
          }
        />
        <Route path="*" element={null} />
      </Routes>
    </MemoryRouter>
  );
}

const complete = () => screen.queryByRole('link', { name: 'Complete your profile in 2 minutes' });
const back = () => screen.getByRole('button', { name: 'Back to Neighbourhood library' });

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'MEMB01');
  invalidateMe();
  vi.clearAllMocks();
  declarePalette({
    color_01: 'bus',
    color_02: 'suomenlinna-light',
    color_03: 'copper',
    color_04: 'black',
    color_05: 'white',
    color_06: 'white',
  });
});
afterEach(async () => {
  await settle(apiFetch);
});

describe('the way on after a request', () => {
  test.each([
    ['has no name', me({ name: '' })],
    ['has a name and neither age nor postal code', me({ age_range: '', postal_code: '' })],
  ])('an account that %s is offered to complete the profile', async (_, profile) => {
    answerMe(ok(profile));
    renderSuccess();
    expect(await screen.findByRole('link', { name: 'Complete your profile in 2 minutes' })).toBe(
      complete()
    );
  });

  test.each([
    ['a name and only the age', me({ postal_code: '' })],
    ['a name and only the postal code', me({ age_range: '' })],
    ['everything', me()],
  ])('an account with %s is offered nothing but the way back', async (_, profile) => {
    answerMe(ok(profile));
    renderSuccess();
    await settle(apiFetch);
    expect(complete()).toBeNull();
    expect(back()).toBeInTheDocument();
  });

  // HDS marks full width with a CSS-modules class whose hash changes between builds, so it is
  // read by its stable part ("fullWidth"), as `doorSubmitButtons.test.jsx` does.
  const fullWidth = (button) => [...button.classList].some((name) => /fullWidth/i.test(name));

  test('the profile comes first and primary, the way back second and secondary, stacked at the full width', async () => {
    answerMe(ok(me({ name: '' })));
    renderSuccess();
    const link = await screen.findByRole('link', { name: 'Complete your profile in 2 minutes' });
    const column = link.parentElement;

    // A column of two, whatever the width of the screen: not a row that is only as wide as
    // its text from 768px.
    expect(column).toHaveClass('button-col');
    expect(column).not.toHaveClass('button-row-wide');
    expect(Array.from(column.children)).toEqual([link, back()]);
    expect(link).toHaveClass('button-link--full');
    expect(fullWidth(back())).toBe(true);
    expect(link.style.getPropertyValue('--background-color')).toBe('var(--color-bus)');
    expect(back().style.getPropertyValue('--background-color')).toBe('var(--color-white)');
    expect(within(column).getAllByRole('button')).toHaveLength(1);
  });

  test('with a complete profile the way back is the full-width button it always was', async () => {
    answerMe(ok(me()));
    renderSuccess();
    await settle(apiFetch);

    expect(fullWidth(back())).toBe(true);
    expect(back().parentElement.classList.contains('button-col')).toBe(false);
  });

  test('the link goes to the profile and brings the person back to the thing afterwards', async () => {
    answerMe(ok(me({ name: '' })));
    renderSuccess();
    const link = await screen.findByRole('link', { name: 'Complete your profile in 2 minutes' });
    expect(link).toHaveAttribute('href', '/me/edit');

    fireEvent.click(link);

    expect(screen.getByTestId('where')).toHaveTextContent('/me/edit');
    expect(JSON.parse(screen.getByTestId('where').dataset.state)).toEqual({
      backPath: BACK,
      backLabel: 'Neighbourhood library',
    });
  });

  test('the way back still goes back', async () => {
    answerMe(ok(me({ name: '' })));
    renderSuccess();
    await screen.findByRole('link', { name: 'Complete your profile in 2 minutes' });

    fireEvent.click(back());

    expect(screen.getByTestId('where')).toHaveTextContent(BACK);
  });

  test('nothing is added while /auth/me/ has not answered', async () => {
    let release;
    answerMe(() => new Promise((resolve) => (release = resolve)));
    renderSuccess();

    expect(complete()).toBeNull();
    expect(back()).toBeInTheDocument();
    release({ ok: true, status: 200, json: () => Promise.resolve(me({ name: '' })) });
    expect(await screen.findByRole('link', { name: /Complete your profile/ })).toBeInTheDocument();
  });

  test('nothing is added if /auth/me/ fails, and the way back is untouched', async () => {
    answerMe(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) }));
    renderSuccess();
    await settle(apiFetch);

    expect(complete()).toBeNull();
    expect(back()).toBeInTheDocument();
  });

  test('nothing is added if the request is dropped', async () => {
    answerMe(() => Promise.reject(new TypeError('network')));
    renderSuccess();
    await settle(apiFetch);

    expect(complete()).toBeNull();
    expect(back()).toBeInTheDocument();
  });
});
