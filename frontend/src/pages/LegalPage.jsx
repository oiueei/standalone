import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import PageLayout from '../components/PageLayout';
import MarkdownText from '../components/MarkdownText';
import legalEs from '../legal/es';
import legalCa from '../legal/ca';
import legalEn from '../legal/en';

const CONTENT = { es: legalEs, ca: legalCa, en: legalEn };

/**
 * Public legal page (`/legal`): commitment (the manifesto, now public),
 * instance/operator identification, privacy, and basic terms — in the reader's
 * language. The content lives in `src/legal/{lang}.js` as Markdown so a
 * deployment can carry its own version: the standalone repo ships a generic
 * operator-neutral text, and the official www.oiueei.com deploy branch
 * replaces those files with the full RGPD/LSSI version of its owner.
 */
export default function LegalPage() {
  const { t, i18n } = useTranslation();
  useEffect(() => { document.title = t('titles.legal'); }, [t]);
  const lang = (i18n.language || 'en').split('-')[0];
  const content = CONTENT[lang] || CONTENT.en;
  const isLoggedIn = !!localStorage.getItem('userCode');

  return (
    <PageLayout
      title={t('legal.pageTitle')}
      backTo={isLoggedIn ? '/' : '/login'}
      backLabel={isLoggedIn ? t('common.home') : t('verify.goToLogin')}
    >
      <div className="legal-content" style={{ maxWidth: '720px' }}>
        <MarkdownText text={content} headingBase={2} />
      </div>
    </PageLayout>
  );
}
