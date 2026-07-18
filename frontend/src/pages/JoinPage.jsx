import { useEffect } from 'react';
import { useParams, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Koros } from 'hds-react';
import BackLink from '../components/BackLink';
import JoinToAct from '../components/JoinToAct';
import useTheeeme from '../hooks/useTheeeme';
import ContactCorner from '../components/ContactCorner';

/**
 * Login-to-act landing page for a PUBLIC collection. An anonymous visitor who
 * clicks an action button (reserve / order / respond …) on a public collection
 * lands here: they enter their email, the backend (pop-in) joins them to that
 * collection and emails a magic link, and following it drops them back on the
 * collection — now a member who can act. Standard `form-hero` + `Koros` layout.
 */
export default function JoinPage() {
  const { code } = useParams();
  const location = useLocation();
  const { t } = useTranslation();
  const { tc, koro } = useTheeeme();
  const headline = location.state?.collectionHeadline || '';

  useEffect(() => { document.title = `${t('joinToAct.heading')} — OIUEEI`; }, [t]);

  return (
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})`, '--hero-logo-color': `var(--color-${tc.color_02})` } : undefined}
      >
        <div className="form-hero-content" style={tc.color_05 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
          <ContactCorner />
          <BackLink to={`/collections/${code}`} label={headline || t('common.collection')} />
          <h1 className="form-hero-title">{t('joinToAct.heading')}</h1>
        </div>
        <Koros
          className="form-hero-koros"
          type={koro}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        <JoinToAct collectionCode={code} collectionHeadline={headline} />
      </div>
    </div>
  );
}
