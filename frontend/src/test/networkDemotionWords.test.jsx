import { describe, test, expect } from 'vitest';
import en from '../i18n/locales/en.json';
import es from '../i18n/locales/es.json';
import ca from '../i18n/locales/ca.json';
import i18n from '../i18n';

/**
 * The words of the network demotion notices (the inbox notice and the confirmation
 * dialog), the member-proposals switch and the About label: the singular names the
 * thing without the number, the plural keeps it.
 */
describe('the singular of the network demotion notices has no number', () => {
  test('the two singular forms are fixed letter by letter in the three languages', () => {
    expect([es, ca, en].map((l) => l.home.demotedNetworkBody_one)).toEqual([
      'Vuelves a ser un miembro normal de “{{collection_headline}}”. Tu cosa de allí se ha borrado.',
      "Tornes a ser un membre normal de “{{collection_headline}}”. La teva cosa d'allà s'ha esborrat.",
      "You're a regular member of “{{collection_headline}}” again. Your thing there was deleted.",
    ]);
    expect([es, ca, en].map((l) => l.manageInvites.demoteNetworkBody_one)).toEqual([
      'Su cosa se borrará de la red y se avisará a quien la hubiera pedido. Sigue siendo miembro.',
      "La seva cosa s'esborrarà de la xarxa i s'avisarà qui l'hagués demanada. Continua sent membre.",
      'Their thing will be deleted from the network, and whoever asked for it will be told. They stay a member.',
    ]);
  });

  test.each(['es', 'ca', 'en'])(
    'in %s a count of 1 picks the singular and paints no 1',
    async (lang) => {
      await i18n.loadLanguages(lang);
      const t = i18n.getFixedT(lang);
      const one = [
        t('home.demotedNetworkBody', { count: 1, collection_headline: 'Toy library' }),
        t('manageInvites.demoteNetworkBody', { count: 1 }),
      ];
      // Guard against the lazy locale not being loaded: the text must be in this language.
      expect(one[1]).toBe({ es, ca, en }[lang].manageInvites.demoteNetworkBody_one);
      for (const text of one) expect(text).not.toMatch(/\b1\b/);
      expect(one[0]).toContain('Toy library');
    }
  );

  test.each(['es', 'ca', 'en'])('in %s a count of 3 keeps the number', async (lang) => {
    await i18n.loadLanguages(lang);
    const t = i18n.getFixedT(lang);
    expect(t('home.demotedNetworkBody', { count: 3, collection_headline: 'X' })).toContain('3');
    expect(t('manageInvites.demoteNetworkBody', { count: 3 })).toContain('3');
  });
});

describe('two labels reworded', () => {
  test('the members-may-recommend switch says whose the proposal and the decision are', () => {
    expect([es, ca, en].map((l) => l.recommend.settingFull)).toEqual([
      'Los miembros pueden recomendar personas (La propuesta es suya y la decisión, tuya: no sale ninguna invitación sin tu visto bueno.)',
      'Els membres poden recomanar persones (La proposta és seva i la decisió, teva: no surt cap invitació sense el teu vistiplau.)',
      'Members can recommend people: They suggest, you decide — no invitation goes out without your say-so.',
    ]);
  });

  test('the organisation’s About is “Presentación” / “Presentació” in the two languages that changed', () => {
    expect([es, ca, en].map((l) => l.organisation.aboutLabel)).toEqual([
      'Presentación',
      'Presentació',
      'About',
    ]);
  });
});
