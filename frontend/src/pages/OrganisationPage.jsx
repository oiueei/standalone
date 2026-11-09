import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import { useTranslation } from 'react-i18next';
import { TextInput, TextArea, Button } from 'hds-react';
import { apiFetch, extractApiError } from '../services/api';
import ImageUpload from '../components/ImageUpload';
import PageLayout from '../components/PageLayout';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import ClosedDatesField from '../components/ClosedDatesField';
import WeekdayChips from '../components/WeekdayChips';
import FieldNotice from '../components/FieldNotice';
import useTheeeme from '../hooks/useTheeeme';
import useCollectionTheeeme from '../hooks/useCollectionTheeeme';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import useDocumentTitle from '../hooks/useDocumentTitle';
import { useCollectionBase } from '../hooks/useCollectionBase';
import { closedDatesToDisplay } from '../utils/rental';
import { localizedCounter, localizedHelper, useLocalized } from '../utils/localized';

const EMAIL_NOTE_EXAMPLE = '{"es": "Estamos en la planta 2", "ca": "Estem a la planta 2"}';
const REQUEST_INFO_EXAMPLE = '{"es": "Trae el carné", "ca": "Porta el carnet"}';
const POLICY_EXAMPLE = '{"es": "20 € de fianza", "ca": "20 € de fiança"}';

/**
 * The page a curator (founder or co-curator) has in a group: the entity they answer for
 * there — a name, a logo, an About in Markdown and a contact — apart from their profile.
 * Each reads and edits **only their own**; the pages are public with the collection.
 *
 * **Only in a network** the page is also a pickup point (address, hours, days, closures)
 * and carries the conditions of the curator's own loans, which are the collection's own
 * fields (same limits, same one-text-per-language form): whatever is left empty falls
 * back to the network's, field by field. Outside a network the PUT sends only the four
 * identity fields, and the server ignores anything else.
 *
 * The page is not gated here: the server answers 403 to a member who is not a curator,
 * and the page says so.
 */
export default function OrganisationPage() {
  const { t } = useTranslation();
  const L = useLocalized();
  const { code } = useParams();
  const navigate = useNavigate();
  const base = useCollectionBase(code);
  const { btnStyle } = useTheeeme();
  const userCode = localStorage.getItem('userCode');

  const [collection, setCollection] = useState(null);
  const [palette, setPalette] = useState(null);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState('');
  const [toast, setToast] = useState(null);
  const [saving, setSaving] = useState(false);

  const [entityName, setEntityName] = useState('');
  const [address, setAddress] = useState('');
  const [hoursNote, setHoursNote] = useState('');
  const [about, setAbout] = useState('');
  const [contact, setContact] = useState('');
  const [logo, setLogo] = useState('');
  const [logoUrl, setLogoUrl] = useState('');
  const [weekdays, setWeekdays] = useState([]);
  const [closedDates, setClosedDates] = useState('');
  const [depositPolicy, setDepositPolicy] = useState('');
  const [requestInfo, setRequestInfo] = useState('');
  const [emailNote, setEmailNote] = useState('');

  useCollectionLanguage(collection?.language || '', [
    collection?.headline,
    collection?.description,
  ]);
  useCollectionTheeeme(palette?.colors, palette?.koro);
  useDocumentTitle(t('titles.organisation'));

  useEffect(() => {
    if (!userCode) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const [collectionRes, pointRes] = await Promise.all([
          apiFetch(`/api/v1/collections/${code}/`),
          apiFetch(`/api/v1/collections/${code}/point/`),
        ]);
        if (cancelled) return;
        if (collectionRes.ok) {
          const data = await collectionRes.json();
          setCollection(data);
          setPalette({ colors: data.theeeme_colors, koro: data.koro });
        }
        if (pointRes.status === 403) {
          setProblem('organisation.notACurator');
        } else if (pointRes.ok) {
          const point = await pointRes.json();
          setEntityName(point.entity_name || '');
          setAddress(point.address || '');
          setHoursNote(point.hours_note || '');
          setAbout(point.about || '');
          setContact(point.contact || '');
          setLogo(point.logo || '');
          setLogoUrl(point.logo_url || '');
          setWeekdays(point.weekdays || []);
          setClosedDates(closedDatesToDisplay(point.closed_dates));
          setDepositPolicy(point.deposit_policy || '');
          setRequestInfo(point.request_info || '');
          setEmailNote(point.email_note || '');
        } else {
          setProblem('organisation.errorLoading');
        }
      } catch {
        if (!cancelled) setProblem('common.connectionError');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userCode, code]);

  const isNetwork = collection?.mode === 'NETWORK';
  const aboutCount = localizedCounter(about, 2000);
  const requestInfoCount = localizedCounter(requestInfo, 512);
  const emailNoteCount = localizedCounter(emailNote, 512);
  const depositCount = localizedCounter(depositPolicy, 256);
  // The network's fields only count while they are on screen.
  const tooLong =
    aboutCount.over ||
    (isNetwork && (requestInfoCount.over || emailNoteCount.over || depositCount.over));

  const handleSave = async () => {
    if (tooLong) return;
    setSaving(true);
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/point/`, {
        method: 'PUT',
        body: JSON.stringify({
          entity_name: entityName.trim(),
          // Sent empty too: that is what takes the logo off.
          logo: logo || '',
          about: about.trim(),
          contact: contact.trim(),
          // The place and the conditions are a network's: elsewhere the server would
          // ignore them, and the page does not send what it does not show.
          ...(isNetwork && {
            address: address.trim(),
            hours_note: hoursNote.trim(),
            weekdays,
            closed_dates: closedDates,
            deposit_policy: depositPolicy.trim(),
            request_info: requestInfo.trim(),
            email_note: emailNote.trim(),
          }),
        }),
      });
      if (res.ok) {
        // Saving ends the visit, as the collection's and the profile's forms do.
        navigate(base);
      } else if (res.status === 429) {
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else if (res.status === 400) {
        const message = await extractApiError(res);
        setToast({ type: 'error', message: message || t('organisation.errorSaving') });
      } else {
        setToast({ type: 'error', message: t('organisation.errorSaving') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <PageLayout
      backTo={base}
      backLabel={(collection && L(collection.headline)) || t('common.collection')}
    >
      <h1 className="page-title-xl">{t('organisation.pageTitle')}</h1>
      {problem ? (
        <p>{t(problem)}</p>
      ) : (
        <div className="form-grid">
          <FieldNotice id="organisation-notice" label={t('organisation.noticeTitle')}>
            {t('organisation.notice')}
          </FieldNotice>
          <TextInput
            id="organisation-name"
            label={t('organisation.nameLabel')}
            helperText={t('organisation.nameHelper')}
            value={entityName}
            maxLength={64}
            onChange={(e) => setEntityName(e.target.value)}
          />
          <ImageUpload
            id="organisation-logo"
            label={t('organisation.logoLabel')}
            helperText={`${t('organisation.logoHelper')} ${t('collectionSettings.logoHelper')}`}
            onChange={setLogo}
            currentUrl={logoUrl}
            folder="oiueei/collections"
          />
          <TextArea
            id="organisation-about"
            label={t('organisation.aboutLabel')}
            value={about}
            onChange={(e) => setAbout(e.target.value)}
            invalid={aboutCount.over}
            errorText={aboutCount.over ? t('organisation.aboutMaxLength') : undefined}
            helperText={localizedHelper(about, 2000, t)}
          />
          <TextInput
            id="organisation-contact"
            label={t('organisation.contactLabel')}
            helperText={t('networkPoint.contactHelper')}
            value={contact}
            maxLength={64}
            onChange={(e) => setContact(e.target.value)}
          />
          {isNetwork && (
            <>
              <h2>{t('organisation.pickupTitle')}</h2>
              <p>{t('organisation.pickupIntro')}</p>
              <TextInput
                id="organisation-address"
                label={t('networkPoint.address')}
                value={address}
                maxLength={64}
                onChange={(e) => setAddress(e.target.value)}
              />
              <TextInput
                id="organisation-hours"
                label={t('networkPoint.hours')}
                helperText={t('networkPoint.hoursHelper')}
                value={hoursNote}
                maxLength={128}
                onChange={(e) => setHoursNote(e.target.value)}
              />
              <WeekdayChips
                labelId="organisation-weekdays"
                labelKey="networkPoint.weekdaysLabel"
                helperKey="networkPoint.weekdaysHelper"
                weekdays={weekdays}
                setWeekdays={setWeekdays}
              />
              <ClosedDatesField
                id="organisation-closed-dates"
                value={closedDates}
                onChange={setClosedDates}
              />
              <h2>{t('networkPoint.conditionsTitle')}</h2>
              <p>{t('networkPoint.conditionsIntro')}</p>
              <div>
                <FieldNotice
                  id="organisation-request-info-notice"
                  label={t('requestInfo.label')}
                  example={REQUEST_INFO_EXAMPLE}
                  after={t('requestInfo.helper')}
                >
                  {t('localized.requestInfoNotice')}
                </FieldNotice>
                <TextArea
                  id="organisation-request-info"
                  label={t('requestInfo.label')}
                  value={requestInfo}
                  onChange={(e) => setRequestInfo(e.target.value)}
                  invalid={requestInfoCount.over}
                  errorText={requestInfoCount.over ? t('requestInfo.maxLength') : undefined}
                  helperText={localizedHelper(requestInfo, 512, t)}
                />
              </div>
              <div>
                <FieldNotice
                  id="organisation-deposit-notice"
                  label={t('rental.depositPolicyLabel')}
                  example={POLICY_EXAMPLE}
                  after={t('rental.depositPolicyHelper')}
                >
                  {t('localized.policyNotice')}
                </FieldNotice>
                <TextArea
                  id="organisation-deposit-policy"
                  label={t('rental.depositPolicyLabel')}
                  value={depositPolicy}
                  onChange={(e) => setDepositPolicy(e.target.value)}
                  invalid={depositCount.over}
                  errorText={depositCount.over ? t('rental.depositPolicyMaxLength') : undefined}
                  helperText={localizedHelper(depositPolicy, 256, t)}
                />
              </div>
              <div>
                <FieldNotice
                  id="organisation-email-note-notice"
                  label={t('emailNote.label')}
                  example={EMAIL_NOTE_EXAMPLE}
                  after={t('emailNote.helper')}
                >
                  {t('localized.emailNoteNotice')}
                </FieldNotice>
                <TextArea
                  id="organisation-email-note"
                  label={t('emailNote.label')}
                  value={emailNote}
                  onChange={(e) => setEmailNote(e.target.value)}
                  invalid={emailNoteCount.over}
                  errorText={emailNoteCount.over ? t('emailNote.maxLength') : undefined}
                  helperText={localizedHelper(emailNote, 512, t)}
                />
              </div>
            </>
          )}
          <Button
            disabled={saving || tooLong}
            onClick={handleSave}
            style={{ ...btnStyle, width: '100%' }}
          >
            {saving ? t('common.saving') : t('common.save')}
          </Button>
        </div>
      )}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
