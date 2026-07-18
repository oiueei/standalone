import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ContactFormPage from '../components/ContactFormPage';

/**
 * The support channel (`/contact`): the shared operator-message form with the
 * support copy, plus a quiet pointer to the collaborate page — the other door.
 */
export default function ContactPage() {
  const { t } = useTranslation();
  return (
    <ContactFormPage
      docTitleKey="titles.contact"
      titleKey="contact.pageTitle"
      introKey="contact.intro"
      kind="support"
      idPrefix="contact"
    >
      <p style={{ marginTop: 'var(--spacing-m)' }}>
        <Link to="/collaborate" style={{ textDecoration: 'underline' }}>
          {t('collaborate.linkFromContact')}
        </Link>
      </p>
    </ContactFormPage>
  );
}
