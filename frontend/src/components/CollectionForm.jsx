import { Select, ToggleButton } from 'hds-react';
import { useTranslation } from 'react-i18next';
import {
  PROPRIETARY_TYPES,
  COMMUNITY_TYPES,
  isLockedToSingleType,
  reconcileAllowedTypes,
} from '../constants/things';

/**
 * The shared identity cluster of the Create and Edit collection forms — the part
 * that stays visible above the "More options" accordion (O1): the visibility
 * toggle, the COMMUNITY-only toggles (swap, require-3-items, share, newsletter)
 * and the allowed-thing-types multi-select (locked + pre-filled when a flag
 * forces a single type; its "pick at least one" rule must never hide).
 *
 * The rental-rules fields that used to trail this cluster now live in
 * `RentalRulesFields` (rendered by the pages inside the accordion).
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
  requireMinimumSwapItems,
  setRequireMinimumSwapItems,
  allowedThingTypes,
  setAllowedThingTypes,
  visibility = 'PRIVATE',
  setVisibility = () => {},
  errors,
  theeemeColor01,
}) {
  const { t } = useTranslation();
  const toggleTheme = theeemeColor01 ? { '--toggle-button-color': `var(--color-${theeemeColor01})` } : undefined;
  const locked = isLockedToSingleType({ isSwap, isShare });

  const allowedTypesOptions = (() => {
    if (mode === 'PROPRIETARY') {
      return PROPRIETARY_TYPES.map((v) => ({ label: t('types.' + v), value: v }));
    }
    if (isSwap) return [{ label: t('types.SWAP_THING'), value: 'SWAP_THING' }];
    if (isShare) return [{ label: t('types.SHARE_THING'), value: 'SHARE_THING' }];
    return COMMUNITY_TYPES.map((v) => ({ label: t('types.' + v), value: v }));
  })();

  return (
    <>
      <div className="toggle-left">
        <ToggleButton
          id={`${idPrefix}-visibility`}
          label={<>{t('visibility.publicLabel')}<br/><span style={{ fontSize: 'var(--fontsize-body-s)', fontWeight: 400, color: 'var(--color-black-70)' }}>{t('visibility.publicHelper')}</span></>}
          checked={visibility === 'PUBLIC'}
          onChange={(val) => setVisibility(val ? 'PRIVATE' : 'PUBLIC')}
          variant="inline"
          theme={toggleTheme}
        />
      </div>
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
              // is_swap forces SWAP_THING (locked); turning off keeps whatever of
              // the previous selection is still valid in the wider community set.
              setAllowedThingTypes((prev) => reconcileAllowedTypes(prev, {
                mode, isSwap: next, isShare: next ? false : isShare,
              }));
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
              setAllowedThingTypes((prev) => reconcileAllowedTypes(prev, {
                mode, isShare: next, isSwap: next ? false : isSwap,
              }));
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
      <div className={locked ? 'multiselect-locked' : undefined}>
        <Select
          language="en"
          multiSelect
          id={`${idPrefix}-allowed-thing-types`}
          texts={{
            label: t('createCollection.allowedTypesLabel'),
            placeholder: t('createCollection.allowedTypesPlaceholder'),
            assistive: (() => {
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
