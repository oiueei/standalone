import { Notification } from 'hds-react';
import { useTranslation } from 'react-i18next';
import { useLocalized } from '../utils/localized';
import { formatList } from '../utils/team';
import { uiLanguage } from '../utils/uiLanguage';

/**
 * The warning on the two pages that end a membership (leaving a group, removing
 * a member): the things of that person in that group are deleted with it, and it
 * names them. Nothing at all when there are none.
 *
 * `label` is the notice's title and `body(count, list)` its sentence, both written
 * by the page in its own words; `titles` are the things' headlines as the API sends
 * them (an owner may have written one per language).
 */
export default function ThingsGoNotice({ titles, label, body }) {
  const { i18n } = useTranslation();
  const L = useLocalized();
  if (!titles?.length) return null;
  const list = formatList(titles.map(L), uiLanguage(i18n));
  return (
    <>
      <div className="spacer-xs" />
      <Notification type="alert" label={label}>
        {body(titles.length, list)}
      </Notification>
    </>
  );
}
