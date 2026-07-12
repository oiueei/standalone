import { Koros } from 'hds-react';
import BackLink from './BackLink';
import useTheeeme from '../hooks/useTheeeme';

/**
 * The shared page chrome: a theeeme-coloured `form-hero` (optional back link,
 * title, optional description) bridged by a `Koros` wave into a `page-container`
 * for the main content.
 *
 * Centralises the ~18-line wrapper that was copied across the uniform form pages.
 * Pages with a custom hero (owner action buttons, a profile photo, etc.) keep
 * their bespoke markup and do not use this component. The theeeme colours and
 * Koros type come from `useTheeeme`, so the output is identical to the inline
 * version each page had.
 *
 * Props:
 * - `title`: hero `<h1>` text.
 * - `backTo` / `backLabel`: optional back link (rendered only when `backTo` is set).
 * - `description`: optional hero paragraph under the title.
 * - `children`: page-container content.
 */
export default function PageLayout({ title, backTo, backLabel, description, children }) {
  const { tc, koro } = useTheeeme();
  return (
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})`, '--hero-logo-color': `var(--color-${tc.color_02})` } : undefined}
      >
        <div
          className="form-hero-content"
          style={tc.color_05 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}
        >
          {backTo && <BackLink to={backTo} label={backLabel} />}
          {title && <h1 className="form-hero-title">{title}</h1>}
          {description && <p className="form-hero-text">{description}</p>}
        </div>
        <Koros
          className="form-hero-koros"
          type={koro}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">{children}</div>
    </div>
  );
}
