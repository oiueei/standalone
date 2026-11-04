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
import LocalizedInfo from '../components/LocalizedInfo';
import useTheeeme from '../hooks/useTheeeme';
import useCollectionTheeeme from '../hooks/useCollectionTheeeme';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import useDocumentTitle from '../hooks/useDocumentTitle';
import { useCollectionBase } from '../hooks/useCollectionBase';
import { closedDatesToDisplay } from '../utils/rental';
import { localizedCounter, localizedHelper, useLocalized } from '../utils/localized';

/**
 * The pickup point of the dinamizador who is looking: the entity they answer for in a
 * network, where and when members collect and return, and the conditions of their own
 * loans. Each reads and edits **only their own** (the founder is one too); the
 * points are public with the collection, address included.
 *
 * The conditions are the collection's own fields (same limits, same one-text-per-
 * language form): whatever is left empty falls back to the network's, field by field.
 * The page is not gated here: the server answers 404 outside a network and 403 to a
 * member who is not a dinamizador, and says so.
 */
export default function NetworkPointPage() {
  const { t } = useTranslation();
  const L = useLocalized();
  const { code } = useParams();
  const navigate = useNavigate();
  const base = useCollectionBase(code);
  const { tc, btnStyle } = useTheeeme();
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
  const [contact, setContact] = useState('');
  const [logo, setLogo] = useState('');
  const [logoUrl, setLogoUrl] = useState('');
  const [weekdays, setWeekdays] = useState([]);
  const [closedDates, setClosedDates] = useState('');
  const [depositPolicy, setDepositPolicy] = useState('');
  const [requestInfo, setRequestInfo] = useState('');
  const [emailNote, setEmailNote] = useState('');

  useCollectionLanguage(collection?.language || '', [collection]);
  useCollectionTheeeme(palette?.colors, palette?.koro);
  useDocumentTitle(t('titles.networkPoint'));

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
        if (pointRes.status === 404) {
          setProblem(t('networkPoint.notANetwork'));
        } else if (pointRes.status === 403) {
          setProblem(t('networkPoint.notADinamizador'));
        } else if (pointRes.ok) {
          const point = await pointRes.json();
          setEntityName(point.entity_name || '');
          setAddress(point.address || '');
          setHoursNote(point.hours_note || '');
          setContact(point.contact || '');
          setLogo(point.logo || '');
          setLogoUrl(point.logo_url || '');
          setWeekdays(point.weekdays || []);
          setClosedDates(closedDatesToDisplay(point.closed_dates));
          setDepositPolicy(point.deposit_policy || '');
          setRequestInfo(point.request_info || '');
          setEmailNote(point.email_note || '');
        } else {
          setProblem(t('networkPoint.errorLoading'));
        }
      } catch {
        if (!cancelled) setProblem(t('common.connectionError'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userCode, code, t]);

  const requestInfoCount = localizedCounter(requestInfo, 512);
  const emailNoteCount = localizedCounter(emailNote, 512);
  const depositCount = localizedCounter(depositPolicy, 256);

  const handleSave = async () => {
    setSaving(true);
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/point/`, {
        method: 'PUT',
        body: JSON.stringify({
          entity_name: entityName.trim(),
          address: address.trim(),
          hours_note: hoursNote.trim(),
          contact: contact.trim(),
          // Sent empty too: that is what takes the logo off.
          logo: logo || '',
          weekdays,
          closed_dates: closedDates,
          deposit_policy: depositPolicy.trim(),
          request_info: requestInfo.trim(),
          email_note: emailNote.trim(),
        }),
      });
      if (res.ok) {
        // Saving ends the visit, as the collection's and the profile's forms do.
        navigate(base);
      } else if (res.status === 429) {
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else if (res.status === 400) {
        const message = await extractApiError(res);
        setToast({ type: 'error', message: message || t('networkPoint.errorSaving') });
      } else {
        setToast({ type: 'error', message: t('networkPoint.errorSaving') });
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
      <h1 className="page-title-xl">{t('networkPoint.pageTitle')}</h1>
      {problem ? (
        <p>{problem}</p>
      ) : (
        <div className="form-grid">
          <p>{t('networkPoint.intro')}</p>
          <TextInput
            id="network-point-entity-name"
            label={t('networkPoint.entityName')}
            helperText={t('networkPoint.entityNameHelper')}
            value={entityName}
            maxLength={64}
            onChange={(e) => setEntityName(e.target.value)}
          />
          <ImageUpload
            id="network-point-logo"
            label={t('networkPoint.logoLabel')}
            helperText={`${t('networkPoint.logoHelper')} ${t('collectionSettings.logoHelper')}`}
            onChange={setLogo}
            currentUrl={logoUrl}
            folder="oiueei/collections"
          />
          <TextInput
            id="network-point-address"
            label={t('networkPoint.address')}
            value={address}
            maxLength={64}
            onChange={(e) => setAddress(e.target.value)}
          />
          <TextInput
            id="network-point-hours"
            label={t('networkPoint.hours')}
            helperText={t('networkPoint.hoursHelper')}
            value={hoursNote}
            maxLength={128}
            onChange={(e) => setHoursNote(e.target.value)}
          />
          <TextInput
            id="network-point-contact"
            label={t('networkPoint.contact')}
            helperText={t('networkPoint.contactHelper')}
            value={contact}
            maxLength={64}
            onChange={(e) => setContact(e.target.value)}
          />
          <WeekdayChips
            labelId="network-point-weekdays"
            labelKey="networkPoint.weekdaysLabel"
            helperKey="networkPoint.weekdaysHelper"
            weekdays={weekdays}
            setWeekdays={setWeekdays}
            color01={tc.color_01}
            color06={tc.color_06}
          />
          <ClosedDatesField
            id="network-point-closed-dates"
            value={closedDates}
            onChange={setClosedDates}
          />
          <h2>{t('networkPoint.conditionsTitle')}</h2>
          <p>{t('networkPoint.conditionsIntro')}</p>
          <div>
            <p className="weekday-field-helper">{t('rental.depositPolicyHelper')}</p>
            <TextArea
              id="network-point-deposit-policy"
              label={t('rental.depositPolicyLabel')}
              value={depositPolicy}
              onChange={(e) => setDepositPolicy(e.target.value)}
              invalid={depositCount.over}
              helperText={localizedHelper(depositPolicy, 256, t)}
            />
            <LocalizedInfo id="network-point-deposit-policy-info" variant="policy" />
          </div>
          <div>
            <p className="weekday-field-helper">{t('requestInfo.helper')}</p>
            <TextArea
              id="network-point-request-info"
              label={t('requestInfo.label')}
              value={requestInfo}
              onChange={(e) => setRequestInfo(e.target.value)}
              invalid={requestInfoCount.over}
              errorText={requestInfoCount.over ? t('requestInfo.maxLength') : undefined}
              helperText={localizedHelper(requestInfo, 512, t)}
            />
            <LocalizedInfo id="network-point-request-info-info" variant="requestInfo" />
          </div>
          <div>
            <p className="weekday-field-helper">{t('emailNote.helper')}</p>
            <TextArea
              id="network-point-email-note"
              label={t('emailNote.label')}
              value={emailNote}
              onChange={(e) => setEmailNote(e.target.value)}
              invalid={emailNoteCount.over}
              errorText={emailNoteCount.over ? t('emailNote.maxLength') : undefined}
              helperText={localizedHelper(emailNote, 512, t)}
            />
            <LocalizedInfo id="network-point-email-note-info" variant="emailNote" />
          </div>
          <Button disabled={saving} onClick={handleSave} style={{ ...btnStyle, width: '100%' }}>
            {t('networkPoint.save')}
          </Button>
        </div>
      )}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
