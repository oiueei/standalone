import { useEffect, useRef, useState } from 'react';
import { useParams, Link } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Koros, Notification } from 'hds-react';
import BackLink from '../components/BackLink';
import PageLayout from '../components/PageLayout';
import { apiFetch } from '../services/api';
import { fetchAllPages } from '../utils/fetchAllPages';
import LoadingSpinner from '../components/LoadingSpinner';
import MarkdownText from '../components/MarkdownText';
import CollectionLinkbox from '../components/CollectionLinkbox';
import { useLocalized } from '../utils/localized';
import { formatDate } from '../utils/rental';
import { teamText } from '../utils/team';
import HeroPhoto from '../components/HeroPhoto';
import AccountMenu from '../components/AccountMenu';
import ButtonLink from '../components/ButtonLink';
import ResponsiveTable from '../components/ResponsiveTable';
import useTheeeme from '../hooks/useTheeeme';
import { collectionPath } from '../utils/collectionPath';
import useDocumentTitle from '../hooks/useDocumentTitle';
import { errorKey, translateError } from '../utils/errorKey';
import { uiLanguage } from '../utils/uiLanguage';

// The groups of the account, each once: the ones it runs first, then the ones it is
// only a member of; each part keeps the order of its own list. What it runs is what
// `/collections/` lists (the active ones — Home lists the archived apart) and, should
// that list be missing, a co-curator's group from the other list, which says so in
// `is_curator`: a co-curator is always on the invite list too.
function groupRows(running, memberships) {
  const all = [
    ...running.filter((c) => c.status === 'ACTIVE').map((c) => ({ ...c, _runs: true })),
    ...memberships.map((c) => ({ ...c, _runs: !!c.is_curator })),
  ];
  const seen = new Set();
  const once = all.filter((c) => !seen.has(c.code) && seen.add(c.code));
  return [...once.filter((c) => c._runs), ...once.filter((c) => !c._runs)];
}

export default function UserPage() {
  const { userCode: paramCode } = useParams();
  const { t, i18n } = useTranslation();
  // A group's headline may carry one text per language.
  const L = useLocalized();
  const [user, setUser] = useState(null);
  const [error, setError] = useState('');
  // Every group the account is in, so the profile shows them all: the ones it
  // runs, owner or co-curator (`/collections/`, the list Home calls "My
  // collections"), and the ones it is only a member of (`/invited-collections/`).
  // Each list is read on its own, so one failing costs only its half. Leaving is
  // something you do to your own membership, so "Leave the group" is here, and
  // only for a member: whoever runs a group cannot leave it (the server refuses
  // it; a co-curator is demoted first), so those rows say so instead of offering
  // a link that would fail.
  const [running, setRunning] = useState([]);
  const [memberships, setMemberships] = useState([]);

  const userCode = paramCode || localStorage.getItem('userCode');
  const isOwnProfile = !paramCode || paramCode === localStorage.getItem('userCode');

  // This page builds its own hero (not PageLayout), so it derives the theeeme
  // styles itself — via the shared hook, so the keyboard-focus pins ride along.
  // A profile is an app page: the app's palette, whoever's it is.
  const { tc, koro: koroType, btnStyle, btnSecondaryStyle, tableTheme } = useTheeeme();
  useDocumentTitle(t('titles.user', { name: user?.name || t('common.profile') }));

  // The code `/auth/me/` answered with, when this page had none stored: that answer
  // is the profile (`UserSerializer`, the same one `/users/{code}/` serves for the
  // own profile), so storing the code must not send a second request for it.
  const loadedFromMe = useRef(null);

  useEffect(() => {
    if (loadedFromMe.current && loadedFromMe.current === userCode) return;
    if (!userCode) {
      // If no userCode yet, fetch /me to get it
      apiFetch('/api/v1/auth/me/')
        .then((res) => (res.ok ? res.json() : Promise.reject()))
        .then((data) => {
          if (data.code) {
            loadedFromMe.current = data.code;
            localStorage.setItem('userCode', data.code);
          }
          setUser(data);
        })
        .catch(() => setError(errorKey('userPage.errorLoading')));
      return;
    }

    const fetchUser = async () => {
      try {
        const res = await apiFetch(`/api/v1/users/${userCode}/`);
        if (res.ok) {
          const data = await res.json();
          setUser(data);
        } else if (res.status === 403) {
          setError(errorKey('userPage.noPermission'));
        } else if (res.status === 404) {
          setError(errorKey('userPage.notFound'));
        } else {
          setError(errorKey('userPage.errorLoading'));
        }
      } catch {
        setError(errorKey('common.connectionError'));
      }
    };
    fetchUser();
  }, [userCode, isOwnProfile, t]);

  useEffect(() => {
    if (!isOwnProfile) return undefined;
    const controller = new AbortController();
    fetchAllPages(apiFetch, '/api/v1/collections/?page_size=100', { signal: controller.signal })
      .then(({ rows }) => setRunning(rows))
      // A failed fetch only costs its half of the groups — it must never take the
      // profile down with it.
      .catch(() => {});
    apiFetch('/api/v1/invited-collections/', { signal: controller.signal })
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => setMemberships(Array.isArray(data) ? data : []))
      .catch(() => {});
    return () => controller.abort();
  }, [isOwnProfile]);

  if (error) {
    return (
      <PageLayout title={t('common.error')} backTo="/" backLabel={t('common.home')}>
        <Notification label={t('common.error')} type="error">
          {translateError(t, error)}
        </Notification>
      </PageLayout>
    );
  }

  if (!user) {
    return <LoadingSpinner />;
  }

  const groups = groupRows(running, memberships);

  const heroContent = (
    <div
      className="form-hero-content"
      style={tc.color_05 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}
    >
      <span className="hero-corners">
        <AccountMenu />
      </span>
      <BackLink to="/" label={t('common.home')} />
      {user.headline && (
        <p
          style={{
            fontSize: 'var(--fontsize-heading-m)',
            fontWeight: 700,
            lineHeight: 'var(--lineheight-m)',
            letterSpacing: '-0.2px',
            color: 'var(--hero-text-color, var(--color-black-90))',
          }}
        >
          {user.headline}
        </p>
      )}
      <h1 className="form-hero-title">{user.name || user.email}</h1>
      {user.created && (
        <p className="form-hero-text" style={{ fontSize: 'var(--fontsize-body-m)' }}>
          {t('userPage.memberSince', {
            date: formatDate(user.created),
          })}
        </p>
      )}
      {isOwnProfile && (
        <div className="button-row-wide">
          <ButtonLink to="/me/edit" style={btnStyle}>
            {t('userPage.editProfile')}
          </ButtonLink>
          <ButtonLink to="/logout" style={btnSecondaryStyle}>
            {t('userPage.logout')}
          </ButtonLink>
        </div>
      )}
    </div>
  );

  return (
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className={`form-hero${user.photo_url ? ' form-hero--photo' : ''}`}
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})` } : undefined}
      >
        <div className="form-hero-split">{heroContent}</div>
        {user.photo_url && (
          <HeroPhoto
            photoUrl={user.photo_url}
            alt={t('userPage.photoAlt', { name: user.name || user.email })}
            koroType={koroType}
            color03={tc.color_03}
          />
        )}
        <Koros
          className="form-hero-koros"
          type={koroType}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        {user.about && (
          <>
            <h2>{t('userPage.aboutHeading')}</h2>
            <div className="spacer-s" />
            <MarkdownText text={user.about} className="about-markdown" />
            <div className="spacer-l" />
          </>
        )}
        {isOwnProfile && groups.length > 0 && (
          <>
            <h2>{t('userPage.myGroups')}</h2>
            <div className="spacer-s" />
            <p className="text-muted">{t('userPage.myGroupsIntro')}</p>
            <div className="spacer-m" />
            {/* The same table as the request pages: the group, who
                runs it — the rule the collection's own hero follows, as plain
                text — and the way out, on the right. On a phone each group is a
                card: the name on top, "Run by: …" under it and
                the way out on the right, the same cells in the same order. */}
            <ResponsiveTable
              cols={[
                {
                  key: '_group',
                  headerName: t('userPage.colGroup'),
                  transform: (row) => (
                    <Link to={collectionPath(row._code, row._kind)}>{row._headline}</Link>
                  ),
                },
                {
                  key: '_team',
                  headerName: t('userPage.colTeam'),
                  // "Run by: …" in a card, where the other columns need no label.
                  // Nothing when no one is named: the table's cell stays empty and
                  // the card leaves out the whole line, label included.
                  cardLabel: true,
                  transform: (row) =>
                    row._team ? (
                      <div className="table-cell-lines">
                        <p>{row._team}</p>
                      </div>
                    ) : null,
                },
                {
                  key: '_actions',
                  // Named for a screen reader only, like the request tables: the
                  // link says what it does, and an empty <th> leaves the column
                  // nameless (axe empty-table-header).
                  headerName: <span className="sr-only">{t('common.colActions')}</span>,
                  transform: (row) => (
                    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                      {row._runs ? (
                        <div className="table-cell-lines">
                          <p className="table-cell-line--muted">{t('userPage.youRunIt')}</p>
                        </div>
                      ) : (
                        <Link
                          to={collectionPath(row._code, row._kind, '/leave')}
                          state={{ headline: row._headline }}
                          className="table-cell-link--muted"
                        >
                          {t('collectionPage.leaveGroup')}
                        </Link>
                      )}
                    </div>
                  ),
                },
              ]}
              caption={<span className="sr-only">{t('userPage.myGroups')}</span>}
              rows={groups.map((c) => ({
                _id: c.code,
                _code: c.code,
                _kind: c.kind,
                _headline: L(c.headline),
                _team: teamText(c, t, uiLanguage(i18n)),
                _runs: c._runs,
              }))}
              indexKey="_id"
              renderIndexCol={false}
              dense
              theme={tableTheme}
            />
            <div className="spacer-l" />
          </>
        )}
        {!isOwnProfile && user.shared_collections && user.shared_collections.length > 0 && (
          <>
            <h2>{t('userPage.collectionsInCommon')}</h2>
            <div className="spacer-m" />
            <div className="collections-grid">
              {user.shared_collections.map((c) => (
                <CollectionLinkbox key={c.code} collection={c} />
              ))}
            </div>
          </>
        )}
        {!isOwnProfile &&
          !user.about &&
          (!user.shared_collections || user.shared_collections.length === 0) && (
            <p>{t('userPage.noSharedCollections', { name: user.name || user.email })}</p>
          )}
      </div>
    </div>
  );
}
