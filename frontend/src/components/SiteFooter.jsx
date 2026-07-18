import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import useTheeeme from '../hooks/useTheeeme';

/**
 * The one-line colophon under every page (i14): "Made with ♥︎ in Zona Franca,
 * Barcelona…". Global (mounted once in App), painted with the viewer's theeeme
 * `color_02` — the same token every `.form-page` uses as its background — so
 * there is no colour seam under the 100vh page. `useLocation()` re-renders it
 * on navigation, which re-reads the theeeme after a login/profile change (the
 * pages get this for free by remounting; a permanent component must ask).
 * The heart is U+2665 + U+FE0E (text presentation) so it inherits the text
 * colour instead of turning into a red emoji.
 */
export default function SiteFooter() {
  useLocation();
  const { t } = useTranslation();
  const { tc } = useTheeeme();
  return (
    <footer
      className="site-footer"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      {t('footer.madeIn')}
    </footer>
  );
}
