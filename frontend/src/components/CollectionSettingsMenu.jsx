import { useRef, useState } from 'react';
import { Link } from 'react-router';
import { useTranslation } from 'react-i18next';
import { IconBell, IconCalendar, IconPenLine } from 'hds-react';
import { IconGeneral, IconTheeemes } from './icons/OiueeiIcons';
import useDismissable from '../hooks/useDismissable';
import { useCollectionBase } from '../hooks/useCollectionBase';
import { collectionPath } from '../utils/collectionPath';

const PANEL_ID = 'collection-settings-menu-panel';

/**
 * The way to the collection's settings pages, one icon in the hero's corner
 * between the account menu and the collection menu. Curators only (owner and
 * co-curators, `is_curator`; in a network only its founder, `canEditCollection`).
 *
 * Built like `CollectionMenu`: a trigger with `aria-expanded` / `aria-controls`
 * and a plain `<div>` panel of links — not `role="menu"`, which would promise
 * arrow-key navigation these ordinary Tab-reachable links do not have, and no
 * `aria-label` on the panel (axe flags one on a div with no role).
 *
 * The panel opens with "General" (the collection's title, description, state, mode and
 * visibility), then Appearance, Notifications and, where the kind has one,
 * Availability.
 *
 * Props: `code`; `kind` (makes the address of the pages).
 */
export default function CollectionSettingsMenu({ code, kind }) {
  const { t } = useTranslation();
  const routeBase = useCollectionBase(code);
  const base = kind ? collectionPath(code, kind) : routeBase;
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef(null);
  const buttonRef = useRef(null);
  useDismissable({ open, setOpen, wrapperRef, buttonRef });
  const close = () => setOpen(false);

  return (
    <span className="collection-settings-menu" ref={wrapperRef}>
      <button
        type="button"
        ref={buttonRef}
        className="collection-settings-menu-trigger"
        aria-label={t('collectionSettings.menu')}
        aria-expanded={open}
        aria-controls={open ? PANEL_ID : undefined}
        onClick={() => setOpen((v) => !v)}
      >
        <IconPenLine aria-hidden="true" />
      </button>
      {open && (
        <div id={PANEL_ID} className="collection-settings-menu-panel">
          <Link to={`${base}/edit`} onClick={close}>
            <IconGeneral aria-hidden="true" />
            <span>{t('collectionSettings.general')}</span>
          </Link>
          <Link to={`${base}/settings/appearance`} onClick={close}>
            <IconTheeemes aria-hidden="true" />
            <span>{t('collectionSettings.appearance')}</span>
          </Link>
          <Link to={`${base}/settings/notifications`} onClick={close}>
            <IconBell aria-hidden="true" />
            <span>{t('collectionSettings.notifications')}</span>
          </Link>
          {/* A stall has no request page, so nothing to say about when it can be asked for. */}
          {(kind === 'LIBRARY' || kind === 'SHED') && (
            <Link to={`${base}/settings/availability`} onClick={close}>
              <IconCalendar aria-hidden="true" />
              <span>{t('collectionSettings.availability')}</span>
            </Link>
          )}
        </div>
      )}
    </span>
  );
}
