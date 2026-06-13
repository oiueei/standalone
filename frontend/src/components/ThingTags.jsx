import { Tag } from 'hds-react';
import { useTranslation } from 'react-i18next';
import { TAG_THEMES } from '../constants/things';

export default function ThingTags({ thing, isOwner, showType = true }) {
  const { t } = useTranslation();

  return (
    <div className="gallery-row" style={{ gap: 'var(--spacing-2-xs)' }}>
      {showType && <Tag>{t('types.' + thing.type) || thing.type}</Tag>}
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
        <Tag key={tag} theme={TAG_THEMES.custom}>{tag}</Tag>
      ))}
    </div>
  );
}
