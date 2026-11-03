import { useState } from 'react';
import { Navigate, useNavigate, useLocation } from 'react-router';
import { useTranslation } from 'react-i18next';
import { TextInput, TextArea, Button } from 'hds-react';
import { apiFetch, extractApiError } from '../services/api';
import PageLayout from '../components/PageLayout';
import CollectionForm from '../components/CollectionForm';
import CollectionAdvancedFields from '../components/CollectionAdvancedFields';
import CollectionModeField from '../components/CollectionModeField';
import useCapabilities, { useCapabilitiesSettled, isOfferable } from '../hooks/useCapabilities';
import LoadingSpinner from '../components/LoadingSpinner';
import LocalizedInfo from '../components/LocalizedInfo';
import { localizedCounter, localizedHelper } from '../utils/localized';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';
import ApprovalNotice from '../components/ApprovalNotice';
import { collectionPath, kindOfPrefix } from '../utils/collectionPath';
import { allowedVerbsFor } from '../utils/collectionKind';
import useDocumentTitle from '../hooks/useDocumentTitle';
import { hasOpeningHours } from '../utils/rental';

/**
 * `/stall/new`, `/library/new` and `/shed/new`: the form for the kind named by the
 * address, which is chosen at `/new` and never changes afterwards. An account the
 * deployment's policy does not give that kind to sees the same "needs approval"
 * line as the chooser, and no form: filling one in would end in a refusal.
 */
export default function CreateCollectionPage() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const { capabilities, settled } = useCapabilitiesSettled();
  const kind = kindOfPrefix(pathname.split('/')[1]);
  if (!kind) return <Navigate to="/new" replace />;
  // Until the deployment has answered, neither form nor notice: showing the form
  // first and swapping it for the notice would throw away what was typed. A failed
  // answer is `null` and settles open, as everywhere else.
  if (!settled) return <LoadingSpinner />;
  if (!isOfferable(capabilities, 'collection_kinds', kind)) {
    return (
      <PageLayout
        title={t(`kinds.${kind}.create`)}
        backTo="/new"
        backLabel={t('createCollection.pageTitle')}
      >
        <ApprovalNotice
          kind="collection_kinds"
          catalogue={[{ value: kind, label: t(`kinds.${kind}.long`) }]}
        />
      </PageLayout>
    );
  }
  return <CreateCollectionForm kind={kind} />;
}

function CreateCollectionForm({ kind }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  useDocumentTitle(t('titles.newCollection'));
  const location = useLocation();
  const backPath = location.state?.backPath || '/';
  const backLabel = location.state?.backLabel || t('common.home');
  const { tc: theeemeColors, btnStyle } = useTheeeme();

  const [headline, setHeadline] = useState('');
  const [description, setDescription] = useState('');
  const [mode, setMode] = useState('PROPRIETARY');
  const [visibility, setVisibility] = useState('PRIVATE');
  const [allowProposals, setAllowProposals] = useState(false);
  // Whether the members of a COMMUNITY stall or library may set a price: on, both of
  // the kind's verbs; off, only the free one.
  const [membersPrice, setMembersPrice] = useState(true);
  const [rentalDurations, setRentalDurations] = useState([]);
  const [rentalWeekdays, setRentalWeekdays] = useState([]);
  const [reservationUnit, setReservationUnit] = useState('DAY');
  const [reservationMaxDays, setReservationMaxDays] = useState(1);
  const [reservationHorizonDays, setReservationHorizonDays] = useState(90);
  const [reservationMaxActivePerMember, setReservationMaxActivePerMember] = useState(10);
  const [reservationAsksPhone, setReservationAsksPhone] = useState(false);
  const [reservationMinMinutes, setReservationMinMinutes] = useState(60);
  const [reservationMaxMinutes, setReservationMaxMinutes] = useState(180);
  const [openingHours, setOpeningHours] = useState({});
  // False while the opening-hours JSON on screen doesn't parse — Create refuses
  // then, rather than sending the last good value and navigating away.
  const [openingHoursValid, setOpeningHoursValid] = useState(true);
  const [closedDates, setClosedDates] = useState('');
  const [homePage, setHomePage] = useState('');
  const [depositPolicy, setDepositPolicy] = useState('');
  // Shown on the request page for every verb that reaches it (LEND/RENT/
  // RESERVE — GIFT/SELL complete from the card and never do), not only
  // reservations — general to the collection, so it lives outside
  // RentalRulesFields / ReservationRulesFields, alongside closed_dates/home_page.
  const [requestInfo, setRequestInfo] = useState('');
  // The owner's note in the emails a requester receives about their request
  // — "received" + "accepted" for every verb, plus RESERVE's auto-confirm —
  // same shape and same placement in the form as requestInfo, one field
  // below it.
  const [emailNote, setEmailNote] = useState('');
  const [tags, setTags] = useState([]);
  const [thumbnail, setThumbnail] = useState('');
  // The group's email language. Defaults to whatever the owner is reading the app
  // in; each member's own preference still wins over it.
  const [language, setLanguage] = useState(i18n.resolvedLanguage || i18n.language);
  // Mirrors the model default (MONTHLY). A new collection mails its members on the
  // owner's behalf, so the owner has to be able to see and change it at the moment
  // they create the group.
  const [digestFrequency, setDigestFrequency] = useState('MONTHLY');
  // The palette of the group's pages. None picked by default: the server draws one of the
  // twelve at random, and the selector says so. The koro starts as the basic wave.
  const [theeeme, setTheeeme] = useState('');
  const [koro, setKoro] = useState('basic');
  const [welcomeDoc, setWelcomeDoc] = useState('');
  const [errors, setErrors] = useState({});

  const ALL_MODE_OPTIONS = [
    {
      label: t('createCollection.modeProprietaryFull'),
      value: 'PROPRIETARY',
    },
    {
      label: t('createCollection.modeCommunityFull'),
      value: 'COMMUNITY',
    },
    {
      label: t('createCollection.modeNetworkFull'),
      value: 'NETWORK',
    },
  ];
  // Both modes upstream. A deployment that withholds one drops it from the
  // group rather than disabling it — an unchoosable radio is noise — and
  // ApprovalNotice below is what says it exists and where to ask for it.
  const capabilities = useCapabilities();
  // A shed is always PROPRIETARY — an operator runs the premises — so it has no
  // mode to choose; a stall and a library choose, and the deployment may narrow it.
  const isReservations = kind === 'SHED';
  // What a kind shows: a reservation is made on the request page, a loan or rental
  // too, but a gift or a sale completes from the card and never reaches it, so the
  // note for that page, the closed days and the rental rules are for the other two.
  const hasRequestPage = kind !== 'STALL';
  // A network is a way for a library to be run: no other kind offers it.
  const KIND_MODE_OPTIONS = ALL_MODE_OPTIONS.filter(
    (opt) => opt.value !== 'NETWORK' || kind === 'LIBRARY'
  );
  const MODE_OPTIONS = KIND_MODE_OPTIONS.filter((opt) =>
    isOfferable(capabilities, 'collection_modes', opt.value)
  );

  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const handleModeChange = (newMode) => {
    if (newMode === mode) return;
    setMode(newMode);
    // The mode does not touch visibility: a new group is private in either mode
    // and only the switch makes it public. Community used to turn
    // the switch on by itself — and again every time it was re-chosen, even after
    // the curator had switched it off — but whoever contributes to a group is
    // never shown whether it is public, so a group of families ended up readable
    // by anyone without its members knowing. The server takes the same view when
    // no visibility is sent (`CollectionCreateSerializer.validate`).
  };

  const validate = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = t('createCollection.titleRequired');
    if (localizedCounter(headline, 64).over) newErrors.headline = t('createCollection.maxHeadline');
    if (localizedCounter(description, 2000).over)
      newErrors.description = t('createCollection.maxDescription');
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    // A toast, not an inline error: the field sits inside the "More options"
    // accordion, which may be collapsed by now, and a refusal whose reason is
    // out of sight would be the silent failure this guards against.
    if (isReservations && reservationUnit === 'HOUR' && !openingHoursValid) {
      setToast({ type: 'error', message: t('openingHours.invalidOnSave') });
      return;
    }
    // An hourly space with no time range can never be booked; the server refuses
    // it too (`opening_hours_required`).
    if (isReservations && reservationUnit === 'HOUR' && !hasOpeningHours(openingHours)) {
      setToast({ type: 'error', message: t('openingHours.requiredOnSave') });
      return;
    }
    setSubmitting(true);
    setToast(null);

    const body = {
      kind,
      headline: headline.trim(),
      mode: isReservations ? 'PROPRIETARY' : mode,
      visibility,
      allow_member_proposals: allowProposals,
      allowed_thing_types: allowedVerbsFor(kind, mode, membersPrice),
      home_page: homePage.trim(),
      email_note: emailNote.trim(),
      tags,
      thumbnail: thumbnail || '',
      language,
      digest_frequency: digestFrequency,
      koro,
      welcome_doc: welcomeDoc || '',
    };
    if (theeeme) body.theeeme = theeeme;
    if (description.trim()) body.description = description.trim();
    if (hasRequestPage) {
      body.closed_dates = closedDates;
      body.request_info = requestInfo.trim();
      body.rental_weekdays = rentalWeekdays;
    }
    if (isReservations) {
      body.reservation_horizon_days = reservationHorizonDays;
      body.reservation_max_active_per_member = reservationMaxActivePerMember;
      body.reservation_asks_phone = reservationAsksPhone;
      body.reservation_unit = reservationUnit;
      if (reservationUnit === 'HOUR') {
        body.reservation_min_minutes = reservationMinMinutes;
        body.reservation_max_minutes = reservationMaxMinutes;
        body.opening_hours = openingHours;
      } else {
        body.reservation_max_days = reservationMaxDays;
      }
    } else if (hasRequestPage) {
      body.rental_durations = rentalDurations;
      if (depositPolicy.trim()) body.deposit_policy = depositPolicy.trim();
    }
    try {
      const res = await apiFetch('/api/v1/collections/', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const data = await res.json();
        navigate(collectionPath(data.code, data.kind));
      } else if (res.status === 429) {
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else {
        const detail = await extractApiError(res);
        setToast({ type: 'error', message: detail || t('createCollection.errorCreating') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <PageLayout backTo={backPath} backLabel={backLabel}>
      <h1 className="page-title-xl">{t(`kinds.${kind}.create`)}</h1>
      <div className="form-grid">
        <TextInput
          id="create-collection-headline"
          label={t('createCollection.titleLabel')}
          value={headline}
          onChange={(e) => setHeadline(e.target.value)}
          required
          invalid={!!errors.headline}
          errorText={errors.headline}
          helperText={localizedHelper(headline, 64, t)}
        />
        <TextArea
          id="create-collection-description"
          label={t('createCollection.descriptionLabel')}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          invalid={!!errors.description}
          errorText={errors.description}
          helperText={localizedHelper(description, 2000, t)}
        />
        <LocalizedInfo id="create-collection-localized-info" />
        {!isReservations && (
          <CollectionModeField
            idPrefix="create-collection"
            label={t('createCollection.modeLabel')}
            options={MODE_OPTIONS}
            catalogue={KIND_MODE_OPTIONS}
            value={mode}
            onChange={handleModeChange}
          />
        )}
        <CollectionForm
          idPrefix="create-collection"
          kind={kind}
          mode={mode}
          visibility={visibility}
          setVisibility={setVisibility}
          allowProposals={allowProposals}
          setAllowProposals={setAllowProposals}
          membersPrice={membersPrice}
          setMembersPrice={setMembersPrice}
          theeemeColor01={theeemeColors.color_01}
        />
      </div>
      <CollectionAdvancedFields
        idPrefix="create-collection"
        colors={theeemeColors}
        isReservations={isReservations}
        hasRequestPage={hasRequestPage}
        tags={tags}
        setTags={setTags}
        reservationRules={{
          reservationUnit,
          setReservationUnit,
          reservationMaxDays,
          setReservationMaxDays,
          reservationHorizonDays,
          setReservationHorizonDays,
          reservationMaxActivePerMember,
          setReservationMaxActivePerMember,
          reservationAsksPhone,
          setReservationAsksPhone,
          reservationMinMinutes,
          setReservationMinMinutes,
          reservationMaxMinutes,
          setReservationMaxMinutes,
          openingHours,
          setOpeningHours,
          setOpeningHoursValid,
          rentalWeekdays,
          setRentalWeekdays,
        }}
        rentalRules={{
          rentalDurations,
          setRentalDurations,
          rentalWeekdays,
          setRentalWeekdays,
          depositPolicy,
          setDepositPolicy,
        }}
        closedDates={closedDates}
        setClosedDates={setClosedDates}
        requestInfo={requestInfo}
        setRequestInfo={setRequestInfo}
        emailNote={emailNote}
        setEmailNote={setEmailNote}
        homePage={homePage}
        setHomePage={setHomePage}
        digestFrequency={digestFrequency}
        setDigestFrequency={setDigestFrequency}
        language={language}
        setLanguage={setLanguage}
        theeeme={theeeme}
        setTheeeme={setTheeeme}
        theeemeHint={t('createCollection.theeemeRandom')}
        koro={koro}
        setKoro={setKoro}
        thumbnail={thumbnail}
        setThumbnail={setThumbnail}
        setWelcomeDoc={setWelcomeDoc}
      />
      <div className="form-actions">
        <Button fullWidth disabled={submitting} onClick={handleSubmit} style={btnStyle}>
          {submitting ? t('common.creating') : t('common.create')}
        </Button>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
