import { TextArea, ToggleButton } from 'hds-react';
import { useTranslation } from 'react-i18next';
import useTheeeme from '../hooks/useTheeeme';
import { hasPriceVerbs } from '../utils/collectionKind';
import { localizedCounter, localizedHelper } from '../utils/localized';
import FieldNotice from './FieldNotice';

const DONATIONS_EXAMPLE = '{"es": "Aceptamos libros", "ca": "Acceptem llibres"}';

/**
 * The shared cluster of the Create and Edit collection forms that follows the mode:
 * for a stall or a library that members can add to, whether those members may set a
 * price, and under a "Visibility" heading the visibility toggle. Whether members may
 * recommend people is a setting of its own (the Notifications page), not asked here.
 *
 * What a collection holds is its kind, fixed when it is created, so there is no
 * longer a choice of verbs here. A COMMUNITY stall or library takes both of its
 * verbs when members may set a price (the default) and only the free one when
 * they may not; the page turns that switch into `allowed_thing_types`.
 *
 * **Donations** (a library's switch and the instructions its "Donate things" page shows)
 * come last, and only when the page passes `donations` — `{ accepts, setAccepts, info,
 * setInfo, error }` — for a `LIBRARY`. The creation page never does. The text field is
 * drawn only with the switch on: turning it off keeps what was written.
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
  membersPrice = true,
  setMembersPrice = () => {},
  donations = null,
}) {
  const { t } = useTranslation();
  const { toggleTheme } = useTheeeme();
  // Only where members add things themselves and a price is possible at all.
  const showMembersPrice = hasPriceVerbs(kind) && mode === 'COMMUNITY';
  const showDonations = kind === 'LIBRARY' && !!donations;
  const infoCount = localizedCounter(donations?.info, 2000);

  return (
    <>
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
      <h2 className="form-section-heading">{t('createCollection.visibilityHeading')}</h2>
      <ToggleButton
        id={`${idPrefix}-visibility`}
        variant="inline"
        label={t('visibility.publicFull')}
        checked={visibility === 'PUBLIC'}
        onChange={(val) => setVisibility(val ? 'PRIVATE' : 'PUBLIC')}
        theme={toggleTheme}
      />
      {showDonations && (
        <>
          <h2 className="form-section-heading">{t('donations.heading')}</h2>
          <ToggleButton
            id={`${idPrefix}-donations`}
            variant="inline"
            label={t('donations.toggleLabel')}
            checked={donations.accepts}
            onChange={(val) => donations.setAccepts(!val)}
            theme={toggleTheme}
          />
          {donations.accepts && (
            <>
              <FieldNotice
                id={`${idPrefix}-donations-notice`}
                label={t('donations.infoLabel')}
                example={DONATIONS_EXAMPLE}
                after={t('localized.textNoticeAfter')}
              >
                {t('donations.notice')}
              </FieldNotice>
              <TextArea
                id={`${idPrefix}-donations-info`}
                label={t('donations.infoLabel')}
                required
                value={donations.info}
                onChange={(e) => donations.setInfo(e.target.value)}
                invalid={infoCount.over || !!donations.error}
                errorText={infoCount.over ? t('donations.maxLength') : donations.error || undefined}
                helperText={`${t('donations.infoHelper')} · ${localizedHelper(donations.info, 2000, t)}`}
              />
            </>
          )}
        </>
      )}
    </>
  );
}
