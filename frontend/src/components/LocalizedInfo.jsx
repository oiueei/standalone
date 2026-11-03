import { useTranslation } from 'react-i18next';
import InfoPopover from './InfoPopover';

// The example is a code sample, not UI copy: the keys are the language codes the
// server accepts and the values illustrate what a Spanish/Catalan owner writes,
// so it reads the same whatever language the form itself is in.
const EXAMPLE = '{"es": "Las cosas de mamá", "ca": "Les coses de mama"}';

/**
 * The quiet hint + (i) that tells an owner they may write one text per language.
 * Rendered under the description in the thing/collection forms
 * (`variant="text"`, covering headline *and* description) and under the tag
 * editor.
 *
 * Deliberately one hint per field group rather than one per input: the trick is
 * a single idea, and DESIGN §3 says remove what isn't necessary. It uses the
 * established `.info-popover-row` pattern (help line left, icon flush right, so
 * the `right: 0`-anchored panel stays inside the viewport).
 *
 * Props: `id` (the popover panel's id), `variant` (`text` | `policy` |
 * `requestInfo` | `emailNote`). `policy` is the deposit policy on
 * the network point's page — its own variant rather than reusing `text`, since that
 * hint specifically names "the title or the description" and a deposit
 * policy is neither. `requestInfo` (Collection.request_info, shown on
 * RequestThingPage for every verb) and `emailNote` (Collection.email_note,
 * the owner's note in the two requester emails) are the same shape again.
 */

const VARIANT_KEYS = {
  text: { hint: 'localized.hint', infoBody: 'localized.infoBody', example: EXAMPLE },
  policy: { hint: 'localized.policyHint', infoBody: 'localized.policyInfoBody', example: EXAMPLE },
  requestInfo: {
    hint: 'localized.requestInfoHint',
    infoBody: 'localized.requestInfoInfoBody',
    example: EXAMPLE,
  },
  emailNote: {
    hint: 'localized.emailNoteHint',
    infoBody: 'localized.emailNoteInfoBody',
    example: EXAMPLE,
  },
};

export default function LocalizedInfo({ id, variant = 'text' }) {
  const { t } = useTranslation();
  const keys = VARIANT_KEYS[variant];

  return (
    <div className="info-popover-row">
      <span className="localized-hint">{t(keys.hint)}</span>
      <InfoPopover id={id} title={t('localized.infoTitle')}>
        <p>{t(keys.infoBody)}</p>
        <code className="localized-example">{keys.example}</code>
        <p>{t('localized.infoFallback')}</p>
      </InfoPopover>
    </div>
  );
}
