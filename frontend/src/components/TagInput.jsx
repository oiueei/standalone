import { useState } from 'react';
import { TextInput, Button, Tag } from 'hds-react';
import { useTranslation } from 'react-i18next';
import { parseLocalized, useLocalized, localizedCounter } from '../utils/localized';

const MAX_TAGS = 12;
const MAX_LEN = 32;

/**
 * Chip-style free-text tag editor for the collection owner to define the
 * collection's tag vocabulary. Type a label and press Enter (or "Add") to add
 * it as a removable HDS Tag. Trims, dedupes (case-insensitive), caps at `max`
 * tags and `MAX_LEN` chars each — mirroring the backend `_normalize_tags`.
 *
 * A label may also carry one text per language (O6): `{"es": "Juguetes", "ca":
 * "Joguines"}`. The **raw string stays the value** — it is what the vocabulary
 * stores and what a thing's tags are checked against — so only the chip
 * resolves. The length rule is therefore mode-aware: 32 characters for a plain
 * label, 32 **per language** for a map. That is also why the input no longer
 * carries a native `maxLength`, which would have truncated a map mid-JSON.
 *
 * Props: tags (string[]), onChange (string[]), label, placeholder, helperText, max.
 */
export default function TagInput({ tags = [], onChange, label, placeholder, helperText, max = MAX_TAGS }) {
  const { t } = useTranslation();
  const L = useLocalized();
  const [input, setInput] = useState('');
  const [error, setError] = useState('');
  const atMax = tags.length >= max;

  const addTag = () => {
    const value = input.trim();
    if (!value || atMax) return;
    if (localizedCounter(value, MAX_LEN).over) {
      setError(t('tags.tooLong', { limit: MAX_LEN }));
      return;
    }
    if (tags.some((tg) => tg.toLowerCase() === value.toLowerCase())) {
      setInput('');
      setError('');
      return;
    }
    onChange([...tags, value]);
    setInput('');
    setError('');
  };

  return (
    <div className="tag-input">
      <TextInput
        id="collection-tag-input"
        label={label}
        placeholder={placeholder}
        helperText={`${helperText ? helperText + ' · ' : ''}${tags.length}/${max}`}
        value={input}
        invalid={!!error}
        errorText={error}
        onChange={(e) => {
          setInput(e.target.value);
          if (error) setError('');
        }}
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
          {tags.map((tg) => {
            const localized = parseLocalized(tg);
            return (
              <Tag
                key={tg}
                onDelete={() => onChange(tags.filter((x) => x !== tg))}
                // A localized chip reads as words like any other; the tooltip names
                // the languages it carries, so the owner can tell the two apart.
                title={localized ? Object.keys(localized).join(' · ') : undefined}
              >
                {L(tg)}
              </Tag>
            );
          })}
        </div>
      )}
    </div>
  );
}
