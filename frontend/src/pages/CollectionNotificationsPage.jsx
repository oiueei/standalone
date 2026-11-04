import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import { TextArea, Select, Button, ToggleButton } from 'hds-react';
import { apiFetch, extractApiError } from '../services/api';
import PageLayout from '../components/PageLayout';
import PdfUpload from '../components/PdfUpload';
import FieldNotice from '../components/FieldNotice';
import EmailNoteTest from '../components/EmailNoteTest';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';
import useCollectionTheeeme from '../hooks/useCollectionTheeeme';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import useDocumentTitle from '../hooks/useDocumentTitle';
import { useCollectionBase } from '../hooks/useCollectionBase';
import { useLocalized, localizedCounter, localizedHelper } from '../utils/localized';
import hdsLang from '../utils/hdsLang';
import { SUPPORTED_LANGUAGES } from '../i18n';

const EMAIL_NOTE_EXAMPLE = '{"es": "Estamos en la planta 2", "ca": "Estem a la planta 2"}';

/**
 * What the collection tells its people: whether members may recommend someone, the
 * welcome document, how often the summary goes out, the language of the group's
 * messages and the owner's note in the emails a requester receives.
 *
 * It sends only these five fields in a partial update, and only once the collection
 * has loaded. Every value comes from what was loaded: a document that is not touched
 * is saved back as it was (the save never deletes it), and a summary frequency or a
 * recommend switch never falls back to a value the collection does not have.
 */
export default function CollectionNotificationsPage() {
  const { t, i18n } = useTranslation();
  const L = useLocalized();
  const { code } = useParams();
  const base = useCollectionBase(code);
  const navigate = useNavigate();
  const { btnStyle, btnSecondaryStyle, tc } = useTheeeme();
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [headline, setHeadline] = useState('');
  const [allowProposals, setAllowProposals] = useState(false);
  const [welcomeDoc, setWelcomeDoc] = useState('');
  const [welcomeDocUrl, setWelcomeDocUrl] = useState('');
  const [digestFrequency, setDigestFrequency] = useState('');
  const [language, setLanguage] = useState('');
  const [emailNote, setEmailNote] = useState('');
  // The page wears the palette the collection has saved.
  const [savedPalette, setSavedPalette] = useState(null);
  useCollectionTheeeme(savedPalette?.colors, savedPalette?.koro);
  // The collection's stored language, never the draft in the `Select` below: that one
  // shows the interface's language while the stored one is blank, and following it
  // would flip this page's own language as the owner merely tries options.
  const [savedLanguage, setSavedLanguage] = useState('');
  const [savedTexts, setSavedTexts] = useState([]);
  useCollectionLanguage(savedLanguage, savedTexts);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);
  useDocumentTitle(
    headline
      ? t('titles.collectionNotifications', { headline: L(headline) })
      : t('titles.collectionNotificationsDefault')
  );

  useEffect(() => {
    const load = async () => {
      try {
        const res = await apiFetch(`/api/v1/collections/${code}/`);
        if (res.ok) {
          const data = await res.json();
          setHeadline(data.headline || '');
          // `?? false`, the model's default; a genuine `false` survives the load.
          setAllowProposals(data.allow_member_proposals ?? false);
          setWelcomeDoc(data.welcome_doc || '');
          setWelcomeDocUrl(data.welcome_doc_url || '');
          setDigestFrequency(data.digest_frequency);
          // Blank = inherit the deployment default; the Select's "Automatic" option says so.
          setLanguage(data.language || '');
          setSavedLanguage(data.language || '');
          setEmailNote(data.email_note || '');
          setSavedPalette({ colors: data.theeeme_colors, koro: data.koro });
          setSavedTexts([data.headline, data.description]);
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
    load();
    // Mount-once, like EditCollectionPage's load: `useCollectionLanguage` changes the
    // language as this very response lands.
  }, [code]);

  const emailNoteCount = localizedCounter(emailNote, 512);

  const handleSubmit = async () => {
    if (!loaded || emailNoteCount.over) return;
    setSubmitting(true);
    setToast(null);
    const body = {
      allow_member_proposals: allowProposals,
      welcome_doc: welcomeDoc,
      digest_frequency: digestFrequency,
      language,
      email_note: emailNote.trim(),
    };

    try {
      const res = await apiFetch(`/api/v1/collections/${code}/`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate(base);
      } else if (res.status === 429) {
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else if (res.status === 400) {
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

  if (loading) return <LoadingSpinner />;

  const toggleTheme = tc.color_01
    ? { '--toggle-button-color': `var(--color-${tc.color_01})` }
    : undefined;
  const digestOptions = [
    { label: t('editCollection.digestNone'), value: 'NONE' },
    { label: t('editCollection.digestWeekly'), value: 'WEEKLY' },
    { label: t('editCollection.digestMonthly'), value: 'MONTHLY' },
  ];

  return (
    <PageLayout backTo={base} backLabel={L(headline) || t('common.collection')}>
      <h1 className="page-title-xl">{t('collectionSettings.notifications')}</h1>
      <div className="form-grid">
        <ToggleButton
          id="notifications-allow-proposals"
          variant="inline"
          label={t('recommend.settingFull')}
          checked={allowProposals}
          onChange={(val) => setAllowProposals(!val)}
          theme={toggleTheme}
        />
        <PdfUpload
          id="notifications-welcome-doc"
          label={t('upload.welcomeDocLabel')}
          onChange={setWelcomeDoc}
          currentUrl={welcomeDocUrl}
          helperText={t('upload.welcomeDocHelper')}
        />
        <Select
          id="notifications-digest"
          texts={{
            label: t('editCollection.digestLabel'),
            assistive: t('editCollection.digestHelper'),
            language: hdsLang(i18n.language),
          }}
          options={digestOptions}
          value={digestFrequency}
          onChange={(selected) => {
            if (selected.length > 0) setDigestFrequency(selected[0].value);
          }}
        />
        <Select
          id="notifications-language"
          texts={{
            label: t('collectionLanguage.label'),
            assistive: t('collectionLanguage.helper'),
            language: hdsLang(i18n.language),
          }}
          options={[
            { label: t('editProfile.languageAutomatic'), value: '' },
            ...SUPPORTED_LANGUAGES.map((l) => ({ label: l.name, value: l.code })),
          ]}
          value={language}
          onChange={(selected) => {
            if (selected.length > 0) setLanguage(selected[0].value);
          }}
        />
        <div>
          <FieldNotice
            id="notifications-email-note-notice"
            label={t('emailNote.label')}
            example={EMAIL_NOTE_EXAMPLE}
            after={t('emailNote.helper')}
          >
            {t('localized.emailNoteNotice')}
          </FieldNotice>
          <TextArea
            id="notifications-email-note"
            label={t('emailNote.label')}
            value={emailNote}
            onChange={(e) => setEmailNote(e.target.value)}
            invalid={emailNoteCount.over}
            errorText={emailNoteCount.over ? t('emailNote.maxLength') : undefined}
            helperText={localizedHelper(emailNote, 512, t)}
          />
          <EmailNoteTest collectionCode={code} note={emailNote} buttonStyle={btnSecondaryStyle} />
        </div>
      </div>
      <div className="form-actions">
        <Button
          disabled={submitting || !loaded}
          onClick={handleSubmit}
          style={{ ...btnStyle, width: '100%' }}
        >
          {submitting ? t('common.saving') : t('common.save')}
        </Button>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
