import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import {
  TextInput,
  Button,
  Notification,
  Table,
  IconCrossCircle,
  IconStar,
  IconStarFill,
} from 'hds-react';
import ThemedDialog from '../components/ThemedDialog';
import { apiFetch, extractApiError } from '../services/api';
import PageLayout from '../components/PageLayout';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import TooltipButton from '../components/TooltipButton';
import BulkInviteResult from '../components/BulkInviteResult';
import useTheeeme from '../hooks/useTheeeme';
import useCollectionTheeeme from '../hooks/useCollectionTheeeme';
import { useLocalized } from '../utils/localized';
import { parseEmailList } from '../utils/emailList';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import { useCollectionBase } from '../hooks/useCollectionBase';
import useDocumentTitle from '../hooks/useDocumentTitle';

export default function ManageInvitesPage() {
  const { code } = useParams();
  const base = useCollectionBase(code);
  const navigate = useNavigate();
  const { t } = useTranslation();
  // Owner content (headlines, tags) may carry one text per language.
  const L = useLocalized();
  const { btnStyle, btnSecondaryStyle, tableTheme } = useTheeeme();
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [invites, setInvites] = useState([]);
  const [things, setThings] = useState([]);
  const [pendingInvites, setPendingInvites] = useState([]);
  // Members' recommendations awaiting a curator's answer. Curator-only from
  // the serializer: they name someone who has not been contacted and does not
  // know they were suggested, and they carry the proposer's private note.
  const [proposals, setProposals] = useState([]);
  const [answering, setAnswering] = useState(null);
  const [collectionHeadline, setCollectionHeadline] = useState('');
  const [collectionLanguage, setCollectionLanguage] = useState('');
  useCollectionLanguage(collectionLanguage, [collectionHeadline]);
  const [palette, setPalette] = useState(null);
  useCollectionTheeeme(palette?.colors, palette?.koro);
  const headline = L(collectionHeadline);
  useDocumentTitle(headline ? t('titles.guests', { headline }) : t('titles.guestsDefault'));
  // The whole management UI — promoting/demoting a co-curator included, since
  // 2026-09 — reads `isCurator`, the server-computed field that admits a
  // co-owner. The founder is no longer a distinct client-side tier here.
  const [isCurator, setIsCurator] = useState(false);
  // In a network the team and the members are the founder's alone: what one entity
  // does there reaches the others. `canAdmin` is what the star and the remove
  // control read; inviting and everything else stays with every curator.
  const [isNetwork, setIsNetwork] = useState(false);
  const [ownerCode, setOwnerCode] = useState('');
  const canAdmin =
    isCurator && (!isNetwork || ownerCode === (localStorage.getItem('userCode') || ''));
  const [coOwnerCodes, setCoOwnerCodes] = useState(new Set());
  // What is in the invitations field: one address or several, cut by commas.
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  // The summary of the last batch the field sent (several addresses at once), in the
  // shape the CSV tool says it in; null for none, or after a single invitation.
  const [bulkResult, setBulkResult] = useState(null);
  const [toast, setToast] = useState(null);
  const [promoting, setPromoting] = useState(null);
  // The member a curator has clicked to promote, pending confirmation. Promotion
  // hands over nearly the founder's whole reach — the member list (with emails)
  // and the power to appoint more co-curators included — and makes the person's
  // name public on the group's page, so it gets a confirm (DESIGN §6). Demotion
  // only removes access, so it stays a one-click toggle.
  const [promoteCandidate, setPromoteCandidate] = useState(null);
  // In a network demoting deletes the things the dinamizador ran, so it asks first and
  // says how many go (the same form as leaving a community group).
  const [demoteCandidate, setDemoteCandidate] = useState(null);
  const inviteLockRef = useRef(false);

  const fetchCollection = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/`);
      if (res.ok) {
        const data = await res.json();
        setInvites(data.invites || []);
        setThings(data.things || []);
        setPendingInvites(data.pending_invites || []);
        setProposals(data.pending_proposals || []);
        setCollectionHeadline(data.headline || '');
        setCollectionLanguage(data.language || '');
        setPalette({ colors: data.theeeme_colors, koro: data.koro });
        setIsCurator(!!data.is_curator);
        setIsNetwork(data.mode === 'NETWORK');
        setOwnerCode(data.owner || '');
        setCoOwnerCodes(new Set((data.co_owners || []).map((u) => u.code)));
        setLoadError('');
      } else {
        // A persistent error, not the auto-closing toast this used to raise.
        // The toast faded and left the page rendering isCurator=false over an
        // empty list — "no guests, and you can't invite anyone" — which is not
        // what happened. Every other data page in the app stops and says so.
        setLoadError(
          res.status === 403 ? 'manageInvites.noPermission' : 'manageInvites.errorLoading'
        );
      }
    } catch {
      setLoadError('common.connectionError');
    } finally {
      setLoading(false);
    }
    // `loadError` is an i18n key, translated where it is painted, so this callback
    // — and the effect below that re-runs whenever it changes — does not depend on
    // `t`. `useCollectionLanguage` swaps `t` once the first response lands; listing
    // it here fetched the collection a second time.
  }, [code]);

  useEffect(() => {
    // Calling the memoised fetch rather than inlining it: this same function is
    // what the approve/resend handlers re-run, so a copy here would be a second
    // definition to keep in step. It sets state, but none of that is a
    // render-time cascade — it is async and its first statement is the `await`,
    // so every setState lands in a continuation the network schedules long after
    // this render has painted.
    fetchCollection();
  }, [fetchCollection]);

  const answerProposal = async (proposalCode, decision) => {
    setAnswering(proposalCode);
    try {
      const res = await apiFetch(`/api/v1/proposals/${proposalCode}/${decision}/`, {
        method: 'POST',
      });
      if (res.ok) {
        setProposals((prev) => prev.filter((p) => p.code !== proposalCode));
        setToast({
          type: 'success',
          message:
            decision === 'approve' ? t('recommend.ownerApproved') : t('recommend.ownerDeclined'),
        });
        // An approval creates a pending invitation — reload so the guest list
        // shows it rather than looking as though nothing happened.
        if (decision === 'approve') fetchCollection();
      } else {
        const detail = await extractApiError(res);
        setToast({ type: 'error', message: detail || t('common.error') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setAnswering(null);
    }
  };

  // Promote/demote a co-curator. Any curator may, like the endpoint it calls
  // (2026-09). Re-fetches rather than patching state locally: the set of
  // co-owners is small and this keeps it the server's own word.
  const togglePromote = async (userCode, promote) => {
    setPromoting(userCode);
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/co-owners/`, {
        method: promote ? 'POST' : 'DELETE',
        body: JSON.stringify({ user_code: userCode }),
      });
      if (res.ok) {
        setToast({
          type: 'success',
          message: promote ? t('manageInvites.promoted') : t('manageInvites.demoted'),
        });
        fetchCollection();
      } else if (res.status === 429) {
        // Both directions are rate-limited (30/h), and a 429 has no body worth
        // showing.
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else {
        // A coded refusal (the co-curator ceiling) is said in the reader's
        // language by `extractApiError`, from `requestErrors.<code>`.
        const detail = await extractApiError(res);
        setToast({ type: 'error', message: detail || t('common.error') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setPromoting(null);
    }
  };

  // Several addresses are one batch for `invite/bulk/` — best-effort, never split into
  // single calls behind the reader's back, and never cut at 100: past the server's cap
  // its own message comes back and the field stays as it was. What was skipped (and
  // why) is the summary; what went out joins the pending list; the field keeps exactly
  // the addresses that did not, to be corrected or retried.
  const inviteMany = async (emails) => {
    const res = await apiFetch(`/api/v1/collections/${code}/invite/bulk/`, {
      method: 'POST',
      body: JSON.stringify({ invites: emails.map((email) => ({ email })) }),
    });
    if (res.ok) {
      const data = await res.json();
      // The server lowercases what it validates and cuts an invalid one at 64
      // characters, so the addresses are compared in that shape.
      const same = (email) => String(email).slice(0, 64).toLowerCase();
      const skipped = new Set((data.skipped || []).map((row) => same(row.email)));
      setPendingInvites((prev) => [
        ...prev,
        ...emails.filter((email) => !skipped.has(same(email))).map((email) => ({ email })),
      ]);
      setInviteEmail(emails.filter((email) => skipped.has(same(email))).join(', '));
      setBulkResult(data);
    } else if (res.status === 429) {
      setToast({ type: 'error', message: t('common.tooManyAttempts') });
    } else {
      const detail = await extractApiError(res);
      setToast({ type: 'error', message: detail || t('bulkInvite.error') });
    }
  };

  const inviteOne = async (email) => {
    const res = await apiFetch(`/api/v1/collections/${code}/invite/`, {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
    if (res.ok) {
      setPendingInvites((prev) => [...prev, { email }]);
      setInviteEmail('');
      setToast({ type: 'success', message: t('manageInvites.invitationSent') });
    } else if (res.status === 429) {
      setToast({ type: 'error', message: t('common.tooManyAttempts') });
    } else {
      const detail = await extractApiError(res);
      setToast({ type: 'error', message: detail || t('manageInvites.errorSending') });
    }
  };

  const handleInvite = async () => {
    if (inviteLockRef.current) return;
    const emails = parseEmailList(inviteEmail);
    if (emails.length === 0) return;
    inviteLockRef.current = true;
    setInviteLoading(true);
    setToast(null);
    setBulkResult(null);
    try {
      // One address is the invitation it always was; several are a batch.
      if (emails.length === 1) await inviteOne(emails[0]);
      else await inviteMany(emails);
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setInviteLoading(false);
      inviteLockRef.current = false;
    }
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  if (loadError) {
    return (
      <PageLayout title={t('common.error')} backTo={`${base}`} backLabel={t('common.collection')}>
        <Notification label={t('common.error')} type="error">
          {t(loadError)}
        </Notification>
        <div className="spacer-m" />
        <div className="button-row-wide">
          <Button
            variant="secondary"
            style={btnSecondaryStyle}
            onClick={() => {
              setLoading(true);
              fetchCollection();
            }}
          >
            {t('common.retry')}
          </Button>
        </div>
      </PageLayout>
    );
  }

  return (
    <PageLayout
      title={t('manageInvites.pageTitle')}
      backTo={`${base}`}
      backLabel={headline || t('common.collection')}
    >
      {/* Members' recommendations, above the guest list because they are the
          thing waiting on the owner. Each shows who suggested whom and their
          note — an owner asked to admit an address they don't recognise needs
          the proposer's word to decide. Nothing has been sent to the person
          named here. */}
      {isCurator && proposals.length > 0 && (
        <>
          <h2>{t('recommend.ownerHeading')}</h2>
          <div className="spacer-s" />
          <p className="text-muted">{t('recommend.ownerIntro')}</p>
          <div className="spacer-s" />
          {proposals.map((p) => (
            <div key={p.code} className="proposal-card">
              <p className="proposal-who">
                <strong>{p.email}</strong>
                <span className="proposal-by">
                  {' '}
                  {t('recommend.ownerBy', { name: p.proposer_name })}
                </span>
              </p>
              {p.note && <p className="proposal-note">“{p.note}”</p>}
              <div className="button-row-wide">
                <Button
                  style={btnStyle}
                  disabled={answering === p.code}
                  onClick={() => answerProposal(p.code, 'approve')}
                >
                  {t('recommend.ownerApprove')}
                </Button>
                <Button
                  variant="secondary"
                  style={btnSecondaryStyle}
                  disabled={answering === p.code}
                  onClick={() => answerProposal(p.code, 'reject')}
                >
                  {t('recommend.ownerReject')}
                </Button>
              </div>
            </div>
          ))}
          <div className="spacer-xl" />
        </>
      )}

      {invites.length === 0 && pendingInvites.length === 0 ? (
        <p>
          {t('manageInvites.noGuests')} {isCurator && t('manageInvites.noGuestsCta')}
        </p>
      ) : (
        (() => {
          const tableRows = [
            ...invites.map((inv) => ({
              _id: inv.code,
              guest: inv.name ? `${inv.name} (${inv.email})` : inv.email,
              status: coOwnerCodes.has(inv.code)
                ? t('manageInvites.coOwnerStatus')
                : t('manageInvites.accepted'),
              _isPending: false,
              _isCoOwner: coOwnerCodes.has(inv.code),
              _email: inv.email,
              _code: inv.code,
              _name: inv.name || inv.email,
              _ageRange: inv.age_range || '',
              _postal: inv.postal_code || '',
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
            {
              key: 'guest',
              headerName: t('manageInvites.colGuest'),
              transform: (row) => (
                <div>
                  <div>{row.guest}</div>
                  {(row._ageRange || row._postal) && (
                    <div
                      style={{ fontSize: 'var(--fontsize-body-s)', color: 'var(--color-black-60)' }}
                    >
                      {[row._ageRange ? t(`ageRange.${row._ageRange}`) : null, row._postal]
                        .filter(Boolean)
                        .join(' · ')}
                    </div>
                  )}
                </div>
              ),
            },
            { key: 'status', headerName: t('manageInvites.colStatus') },
            ...(isCurator
              ? [
                  {
                    key: '_actions',
                    // Named for a screen reader only: the buttons below say what they do,
                    // and an empty <th> leaves the column nameless (axe empty-table-header).
                    headerName: <span className="sr-only">{t('common.colActions')}</span>,
                    transform: (row) => (
                      <div
                        style={{
                          display: 'flex',
                          gap: 'var(--spacing-xs)',
                          alignItems: 'center',
                          justifyContent: 'flex-end',
                        }}
                      >
                        {/* Any curator promotes or demotes a co-curator now
                        (2026-09) — the founder is not a distinct tier here.
                        The founder's own row cannot be demoted (they are an
                        FK, not an invites row), so it never carries this. */}
                        {canAdmin && !row._isPending && (
                          <TooltipButton
                            tooltip={
                              row._isCoOwner
                                ? t('manageInvites.demoteTooltip')
                                : t('manageInvites.promoteTooltip')
                            }
                            onClick={() =>
                              row._isCoOwner
                                ? isNetwork
                                  ? setDemoteCandidate(row)
                                  : togglePromote(row._code, false)
                                : setPromoteCandidate(row)
                            }
                            disabled={promoting === row._code}
                          >
                            {row._isCoOwner ? (
                              <IconStarFill aria-hidden />
                            ) : (
                              <IconStar aria-hidden />
                            )}
                          </TooltipButton>
                        )}
                        {(row._isPending || canAdmin) && (
                          <TooltipButton
                            tooltip={t('manageInvites.removeTooltip')}
                            onClick={() =>
                              navigate(`${base}/invites/remove`, {
                                state: {
                                  guestCode: row._code,
                                  guestName: row._name,
                                  // Their things in this group go with them; the
                                  // confirmation names them.
                                  thingTitles: things
                                    .filter((thing) => thing.owner === row._code)
                                    .map((thing) => thing.headline),
                                  // Bare: with no headline, RemoveGuestPage's own
                                  // `t('removeGuest.guests')` is the right label for
                                  // where the link goes. A literal here is truthy and
                                  // would beat that fallback to it, in English.
                                  backLabel: headline,
                                  // The group's colours, so the confirmation is painted with
                                  // them from the first frame (it reads no collection).
                                  palette,
                                },
                              })
                            }
                          >
                            <IconCrossCircle aria-hidden />
                          </TooltipButton>
                        )}
                      </div>
                    ),
                  },
                ]
              : []),
          ];
          return (
            <div className="table-wrap">
              <Table
                cols={cols}
                caption={<span className="sr-only">{t('manageInvites.caption')}</span>}
                rows={tableRows}
                indexKey="_id"
                renderIndexCol={false}
                theme={tableTheme}
              />
            </div>
          );
        })()
      )}

      {isCurator && (
        <>
          <div className="spacer-xl" />
          <div className="form-grid section-mt">
            {/* One address or several, separated by commas, so this is
                a text field and not `type="email"`: the browser's email field strips
                the line breaks of a pasted list (gluing two addresses into one), has
                no place for `;`, and only takes commas with `multiple`. `inputMode`
                keeps the email keyboard on a phone, and the three attributes after it
                keep it from capitalising or "correcting" an address, which `type=email`
                did on its own. */}
            <TextInput
              id="manage-invites-email"
              label={t('manageInvites.emailLabel')}
              type="text"
              inputMode="email"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder={t('manageInvites.emailPlaceholder')}
              helperText={t('manageInvites.multipleHelper')}
            />
            <Button
              disabled={inviteLoading || parseEmailList(inviteEmail).length === 0}
              onClick={handleInvite}
              style={{ ...btnStyle, width: '100%' }}
            >
              {inviteLoading ? t('common.sending') : t('manageInvites.invite')}
            </Button>
          </div>
          <BulkInviteResult result={bulkResult} />
        </>
      )}

      {promoteCandidate && (
        <ThemedDialog
          id="promote-confirm"
          aria-labelledby="promote-confirm-title"
          isOpen
          close={() => setPromoteCandidate(null)}
          closeButtonLabelText={t('common.close')}
        >
          <ThemedDialog.Header
            id="promote-confirm-title"
            title={t('manageInvites.promoteConfirmTitle', { name: promoteCandidate._name })}
          />
          <ThemedDialog.Content>
            <p style={{ marginBottom: 0 }}>
              {t(
                isNetwork
                  ? 'manageInvites.promoteConfirmNetworkBody'
                  : 'manageInvites.promoteConfirmBody'
              )}
            </p>
          </ThemedDialog.Content>
          <ThemedDialog.ActionButtons>
            <Button
              style={btnStyle}
              onClick={() => {
                const row = promoteCandidate;
                setPromoteCandidate(null);
                togglePromote(row._code, true);
              }}
            >
              {t('manageInvites.promoteConfirm')}
            </Button>
            <Button
              variant="secondary"
              style={btnSecondaryStyle}
              onClick={() => setPromoteCandidate(null)}
            >
              {t('common.cancel')}
            </Button>
          </ThemedDialog.ActionButtons>
        </ThemedDialog>
      )}

      {demoteCandidate && (
        <ThemedDialog
          id="demote-confirm"
          aria-labelledby="demote-confirm-title"
          isOpen
          close={() => setDemoteCandidate(null)}
          closeButtonLabelText={t('common.close')}
        >
          <ThemedDialog.Header
            id="demote-confirm-title"
            title={t('manageInvites.demoteConfirmTitle', { name: demoteCandidate._name })}
          />
          <ThemedDialog.Content>
            <p style={{ marginBottom: 0 }}>
              {t('manageInvites.demoteNetworkBody', {
                count: things.filter((thing) => thing.owner === demoteCandidate._code).length,
              })}
            </p>
          </ThemedDialog.Content>
          <ThemedDialog.ActionButtons>
            <Button
              style={btnStyle}
              onClick={() => {
                const row = demoteCandidate;
                setDemoteCandidate(null);
                togglePromote(row._code, false);
              }}
            >
              {t('manageInvites.demoteConfirm')}
            </Button>
            <Button
              variant="secondary"
              style={btnSecondaryStyle}
              onClick={() => setDemoteCandidate(null)}
            >
              {t('common.cancel')}
            </Button>
          </ThemedDialog.ActionButtons>
        </ThemedDialog>
      )}

      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
