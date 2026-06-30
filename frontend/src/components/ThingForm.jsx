import { Select, TextInput, TextArea, NumberInput, ToggleButton } from 'hds-react';
import { useTranslation } from 'react-i18next';
import { FEE_TYPES, DETAIL_TYPES, AVAILABILITY_VALUES, CONDITION_VALUES } from '../constants/things';
import ImageUpload from './ImageUpload';
import GalleryUpload from './GalleryUpload';
import DocumentUpload from './DocumentUpload';

/**
 * The shared field cluster of the Add and Edit thing forms: type selector, the
 * endless / notify-group toggles, headline, description, fee, the
 * availability/condition/location detail fields, the per-thing tags select, the
 * thumbnail upload and gallery + documents.
 *
 * Controlled: each value + setter is owned by the page. Field visibility is
 * derived from `type` so both pages share one set of rules. The page supplies
 * the already filtered `typeOptions` and whether the selector is shown (Add
 * hides it for swap/share collections). `idPrefix` is `add-thing` or `edit-thing`.
 */
export default function ThingForm({
  idPrefix,
  theeemeColor01,
  errors,
  typeOptions,
  showTypeSelector = true,
  type,
  setType,
  isEndless,
  setIsEndless,
  showNotifyGroup = false,
  notifyGroup,
  setNotifyGroup,
  headline,
  setHeadline,
  description,
  setDescription,
  fee,
  setFee,
  feeStep,
  availability,
  setAvailability,
  condition,
  setCondition,
  location,
  setLocation,
  collectionTags = [],
  tags,
  setTags,
  imageLabel,
  thumbnail,
  setThumbnail,
  thumbnailUrl,
  gallery,
  setGallery,
  documents,
  setDocuments,
}) {
  const { t } = useTranslation();
  const toggleTheme = theeemeColor01 ? { '--toggle-button-color': `var(--color-${theeemeColor01})` } : undefined;

  const showEndless = ['GIFT_THING', 'SELL_THING'].includes(type);
  const isFeeType = FEE_TYPES.includes(type);
  const isDetailType = DETAIL_TYPES.includes(type);
  const showFee = isFeeType;
  const showSpacer = isFeeType && isDetailType;
  const showDetailFields = isDetailType;

  return (
    <>
      {showTypeSelector && (
        <Select
          language="en"
          id={`${idPrefix}-type`}
          texts={{ label: t('addThing.typeLabel') }}
          options={typeOptions}
          value={type}
          onChange={(selectedOptions) => {
            if (selectedOptions.length > 0) {
              setType(selectedOptions[0].value);
            }
          }}
        />
      )}
      {showEndless && (
        <div className="toggle-left">
          <ToggleButton
            id={`${idPrefix}-is-endless`}
            label={t('endless.label')}
            checked={isEndless}
            onChange={(val) => setIsEndless(!val)}
            variant="inline"
            theme={toggleTheme}
          />
        </div>
      )}
      {showNotifyGroup && (
        <div className="toggle-left">
          <ToggleButton
            id={`${idPrefix}-notify-group`}
            label={t('wishes.notifyGroup')}
            checked={notifyGroup}
            onChange={(val) => setNotifyGroup(!val)}
            variant="inline"
            theme={toggleTheme}
          />
        </div>
      )}
      <TextInput
        id={`${idPrefix}-headline`}
        label={t('addThing.titleLabel')}
        value={headline}
        onChange={(e) => setHeadline(e.target.value)}
        required
        invalid={!!errors.headline}
        errorText={errors.headline}
        helperText={`${headline.length}/64`}
      />
      <TextArea
        id={`${idPrefix}-description`}
        label={t('addThing.descriptionLabel')}
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        helperText={`${description.length}/256`}
      />
      {showFee && (
        <NumberInput
          id={`${idPrefix}-fee`}
          label={t('addThing.priceLabel')}
          value={fee === '' ? '' : Number(fee)}
          onChange={(e) => setFee(e.target.value)}
          min={0}
          step={feeStep}
          unit="EUR"
          required
          invalid={!!errors.fee}
          errorText={errors.fee}
        />
      )}
      {showSpacer && (
        <div className="spacer-xxxx" />
      )}
      {showDetailFields && (
        <>
          <Select
            language="en"
            id={`${idPrefix}-availability`}
            texts={{ label: t('addThing.availabilityLabel') }}
            options={AVAILABILITY_VALUES.map((v) => ({ label: t('availability.' + v), value: v }))}
            value={availability}
            onChange={(sel) => setAvailability(sel.length > 0 ? sel[0].value : '')}
            clearable
          />
          <Select
            language="en"
            id={`${idPrefix}-condition`}
            texts={{ label: t('addThing.conditionLabel') }}
            options={CONDITION_VALUES.map((v) => ({ label: t('condition.' + v), value: v }))}
            value={condition}
            onChange={(sel) => setCondition(sel.length > 0 ? sel[0].value : '')}
            clearable
          />
          <TextInput
            id={`${idPrefix}-location`}
            label={t('addThing.locationLabel')}
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            helperText={`${location.length}/32`}
            invalid={!!errors.location}
            errorText={errors.location}
          />
        </>
      )}
      {collectionTags.length > 0 && (
        <Select
          language="en"
          multiSelect
          id={`${idPrefix}-tags`}
          texts={{
            label: t('addThing.tagsLabel'),
            placeholder: t('addThing.tagsPlaceholder'),
            assistive: t('addThing.tagsHelper'),
          }}
          options={collectionTags.map((tg) => ({ label: tg, value: tg }))}
          value={tags.map((tg) => ({ label: tg, value: tg }))}
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
      <DocumentUpload
        documents={documents}
        onChange={setDocuments}
      />
    </>
  );
}
