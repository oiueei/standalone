import { useTranslation } from 'react-i18next';

// Alpha feedback channel (also linked from the README) — a quiet line so every
// page it sits on doubles as a listening post, without shouting. A deployment
// can point it at its own form via VITE_FEEDBACK_URL (baked in at build time).
const FEEDBACK_URL = import.meta.env.VITE_FEEDBACK_URL || 'https://tally.so/r/A76Xkz';

export default function FeedbackLink() {
  const { t } = useTranslation();
  return (
    <p className="feedback-link">
      {t('feedback.prompt')}{' '}
      <a href={FEEDBACK_URL} target="_blank" rel="noopener noreferrer">
        {t('feedback.cta')} →
      </a>
    </p>
  );
}
