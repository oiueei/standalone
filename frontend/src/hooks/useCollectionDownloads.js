import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../services/api';
import downloadBlob, { filenameFromResponse } from '../utils/downloadBlob';
import useCalendarExport from './useCalendarExport';

/**
 * The three downloads a curator takes from the collection's own page (the
 * collection menu, 2026-10-03): the calendar .ics, the stats CSV and the
 * whole-collection JSON. `CollectionPage` calls this once and hands the
 * result to the menu and to the status zone under the hero's
 * row of buttons: one call, two halves, so the menu that starts a download and the zone
 * that reports it can never disagree about which one is running.
 *
 * The calendar half is `useCalendarExport` untouched: the POST, the
 * `X-Calendar-Events` count gate and the server-set filename stay where
 * they were. The stats and JSON halves moved from `EditCollectionPage`
 * as they were — same URLs, same filenames, same failure copy.
 *
 * `active` names the download that last started, and the status zone
 * renders only that one's state, which is what keeps the page at one
 * message at a time: starting a second download drops the first's
 * outcome, so a finished "3 events" cannot sit beside a half-done
 * stats file and read as both having completed.
 */
export default function useCollectionDownloads(code) {
  const { t } = useTranslation();
  const calendar = useCalendarExport(code);
  const [active, setActive] = useState(null);
  const [statsError, setStatsError] = useState(false);
  const [statsDownloading, setStatsDownloading] = useState(false);
  const [collectionExportError, setCollectionExportError] = useState(null);
  const [collectionExportDownloading, setCollectionExportDownloading] = useState(false);

  const calendarDownload = calendar.download;
  const downloadCalendar = useCallback(async () => {
    setActive('calendar');
    await calendarDownload();
  }, [calendarDownload]);

  const downloadStats = useCallback(async () => {
    setActive('stats');
    setStatsError(false);
    setStatsDownloading(true);
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/stats/`);
      if (!res.ok) throw new Error('stats');
      downloadBlob(await res.blob(), `${code}-stats.csv`);
    } catch {
      setStatsError(true);
    } finally {
      setStatsDownloading(false);
    }
  }, [code]);

  const downloadCollectionExport = useCallback(async () => {
    setActive('collectionExport');
    setCollectionExportError(null);
    setCollectionExportDownloading(true);
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/export/`);
      if (res.ok) {
        downloadBlob(await res.blob(), filenameFromResponse(res, `${code}.json`));
      } else if (res.status === 429) {
        setCollectionExportError(t('common.tooManyAttempts'));
      } else {
        setCollectionExportError(t('collectionExport.error'));
      }
    } catch {
      setCollectionExportError(t('common.connectionError'));
    } finally {
      setCollectionExportDownloading(false);
    }
  }, [code, t]);

  return {
    active,
    calendar: { ...calendar, download: downloadCalendar },
    stats: { download: downloadStats, downloading: statsDownloading, error: statsError },
    collectionExport: {
      download: downloadCollectionExport,
      downloading: collectionExportDownloading,
      error: collectionExportError,
    },
  };
}
