import { render, screen, waitFor, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';
import en from '../i18n/locales/en.json';
import es from '../i18n/locales/es.json';
import ca from '../i18n/locales/ca.json';

/**
 * The forms a deployment hosts elsewhere in the place of the app's own ways of writing
 * to the team: the footer's "Contact us", "Ideas and bugs" and
 * "Request access". Core knows nothing about who hosts them: `deployment/externalForms`
 * is `{ contact, feedback, requestAccess }`, each `{ es, ca, en }`, and the page of the
 * reader's language is opened **as written** — no parameter added — in a new tab.
 *
 * The `deployment` module is mocked (upstream's `externalForms` is `null`, so a
 * replacement can only be exercised this way), and the real `../i18n` changes the
 * language the components read. The files that pin the upstream behaviour of each
 * component switch the helper off instead (`vi.mock('../utils/externalForms')`).
 */
const FORMS = {
  contact: {
    es: 'https://forms.example/contacto',
    ca: 'https://forms.example/contacte',
    en: 'https://forms.example/contact',
  },
  feedback: {
    es: 'https://forms.example/ideas?src=es#top',
    ca: 'https://forms.example/idees',
    en: 'https://forms.example/ideas-en',
  },
  requestAccess: {
    es: 'https://forms.example/acceso',
    ca: 'https://forms.example/acces',
    en: 'https://forms.example/access',
  },
};
const LOCALES = { es, ca, en };
const LANGUAGES = ['es', 'ca', 'en'];

window.scrollTo = vi.fn();

let i18n;

async function setUp({ externalForms = FORMS, language = 'en', feedbackEnv = '' } = {}) {
  vi.resetModules();
  vi.stubEnv('VITE_FEEDBACK_URL', feedbackEnv);
  // The whole of the module, since `../i18n` reads `deploymentI18n` from it too.
  vi.doMock('../deployment', () => ({
    deploymentRoutes: [],
    popInPath: null,
    aboutPath: null,
    faqPath: null,
    deploymentI18n: {},
    externalForms,
    requestAccessPaths: {},
  }));
  ({ default: i18n } = await import('../i18n'));
  await act(async () => {
    await i18n.changeLanguage(language);
  });
  const [{ default: SiteFooter }, { default: FeedbackLink }, { default: ApprovalNotice }] =
    await Promise.all([
      import('../components/SiteFooter'),
      import('../components/FeedbackLink'),
      import('../components/ApprovalNotice'),
    ]);
  return { SiteFooter, FeedbackLink, ApprovalNotice };
}

function mockCapabilities(requestUrl) {
  localStorage.setItem('userCode', `U${Math.random()}`);
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({
          capabilities: {
            collection_modes: ['PROPRIETARY'],
            thing_types: [],
            request_url: requestUrl,
          },
        }),
    })
  );
}

const MODES = [
  { value: 'PROPRIETARY', label: 'Just mine' },
  { value: 'COMMUNITY', label: 'Shared' },
];

const inRouter = (node) => render(<MemoryRouter>{node}</MemoryRouter>);
/** The footer's third door: the one after "Privacy & legal". */
const contactDoor = (container) => container.querySelector('footer nav a:last-of-type');

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});
afterEach(async () => {
  vi.unstubAllEnvs();
  vi.doUnmock('../deployment');
  if (i18n) {
    await act(async () => {
      await i18n.changeLanguage('en');
    });
    localStorage.removeItem('i18nextLng');
  }
});

describe('when `resolvedLanguage` lags behind the language on screen', () => {
  test('the footer’s "Contact us" is the form of the language on screen, not of the lagging one', async () => {
    const { SiteFooter } = await setUp({ language: 'es' });
    // i18next works `resolvedLanguage` out apart from `language`, and it can stay on the
    // fallback while `t()` already translates in the language that was asked for.
    Object.defineProperty(i18n, 'resolvedLanguage', { value: 'en', configurable: true });
    expect(i18n.language).toBe('es');
    const { container } = inRouter(<SiteFooter />);

    expect(contactDoor(container).getAttribute('href')).toBe(FORMS.contact.es);
  });
});

describe.each(LANGUAGES)('with forms hosted elsewhere, in %s', (language) => {
  const locale = LOCALES[language];
  const opensInNewTab = locale.common.opensInNewTab;

  test('the footer’s "Contact us" is a plain link to that language’s form, in a new tab', async () => {
    const { SiteFooter } = await setUp({ language });
    const { container } = inRouter(<SiteFooter />);

    const door = contactDoor(container);
    expect(door).toHaveTextContent(locale.footer.contact);
    // Exactly the address written, with nothing added.
    expect(door.getAttribute('href')).toBe(FORMS.contact[language]);
    expect(door).toHaveAttribute('target', '_blank');
    expect(door.getAttribute('rel')).toContain('noopener');
    expect(door.getAttribute('rel')).toContain('noreferrer');
    // The new tab is announced: the visible words first, then the sentence.
    expect(door).toHaveAttribute('aria-label', `${locale.footer.contact}. ${opensInNewTab}`);
    // …and the app's own page is not offered anywhere in the footer.
    expect(container.querySelector('footer a[href="/contact"]')).toBeNull();
  });

  test('"Ideas and bugs" is a link to that language’s form, in a new tab', async () => {
    const { FeedbackLink } = await setUp({ language });
    render(<FeedbackLink />);

    const link = screen.getByRole('link');
    expect(link.getAttribute('href')).toBe(FORMS.feedback[language]);
    expect(link).toHaveAttribute('target', '_blank');
    expect(link.getAttribute('rel')).toContain('noopener');
    expect(link).toHaveAttribute('aria-label', `${locale.feedback.button}. ${opensInNewTab}`);
  });

  test('"Request access" goes to that language’s form, not to the server’s address', async () => {
    mockCapabilities('https://server.example/request/');
    const { ApprovalNotice } = await setUp({ language });
    render(<ApprovalNotice kind="collection_modes" catalogue={MODES} />);

    const button = await screen.findByRole('link', {
      name: `${locale.capabilities.requestAccess}. ${opensInNewTab}`,
    });
    expect(button.getAttribute('href')).toBe(FORMS.requestAccess[language]);
    expect(button).toHaveAttribute('target', '_blank');
    expect(button.getAttribute('rel')).toContain('noopener');
  });
});

describe('the language is the one on screen, and follows it', () => {
  test('changing the language changes the address the links point to', async () => {
    const { SiteFooter, FeedbackLink } = await setUp({ language: 'es' });
    const { container } = render(
      <MemoryRouter>
        <FeedbackLink />
        <SiteFooter />
      </MemoryRouter>
    );
    expect(contactDoor(container).getAttribute('href')).toBe(FORMS.contact.es);
    expect(container.querySelector('a[target="_blank"][href*="ideas"]').getAttribute('href')).toBe(
      FORMS.feedback.es
    );

    await act(async () => {
      await i18n.changeLanguage('ca');
    });

    expect(contactDoor(container).getAttribute('href')).toBe(FORMS.contact.ca);
    expect(container.querySelector('a[href="' + FORMS.feedback.ca + '"]')).not.toBeNull();
    expect(container.querySelector('a[href="' + FORMS.feedback.es + '"]')).toBeNull();
  });
});

describe('a language the deployment has no form for uses the es one', () => {
  const ONLY_ES_AND_EN = {
    contact: { es: FORMS.contact.es, en: FORMS.contact.en },
    feedback: { es: FORMS.feedback.es, en: FORMS.feedback.en },
    requestAccess: { es: FORMS.requestAccess.es, en: FORMS.requestAccess.en },
  };

  test('in Catalan, all three', async () => {
    mockCapabilities('https://server.example/request/');
    const { SiteFooter, FeedbackLink, ApprovalNotice } = await setUp({
      externalForms: ONLY_ES_AND_EN,
      language: 'ca',
    });
    const { container } = render(
      <MemoryRouter>
        <FeedbackLink />
        <ApprovalNotice kind="collection_modes" catalogue={MODES} />
        <SiteFooter />
      </MemoryRouter>
    );

    expect(contactDoor(container).getAttribute('href')).toBe(FORMS.contact.es);
    expect(container.querySelector('a[href="' + FORMS.feedback.es + '"]')).not.toBeNull();
    await waitFor(() =>
      expect(container.querySelector('a[href="' + FORMS.requestAccess.es + '"]')).not.toBeNull()
    );
  });
});

describe('upstream: no externalForms, nothing changes', () => {
  test('the footer’s "Contact us" is the app’s own /contact, in the same tab', async () => {
    const { SiteFooter } = await setUp({ externalForms: null });
    const { container } = inRouter(<SiteFooter />);

    const door = contactDoor(container);
    expect(door.getAttribute('href')).toBe('/contact');
    expect(door).not.toHaveAttribute('target');
    expect(door).not.toHaveAttribute('aria-label');
  });

  test('"Ideas and bugs" is VITE_FEEDBACK_URL, one address for every language, or nothing', async () => {
    const { FeedbackLink: WithEnv } = await setUp({
      externalForms: null,
      language: 'ca',
      feedbackEnv: 'https://env.example/f',
    });
    const { unmount } = render(<WithEnv />);
    expect(screen.getByRole('link').getAttribute('href')).toBe('https://env.example/f');
    unmount();

    const { FeedbackLink: Without } = await setUp({
      externalForms: null,
      language: 'ca',
      feedbackEnv: '',
    });
    const { container } = render(<Without />);
    expect(container).toBeEmptyDOMElement();
  });

  test('"Request access" is the address the server gives, or no button at all', async () => {
    mockCapabilities('https://server.example/request/');
    const { ApprovalNotice: WithUrl } = await setUp({ externalForms: null });
    const { unmount } = render(<WithUrl kind="collection_modes" catalogue={MODES} />);
    expect(
      (await screen.findByRole('link', { name: /^Request access/ })).getAttribute('href')
    ).toBe('https://server.example/request/');
    unmount();

    mockCapabilities(null);
    const { ApprovalNotice: WithoutUrl } = await setUp({ externalForms: null });
    render(<WithoutUrl kind="collection_modes" catalogue={MODES} />);
    await screen.findByText(/Shared/);
    expect(screen.queryByRole('link')).toBeNull();
  });
});

describe('a deployment with some of the forms only', () => {
  test('the others keep the way they were', async () => {
    mockCapabilities('https://server.example/request/');
    const { SiteFooter, FeedbackLink, ApprovalNotice } = await setUp({
      externalForms: { contact: FORMS.contact },
      language: 'en',
      feedbackEnv: 'https://env.example/f',
    });
    const { container } = render(
      <MemoryRouter>
        <FeedbackLink />
        <ApprovalNotice kind="collection_modes" catalogue={MODES} />
        <SiteFooter />
      </MemoryRouter>
    );

    // The one it has, its form; the other two, the env var and the server's address.
    expect(contactDoor(container).getAttribute('href')).toBe(FORMS.contact.en);
    expect(container.querySelector('a[href="https://env.example/f"]')).not.toBeNull();
    await waitFor(() =>
      expect(container.querySelector('a[href="https://server.example/request/"]')).not.toBeNull()
    );
  });

  test('the form wins over the env var and over the server’s address', async () => {
    mockCapabilities('https://server.example/request/');
    const { FeedbackLink, ApprovalNotice } = await setUp({
      externalForms: FORMS,
      language: 'en',
      feedbackEnv: 'https://env.example/f',
    });
    const { container } = render(
      <MemoryRouter>
        <FeedbackLink />
        <ApprovalNotice kind="collection_modes" catalogue={MODES} />
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(container.querySelector('a[href="' + FORMS.requestAccess.en + '"]')).not.toBeNull()
    );
    expect(container.querySelector('a[href="' + FORMS.feedback.en + '"]')).not.toBeNull();
    expect(container.querySelector('a[href="https://env.example/f"]')).toBeNull();
    expect(container.querySelector('a[href="https://server.example/request/"]')).toBeNull();
  });
});
