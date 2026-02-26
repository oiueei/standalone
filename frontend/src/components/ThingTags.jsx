import { Tag } from 'hds-react';
import { TYPE_LABELS, TAG_THEMES } from '../constants/things';

export default function ThingTags({ thing, isOwner }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
      <Tag>{TYPE_LABELS[thing.type] || thing.type}</Tag>
      {isOwner && thing.status === 'TAKEN' && (
        <Tag theme={TAG_THEMES.taken}>Taken</Tag>
      )}
      {isOwner && thing.status === 'INACTIVE' && (
        <Tag theme={TAG_THEMES.inactive}>Inactive</Tag>
      )}
      {isOwner && !thing.available && (
        <Tag theme={TAG_THEMES.unavailable}>Unavailable</Tag>
      )}
      {isOwner && thing.pending_questions > 0 && (
        <Tag theme={TAG_THEMES.pending}>Pending questions</Tag>
      )}
    </div>
  );
}
