import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import { TextInput, TextArea, Select, Button } from 'hds-react';
import { apiFetch, extractApiError } from '../services/api';
import PageLayout from '../components/PageLayout';
import CollectionForm from '../components/CollectionForm';
import CollectionModeField from '../components/CollectionModeField';
import FieldNotice from '../components/FieldNotice';
import useCapabilities, { isOfferable } from '../hooks/useCapabilities';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';
import useCollectionTheeeme from '../hooks/useCollectionTheeeme';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import { useLocalized, localizedCounter, localizedHelper } from '../utils/localized';
import hdsLang from '../utils/hdsLang';
import { useCollectionBase } from '../hooks/useCollectionBase';
import { allowedVerbsFor, membersPriceFromVerbs } from '../utils/collectionKind';
import useDocumentTitle from '../hooks/useDocumentTitle';

// A code sample the owner copies: the keys are the language codes the server accepts, so it
// reads the same in whatever language the form is in.
const TEXT_EXAMPLE = '{"es": "Las cosas de mamá", "ca": "Les coses de mama"}';

/**
 * `/{kind}/{code}/edit`: what the collection is called and how it is run — title,
 * description, state, mode (with the members' price switch for a community) and
 * visibility — and, at the foot, deleting it (the founder's) and pausing it. Everything
 * else about a collection has a page under the settings menu (Appearance, Notifications,
 * Availability), each sending only its own fields.
 *
 * The PATCH sends exactly `headline`, `description`, `status`, `mode`, `visibility` and
 * `allowed_thing_types`, and only once the collection has loaded.
 */
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
  const [loaded, setLoaded] = useState(false);
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
  // The kind is the collection's own and never changes: the page shows it as a fact
  // about the collection and sends it nowhere.
  const [kind, setKind] = useState('');
  // Whether the members of a COMMUNITY stall or library may set a price (both of the
  // kind's verbs stored) or only give and lend (the free verb alone).
  const [membersPrice, setMembersPrice] = useState(true);
  // The collection's stored language, and its texts as saved, never as being typed: the
  // page follows these so that rewriting the title does not move its own language.
  const [savedLanguage, setSavedLanguage] = useState('');
  const [savedTexts, setSavedTexts] = useState([]);
  useCollectionLanguage(savedLanguage, savedTexts);
  // The page wears the palette the group has saved.
  const [savedPalette, setSavedPalette] = useState(null);
  useCollectionTheeeme(savedPalette?.colors, savedPalette?.koro);
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
  // A shed is always PROPRIETARY, so it has no mode to change.
  const isReservations = kind === 'SHED';
  const MODE_OPTIONS = ALL_MODE_OPTIONS.filter((opt) =>
    isOfferable(capabilities, 'collection_modes', opt.value, savedMode)
  );

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
          setKind(data.kind || '');
          setMembersPrice(membersPriceFromVerbs(data.kind, data.allowed_thing_types));
          setSavedLanguage(data.language || '');
          setSavedPalette({ colors: data.theeeme_colors, koro: data.koro });
          setSavedTexts([data.headline, data.description]);
          setPauseMessage(data.pause_message || '');
          setIsPaused(data.is_paused || false);
          setLoaded(true);
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
    if (!loaded || !validate()) return;
    setSubmitting(true);
    setToast(null);

    const body = {
      headline: headline.trim(),
      description: description.trim(),
      status,
      mode,
      visibility,
      allowed_thing_types: allowedVerbsFor(kind, mode, membersPrice),
    };

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
        // narrowing would orphan things — so the owner can act on it.
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
        <FieldNotice
          id="edit-collection-text-notice"
          label={t('editCollection.titleLabel')}
          example={TEXT_EXAMPLE}
          after={t('localized.textNoticeAfter')}
        >
          {t('localized.textNotice')}
        </FieldNotice>
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
          membersPrice={membersPrice}
          setMembersPrice={setMembersPrice}
          theeemeColor01={tc.color_01}
        />
      </div>
      <div className="form-actions">
        <Button
          disabled={submitting || !loaded}
          onClick={handleSubmit}
          style={{ ...btnStyle, width: '100%' }}
        >
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
