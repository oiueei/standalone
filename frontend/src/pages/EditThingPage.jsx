import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Button } from 'hds-react';
import {
  DATE_TYPES,
  DETAIL_TYPES,
  KIND_THING_TYPES,
  clampUnits,
  deriveThingType,
  kindHasUnits,
  kindOfThingType,
} from '../constants/things';
import { apiFetch, extractApiError } from '../services/api';
import PageLayout from '../components/PageLayout';
import LoadingSpinner from '../components/LoadingSpinner';
import ThingForm from '../components/ThingForm';
import PauseFields from '../components/PauseFields';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';
import useCollectionTheeeme from '../hooks/useCollectionTheeeme';
import useCapabilities, { isOfferable } from '../hooks/useCapabilities';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import { useLocalized, localizedCounter } from '../utils/localized';
import { collectionPath, collectionThingPath } from '../utils/collectionPath';
import { displayToIso, isoToDisplay } from '../utils/rental';
import { membersPriceFromVerbs } from '../utils/collectionKind';
import useDocumentTitle from '../hooks/useDocumentTitle';

export default function EditThingPage() {
  const { t } = useTranslation();
  // Owner content (headlines, tags) may carry one text per language.
  const L = useLocalized();
  const { code, thingCode } = useParams();
  const navigate = useNavigate();
  const userCode = localStorage.getItem('userCode');
  const { tc, btnStyle, btnSecondaryStyle } = useTheeeme();

  const [loading, setLoading] = useState(true);
  const capabilities = useCapabilities();
  // The verb as the server has it. The form never edits it — the server puts it from
  // the collection's kind and the price — but it says which kind of thing this is
  // (a thing a mixed collection kept from the other family, say) and whether a
  // verb the policy withholds would be a *change* or just what it already is.
  const [savedType, setSavedType] = useState(null);
  // The allowlist of its collection, only to tell whether members may set a price.
  const [collectionAllowedTypes, setCollectionAllowedTypes] = useState([]);
  const [headline, setHeadline] = useState('');
  useDocumentTitle(
    headline ? t('titles.editThing', { headline: L(headline) }) : t('titles.editThingDefault')
  );
  const [description, setDescription] = useState('');
  const [thumbnail, setThumbnail] = useState('');
  const [thumbnailUrl, setThumbnailUrl] = useState('');
  const [fee, setFee] = useState('');
  const [deposit, setDeposit] = useState('');
  const [availability, setAvailability] = useState('');
  const [location, setLocation] = useState('');
  const [condition, setCondition] = useState('');
  const [isEndless, setIsEndless] = useState(false);
  const [units, setUnits] = useState(1);
  // The pause: on or off, its two days as the date inputs hold them (DD/MM/YYYY), what
  // the server said about each, and the bookings the manager already receives, which
  // the warning before saving counts.
  const [pauseOn, setPauseOn] = useState(false);
  const [pauseFrom, setPauseFrom] = useState('');
  const [pauseUntil, setPauseUntil] = useState('');
  const [pauseErrors, setPauseErrors] = useState({});
  const [bookings, setBookings] = useState([]);
  const [gallery, setGallery] = useState([]);
  const [tags, setTags] = useState([]);
  const [collectionTags, setCollectionTags] = useState([]);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);
  const [thingCollectionCode, setThingCollectionCode] = useState(code || '');
  const [thingCollectionKind, setThingCollectionKind] = useState('');
  const [isNetwork, setIsNetwork] = useState(false);
  const [thingCollectionHeadline, setThingCollectionHeadline] = useState('');
  const [thingCollectionLanguage, setThingCollectionLanguage] = useState('');
  // The texts as loaded, not the live draft: typing must not flip the page's
  // language under the editor's hands.
  const [loadedTexts, setLoadedTexts] = useState([]);
  useCollectionLanguage(thingCollectionLanguage, loadedTexts);
  // The colours of the collection the thing is read through, as loaded.
  const [thingPalette, setThingPalette] = useState(null);
  useCollectionTheeeme(thingPalette?.colors, thingPalette?.koro);

  useEffect(() => {
    const fetchThing = async () => {
      try {
        const res = await apiFetch(`/api/v1/things/${thingCode}/`);
        if (res.ok) {
          const data = await res.json();
          setSavedType(data.type);
          setHeadline(data.headline || '');
          setDescription(data.description || '');
          setThumbnail(data.thumbnail || '');
          setThumbnailUrl(data.thumbnail_url || '');
          setFee(data.fee != null ? data.fee : '');
          setDeposit(data.deposit != null ? data.deposit : '');
          setAvailability(data.availability || '');
          setLocation(data.location || '');
          setCondition(data.condition || '');
          if (data.gallery && data.gallery.length) {
            const urls = data.gallery_urls || [];
            setGallery(data.gallery.map((publicId, i) => ({ publicId, url: urls[i] })));
          }
          if (data.tags) setTags(data.tags);
          if (data.collection_tags) setCollectionTags(data.collection_tags);
          if (data.is_endless) setIsEndless(true);
          setUnits(data.units || 1);
          // A pause in force comes back with its days; one that has passed comes back empty.
          if (data.paused_from && data.paused_until) {
            setPauseOn(true);
            setPauseFrom(isoToDisplay(data.paused_from));
            setPauseUntil(isoToDisplay(data.paused_until));
          }
          setBookings(data.bookings || []);
          if (!code && data.collection_code) setThingCollectionCode(data.collection_code);
          if (data.collection_headline) setThingCollectionHeadline(data.collection_headline);
          setThingCollectionKind(data.collection_kind || '');
          setIsNetwork(data.collection_mode === 'NETWORK');
          setCollectionAllowedTypes(data.collection_allowed_thing_types || []);
          setThingCollectionLanguage(data.collection_language || '');
          setThingPalette({
            colors: data.collection_theeeme_colors,
            koro: data.collection_koro,
          });
          setLoadedTexts([data.headline, data.description]);
        } else {
          setToast({ type: 'error', messageKey: 'editThing.errorLoading' });
        }
      } catch {
        setToast({ type: 'error', messageKey: 'common.connectionError' });
      } finally {
        setLoading(false);
      }
    };
    fetchThing();
    // No `t`: the failure toasts carry a key (`Toast` translates it). This load
    // *sets every field of the form*, and `useCollectionLanguage` swaps `t` once
    // its response lands — listing it re-ran the load and wrote the server's copy
    // over anything the editor had typed in the meantime.
  }, [userCode, thingCode, navigate, code]);

  // What the form is for. A thing is a stall's, a library's or a shed's by its
  // collection — except one a mixed collection kept from the other family at the
  // migration, which keeps its own verb (the server leaves it as it is) and is
  // edited as what it is.
  const isStray =
    !!savedType &&
    !!thingCollectionKind &&
    !KIND_THING_TYPES[thingCollectionKind]?.includes(savedType);
  const kind = isStray
    ? kindOfThingType(savedType)
    : thingCollectionKind || kindOfThingType(savedType) || 'STALL';
  // Only a thing with a calendar (a loan, a rental, a reservation space) can be paused.
  const hasCalendar = DATE_TYPES.includes(savedType);
  // The verb the price makes now (a stray's does not follow it).
  const type = isStray ? savedType : deriveThingType(kind, fee);
  // A community stall or library whose members may not set a price lists only its free
  // verb: there is no price to edit, as there was none to give.
  const priceAllowed = membersPriceFromVerbs(thingCollectionKind, collectionAllowedTypes);
  // A thing already offered under a verb this deployment has stopped handing out stays
  // editable, as the server allows: it only refuses a *change* into a withheld one,
  // so the stored verb is never withheld here.
  const notOffered = type !== savedType && !isOfferable(capabilities, 'thing_types', type);

  const returnPath = thingCollectionCode
    ? collectionPath(thingCollectionCode, thingCollectionKind)
    : '/';
  const returnLabel =
    L(thingCollectionHeadline) || (thingCollectionCode ? t('common.collection') : t('common.home'));

  const validate = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = t('addThing.titleRequired');
    if (localizedCounter(headline, 64).over) newErrors.headline = t('addThing.maxHeadline');
    if (localizedCounter(description, 2000).over)
      newErrors.description = t('addThing.maxDescription');
    if (location.length > 64) newErrors.location = t('addThing.maxLocation');
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);
    setToast(null);
    setPauseErrors({});

    // No `type`: the server puts the verb, and puts it back in step when the price
    // changes. Sending the one it already has would be harmless; sending a derived
    // one over a thing a mixed collection kept from the other family would not.
    const body = { headline: headline.trim() };
    body.description = description.trim() || '';
    body.thumbnail = thumbnail || '';
    // Clearing the price has to be said: it is what turns a sale back into a gift.
    if (priceAllowed) body.fee = fee === '' ? null : fee;
    // Always explicit, never omitted: the server judges the row that lands, so a
    // deposit that is still stored has to be cleared in the same request as whatever
    // makes it meaningless (core/serializers/CLAUDE.md — "the one field with a type
    // rule"). Only a library's things carry one.
    body.deposit = kind === 'LIBRARY' && deposit !== '' ? deposit : null;
    if (DETAIL_TYPES.includes(type)) {
      // A library's and a shed's things show live availability, not this static
      // hint — clear any value a previous verb left stored so a dormant
      // "IMMEDIATE" can't outlive what it belonged to.
      body.availability = DATE_TYPES.includes(type) ? '' : availability || '';
      // In a network the column is left as it is: the pickup point says where.
      if (!isNetwork) body.location = location.trim();
      body.condition = condition || '';
    }
    body.gallery = gallery.map((g) => g.publicId);
    body.tags = tags;
    if (kind === 'STALL') {
      body.is_endless = isEndless;
    }
    // Only a shed's space and a library's thing have several identical ones.
    if (kindHasUnits(kind)) body.units = clampUnits(units);
    // Only a thing with a calendar can be paused. Off sends both days empty: that is
    // what takes a pause off.
    if (hasCalendar) {
      body.paused_from = pauseOn ? displayToIso(pauseFrom) || null : null;
      body.paused_until = pauseOn ? displayToIso(pauseUntil) || null : null;
    }

    try {
      const res = await apiFetch(`/api/v1/things/${thingCode}/`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate(returnPath);
      } else if (res.status === 429) {
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else {
        // What the server says about a day of the pause belongs on that day's field.
        const fields = await res
          .clone?.()
          ?.json?.()
          .catch(() => null);
        const first = (value) => (Array.isArray(value) ? value[0] : value);
        if (fields && (fields.paused_from || fields.paused_until)) {
          setPauseErrors({ from: first(fields.paused_from), until: first(fields.paused_until) });
        } else {
          const detail = await extractApiError(res);
          setToast({ type: 'error', message: detail || t('editThing.errorSaving') });
        }
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  return (
    <PageLayout backTo={returnPath} backLabel={returnLabel}>
      <h1 className="page-title-xl">{t('editThing.pageTitle')}</h1>
      <div className="form-grid">
        <ThingForm
          idPrefix="edit-thing"
          theeemeColor01={tc.color_01}
          errors={errors}
          kind={kind}
          type={type}
          priceAllowed={priceAllowed}
          verbFollowsPrice={!!thingCollectionKind && !isStray}
          approvalCatalogue={notOffered ? [{ label: t('types.' + type), value: type }] : []}
          isEndless={isEndless}
          setIsEndless={setIsEndless}
          units={units}
          setUnits={setUnits}
          headline={headline}
          setHeadline={setHeadline}
          description={description}
          setDescription={setDescription}
          fee={fee}
          setFee={setFee}
          feeStep={0.01}
          deposit={deposit}
          setDeposit={setDeposit}
          depositStep={0.01}
          availability={availability}
          setAvailability={setAvailability}
          condition={condition}
          setCondition={setCondition}
          location={location}
          setLocation={setLocation}
          askLocation={!isNetwork}
          collectionTags={collectionTags}
          tags={tags}
          setTags={setTags}
          imageLabel={t('upload.thumbnailLabel')}
          thumbnail={thumbnail}
          setThumbnail={setThumbnail}
          thumbnailUrl={thumbnailUrl}
          gallery={gallery}
          setGallery={setGallery}
        />
        {hasCalendar && (
          <PauseFields
            idPrefix="edit-thing"
            theeemeColor01={tc.color_01}
            enabled={pauseOn}
            setEnabled={setPauseOn}
            from={pauseFrom}
            setFrom={setPauseFrom}
            until={pauseUntil}
            setUntil={setPauseUntil}
            errors={pauseErrors}
            bookings={bookings}
          />
        )}
      </div>
      <div className="form-actions">
        <Button
          fullWidth
          disabled={submitting || notOffered}
          onClick={handleSubmit}
          style={btnStyle}
        >
          {submitting ? t('common.saving') : t('common.save')}
        </Button>
        <Button
          variant="secondary"
          fullWidth
          disabled={submitting}
          onClick={() => {
            const deletePath = thingCollectionCode
              ? collectionThingPath(thingCollectionCode, thingCollectionKind, thingCode, '/delete')
              : `/things/${thingCode}/delete`;
            navigate(deletePath, { state: { backPath: returnPath, backLabel: returnLabel } });
          }}
          style={{ ...btnSecondaryStyle, marginTop: 'var(--spacing-s)' }}
        >
          {t('common.delete')}
        </Button>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
