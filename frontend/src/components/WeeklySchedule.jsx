import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Table } from 'hds-react';
import { apiFetch } from '../services/api';

const DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];

function getMonday(date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  d.setDate(diff);
  return d;
}

function formatDate(d) {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export default function WeeklySchedule({ thingCode, isOwner, requestPath }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [weekStart, setWeekStart] = useState(() => getMonday(new Date()));
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const tc = JSON.parse(localStorage.getItem('theeemeColors') || '{}');
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;
  const btnSecondaryStyle = tc.color_01 ? {
    '--background-color': tc.color_02 ? `var(--color-${tc.color_02})` : undefined,
    '--border-color': `var(--color-${tc.color_01})`,
    '--color': `var(--color-${tc.color_04})`,
    '--background-color-hover': `var(--color-${tc.color_01})`,
    '--color-hover': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
  } : undefined;

  useEffect(() => {
    setLoading(true);
    const ws = formatDate(weekStart);
    apiFetch(`/api/v1/things/${thingCode}/slots/?week_start=${ws}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((d) => { if (d) setData(d); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [thingCode, weekStart]);

  const handlePrevWeek = () => {
    const d = new Date(weekStart);
    d.setDate(d.getDate() - 7);
    setWeekStart(d);
  };

  const handleNextWeek = () => {
    const d = new Date(weekStart);
    d.setDate(d.getDate() + 7);
    setWeekStart(d);
  };

  if (loading && !data) return <p>{t('common.loading')}</p>;
  if (!data || !data.days || data.days.every((d) => d.slots.length === 0)) {
    return <p>{t('appointment.noSlots')}</p>;
  }

  // Collect all unique time slots across all days
  const allTimes = new Set();
  data.days.forEach((day) => {
    day.slots.forEach((s) => {
      allTimes.add(s.start_time + '-' + s.end_time);
    });
  });
  const sortedTimes = [...allTimes].sort();

  // Build rows for the table
  const rows = sortedTimes.map((timeKey) => {
    const [start, end] = timeKey.split('-');
    const row = { _id: timeKey, time: `${start}–${end}` };
    data.days.forEach((day, i) => {
      const slot = day.slots.find((s) => s.start_time + '-' + s.end_time === timeKey);
      row[DAY_KEYS[i]] = slot || null;
      row[DAY_KEYS[i] + '_date'] = day.date;
    });
    return row;
  });

  // Build columns
  const cols = [
    { key: 'time', headerName: '' },
    ...data.days.map((day, i) => ({
      key: DAY_KEYS[i],
      headerName: `${t('appointment.' + DAY_KEYS[i])} ${new Date(day.date + 'T00:00:00').toLocaleDateString(i18n.language, { day: 'numeric', month: 'short' })}`,
      transform: ({ _id: timeKey, ...row }) => {
        const slot = row[DAY_KEYS[i]];
        const date = row[DAY_KEYS[i] + '_date'];
        if (!slot) return '';
        if (slot.status === 'available') {
          if (isOwner) return t('appointment.available');
          return (
            <button
              className="slot-available"
              style={btnStyle}
              onClick={() => {
                navigate(requestPath, {
                  state: {
                    backPath: window.location.pathname,
                    backLabel: t('common.back'),
                    prefillDate: date,
                    prefillStartTime: slot.start_time,
                    prefillEndTime: slot.end_time,
                  },
                });
              }}
            >
              {t('appointment.bookSlot')}
            </button>
          );
        }
        if (slot.status === 'pending') {
          return <span className="slot-pending">{t('appointment.pending')}</span>;
        }
        return <span className="slot-booked">{t('appointment.booked')}</span>;
      },
    })),
  ];

  return (
    <div className="weekly-schedule">
      <div className="weekly-schedule-nav">
        <Button variant="secondary" size="small" onClick={handlePrevWeek} style={btnSecondaryStyle}>
          {t('appointment.prevWeek')}
        </Button>
        <span className="weekly-schedule-label">
          {new Date(data.week_start + 'T00:00:00').toLocaleDateString(i18n.language, { day: 'numeric', month: 'long', year: 'numeric' })}
        </span>
        <Button variant="secondary" size="small" onClick={handleNextWeek} style={btnSecondaryStyle}>
          {t('appointment.nextWeek')}
        </Button>
      </div>
      <Table
        cols={cols}
        rows={rows}
        indexKey="_id"
        renderIndexCol={false}
        zebra
        theme={tc.color_03 ? { '--header-background-color': `var(--color-${tc.color_03})` } : undefined}
      />
    </div>
  );
}
