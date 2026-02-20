import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Card, DateInput, Dialog, NumberInput, Notification } from 'hds-react';
import placeholderImg from '../assets/image-s.png';

const TYPE_LABELS = {
  GIFT_THING: 'Regalo',
  SELL_THING: 'Venta',
  ORDER_THING: 'Pedido',
  RENT_THING: 'Alquiler',
  LEND_THING: 'Prestamo',
  SHARE_THING: 'Compartir',
};

const DATE_TYPES = ['LEND_THING', 'RENT_THING', 'SHARE_THING'];
const ORDER_TYPE = 'ORDER_THING';

const TODAY = new Date();
TODAY.setHours(0, 0, 0, 0);
const MAX_DATE = new Date(TODAY);
MAX_DATE.setDate(MAX_DATE.getDate() + 90);
const RANGE_ERROR = 'La fecha debe estar entre hoy y 90 dias a partir de hoy.';

export default function ThingCard({ thing, userCode, collectionCode, onDelete, onUpdateThing }) {
  const navigate = useNavigate();
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [deliveryDate, setDeliveryDate] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [requested, setRequested] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [toast, setToast] = useState(null);
  const [blockedPeriods, setBlockedPeriods] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [bookingAction, setBookingAction] = useState(false);

  const isDateBased = DATE_TYPES.includes(thing.type);
  const isOrder = thing.type === ORDER_TYPE;
  const needsDialog = isDateBased || isOrder;

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
        setDialogOpen(false);
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

  const editPath = collectionCode
    ? `/collections/${collectionCode}/edit-thing/${thing.code}`
    : `/things/${thing.code}/edit`;

  const thingPath = collectionCode
    ? `/collections/${collectionCode}/things/${thing.code}`
    : `/things/${thing.code}`;

  return (
    <div onClick={() => navigate(thingPath)} style={{ cursor: 'pointer' }}>
    <Card heading={thing.headline} text={thing.description || ''} border>
      <img
        src={thing.thumbnail_url || placeholderImg}
        alt={thing.headline}
        className="thing-thumbnail"
      />
      <p><strong>Tipo:</strong> {TYPE_LABELS[thing.type] || thing.type}</p>
      <p><strong>Creado:</strong> {new Date(thing.created).toLocaleDateString('es-ES')}</p>
      {thing.fee && <p><strong>Precio:</strong> {thing.fee} EUR</p>}
      {isOwner && (
        <Link to={editPath} onClick={(e) => e.stopPropagation()}>
          <Button size="small">Editar</Button>
        </Link>
      )}
      {isOwner && thing.pending_booking && (
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }} onClick={(e) => e.stopPropagation()}>
          <Button
            disabled={bookingAction}
            onClick={async () => {
              const token = localStorage.getItem('token');
              setBookingAction(true);
              try {
                const res = await fetch(`/api/v1/bookings/${thing.pending_booking}/accept/`, {
                  method: 'POST',
                  headers: { 'Authorization': `Bearer ${token}` },
                });
                if (res.ok) {
                  onUpdateThing(thing.code, { status: 'INACTIVE', pending_booking: null });
                  setToast({ type: 'success', message: 'Reserva aceptada.' });
                } else {
                  const data = await res.json().catch(() => ({}));
                  setToast({ type: 'error', message: data.error || 'Error al aceptar.' });
                }
              } catch {
                setToast({ type: 'error', message: 'Error de conexion.' });
              } finally {
                setBookingAction(false);
              }
            }}
          >
            Aceptar
          </Button>
          <Button
            variant="danger"
            disabled={bookingAction}
            onClick={async () => {
              const token = localStorage.getItem('token');
              setBookingAction(true);
              try {
                const res = await fetch(`/api/v1/bookings/${thing.pending_booking}/reject/`, {
                  method: 'POST',
                  headers: { 'Authorization': `Bearer ${token}` },
                });
                if (res.ok) {
                  onUpdateThing(thing.code, { status: 'ACTIVE', pending_booking: null });
                  setToast({ type: 'success', message: 'Reserva rechazada.' });
                } else {
                  const data = await res.json().catch(() => ({}));
                  setToast({ type: 'error', message: data.error || 'Error al rechazar.' });
                }
              } catch {
                setToast({ type: 'error', message: 'Error de conexion.' });
              } finally {
                setBookingAction(false);
              }
            }}
          >
            Rechazar
          </Button>
        </div>
      )}
      {showButton && (
        <div onClick={(e) => e.stopPropagation()}>
          <Button
            disabled={buttonDisabled}
            onClick={needsDialog ? () => setDialogOpen(true) : handleRequest}
          >
            {submitting ? 'Enviando...' : 'Reservar'}
          </Button>

          {needsDialog && (
            <Dialog
              id={`reserve-dialog-${thing.code}`}
              isOpen={dialogOpen}
              aria-labelledby={`reserve-dialog-title-${thing.code}`}
              close={() => setDialogOpen(false)}
              closeButtonLabelText="Cerrar"
              scrollable
            >
              <Dialog.Header id={`reserve-dialog-title-${thing.code}`} title={`Reservar: ${thing.headline}`} />
              <Dialog.Content style={{ minHeight: '600px' }}>
                {isDateBased && (
                  <div style={{ display: 'grid', gap: '0.5rem' }}>
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
                  <div style={{ display: 'grid', gap: '0.5rem' }}>
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
              </Dialog.Content>
              <Dialog.ActionButtons>
                <Button variant="secondary" onClick={() => setDialogOpen(false)}>Cancelar</Button>
                <Button disabled={submitting} onClick={handleRequest}>
                  {submitting ? 'Enviando...' : 'Reservar'}
                </Button>
              </Dialog.ActionButtons>
            </Dialog>
          )}

        </div>
      )}
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
    </Card>
    </div>
  );
}
