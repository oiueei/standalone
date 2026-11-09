import { useState } from 'react';
import { useParams } from 'react-router';
import { useTranslation } from 'react-i18next';
import { TextArea, Select, Button, ToggleButton } from 'hds-react';
import PageLayout from '../components/PageLayout';
import PdfUpload from '../components/PdfUpload';
import FieldNotice from '../components/FieldNotice';
import EmailNoteTest from '../components/EmailNoteTest';
import LoadingSpinner from '../components/LoadingSpinner';
import CollectionFormRefusal from '../components/CollectionFormRefusal';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';
import useCollectionForm from '../hooks/useCollectionForm';
import useDocumentTitle from '../hooks/useDocumentTitle';
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
  const { btnStyle, btnSecondaryStyle, toggleTheme } = useTheeeme();
  const [headline, setHeadline] = useState('');
  const [allowProposals, setAllowProposals] = useState(false);
  const [welcomeDoc, setWelcomeDoc] = useState('');
  const [welcomeDocUrl, setWelcomeDocUrl] = useState('');
  const [digestFrequency, setDigestFrequency] = useState('');
  const [language, setLanguage] = useState('');
  const [emailNote, setEmailNote] = useState('');
  // The hook follows the collection's stored language, never the draft in the `Select`
  // below: that one shows the interface's language while the stored one is blank, and
  // following it would flip this page's own language as the owner merely tries options.
  const { loading, loaded, refusal, base, save, submitting, toast, setToast } = useCollectionForm(
    code,
    {
      onLoad: (data) => {
        setHeadline(data.headline || '');
        // `?? false`, the model's default; a genuine `false` survives the load.
        setAllowProposals(data.allow_member_proposals ?? false);
        setWelcomeDoc(data.welcome_doc || '');
        setWelcomeDocUrl(data.welcome_doc_url || '');
        setDigestFrequency(data.digest_frequency);
        // Blank = inherit the deployment default; the Select's "Automatic" option says so.
        setLanguage(data.language || '');
        setEmailNote(data.email_note || '');
      },
    }
  );
  useDocumentTitle(
    headline
      ? t('titles.collectionNotifications', { headline: L(headline) })
      : t('titles.collectionNotificationsDefault')
  );

  const emailNoteCount = localizedCounter(emailNote, 512);

  const handleSubmit = () => {
    if (!loaded || emailNoteCount.over) return;
    save({
      allow_member_proposals: allowProposals,
      welcome_doc: welcomeDoc,
      digest_frequency: digestFrequency,
      language,
      email_note: emailNote.trim(),
    });
  };

  if (loading) return <LoadingSpinner />;
  if (refusal) return <CollectionFormRefusal refusal={refusal} base={base} />;

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
          disabled={submitting || !loaded || emailNoteCount.over}
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
