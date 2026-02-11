import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Button, Card, DateInput, NumberInput, Notification } from 'oiueeiDS-react';
import placeholderImg from '../../../../oiueei-ds/site/static/images/foundation/visual-assets/placeholders/image-s.png';

const DATE_TYPES = ['LEND_THING', 'RENT_THING', 'SHARE_THING'];
const ORDER_TYPE = 'ORDER_THING';

const TODAY = new Date();
TODAY.setHours(0, 0, 0, 0);
const MAX_DATE = new Date(TODAY);
MAX_DATE.setDate(MAX_DATE.getDate() + 90);
const RANGE_ERROR = 'La fecha debe estar entre hoy y 90 dias a partir de hoy.';

function ThingCard({ thing, userCode }) {
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [deliveryDate, setDeliveryDate] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [requested, setRequested] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [toast, setToast] = useState(null);
  const [blockedPeriods, setBlockedPeriods] = useState([]);

  const isDateBased = DATE_TYPES.includes(thing.type);
  const isOrder = thing.type === ORDER_TYPE;

  useEffect(() => {
    if (!isDateBased) return;
    const token = localStorage.getItem('token');
    if (!token) return;
    fetch(`/api/v1/things/${thing.code}/calendar/`, {
      headers: { 'Authorization': `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setBlockedPeriods(data))
      .catch(() => {});
  }, [thing.code, isDateBased]);

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

  const handleRequest = async () => {
    const token = localStorage.getItem('token');
    if (!token) return;

    setAttempted(true);

    let body = {};
    if (isDateBased) {
      if (!startDate || !endDate) return;
      body = { start_date: startDate, end_date: endDate };
    } else if (isOrder) {
      if (!deliveryDate || quantity < 1) return;
      body = { delivery_date: deliveryDate, quantity };
    }

    setSubmitting(true);
    setToast(null);
    try {
      const res = await fetch(`/api/v1/things/${thing.code}/request/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setRequested(true);
        setToast({ type: 'success', message: 'Solicitud enviada.' });
      } else if (res.status === 400) {
        const data = await res.json();
        setToast({ type: 'error', message: data.detail || 'Solicitud no valida.' });
      } else if (res.status === 409) {
        setToast({ type: 'error', message: 'La fecha se solapa con otra reserva.' });
      } else {
        setToast({ type: 'error', message: 'Error al enviar la solicitud.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Error de conexion con el servidor.' });
    } finally {
      setSubmitting(false);
    }
  };

  const isOwner = thing.owner === userCode;
  const showButton = !isOwner && thing.status !== 'INACTIVE';
  const buttonDisabled = thing.status === 'TAKEN' || submitting || requested;

  return (
    <Card heading={thing.headline} text={thing.description || ''} border>
      <img
        src={thing.thumbnail_url || placeholderImg}
        alt={thing.headline}
        className="thing-thumbnail"
      />
      {thing.fee && <p><strong>Precio:</strong> {thing.fee} EUR</p>}
      {showButton && (
        <>
          {isDateBased && (
            <div style={{ display: 'grid', gap: '0.5rem', marginBottom: '0.5rem' }}>
              <DateInput
                label="Inicio"
                value={startDate}
                onChange={(value) => setStartDate(value)}
                dateFormat="yyyy-MM-dd"
                language="en"
                required
                invalid={attempted && !startDate}
                errorText={attempted && !startDate ? 'La fecha de inicio es obligatoria.' : undefined}
                minDate={TODAY}
                maxDate={MAX_DATE}
                dateOutsideRangeErrorText={RANGE_ERROR}
                isDateDisabledBy={isDateBlocked}
                malformedDateErrorText="La fecha se solapa con otra reserva."
              />
              <DateInput
                label="Fin"
                value={endDate}
                onChange={(value) => setEndDate(value)}
                dateFormat="yyyy-MM-dd"
                language="en"
                required
                invalid={attempted && !endDate}
                errorText={attempted && !endDate ? 'La fecha de fin es obligatoria.' : undefined}
                minDate={TODAY}
                maxDate={MAX_DATE}
                dateOutsideRangeErrorText={RANGE_ERROR}
                isDateDisabledBy={isDateBlocked}
                malformedDateErrorText="La fecha se solapa con otra reserva."
              />
            </div>
          )}
          {isOrder && (
            <div style={{ display: 'grid', gap: '0.5rem', marginBottom: '0.5rem' }}>
              <DateInput
                label="Entrega"
                value={deliveryDate}
                onChange={(value) => setDeliveryDate(value)}
                dateFormat="yyyy-MM-dd"
                language="en"
                required
                invalid={attempted && !deliveryDate}
                errorText={attempted && !deliveryDate ? 'La fecha de entrega es obligatoria.' : undefined}
                minDate={TODAY}
                maxDate={MAX_DATE}
                dateOutsideRangeErrorText={RANGE_ERROR}
              />
              <NumberInput
                label="Cantidad"
                value={quantity}
                onChange={(e) => setQuantity(Number(e.target.value))}
                min={1}
                step={1}
              />
            </div>
          )}
          <Button disabled={buttonDisabled} onClick={handleRequest}>
            {submitting ? 'Enviando...' : 'Reservar'}
          </Button>
          {toast && (
            <Notification
              label={toast.type === 'success' ? 'Listo' : 'Error'}
              type={toast.type}
              position="top-right"
              autoClose
              dismissible
              closeButtonLabelText="Cerrar"
              onClose={() => setToast(null)}
            >
              {toast.message}
            </Notification>
          )}
        </>
      )}
    </Card>
  );
}

export default function CollectionPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const [collection, setCollection] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      navigate('/login');
      return;
    }

    const fetchCollection = async () => {
      try {
        const res = await fetch(`/api/v1/collections/${code}/`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setCollection(data);
        } else if (res.status === 403) {
          setError('No tienes permiso para ver esta coleccion.');
        } else if (res.status === 404) {
          setError('Coleccion no encontrada.');
        } else {
          setError('Error al cargar la coleccion.');
        }
      } catch {
        setError('Error de conexion con el servidor.');
      }
    };
    fetchCollection();
  }, [code, navigate]);

  if (error) {
    return (
      <div className="page-container">
        <Notification label="Error" type="error">{error}</Notification>
      </div>
    );
  }

  if (!collection) {
    return <div className="page-container"><p>Cargando...</p></div>;
  }

  return (
    <div className="page-container">
      <h1 className="page-title">{collection.headline}</h1>
      <p><strong>Estado:</strong> {collection.status}</p>
      {collection.description && <p>{collection.description}</p>}
      <p><strong>Tema:</strong> {collection.theeeme}</p>

      {localStorage.getItem('userCode') === collection.owner && (
        <Link to={`/collections/${code}/add-thing`} style={{ display: 'inline-block', marginBottom: '1rem' }}>
          <Button>Anadir cosa</Button>
        </Link>
      )}

      <h2>Cosas ({collection.things.length})</h2>
      {collection.things.length === 0 ? (
        <p>Sin cosas en esta coleccion.</p>
      ) : (
        <div style={{ display: 'grid', gap: '1rem' }}>
          {collection.things.map((thing) => (
            <ThingCard key={thing.code} thing={thing} userCode={localStorage.getItem('userCode')} />
          ))}
        </div>
      )}

      <h2>Invitados ({collection.invites.length})</h2>
      {collection.invites.length === 0 ? (
        <p>Sin invitados.</p>
      ) : (
        <ul>
          {collection.invites.map((userCode) => (
            <li key={userCode}>{userCode}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
