import { Tag } from 'hds-react';
import { useTranslation } from 'react-i18next';
import { TAG_THEMES } from '../constants/things';
import { useLocalized } from '../utils/localized';

// "New" signal window (design round, S7): a stateless, privacy-clean
// "what's new" tag — no per-user tracking, matches the weekly digest cadence.
export const NEW_THING_WINDOW_DAYS = 7;

export default function ThingTags({ thing, isOwner, showType = true }) {
  const { t } = useTranslation();
  // A tag label may itself be a per-language map; the raw string stays the value
  // (that's what the subset check compares), only the chip resolves.
  const L = useLocalized();
  // The "New" window is inherently wall-clock-relative — there is no prop/state
  // substitute for "how long ago was this created" that stays derivable and
  // pure. A card remounts on every navigation, so a stale render (component
  // kept alive for a week) is not a real-world concern here.
  // eslint-disable-next-line react-hooks/purity -- see note above
  const now = Date.now();
  const isNew = thing.created && thing.status !== 'INACTIVE'
    && (now - new Date(thing.created).getTime()) < NEW_THING_WINDOW_DAYS * 24 * 3600 * 1000;

  return (
    <div className="gallery-row" style={{ gap: 'var(--spacing-2-xs)' }}>
      {showType && <Tag>{t('types.' + thing.type) || thing.type}</Tag>}
      {isNew && <Tag theme={TAG_THEMES.fresh}>{t('thingTags.new')}</Tag>}
      {isOwner && thing.status === 'TAKEN' && (
        <Tag theme={TAG_THEMES.taken}>{t('thingTags.requested')}</Tag>
      )}
      {isOwner && thing.status === 'INACTIVE' && (
        <Tag theme={TAG_THEMES.inactive}>{t('thingTags.inactive')}</Tag>
      )}
      {isOwner && thing.pending_questions > 0 && (
        <Tag theme={TAG_THEMES.pending}>{t('thingTags.pendingQuestions')}</Tag>
      )}
      {(thing.tags || []).map((tag) => (
        <Tag key={tag} theme={TAG_THEMES.custom}>{L(tag)}</Tag>
      ))}
    </div>
  );
}
