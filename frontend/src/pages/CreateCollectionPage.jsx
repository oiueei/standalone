import { useState } from 'react';
import { Navigate, useNavigate, useLocation } from 'react-router';
import { useTranslation } from 'react-i18next';
import { TextInput, TextArea, Button } from 'hds-react';
import { apiFetch, extractApiError } from '../services/api';
import PageLayout from '../components/PageLayout';
import CollectionForm from '../components/CollectionForm';
import CollectionModeField from '../components/CollectionModeField';
import useCapabilities, { useCapabilitiesSettled, isOfferable } from '../hooks/useCapabilities';
import LoadingSpinner from '../components/LoadingSpinner';
import FieldNotice from '../components/FieldNotice';
import { localizedCounter, localizedHelper } from '../utils/localized';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';
import ApprovalNotice from '../components/ApprovalNotice';
import { collectionPath, kindOfPrefix } from '../utils/collectionPath';
import { allowedVerbsFor } from '../utils/collectionKind';
import useDocumentTitle from '../hooks/useDocumentTitle';

// A code sample the owner copies: the keys are the language codes the server accepts, so it
// reads the same in whatever language the form is in.
const TEXT_EXAMPLE = '{"es": "Las cosas de mamá", "ca": "Les coses de mama"}';

/**
 * `/stall/new`, `/library/new` and `/shed/new`: the form for the kind named by the
 * address, which is chosen at `/new` and never changes afterwards. An account the
 * deployment's policy does not give that kind to sees the same "needs approval"
 * line as the chooser, and no form: filling one in would end in a refusal.
 *
 * The form is short on purpose: title, description, mode (with the members' price switch
 * for a community), visibility. Everything else is the model's default and has its own
 * settings page once the collection exists.
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
  const { btnStyle } = useTheeeme();

  const [headline, setHeadline] = useState('');
  const [description, setDescription] = useState('');
  const [mode, setMode] = useState('PROPRIETARY');
  const [visibility, setVisibility] = useState('PRIVATE');
  // Whether the members of a COMMUNITY stall or library may set a price: on, both of
  // the kind's verbs; off, only the free one.
  const [membersPrice, setMembersPrice] = useState(true);
  // The group's emails speak the owner's own interface language; each member's own
  // preference still wins over it, and the Notifications page changes it.
  const language = i18n.resolvedLanguage || i18n.language;
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
    setSubmitting(true);
    setToast(null);

    // Only what the person chose here. Everything else (the palette, the summary
    // frequency, the rules of a loan or a reservation…) is the model's default, and
    // the settings pages change it afterwards.
    const body = {
      kind,
      headline: headline.trim(),
      mode: isReservations ? 'PROPRIETARY' : mode,
      visibility,
      allowed_thing_types: allowedVerbsFor(kind, mode, membersPrice),
      language,
    };
    if (description.trim()) body.description = description.trim();
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
        <FieldNotice
          id="create-collection-text-notice"
          label={t('createCollection.titleLabel')}
          example={TEXT_EXAMPLE}
          after={t('localized.textNoticeAfter')}
        >
          {t('localized.textNotice')}
        </FieldNotice>
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
          membersPrice={membersPrice}
          setMembersPrice={setMembersPrice}
        />
      </div>
      <div className="form-actions">
        <Button fullWidth disabled={submitting} onClick={handleSubmit} style={btnStyle}>
          {submitting ? t('common.creating') : t(`kinds.${kind}.create`)}
        </Button>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
