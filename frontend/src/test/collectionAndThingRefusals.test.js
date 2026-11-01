import { describe, test, expect, afterEach } from 'vitest';
import i18n from '../i18n';
import es from '../i18n/locales/es.json';
import { apiErrorMessage } from '../services/api';
import { switchLanguage } from './settle';

// Every refusal the collection, invitation, thing and FAQ endpoints send arrives
// as `{error|detail: <English>, code, params?}`; a Spanish reader must read the
// Spanish sentence, never the English one the server wrote.
const CASES = [
  ['already_invited', undefined, 'Esta persona ya está invitada a esta colección.'],
  ['owner_cannot_leave', undefined, 'Quien fundó el grupo no puede abandonarlo.'],
  ['invite_already_asked', undefined, es.requestErrors.invite_already_asked],
  ['joins_spent', undefined, es.requestErrors.joins_spent],
  ['invite_quota_exhausted', undefined, es.requestErrors.invite_quota_exhausted],
  ['too_many_invites', { max: 100 }, 'Se pueden enviar como máximo 100 invitaciones de una vez.'],
  ['too_many_invites', { max: 1 }, 'Solo se puede enviar 1 invitación de una vez.'],
  ['things_limit', { max: 40 }, es.requestErrors.things_limit_other.replace('{{count}}', '40')],
  ['members_limit', { max: 5 }, es.requestErrors.members_limit_other.replace('{{count}}', '5')],
  ['too_many_rows', { max: 100 }, 'Se pueden importar como máximo 100 filas de una vez.'],
  ['thing_not_inactive', undefined, 'Esta cosa no está oculta.'],
  ['cannot_add_things', undefined, 'No puedes añadir cosas a esta colección.'],
  ['cannot_request_own_thing', undefined, 'No puedes pedir una cosa tuya.'],
  ['collection_paused', undefined, es.requestErrors.collection_paused],
  ['booking_not_pending', undefined, es.requestErrors.booking_not_pending],
  ['profile_not_yours', undefined, 'Solo puedes editar tu propio perfil.'],
  ['manager_cannot_ask', undefined, es.requestErrors.manager_cannot_ask],
  ['only_managers_answer', undefined, es.requestErrors.only_managers_answer],
];

describe('coded refusals of collections, invitations, things and questions', () => {
  afterEach(async () => {
    await switchLanguage(i18n, 'en');
  });

  test.each(CASES)('%s is said in Spanish', async (code, params, expected) => {
    await switchLanguage(i18n, 'es');
    const message = apiErrorMessage({ error: 'English sentence', code, params });

    expect(message).toBe(expected);
    expect(message).not.toBe('English sentence');
  });

  test('a code this client does not know falls back to the server sentence', async () => {
    await switchLanguage(i18n, 'es');

    expect(apiErrorMessage({ detail: 'Some new rule.', code: 'brand_new_rule' })).toBe(
      'Some new rule.'
    );
  });
});
