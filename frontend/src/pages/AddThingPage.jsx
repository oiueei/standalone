import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Button, Notification } from 'hds-react';
import { DETAIL_TYPES, clampUnits, deriveThingType } from '../constants/things';
import { membersPriceFromVerbs } from '../utils/collectionKind';
import { apiFetch, extractApiError } from '../services/api';
import PageLayout from '../components/PageLayout';
import ThingForm from '../components/ThingForm';
import DemoNotice from '../components/DemoNotice';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';
import useCollectionTheeeme from '../hooks/useCollectionTheeeme';
import LoadingSpinner from '../components/LoadingSpinner';
import useCapabilities, { isOfferable } from '../hooks/useCapabilities';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import { useLocalized, localizedCounter } from '../utils/localized';
import { useCollectionBase } from '../hooks/useCollectionBase';
import useDocumentTitle from '../hooks/useDocumentTitle';

export default function AddThingPage() {
  const { t } = useTranslation();
  // Owner content (headlines, tags) may carry one text per language.
  const L = useLocalized();
  const { code } = useParams();
  const base = useCollectionBase(code);
  const navigate = useNavigate();

  const userCode = localStorage.getItem('userCode');
  useDocumentTitle(t('titles.addThing'));

  const [collectionHeadline, setCollectionHeadline] = useState('');
  // What the collection is, and so how its things take their verb. Until it has
  // loaded the form is a stall's, the kind with the fewest fields.
  const [kind, setKind] = useState('STALL');
  const [headline, setHeadline] = useState('');
  const [description, setDescription] = useState('');
  const [thumbnail, setThumbnail] = useState('');
  const [fee, setFee] = useState('');
  const [deposit, setDeposit] = useState('');
  const [availability, setAvailability] = useState('');
  const [location, setLocation] = useState('');
  const [condition, setCondition] = useState('');
  const [isEndless, setIsEndless] = useState(false);
  const [units, setUnits] = useState(1);
  const [gallery, setGallery] = useState([]);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const capabilities = useCapabilities();
  const [collectionAllowedTypes, setCollectionAllowedTypes] = useState([]);
  const [isNetwork, setIsNetwork] = useState(false);
  const [collectionTags, setCollectionTags] = useState([]);
  // A community group whose members may not set a price lists only its free verb: the
  // form has no price field there, since a price would only be refused.
  const priceAllowed = membersPriceFromVerbs(kind, collectionAllowedTypes);
  // A member contributing to a COMMUNITY collection they were invited to may
  // offer any type its (vetted) owner allow-listed, whatever this deployment's
  // creator policy says about them personally — the same exception the backend
  // applies in `community_contribution_types` (core/services/creator_policy).
  const [contributingToCommunity, setContributingToCommunity] = useState(false);
  const [isOnboarding, setIsOnboarding] = useState(false);
  const [tags, setTags] = useState([]);
  const [collectionLanguage, setCollectionLanguage] = useState('');
  useCollectionLanguage(collectionLanguage, [collectionHeadline]);
  // The form is the group's: it wears the group's colours and is not painted before the
  // collection has answered (the app's palette would show for an instant). A collection
  // that cannot be read settles with no palette, and the form stays on the app's.
  const [palette, setPalette] = useState(null);
  const [settled, setSettled] = useState(!userCode);
  useCollectionTheeeme(palette?.colors, palette?.koro);

  // The verb the price makes, in the collection's kind, and whether this account may
  // offer it: the deployment's policy is asked about the verb the thing will take, not
  // about one a form selector used to pick — a price in a stall is a sale, and a policy
  // that does not give sales shows its notice here instead of letting it be sent.
  // A member contributing to a COMMUNITY group may offer what its (vetted) owner
  // allow-listed whatever the policy says of them personally.
  const type = deriveThingType(kind, fee);
  const notOffered =
    !(contributingToCommunity && collectionAllowedTypes.includes(type)) &&
    !isOfferable(capabilities, 'thing_types', type);

  useEffect(() => {
    if (!userCode) return;
    apiFetch(`/api/v1/collections/${code}/`)
      .then((res) => {
        if (res.ok) return res.json();
        // The form stays (the server is the gate), but it is the form of a stall
        // until the collection is read: say so rather than let it pass for the real one.
        setToast({ type: 'error', messageKey: 'collectionPage.errorLoading' });
        return {};
      })
      .then((data) => {
        setCollectionHeadline(data.headline || '');
        const allowed = data.allowed_thing_types || [];
        setKind(data.kind || 'STALL');
        setCollectionAllowedTypes(allowed);
        setIsNetwork(data.mode === 'NETWORK');
        setContributingToCommunity(data.mode === 'COMMUNITY' && !!data.is_member);
        setIsOnboarding(!!data.is_onboarding);
        setCollectionTags(data.tags || []);
        setCollectionLanguage(data.language || '');
        setPalette({ colors: data.theeeme_colors, koro: data.koro });
      })
      .catch(() => setToast({ type: 'error', messageKey: 'common.connectionError' }))
      .finally(() => setSettled(true));
  }, [userCode, code]);

  const computeErrors = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = t('addThing.titleRequired');
    else if (localizedCounter(headline, 64).over) newErrors.headline = t('addThing.maxHeadline');
    if (localizedCounter(description, 2000).over)
      newErrors.description = t('addThing.maxDescription');
    if (location.length > 64) newErrors.location = t('addThing.maxLocation');
    return newErrors;
  };

  // Errors surface only after the first submit attempt, then recompute on every
  // render so fixing a field clears its error immediately (live validation).
  const errors = submitAttempted ? computeErrors() : {};

  const handleSubmit = async () => {
    setSubmitAttempted(true);
    if (Object.keys(computeErrors()).length > 0) return;
    setSubmitting(true);
    setToast(null);

    // No `type`: the server puts the verb from the collection's kind and the price.
    const body = {
      headline: headline.trim(),
      collection_code: code,
    };
    if (thumbnail) body.thumbnail = thumbnail;
    if (description.trim()) body.description = description.trim();
    if (priceAllowed && fee !== '') {
      body.fee = fee;
    }
    if (kind === 'LIBRARY' && deposit !== '') {
      body.deposit = deposit;
    }
    if (DETAIL_TYPES.includes(type)) {
      if (availability) body.availability = availability;
      if (!isNetwork && location.trim()) body.location = location.trim();
      if (condition) body.condition = condition;
    }
    if (gallery.length > 0) {
      body.gallery = gallery.map((g) => g.publicId);
    }
    if (tags.length > 0) {
      body.tags = tags;
    }
    if (kind === 'STALL' && isEndless) {
      body.is_endless = true;
    }
    // Only a shed's space has several identical ones.
    if (kind === 'SHED') body.units = clampUnits(units);
    try {
      const res = await apiFetch('/api/v1/things/', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        // The new thing's code rides along in the navigation state: on a phone the
        // collection page tells the person it worked and takes them to the card
        // — the hero fills the screen and nothing of the upload
        // is in sight. The page ignores it on a desktop. A response without a code
        // simply sends no state.
        const created = await res.json().catch(() => null);
        navigate(`${base}`, created?.code ? { state: { addedThing: created.code } } : undefined);
      } else if (res.status === 429) {
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else {
        const detail = await extractApiError(res);
        setToast({ type: 'error', message: detail || t('addThing.errorCreating') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setSubmitting(false);
    }
  };

  // Theeeme colors from localStorage (set by HomePage on login)
  const { tc, btnStyle } = useTheeeme();

  if (!settled) return <LoadingSpinner />;

  return (
    <PageLayout backTo={`${base}`} backLabel={L(collectionHeadline) || t('common.collection')}>
      <h1 className="page-title-xl">{t('addThing.pageTitle')}</h1>
      {isOnboarding && <DemoNotice />}
      <div className="form-grid">
        <ThingForm
          idPrefix="add-thing"
          theeemeColor01={tc.color_01}
          errors={errors}
          kind={kind}
          type={type}
          priceAllowed={priceAllowed}
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
          deposit={deposit}
          setDeposit={setDeposit}
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
          gallery={gallery}
          setGallery={setGallery}
        />
      </div>

      <div className="form-actions">
        <Button
          style={{ ...btnStyle, width: '100%' }}
          disabled={submitting || notOffered}
          onClick={handleSubmit}
        >
          {submitting ? t('common.creating') : t('common.create')}
        </Button>
      </div>

      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
