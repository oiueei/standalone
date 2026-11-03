import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import { TextInput, TextArea, Select, Button } from 'hds-react';
import { apiFetch, extractApiError } from '../services/api';
import PageLayout from '../components/PageLayout';
import CollectionForm from '../components/CollectionForm';
import CollectionAdvancedFields from '../components/CollectionAdvancedFields';
import CollectionModeField from '../components/CollectionModeField';
import useCapabilities, { isOfferable } from '../hooks/useCapabilities';
import LocalizedInfo from '../components/LocalizedInfo';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';
import useCollectionTheeeme from '../hooks/useCollectionTheeeme';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import { useLocalized, localizedCounter, localizedHelper } from '../utils/localized';
import { closedDatesToDisplay, hasOpeningHours } from '../utils/rental';
import hdsLang from '../utils/hdsLang';
import EmailNoteTest from '../components/EmailNoteTest';
import { useCollectionBase } from '../hooks/useCollectionBase';
import { allowedVerbsFor, membersPriceFromVerbs } from '../utils/collectionKind';
import useDocumentTitle from '../hooks/useDocumentTitle';

export default function EditCollectionPage() {
  const { t, i18n } = useTranslation();
  // The form holds the raw value (the owner edits the map itself); only the
  // page title and the back label show the resolved words.
  const L = useLocalized();
  const { code } = useParams();
  const base = useCollectionBase(code);
  const navigate = useNavigate();
  const userCode = localStorage.getItem('userCode');
  const { tc, btnStyle, btnSecondaryStyle } = useTheeeme();
  const [loading, setLoading] = useState(true);
  const [headline, setHeadline] = useState('');
  useDocumentTitle(
    headline
      ? t('titles.editCollection', { headline: L(headline) })
      : t('titles.editCollectionDefault')
  );
  const [description, setDescription] = useState('');
  const [status, setStatus] = useState('ACTIVE');
  const [mode, setMode] = useState('PROPRIETARY');
  // The mode as the server has it, which is **not** `mode` once the user starts
  // picking. It is what `isOfferable` needs: the server judges only a *change*,
  // so the stored mode is always submittable, while the one currently selected
  // in the form carries no such promise. Keying the filter on `mode` made a
  // withheld-but-stored option vanish the moment anything else was clicked,
  // stranding the owner on a form that could no longer express what they had.
  const [savedMode, setSavedMode] = useState(null);
  const [visibility, setVisibility] = useState('PRIVATE');
  const [allowProposals, setAllowProposals] = useState(true);
  const [digestFrequency, setDigestFrequency] = useState('NONE');
  // The kind is the collection's own and never changes: the page shows it as a fact
  // about the collection and sends it nowhere.
  const [kind, setKind] = useState('');
  // Whether the members of a COMMUNITY stall or library may set a price (both of the
  // kind's verbs stored) or only give and lend (the free verb alone).
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
  // False while the opening-hours JSON on screen doesn't parse — Save refuses
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
  const [thumbnailUrl, setThumbnailUrl] = useState('');
  // The palette of the group's pages, as saved and as being picked.
  const [theeeme, setTheeeme] = useState('');
  const [koro, setKoro] = useState('basic');
  const [language, setLanguage] = useState('');
  // The collection's actual stored language, as loaded — never the live-edited
  // `language` draft above, which defaults to the browser's own language the
  // moment the field is blank and would otherwise flip this whole settings
  // form's own UI language as the owner merely tries options in the dropdown,
  // before saving anything.
  const [savedLanguage, setSavedLanguage] = useState('');
  // Likewise the owner's texts as saved, not as being typed.
  const [savedTexts, setSavedTexts] = useState([]);
  useCollectionLanguage(savedLanguage, savedTexts);
  // The page wears the palette the group has *saved*, not the one being picked in the form:
  // trying options must not repaint the page under the curator's hands.
  const [savedPalette, setSavedPalette] = useState(null);
  useCollectionTheeeme(savedPalette?.colors, savedPalette?.koro);
  const [welcomeDoc, setWelcomeDoc] = useState('');
  const [welcomeDocUrl, setWelcomeDocUrl] = useState('');
  const [pauseMessage, setPauseMessage] = useState('');
  const [isPaused, setIsPaused] = useState(false);
  // The one control on this page still stricter than "the server enforces
  // it": deleting the collection is deliberately not a co-owner power, and
  // the button isn't worth showing to someone the server would refuse.
  // Everything else here (save, pause) already carries no client-side gate at
  // all — a co-owner reaching this page saves exactly as the founder would, no
  // change needed.
  const [ownerCode, setOwnerCode] = useState(null);
  const isOwner = userCode === ownerCode;
  const [pauseSubmitting, setPauseSubmitting] = useState(false);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const STATUS_OPTIONS = [
    { label: t('editCollection.statusActive'), value: 'ACTIVE' },
    { label: t('editCollection.statusInactive'), value: 'INACTIVE' },
  ];

  const ALL_MODE_OPTIONS = [
    {
      label: t('createCollection.modeProprietaryFull'),
      value: 'PROPRIETARY',
    },
    {
      label: t('createCollection.modeCommunityFull'),
      value: 'COMMUNITY',
    },
  ];
  // A network is fixed at creation: it is shown, not chosen, and no other collection
  // can become one (the server refuses both). Its mode is a sentence, not a radio.
  const isNetwork = savedMode === 'NETWORK';
  // `savedMode` — not `mode` — is the current value here: a collection opened
  // before this deployment narrowed still shows the mode it is in, and keeps
  // showing it while the owner tries the alternatives. The server only judges a
  // change; a form that hid the stored answer would submit a wrong one.
  const capabilities = useCapabilities();
  // A shed is always PROPRIETARY, so it has no mode to change; a gift or a sale
  // completes from the card and never reaches the request page, so the note for that
  // page, the closed days and the rental rules are for a library and a shed.
  const isReservations = kind === 'SHED';
  const hasRequestPage = kind === 'LIBRARY' || kind === 'SHED';
  const MODE_OPTIONS = ALL_MODE_OPTIONS.filter((opt) =>
    isOfferable(capabilities, 'collection_modes', opt.value, savedMode)
  );

  const DIGEST_OPTIONS = [
    { label: t('editCollection.digestNone'), value: 'NONE' },
    { label: t('editCollection.digestWeekly'), value: 'WEEKLY' },
    { label: t('editCollection.digestMonthly'), value: 'MONTHLY' },
  ];

  const handleModeChange = (newMode) => {
    if (newMode === mode) return;
    setMode(newMode);
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const collectionRes = await apiFetch(`/api/v1/collections/${code}/`);

        if (collectionRes.ok) {
          const data = await collectionRes.json();
          setOwnerCode(data.owner || null);
          setHeadline(data.headline || '');
          setDescription(data.description || '');
          setStatus(data.status || 'ACTIVE');
          setMode(data.mode || 'PROPRIETARY');
          setSavedMode(data.mode || 'PROPRIETARY');
          setVisibility(data.visibility || 'PRIVATE');
          // `?? true` rather than `||`: the field is a boolean, and a genuine
          // `false` (the owner turned recommendations off) must survive the load
          // instead of springing back on at the next save.
          setAllowProposals(data.allow_member_proposals ?? true);
          setDigestFrequency(data.digest_frequency || 'NONE');
          setKind(data.kind || '');
          setMembersPrice(membersPriceFromVerbs(data.kind, data.allowed_thing_types));
          setRentalDurations(data.rental_durations || []);
          setRentalWeekdays(data.rental_weekdays || []);
          setReservationUnit(data.reservation_unit || 'DAY');
          setReservationMaxDays(data.reservation_max_days || 1);
          setReservationHorizonDays(data.reservation_horizon_days || 90);
          setReservationMaxActivePerMember(data.reservation_max_active_per_member || 10);
          setReservationAsksPhone(!!data.reservation_asks_phone);
          setReservationMinMinutes(data.reservation_min_minutes || 60);
          setReservationMaxMinutes(data.reservation_max_minutes || 180);
          setOpeningHours(data.opening_hours || {});
          setClosedDates(closedDatesToDisplay(data.closed_dates));
          setHomePage(data.home_page || '');
          setDepositPolicy(data.deposit_policy || '');
          setRequestInfo(data.request_info || '');
          setEmailNote(data.email_note || '');
          setTags(data.tags || []);
          setThumbnail(data.thumbnail || '');
          setThumbnailUrl(data.thumbnail_url || '');
          // Blank = inherit the deployment default; the members' own preference
          // still wins over whatever the owner picks here.
          setLanguage(data.language || i18n.resolvedLanguage || i18n.language);
          setSavedLanguage(data.language || '');
          setSavedPalette({ colors: data.theeeme_colors, koro: data.koro });
          setTheeeme(data.theeeme || '');
          setKoro(data.koro || 'basic');
          setSavedTexts([data.headline, data.description]);
          setWelcomeDoc(data.welcome_doc || '');
          setWelcomeDocUrl(data.welcome_doc_url || '');
          setPauseMessage(data.pause_message || '');
          setIsPaused(data.is_paused || false);
        } else {
          setToast({ type: 'error', messageKey: 'editCollection.errorLoading' });
        }
      } catch {
        setToast({ type: 'error', messageKey: 'common.connectionError' });
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    // Mount-once on purpose, like EditProfilePage's load: `t` and `i18n` change
    // whenever the language does, and `useCollectionLanguage` changes it as soon as
    // this very response lands — listing them re-ran the load, which *sets every
    // field of the form*, over anything typed in the meantime. The failure toasts
    // carry a key (`Toast` translates it), and `i18n` is read once, above, for the
    // draft language's default — a starting value, not something to track.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userCode, code, navigate]);

  const validate = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = t('editCollection.titleRequired');
    if (localizedCounter(headline, 64).over) newErrors.headline = t('editCollection.maxHeadline');
    if (localizedCounter(description, 2000).over)
      newErrors.description = t('editCollection.maxDescription');
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
      headline: headline.trim(),
      description: description.trim(),
      status,
      mode,
      visibility,
      allow_member_proposals: allowProposals,
      digest_frequency: digestFrequency,
      allowed_thing_types: allowedVerbsFor(kind, mode, membersPrice),
      home_page: homePage.trim(),
      email_note: emailNote.trim(),
      tags,
      thumbnail: thumbnail || '',
      language,
      koro,
      welcome_doc: welcomeDoc || '',
    };
    if (theeeme) body.theeeme = theeeme;
    if (hasRequestPage) {
      body.closed_dates = closedDates;
      body.request_info = requestInfo.trim();
      body.rental_weekdays = rentalWeekdays;
      body.rental_durations = isReservations ? [] : rentalDurations;
      body.deposit_policy = isReservations ? '' : depositPolicy.trim();
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
    }

    try {
      const res = await apiFetch(`/api/v1/collections/${code}/`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate(`${base}`);
      } else if (res.status === 429) {
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else if (res.status === 400) {
        // Surface the backend's own message — it names the offending types when
        // narrowing would orphan things, the bad token / far-future date when
        // `closed_dates` is rejected, etc. — so the owner can act on it.
        const message = await extractApiError(res);
        setToast({ type: 'error', message: message || t('editCollection.errorSaving') });
      } else {
        setToast({ type: 'error', message: t('editCollection.errorSaving') });
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

  const handlePauseToggle = async () => {
    setPauseSubmitting(true);
    setToast(null);
    const newMessage = isPaused ? '' : pauseMessage.trim();
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/`, {
        method: 'PATCH',
        body: JSON.stringify({ pause_message: newMessage }),
      });
      if (res.ok) {
        setIsPaused(!isPaused);
        if (isPaused) setPauseMessage('');
        setToast({ type: 'success', message: isPaused ? t('pause.resumed') : t('pause.paused') });
      } else {
        setToast({ type: 'error', message: t('common.error') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setPauseSubmitting(false);
    }
  };

  return (
    <PageLayout backTo={`${base}`} backLabel={L(headline) || t('common.collection')}>
      <h1 className="page-title-xl">{t('editCollection.pageTitle')}</h1>
      {kind && <p className="collection-kind">{t(`kinds.${kind}.long`)}</p>}
      <div className="form-grid">
        <TextInput
          id="edit-collection-headline"
          label={t('editCollection.titleLabel')}
          value={headline}
          onChange={(e) => setHeadline(e.target.value)}
          required
          invalid={!!errors.headline}
          errorText={errors.headline}
          helperText={localizedHelper(headline, 64, t)}
        />
        <TextArea
          id="edit-collection-description"
          label={t('editCollection.descriptionLabel')}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          invalid={!!errors.description}
          errorText={errors.description}
          helperText={localizedHelper(description, 2000, t)}
        />
        <LocalizedInfo id="edit-collection-localized-info" />
        <Select
          id="edit-collection-status"
          texts={{
            label: t('editCollection.statusLabel'),
            assistive: t('editCollection.statusHelper'),
            language: hdsLang(i18n.language),
          }}
          options={STATUS_OPTIONS}
          value={status}
          onChange={(selectedOptions) => {
            if (selectedOptions.length > 0) {
              setStatus(selectedOptions[0].value);
            }
          }}
        />
        {isNetwork && (
          <p className="form-hero-text" id="edit-collection-network-note">
            {t('editCollection.networkFixed')}
          </p>
        )}
        {!isReservations && !isNetwork && (
          <CollectionModeField
            idPrefix="edit-collection"
            label={t('editCollection.modeLabel')}
            options={MODE_OPTIONS}
            catalogue={ALL_MODE_OPTIONS}
            value={mode}
            onChange={handleModeChange}
          />
        )}
        <CollectionForm
          idPrefix="edit-collection"
          kind={kind}
          mode={mode}
          visibility={visibility}
          setVisibility={setVisibility}
          allowProposals={allowProposals}
          setAllowProposals={setAllowProposals}
          membersPrice={membersPrice}
          setMembersPrice={setMembersPrice}
          theeemeColor01={tc.color_01}
        />
      </div>
      <CollectionAdvancedFields
        idPrefix="edit-collection"
        colors={tc}
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
        afterEmailNote={
          <EmailNoteTest collectionCode={code} note={emailNote} buttonStyle={btnSecondaryStyle} />
        }
        homePage={homePage}
        setHomePage={setHomePage}
        digestFrequency={digestFrequency}
        setDigestFrequency={setDigestFrequency}
        language={language}
        setLanguage={setLanguage}
        theeeme={theeeme}
        setTheeeme={setTheeeme}
        koro={koro}
        setKoro={setKoro}
        thumbnail={thumbnail}
        setThumbnail={setThumbnail}
        thumbnailUrl={thumbnailUrl}
        welcomeDocUrl={welcomeDocUrl}
        setWelcomeDoc={setWelcomeDoc}
      />
      <div className="form-actions">
        <Button disabled={submitting} onClick={handleSubmit} style={{ ...btnStyle, width: '100%' }}>
          {submitting ? t('common.saving') : t('common.save')}
        </Button>
        {isOwner && (
          <Button
            variant="secondary"
            fullWidth
            disabled={submitting}
            onClick={() => {
              navigate(`${base}/delete`, {
                state: {
                  backPath: `${base}/edit`,
                  backLabel: L(headline) || t('common.collection'),
                },
              });
            }}
            style={{ ...btnSecondaryStyle, marginTop: 'var(--spacing-s)' }}
          >
            {t('common.delete')}
          </Button>
        )}
      </div>
      <div
        style={{
          marginTop: 'var(--spacing-xl)',
          borderTop: '1px solid var(--color-black-20)',
          paddingTop: 'var(--spacing-m)',
        }}
      >
        <h2>{t('pause.sectionHeading')}</h2>
        <p>{t('pause.sectionHelper')}</p>
        {!isPaused && (
          <div className="form-grid">
            <TextArea
              id="pause-message"
              label={t('pause.messageLabel')}
              helperText={`${pauseMessage.length}/256 — ${t('pause.messageHelper')}`}
              value={pauseMessage}
              onChange={(e) => setPauseMessage(e.target.value)}
              maxLength={256}
            />
          </div>
        )}
        {isPaused && (
          <blockquote
            style={{
              borderLeft: `4px solid ${tc.color_01 ? `var(--color-${tc.color_01})` : 'var(--color-black-50)'}`,
              paddingLeft: 'var(--spacing-m)',
              margin: 'var(--spacing-m) 0',
              fontStyle: 'italic',
            }}
          >
            {pauseMessage}
          </blockquote>
        )}
        {!isPaused && !pauseMessage.trim() && (
          <p
            style={{
              marginTop: 'var(--spacing-s)',
              fontSize: 'var(--fontsize-body-s)',
              color: 'var(--color-black-60)',
            }}
          >
            {t('pause.messageRequiredHint')}
          </p>
        )}
        <div style={{ marginTop: 'var(--spacing-m)' }}>
          <Button
            variant="secondary"
            fullWidth
            disabled={pauseSubmitting || (!isPaused && !pauseMessage.trim())}
            onClick={handlePauseToggle}
            style={btnSecondaryStyle}
          >
            {pauseSubmitting
              ? isPaused
                ? t('pause.resuming')
                : t('pause.pausing')
              : isPaused
                ? t('pause.resumeButton')
                : t('pause.pauseButton')}
          </Button>
        </div>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
