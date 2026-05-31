import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { TextInput, Button, Koros, Table, IconEnvelope, IconCrossCircle } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import TooltipButton from '../components/TooltipButton';

export default function ManageInvitesPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const userCode = localStorage.getItem('userCode');
  const tc = JSON.parse(localStorage.getItem('theeemeColors') || '{}');
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;
  const [loading, setLoading] = useState(true);
  const [invites, setInvites] = useState([]);
  const [pendingInvites, setPendingInvites] = useState([]);
  const [collectionHeadline, setCollectionHeadline] = useState('');
  useEffect(() => { document.title = collectionHeadline ? t('titles.guests', { headline: collectionHeadline }) : t('titles.guestsDefault'); }, [collectionHeadline, t]);
  const [isOwner, setIsOwner] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [resending, setResending] = useState(null);

  useEffect(() => {
    if (!userCode) {
      navigate('/login');
      return;
    }

    const fetchCollection = async () => {
      try {
        const res = await apiFetch(`/api/v1/collections/${code}/`);
        if (res.ok) {
          const data = await res.json();
          setInvites(data.invites || []);
          setPendingInvites(data.pending_invites || []);
          setCollectionHeadline(data.headline || '');
          setIsOwner(localStorage.getItem('userCode') === data.owner);
        } else {
          setToast({ type: 'error', message: t('manageInvites.errorLoading') });
        }
      } catch {
        setToast({ type: 'error', message: t('common.connectionError') });
      } finally {
        setLoading(false);
      }
    };
    fetchCollection();
  }, [userCode, code, navigate, t]);

  const handleResend = async (email) => {
    setResending(email);
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/invite/`, {
        method: 'POST',
        body: JSON.stringify({ email }),
      });
      if (res.ok) {
        setToast({ type: 'success', message: t('manageInvites.invitationResent') });
      } else {
        setToast({ type: 'error', message: t('manageInvites.errorResending') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setResending(null);
    }
  };

  const handleInvite = async () => {
    setInviteLoading(true);
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/invite/`, {
        method: 'POST',
        body: JSON.stringify({ email: inviteEmail.trim() }),
      });
      if (res.ok) {
        setPendingInvites((prev) => [...prev, { email: inviteEmail.trim() }]);
        setInviteEmail('');
        setToast({ type: 'success', message: t('manageInvites.invitationSent') });
      } else {
        setToast({ type: 'error', message: t('manageInvites.errorSending') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setInviteLoading(false);
    }
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  return (
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})` } : undefined}
      >
        <div className="form-hero-content" style={tc.color_04 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
          <BackLink to={`/collections/${code}`} label={collectionHeadline || t('common.collection')} />
          <h1 className="form-hero-title">{t('manageInvites.pageTitle')}</h1>
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
      {invites.length === 0 && pendingInvites.length === 0 ? (
        <p>{t('manageInvites.noGuests')}</p>
      ) : (() => {
        const tableRows = [
          ...invites.map((inv) => ({
            _id: inv.code,
            guest: inv.name ? `${inv.name} (${inv.email})` : inv.email,
            status: t('manageInvites.accepted'),
            _isPending: false,
            _email: inv.email,
            _code: inv.code,
            _name: inv.name || inv.email,
          })),
          ...pendingInvites.map((p) => ({
            _id: p.code || `pending-${p.email}`,
            guest: p.email,
            status: t('manageInvites.pending'),
            _isPending: true,
            _email: p.email,
            _code: p.code,
            _name: p.email,
          })),
        ];
        const cols = [
          { key: 'guest', headerName: 'Guest' },
          { key: 'status', headerName: 'Status' },
          ...(isOwner ? [{
            key: '_actions',
            headerName: '',
            transform: (row) => (
              <div style={{ display: 'flex', gap: 'var(--spacing-xs)', alignItems: 'center', justifyContent: 'flex-end' }}>
                {row._isPending && (
                  <TooltipButton
                    tooltip={t('manageInvites.resendTooltip')}
                    onClick={() => handleResend(row._email)}
                    disabled={resending === row._email}
                  >
                    <IconEnvelope aria-hidden />
                  </TooltipButton>
                )}
                <TooltipButton
                  tooltip={t('manageInvites.removeTooltip')}
                  onClick={() => navigate(`/collections/${code}/invites/remove`, {
                    state: { guestCode: row._code, guestName: row._name, backLabel: collectionHeadline || 'Guests' },
                  })}
                >
                  <IconCrossCircle aria-hidden />
                </TooltipButton>
              </div>
            ),
          }] : []),
        ];
        return (
          <Table
            cols={cols}
            rows={tableRows}
            indexKey="_id"
            renderIndexCol={false}
            theme={tc.color_03 ? { '--header-background-color': `var(--color-${tc.color_03})` } : undefined}
          />
        );
      })()}

      {isOwner && (
        <>
        <div className="spacer-xl" />
        <div className="form-grid section-mt">
          <TextInput
            id="manage-invites-email"
            label={t('manageInvites.emailLabel')}
            type="email"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            placeholder={t('manageInvites.emailPlaceholder')}
          />
          <Button
            disabled={inviteLoading || !inviteEmail.trim()}
            onClick={handleInvite}
            style={{ ...btnStyle, width: '100%' }}
          >
            {inviteLoading ? t('common.sending') : t('manageInvites.invite')}
          </Button>
        </div>
        </>
      )}

      <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    </div>
  );
}
