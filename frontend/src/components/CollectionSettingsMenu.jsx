import { useRef, useState } from 'react';
import { Link } from 'react-router';
import { useTranslation } from 'react-i18next';
import { IconPenLine } from 'hds-react';
import useDismissable from '../hooks/useDismissable';
import { useCollectionBase } from '../hooks/useCollectionBase';
import { collectionPath } from '../utils/collectionPath';

const PANEL_ID = 'collection-settings-menu-panel';

/**
 * The way to the collection's settings pages, one icon in the hero's corner
 * between the account menu and the collection menu. Curators only (owner and
 * co-curators, `is_curator`): the same gate as "Edit collection".
 *
 * Built like `CollectionMenu`: a trigger with `aria-expanded` / `aria-controls`
 * and a plain `<div>` panel of links — not `role="menu"`, which would promise
 * arrow-key navigation these ordinary Tab-reachable links do not have, and no
 * `aria-label` on the panel (axe flags one on a div with no role).
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
          <Link to={`${base}/settings/appearance`} onClick={close}>
            {t('collectionSettings.appearance')}
          </Link>
          <Link to={`${base}/settings/notifications`} onClick={close}>
            {t('collectionSettings.notifications')}
          </Link>
          {/* A stall has no request page, so nothing to say about when it can be asked for. */}
          {(kind === 'LIBRARY' || kind === 'SHED') && (
            <Link to={`${base}/settings/availability`} onClick={close}>
              {t('collectionSettings.availability')}
            </Link>
          )}
        </div>
      )}
    </span>
  );
}
