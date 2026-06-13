import { useState } from 'react';
import { TextInput, Button, Tag } from 'hds-react';
import { useTranslation } from 'react-i18next';

const MAX_TAGS = 12;
const MAX_LEN = 32;

/**
 * Chip-style free-text tag editor for the collection owner to define the
 * collection's tag vocabulary. Type a label and press Enter (or "Add") to add
 * it as a removable HDS Tag. Trims, dedupes (case-insensitive), caps at `max`
 * tags and `MAX_LEN` chars each — mirroring the backend `_normalize_tags`.
 *
 * Props: tags (string[]), onChange (string[]), label, placeholder, helperText, max.
 */
export default function TagInput({ tags = [], onChange, label, placeholder, helperText, max = MAX_TAGS }) {
  const { t } = useTranslation();
  const [input, setInput] = useState('');
  const atMax = tags.length >= max;

  const addTag = () => {
    const value = input.trim().slice(0, MAX_LEN);
    if (!value || atMax) return;
    if (tags.some((tg) => tg.toLowerCase() === value.toLowerCase())) {
      setInput('');
      return;
    }
    onChange([...tags, value]);
    setInput('');
  };

  return (
    <div className="tag-input">
      <TextInput
        id="collection-tag-input"
        label={label}
        placeholder={placeholder}
        helperText={`${helperText ? helperText + ' · ' : ''}${tags.length}/${max}`}
        value={input}
        maxLength={MAX_LEN}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            addTag();
          }
        }}
        disabled={atMax}
      />
      <Button
        variant="secondary"
        size="small"
        onClick={addTag}
        disabled={!input.trim() || atMax}
        style={{ marginTop: 'var(--spacing-2-xs)' }}
      >
        {t('tags.add')}
      </Button>
      {tags.length > 0 && (
        <div className="tag-chip-row">
          {tags.map((tg) => (
            <Tag key={tg} onDelete={() => onChange(tags.filter((x) => x !== tg))}>
              {tg}
            </Tag>
          ))}
        </div>
      )}
    </div>
  );
}
