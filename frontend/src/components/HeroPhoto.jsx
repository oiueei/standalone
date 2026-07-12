import { Koros } from 'hds-react';

/**
 * The photo block for a `.form-hero.form-hero--photo` hero. Desktop (≥768px)
 * renders the layered angled-koros composition (photo full-bleed, a
 * colour_03 diagonal wedge carving it so the hero text reads, the wave koros
 * rotated 135deg as part of the wedge). Mobile (<768px, see App.css) hides
 * the wedge and stacks instead: the hero text flows above this block on the
 * colour_03 band, then `.hero-photo-top-koros` (biting the photo's top
 * edge), then the photo as a plain full-width block.
 *
 * Render as a sibling of `.form-hero-split`, inside `.form-hero.form-hero--photo`.
 *
 * Props:
 *   photoUrl – image src
 *   alt – image alt text
 *   koroType – the viewer's koro preference (Koros `type` prop)
 *   color03 – the hero's colour_03 token name (e.g. "engel"), used for the
 *     wedge fill and the mobile wave — omitted falls back to the CSS default
 */
export default function HeroPhoto({ photoUrl, alt, koroType, color03 }) {
  const fillStyle = color03 ? { fill: `var(--color-${color03})` } : undefined;
  const bgStyle = color03 ? { backgroundColor: `var(--color-${color03})` } : undefined;

  return (
    <div className="hero-photo-wrap">
      {/* Mobile-only wave, hidden on desktop (App.css) — bites the photo's top edge. */}
      <Koros className="hero-photo-top-koros" type={koroType} style={fillStyle} />
      <img className="hero-photo" src={photoUrl} alt={alt} />
      {/* Desktop-only diagonal colour wedge (z1) carves the photo so the content reads. */}
      <div className="hero-photo-diag" aria-hidden="true">
        <div className="hero-photo-diag-fill" style={bgStyle} />
        <Koros className="hero-photo-diag-koros" type={koroType} style={fillStyle} />
      </div>
    </div>
  );
}
