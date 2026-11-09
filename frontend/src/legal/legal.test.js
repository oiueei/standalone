import { describe, test, expect } from 'vitest';
import es from './es';
import ca from './ca';
import en from './en';

// The legal text is per-language content, not i18n keys — this is its parity
// guard, the analogue of i18nParity for `src/legal/`. `en` is the reference,
// as it is everywhere else in this repo.
//
// It checks structure, never wording: wording is exactly what a translation is
// allowed to change. What a translation must NOT change is how many sections a
// reader gets, in what order, and whether each one actually says something.
// Counting `# ` lines cannot see the failure that matters — a translation that
// keeps all five headings and empties one body reads as a complete document and
// still leaves that language's reader without a privacy notice.

const LANGS = { es, ca, en };
const CODES = Object.keys(LANGS);

/** A section is a `# ` heading plus everything up to the next one. */
function sections(text) {
  const out = [];
  for (const line of text.split('\n')) {
    if (line.startsWith('# ')) out.push({ heading: line.slice(2).trim(), body: '' });
    else if (out.length) out[out.length - 1].body += `${line}\n`;
  }
  return out.map((s) => ({ ...s, prose: s.body.replace(/\s+/g, ' ').trim() }));
}

describe('legal content parity', () => {
  const reference = sections(en);

  test('the reference text is a document, not a stub', () => {
    // Commitment, operator identity, privacy, terms, self-hosting — the five
    // the standalone ships. A sixth is fine; four means one went missing.
    expect(reference.length).toBeGreaterThanOrEqual(5);
  });

  test.each(CODES)('%s ships every section the reference does', (lang) => {
    const got = sections(LANGS[lang]).map((s) => s.heading);
    expect(got, `${lang} has ${got.length} sections, en has ${reference.length}`).toHaveLength(
      reference.length
    );
  });

  test.each(CODES)('%s gives every section a body, not just a heading', (lang) => {
    for (const [i, section] of sections(LANGS[lang]).entries()) {
      expect(section.heading, `${lang} section ${i + 1} has an empty heading`).not.toBe('');
      expect(
        section.prose.length,
        `${lang} section ${i + 1} ("${section.heading}") has no body — a reader of this ` +
          'language would get the heading and nothing under it'
      ).toBeGreaterThan(40);
    }
  });

  // Sections are matched by position, so a reordered translation would file its
  // privacy text where another language keeps its terms. Length is the only
  // cross-language comparison possible without comparing wording: these are
  // translations of one text, so the n-th section must be recognisably the same
  // section. The band is deliberately wide — it catches a swap or a gutting,
  // not the ordinary elasticity of translation.
  test.each(CODES.filter((c) => c !== 'en'))('%s keeps the sections in the same order', (lang) => {
    for (const [i, section] of sections(LANGS[lang]).entries()) {
      const ratio = section.prose.length / reference[i].prose.length;
      expect(
        ratio,
        `${lang} section ${i + 1} ("${section.heading}") is ${ratio.toFixed(1)}× the length of ` +
          `en's "${reference[i].heading}" — a section is missing, gutted, or out of order`
      ).toBeGreaterThan(1 / 3);
      expect(ratio).toBeLessThan(3);
    }
  });

  // The /legal page is one of two places the app names its own licence to a
  // reader (the other is the login page). A partial relicensing that updated
  // one language and not another would leave that language's reader looking at
  // a licence OIUEEI no longer uses — so every language must name EUPL-1.2 and
  // none may still carry the retired BSL wording.
  test.each(CODES)('%s names the licence as EUPL-1.2 and drops the retired BSL wording', (lang) => {
    expect(LANGS[lang]).toMatch(/EUPL-1\.2/);
    expect(LANGS[lang]).not.toMatch(/\bBU?SL\b|Business Source|MIT from 2030|MIT a partir/i);
  });

  // The privacy section says what the app counts by device, and says the two things
  // that make the count harmless: it is numbers only (the lead says so), and it holds
  // no one. Where it sits is the text's own business: a deployment replaces this file
  // with its own legal text, and may write it as a paragraph or as a point of its list
  // of what it processes, so a leading "- " is allowed and nothing is said about what
  // comes before it.
  const COUNTS = {
    en: { lead: '**What we count (numbers only):**', no: /not who/ },
    es: { lead: '**Lo que contamos (solo números):**', no: /ni quién/ },
    ca: { lead: '**El que comptem (només números):**', no: /ni qui,/ },
  };

  test.each(CODES)('%s says what is counted by device, and that it holds no one', (lang) => {
    const { lead, no } = COUNTS[lang];
    const found = sections(LANGS[lang])
      .flatMap((s) => s.body.split('\n'))
      .map((line) => line.trim().replace(/^- /, ''))
      .filter((line) => line.startsWith(lead));

    expect(found, `${lang} must name the per-device count once`).toHaveLength(1);
    expect(found[0]).toMatch(no);
  });
});

describe('the contact phone a group may ask for when booking', () => {
  // The request page promises the number is optional, seen only by whoever manages the
  // booking and deleted the day after; the privacy text has to say the same, in the
  // paragraph about who sees what inside a group, right after its first sentence.
  const SENTENCE = {
    es: 'Si el grupo lo pide al reservar, puedes dejar también un teléfono de contacto: es opcional, solo lo ve quien gestiona esa reserva y se borra el día después de la reserva.',
    ca: "Si el grup ho demana en reservar, també pots deixar un telèfon de contacte: és opcional, només el veu qui gestiona aquesta reserva i s'esborra l'endemà de la reserva.",
    en: 'If the group asks for it when you book, you can also leave a contact phone number: it is optional, only those who manage that booking see it, and it is deleted the day after the booking.',
  };
  const FIRST_SENTENCE_END = {
    es: 'para que puedan responderte. ',
    ca: 'perquè et puguin respondre. ',
    en: 'so they can answer you. ',
  };

  test.each(CODES)('%s says it, once, right after the first sentence of the paragraph', (lang) => {
    const text = LANGS[lang];
    expect(text.split(SENTENCE[lang])).toHaveLength(2);
    expect(text).toContain(FIRST_SENTENCE_END[lang] + SENTENCE[lang]);
  });
});

describe('what is seen of a profile, of a team page and of an invitation', () => {
  // Three things the paragraph about who sees what inside a group has to say: a profile
  // is seen by people who share a group (`can_view_user`, `UserPublicSerializer`), a
  // curator's page travels with the group (`NetworkPointSerializer`), and an emailed
  // invitation leaves a year-long fingerprint of the address (`InvitationRecord`).
  const SENTENCES = {
    es: [
      'Tu perfil (nombre público, presentación, «acerca de ti» y foto) lo ve quien comparte algún grupo contigo, nunca tu email, tu idioma ni tus datos demográficos.',
      'Quien dinamiza un grupo puede tener en él una página con el nombre de su entidad, un logo, una presentación y un contacto (y, en una red, la dirección y el horario de su punto de recogida): se ve junto con el grupo, también sin cuenta si el grupo es público.',
      'Si alguien te invita por email, el grupo guarda durante un año una huella de tu dirección (no la dirección) para no volver a invitarte; se borra pasado ese año.',
    ],
    ca: [
      'El teu perfil (nom públic, presentació, «sobre tu» i foto) el veu qui comparteix algun grup amb tu, mai el teu email, el teu idioma ni les teves dades demogràfiques.',
      "Qui dinamitza un grup hi pot tenir una pàgina amb el nom de la seva entitat, un logo, una presentació i un contacte (i, en una xarxa, l'adreça i l'horari del seu punt de recollida): es veu juntament amb el grup, també sense compte si el grup és públic.",
      "Si algú et convida per email, el grup guarda durant un any una empremta de la teva adreça (no l'adreça) per no tornar a convidar-te; s'esborra passat aquest any.",
    ],
    en: [
      'Your profile (public name, bio, about and photo) is seen by the people who share a group with you, never your email, your language or your demographic details.',
      'Whoever runs a group can have a page in it with the name of their organisation, a logo, an introduction and a contact (and, in a network, the address and hours of their pickup point): it is seen together with the group, also without an account if the group is public.',
      'If someone invites you by email, the group keeps for a year a fingerprint of your address (not the address) so as not to invite you again; it is deleted after that year.',
    ],
  };
  const PARAGRAPH_LEAD = {
    es: '**Quién ve qué dentro de un grupo:**',
    ca: "**Qui veu què dins d'un grup:**",
    en: '**Who sees what inside a group:**',
  };

  test.each(CODES.flatMap((lang) => [0, 1, 2].map((i) => [lang, i])))(
    '%s says sentence %i once, inside that paragraph',
    (lang, i) => {
      const text = LANGS[lang];
      const sentence = SENTENCES[lang][i];
      expect(text.split(sentence)).toHaveLength(2);
      const paragraph = text.split('\n').find((line) => line.startsWith(PARAGRAPH_LEAD[lang]));
      expect(paragraph).toContain(sentence);
    }
  );
});
