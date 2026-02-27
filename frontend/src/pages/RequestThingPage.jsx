import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Button, DateInput, NumberInput } from 'hds-react';
import { DATE_TYPES, ORDER_TYPE } from '../constants/things';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import Toast from '../components/Toast';

const TODAY = new Date();
TODAY.setHours(0, 0, 0, 0);
const MAX_DATE = new Date(TODAY);
MAX_DATE.setDate(MAX_DATE.getDate() + 90);
const RANGE_ERROR = 'Date must be between today and 90 days from today.';

export default function RequestThingPage() {
  const { code, thingCode } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const userCode = localStorage.getItem('userCode');
  const backPath = location.state?.backPath || '/';
  const backLabel = location.state?.backLabel || 'Back';

  useEffect(() => {
    if (!userCode) {
      navigate('/login');
    }
  }, [userCode, navigate]);

  const [thing, setThing] = useState(null);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [deliveryDate, setDeliveryDate] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [attempted, setAttempted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [blockedPeriods, setBlockedPeriods] = useState([]);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    if (!userCode) return;
    apiFetch(`/api/v1/things/${thingCode}/`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) setThing(data);
      })
      .catch(() => {});
  }, [userCode, thingCode, code]);

  useEffect(() => {
    if (!userCode || !thing || !DATE_TYPES.includes(thing.type)) return;
    apiFetch(`/api/v1/things/${thingCode}/calendar/`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setBlockedPeriods(data))
      .catch(() => {});
  }, [userCode, thingCode, thing]);

  const isDateBlocked = (date) => {
    return blockedPeriods.some((period) => {
      const start = new Date(period.start_date);
      const end = new Date(period.end_date);
      start.setHours(0, 0, 0, 0);
      end.setHours(0, 0, 0, 0);
      const d = new Date(date);
      d.setHours(0, 0, 0, 0);
      return d >= start && d <= end;
    });
  };

  const handleSubmit = async () => {
    setAttempted(true);

    const isDateBased = thing && DATE_TYPES.includes(thing.type);
    const isOrder = thing && thing.type === ORDER_TYPE;

    let body = {};
    if (isDateBased) {
      if (!startDate || !endDate) return;
      body = { start_date: startDate, end_date: endDate };
    } else if (isOrder) {
      if (!deliveryDate || quantity < 1) return;
      if (quantity > 99) {
        setToast({ type: 'error', message: 'Maximum quantity allowed is 99.' });
        return;
      }
      body = { delivery_date: deliveryDate, quantity };
    }

    setSubmitting(true);
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/things/${thingCode}/request/`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate(backPath);
      } else if (res.status === 400) {
        const data = await res.json();
        let message = data.detail;
        if (!message) {
          const errors = Object.values(data).flat();
          if (errors.some((e) => String(e).includes('99'))) {
            message = 'Maximum quantity allowed is 99.';
          } else {
            message = errors.join(' ') || 'Invalid request.';
          }
        }
        setToast({ type: 'error', message });
      } else if (res.status === 409) {
        setToast({ type: 'error', message: 'Date overlaps with another booking.' });
      } else {
        setToast({ type: 'error', message: 'Error sending request.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
    } finally {
      setSubmitting(false);
    }
  };

  if (!thing) return null;

  const isDateBased = DATE_TYPES.includes(thing.type);
  const isOrder = thing.type === ORDER_TYPE;

  return (
    <div className="page-container">
      <BackLink to={backPath} label={backLabel} />
      <h2>Hold: {thing.headline}</h2>
      {thing.fee && <p><strong>Price:</strong> {thing.fee} EUR</p>}

      {isDateBased && (
        <div className="summary-grid section-mt">
          <DateInput
            id="request-start-date"
            label="Start"
            value={startDate}
            onChange={(value) => setStartDate(value)}
            dateFormat="yyyy-MM-dd"
            language="en"
            required
            invalid={attempted && !startDate}
            errorText={attempted && !startDate ? 'Start date is required.' : undefined}
            minDate={TODAY}
            maxDate={MAX_DATE}
            dateOutsideRangeErrorText={RANGE_ERROR}
            isDateDisabledBy={isDateBlocked}
            malformedDateErrorText="Date overlaps with another booking."
          />
          <DateInput
            id="request-end-date"
            label="End"
            value={endDate}
            onChange={(value) => setEndDate(value)}
            dateFormat="yyyy-MM-dd"
            language="en"
            required
            invalid={attempted && !endDate}
            errorText={attempted && !endDate ? 'End date is required.' : undefined}
            minDate={TODAY}
            maxDate={MAX_DATE}
            dateOutsideRangeErrorText={RANGE_ERROR}
            isDateDisabledBy={isDateBlocked}
            malformedDateErrorText="Date overlaps with another booking."
          />
        </div>
      )}

      {isOrder && (
        <div className="summary-grid section-mt">
          <DateInput
            id="request-delivery-date"
            label="Delivery"
            value={deliveryDate}
            onChange={(value) => setDeliveryDate(value)}
            dateFormat="yyyy-MM-dd"
            language="en"
            required
            invalid={attempted && !deliveryDate}
            errorText={attempted && !deliveryDate ? 'Delivery date is required.' : undefined}
            minDate={TODAY}
            maxDate={MAX_DATE}
            dateOutsideRangeErrorText={RANGE_ERROR}
          />
          <NumberInput
            id="request-quantity"
            label="Quantity"
            value={quantity}
            onChange={(e) => setQuantity(Number(e.target.value))}
            min={1}
            step={1}
          />
        </div>
      )}

      <div className="button-row section-mt">
        <Button variant="secondary" onClick={() => navigate(backPath)}>
          Cancel
        </Button>
        <Button disabled={submitting} onClick={handleSubmit}>
          {submitting ? 'Sending...' : 'Hold'}
        </Button>
      </div>

      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
