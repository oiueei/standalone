import { Select, TextInput, TextArea, NumberInput, ToggleButton } from 'hds-react';
import { useTranslation } from 'react-i18next';
import {
  DATE_TYPES,
  DETAIL_TYPES,
  AVAILABILITY_VALUES,
  CONDITION_VALUES,
} from '../constants/things';
import ImageUpload from './ImageUpload';
import GalleryUpload from './GalleryUpload';
import LocalizedInfo from './LocalizedInfo';
import ApprovalNotice from './ApprovalNotice';
import { useLocalized, localizedHelper } from '../utils/localized';
import hdsLang from '../utils/hdsLang';

/**
 * The shared field cluster of the Add and Edit thing forms: the endless toggle,
 * headline, description, price, the availability/condition/location detail fields,
 * the per-thing tags select, the thumbnail upload and gallery.
 *
 * There is no selector of verbs: a thing's verb follows its collection's kind and
 * its price (a stall gives or sells, a library lends or rents out, a shed books),
 * and the server puts it. The fields shown follow the **kind**, not the verb, so
 * typing a price never makes another field appear or vanish: a stall has the
 * "endless" switch and the static availability hint, a library the deposit, every
 * kind its condition and place. `type` is the verb the price makes — read here only
 * for the few things that really do depend on it (the detail fields).
 *
 * Controlled: each value + setter is owned by the page. `priceAllowed` is false in a
 * community group whose members may not set a price (there is no price field at all);
 * `approvalCatalogue` lists the verb the deployment's policy withholds from this
 * account for the price typed, so the notice says so instead of letting it be sent.
 * `verbFollowsPrice` is false when the server will not change the verb with the price
 * (a thing with no collection, or one a mixed collection kept from the other
 * family): the line under the price ("No price, it's a gift") would promise what does
 * not happen, so the label is the neutral one and the line is left out.
 * `idPrefix` is `add-thing` or `edit-thing`.
 */
export default function ThingForm({
  idPrefix,
  theeemeColor01,
  errors,
  kind,
  type,
  priceAllowed = true,
  verbFollowsPrice = true,
  approvalCatalogue = [],
  isEndless,
  setIsEndless,
  headline,
  setHeadline,
  description,
  setDescription,
  fee,
  setFee,
  feeStep,
  deposit,
  setDeposit,
  depositStep,
  availability,
  setAvailability,
  condition,
  setCondition,
  location,
  setLocation,
  // A network's things are placed by their dinamizador's pickup point: no location asked.
  askLocation = true,
  collectionTags = [],
  tags,
  setTags,
  imageLabel,
  thumbnail,
  setThumbnail,
  thumbnailUrl,
  gallery,
  setGallery,
}) {
  const { t, i18n } = useTranslation();
  const L = useLocalized();
  const toggleTheme = theeemeColor01
    ? { '--toggle-button-color': `var(--color-${theeemeColor01})` }
    : undefined;

  const showEndless = kind === 'STALL';
  const showFee = priceAllowed;
  // Deposit is a guarantee that comes back, not part of the price — a library's
  // things only. Its own gate, never the price's: a rental carries both, a loan only
  // this. A gift, a sale or a reservation has nothing to give back.
  const showDeposit = kind === 'LIBRARY';
  const isDetailType = DETAIL_TYPES.includes(type);
  const showSpacer = (showFee || showDeposit) && isDetailType;
  const showDetailFields = isDetailType;
  // The static availability hint (IMMEDIATE / NEXT_WEEK / …) is only ever shown
  // for non-date types: a library's and a shed's things render *live* availability
  // from the booking calendar instead (ThingInfoRows), so a value collected here
  // would never surface anywhere. Condition and location still matter for them.
  const showAvailability = showDetailFields && !DATE_TYPES.includes(type);
  const priceLabel =
    verbFollowsPrice && kind === 'STALL'
      ? t('thingForm.priceStall')
      : verbFollowsPrice && kind === 'LIBRARY'
        ? t('thingForm.priceLibrary')
        : t('addThing.priceOptionalLabel');
  const priceHelper = !verbFollowsPrice
    ? undefined
    : kind === 'STALL'
      ? t('thingForm.priceStallHelp')
      : kind === 'LIBRARY'
        ? t('thingForm.priceLibraryHelp')
        : undefined;

  // HDS Select wants the selected option object(s), never a bare string: handed
  // a string it can't resolve against `options`, it renders that string
  // verbatim — which is how a raw `GIFT_THING` ends up in the type box when the
  // collection's allowlist doesn't offer the default. Build each list once so
  // `value` can be matched against the same array `options` is given.
  const availabilityOptions = AVAILABILITY_VALUES.map((v) => ({
    label: t('availability.' + v),
    value: v,
  }));
  const conditionOptions = CONDITION_VALUES.map((v) => ({ label: t('condition.' + v), value: v }));

  return (
    <>
      {showEndless && (
        <ToggleButton
          id={`${idPrefix}-is-endless`}
          variant="inline"
          label={t('endless.label')}
          checked={isEndless}
          onChange={(val) => setIsEndless(!val)}
          theme={toggleTheme}
        />
      )}
      <TextInput
        id={`${idPrefix}-headline`}
        label={t('addThing.titleLabel')}
        value={headline}
        onChange={(e) => setHeadline(e.target.value)}
        required
        invalid={!!errors.headline}
        errorText={errors.headline}
        helperText={localizedHelper(headline, 64, t)}
      />
      <TextArea
        id={`${idPrefix}-description`}
        label={t('addThing.descriptionLabel')}
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        invalid={!!errors.description}
        errorText={errors.description}
        helperText={localizedHelper(description, 2000, t)}
      />
      <LocalizedInfo id={`${idPrefix}-localized-info`} />
      {showFee && (
        <NumberInput
          id={`${idPrefix}-fee`}
          label={priceLabel}
          helperText={priceHelper}
          value={fee === '' ? '' : Number(fee)}
          onChange={(e) => setFee(e.target.value)}
          min={0}
          step={feeStep}
          unit="EUR"
          invalid={!!errors.fee}
          errorText={errors.fee}
        />
      )}
      {approvalCatalogue.length > 0 && (
        <ApprovalNotice kind="thing_types" catalogue={approvalCatalogue} />
      )}
      {/* No default, never pre-filled, and never presented ahead of the price:
          a deposit is exclusionary by nature (DESIGN §6 — no dark pattern nudges
          someone towards asking for one) and the helper text names it as what
          it is, a guarantee given back, not a cost. */}
      {showDeposit && (
        <NumberInput
          id={`${idPrefix}-deposit`}
          label={t('addThing.depositLabel')}
          helperText={t('addThing.depositHelper')}
          value={deposit === '' ? '' : Number(deposit)}
          onChange={(e) => setDeposit(e.target.value)}
          min={0}
          step={depositStep}
          unit="EUR"
          invalid={!!errors.deposit}
          errorText={errors.deposit}
        />
      )}
      {showSpacer && <div className="spacer-xxxx" />}
      {showAvailability && (
        <Select
          id={`${idPrefix}-availability`}
          texts={{ label: t('addThing.availabilityLabel'), language: hdsLang(i18n.language) }}
          options={availabilityOptions}
          value={availabilityOptions.filter((o) => o.value === availability)}
          onChange={(sel) => setAvailability(sel.length > 0 ? sel[0].value : '')}
          clearable
        />
      )}
      {showDetailFields && (
        <>
          <Select
            id={`${idPrefix}-condition`}
            texts={{ label: t('addThing.conditionLabel'), language: hdsLang(i18n.language) }}
            options={conditionOptions}
            value={conditionOptions.filter((o) => o.value === condition)}
            onChange={(sel) => setCondition(sel.length > 0 ? sel[0].value : '')}
            clearable
          />
          {askLocation && (
            <TextInput
              id={`${idPrefix}-location`}
              label={t('addThing.locationLabel')}
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              helperText={`${location.length}/64`}
              invalid={!!errors.location}
              errorText={errors.location}
            />
          )}
        </>
      )}
      {collectionTags.length > 0 && (
        <Select
          multiSelect
          id={`${idPrefix}-tags`}
          texts={{
            label: t('addThing.tagsLabel'),
            placeholder: t('addThing.tagsPlaceholder'),
            assistive: t('addThing.tagsHelper'),
            language: hdsLang(i18n.language),
          }}
          options={collectionTags.map((tg) => ({ label: L(tg), value: tg }))}
          value={tags.map((tg) => ({ label: L(tg), value: tg }))}
          onChange={(opts) => setTags(opts.map((o) => o.value))}
        />
      )}
      <ImageUpload
        id={`${idPrefix}-thumbnail`}
        label={imageLabel}
        value={thumbnail}
        onChange={setThumbnail}
        currentUrl={thumbnailUrl}
        folder="oiueei/things"
      />
      <GalleryUpload items={gallery} onChange={setGallery} />
    </>
  );
}
