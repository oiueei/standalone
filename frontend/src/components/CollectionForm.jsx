import { Select, ToggleButton } from 'hds-react';
import { useTranslation } from 'react-i18next';
import {
  PROPRIETARY_TYPES,
  COMMUNITY_TYPES,
  COMMUNITY_MINIMALIST_TYPES,
  isLockedToSingleType,
} from '../constants/things';

/**
 * The shared mode/swap/share/album field cluster of the Create and Edit
 * collection forms: the COMMUNITY-only toggles (swap, require-3-items, share,
 * newsletter), the always-visible album toggle, and the allowed-thing-types
 * multi-select (locked + pre-filled when a flag forces a single type).
 *
 * Controlled: every value + setter is owned by the page; this component only
 * renders the cluster and holds the (identical-across-both-pages) toggle
 * mutual-exclusivity / allowlist auto-fill logic. `idPrefix` is `create-collection`
 * or `edit-collection`; `theeemeColor01` is the theeeme `color_01` token name.
 */
export default function CollectionForm({
  idPrefix,
  mode,
  isSwap,
  setIsSwap,
  isShare,
  setIsShare,
  newsletterEnabled,
  setNewsletterEnabled,
  isMinimalist,
  setIsMinimalist,
  requireMinimumSwapItems,
  setRequireMinimumSwapItems,
  allowedThingTypes,
  setAllowedThingTypes,
  errors,
  theeemeColor01,
}) {
  const { t } = useTranslation();
  const toggleTheme = theeemeColor01 ? { '--toggle-button-color': `var(--color-${theeemeColor01})` } : undefined;
  const locked = isLockedToSingleType({ mode, isSwap, isShare, isMinimalist });

  const allowedTypesOptions = (() => {
    if (mode === 'PROPRIETARY') {
      return isMinimalist
        ? [{ label: t('types.GIFT_THING'), value: 'GIFT_THING' }]
        : PROPRIETARY_TYPES.map((v) => ({ label: t('types.' + v), value: v }));
    }
    if (isSwap) return [{ label: t('types.SWAP_THING'), value: 'SWAP_THING' }];
    if (isShare) return [{ label: t('types.SHARE_THING'), value: 'SHARE_THING' }];
    const list = isMinimalist ? COMMUNITY_MINIMALIST_TYPES : COMMUNITY_TYPES;
    return list.map((v) => ({ label: t('types.' + v), value: v }));
  })();

  return (
    <>
      {mode === 'COMMUNITY' && (
        <div className="toggle-left">
          <ToggleButton
            id={`${idPrefix}-swap`}
            label={t('swap.enableSwap')}
            checked={isSwap}
            onChange={(val) => {
              const next = !val;
              setIsSwap(next);
              // Turning ON swap clears the mutually-exclusive share flag;
              // turning OFF clears the swap-specific minimum-items rule.
              if (next) { setIsShare(false); } else { setRequireMinimumSwapItems(false); }
              // is_swap forces the type — auto-fill SWAP_THING so the locked
              // select shows it. Toggling off resets so the user re-picks.
              setAllowedThingTypes(next ? ['SWAP_THING'] : []);
            }}
            variant="inline"
            theme={toggleTheme}
          />
        </div>
      )}
      {mode === 'COMMUNITY' && isSwap && (
        <div className="toggle-left">
          <ToggleButton
            id={`${idPrefix}-swap-minimum`}
            label={<>{t('swap.requireMinimumLabel')}<br/><span style={{ fontSize: 'var(--fontsize-body-s)', fontWeight: 400, color: 'var(--color-black-70)' }}>{t('swap.requireMinimumHelper')}</span></>}
            checked={requireMinimumSwapItems}
            onChange={(val) => setRequireMinimumSwapItems(!val)}
            variant="inline"
            theme={toggleTheme}
          />
        </div>
      )}
      {mode === 'COMMUNITY' && (
        <div className="toggle-left">
          <ToggleButton
            id={`${idPrefix}-share`}
            label={t('share.enableShare')}
            checked={isShare}
            onChange={(val) => {
              const next = !val;
              setIsShare(next);
              // Turning ON share clears the mutually-exclusive swap flag;
              // turning OFF clears the share-only newsletter setting.
              if (next) setIsSwap(false); else setNewsletterEnabled(false);
              setAllowedThingTypes(next ? ['SHARE_THING'] : []);
            }}
            variant="inline"
            theme={toggleTheme}
          />
        </div>
      )}
      {mode === 'COMMUNITY' && isShare && (
        <div className="toggle-left">
          <ToggleButton
            id={`${idPrefix}-newsletter`}
            label={t('newsletter.enableNewsletter')}
            checked={newsletterEnabled}
            onChange={(val) => setNewsletterEnabled(!val)}
            variant="inline"
            theme={toggleTheme}
          />
        </div>
      )}
      <div className="toggle-left">
        <ToggleButton
          id={`${idPrefix}-minimalist`}
          label={t('minimalist.enableMinimalist')}
          checked={isMinimalist}
          onChange={(val) => {
            const next = !val;
            setIsMinimalist(next);
            // PROPRIETARY+album → only GIFT_THING is valid, auto-fill and lock.
            // COMMUNITY+album narrows the list to [GIFT, SHARE] but leaves the
            // selection to the user — reset so they pick from the smaller set.
            if (mode === 'PROPRIETARY') {
              setAllowedThingTypes(next ? ['GIFT_THING'] : []);
            } else {
              setAllowedThingTypes([]);
            }
          }}
          variant="inline"
          theme={toggleTheme}
        />
      </div>
      <div className={locked ? 'multiselect-locked' : undefined}>
        <Select
          language="en"
          multiSelect
          id={`${idPrefix}-allowed-thing-types`}
          texts={{
            label: t('createCollection.allowedTypesLabel'),
            placeholder: t('createCollection.allowedTypesPlaceholder'),
            assistive: (() => {
              if (mode === 'PROPRIETARY' && isMinimalist) return t('createCollection.allowedTypesAlbumHelper');
              if (mode === 'COMMUNITY' && isSwap) return t('createCollection.allowedTypesSwapHelper');
              if (mode === 'COMMUNITY' && isShare) return t('createCollection.allowedTypesShareHelper');
              return t('createCollection.allowedTypesHelper');
            })(),
            error: errors.allowedThingTypes,
          }}
          options={allowedTypesOptions}
          value={allowedThingTypes.map((v) => ({
            label: t('types.' + v),
            value: v,
          }))}
          onChange={(opts) => setAllowedThingTypes(opts.map((o) => o.value))}
          disabled={locked}
          invalid={!!errors.allowedThingTypes}
        />
      </div>
    </>
  );
}
