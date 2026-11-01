import { ToggleButton } from 'hds-react';
import { useTranslation } from 'react-i18next';
import { hasPriceVerbs } from '../utils/collectionKind';

/**
 * The shared identity cluster of the Create and Edit collection forms — the part
 * that stays visible above the "More options" accordion: the visibility toggle,
 * the recommend-a-guest toggle and, for a stall or a library that members can add
 * to, whether those members may set a price.
 *
 * What a collection holds is its kind, fixed when it is created, so there is no
 * longer a choice of verbs here. A COMMUNITY stall or library takes both of its
 * verbs when members may set a price (the default) and only the free one when
 * they may not; the page turns that switch into `allowed_thing_types`.
 *
 * The rental-rules fields that used to trail this cluster now live in
 * `RentalRulesFields` (rendered by the pages inside the accordion).
 *
 * Controlled: every value + setter is owned by the page; this component only
 * renders the cluster. `idPrefix` is `create-collection`
 * or `edit-collection`; `theeemeColor01` is the theeeme `color_01` token name.
 */
export default function CollectionForm({
  idPrefix,
  kind,
  mode = 'PROPRIETARY',
  visibility = 'PRIVATE',
  setVisibility = () => {},
  allowProposals = false,
  setAllowProposals = () => {},
  membersPrice = true,
  setMembersPrice = () => {},
  theeemeColor01,
}) {
  const { t } = useTranslation();
  const toggleTheme = theeemeColor01
    ? { '--toggle-button-color': `var(--color-${theeemeColor01})` }
    : undefined;
  // Only where members add things themselves and a price is possible at all.
  const showMembersPrice = hasPriceVerbs(kind) && mode === 'COMMUNITY';

  return (
    <>
      <ToggleButton
        id={`${idPrefix}-visibility`}
        variant="inline"
        label={t('visibility.publicFull')}
        checked={visibility === 'PUBLIC'}
        onChange={(val) => setVisibility(val ? 'PRIVATE' : 'PUBLIC')}
        theme={toggleTheme}
      />
      {/* Whether members may recommend guests. The owner still decides on every
          one — this is whether they are willing to be asked at all, which a
          group with a waiting list or an admission process may not be. Sits
          with visibility because both answer "who can get in here". */}
      <ToggleButton
        id={`${idPrefix}-allow-proposals`}
        variant="inline"
        label={t('recommend.settingFull')}
        checked={allowProposals}
        onChange={(val) => setAllowProposals(!val)}
        theme={toggleTheme}
      />
      {showMembersPrice && (
        <ToggleButton
          id={`${idPrefix}-members-price`}
          variant="inline"
          label={t(
            kind === 'LIBRARY'
              ? 'collectionForm.membersPriceLibrary'
              : 'collectionForm.membersPriceStall'
          )}
          checked={membersPrice}
          onChange={(val) => setMembersPrice(!val)}
          theme={toggleTheme}
        />
      )}
    </>
  );
}
