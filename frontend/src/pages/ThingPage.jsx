import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Button,
  DateInput,
  Dialog,
  Fieldset,
  Highlight,
  NumberInput,
  Notification,
  TextArea,
} from 'hds-react';
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

export default function ThingPage() {
  const { code, thingCode } = useParams();
  const navigate = useNavigate();
  const token = localStorage.getItem('token');
  const userCode = localStorage.getItem('userCode');

  const [thing, setThing] = useState(null);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);

  // Reservation state
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [deliveryDate, setDeliveryDate] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [requested, setRequested] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [blockedPeriods, setBlockedPeriods] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [bookingAction, setBookingAction] = useState(false);

  // FAQ state
  const [faqs, setFaqs] = useState([]);
  const [faqQuestion, setFaqQuestion] = useState('');
  const [faqSubmitting, setFaqSubmitting] = useState(false);
  const [answerTexts, setAnswerTexts] = useState({});
  const [answerSubmitting, setAnswerSubmitting] = useState({});

  useEffect(() => {
    if (!token) {
      navigate('/login');
      return;
    }

    const headers = { 'Authorization': `Bearer ${token}` };

    const fetchThing = async () => {
      try {
        const res = await fetch(`/api/v1/things/${thingCode}/`, { headers });
        if (res.ok) {
          setThing(await res.json());
        } else if (res.status === 403) {
          setError('No tienes permiso para ver esta cosa.');
        } else if (res.status === 404) {
          setError('Cosa no encontrada.');
        } else {
          setError('Error al cargar la cosa.');
        }
      } catch {
        setError('Error de conexion con el servidor.');
      }
    };

    const fetchFaqs = async () => {
      try {
        const res = await fetch(`/api/v1/things/${thingCode}/faq/`, { headers });
        if (res.ok) {
          const data = await res.json();
          setFaqs(data.results || data);
        }
      } catch { /* silently fail */ }
    };

    fetchThing();
    fetchFaqs();
  }, [token, thingCode, navigate]);

  // Fetch blocked periods for date-based types
  useEffect(() => {
    if (!thing || !DATE_TYPES.includes(thing.type) || !token) return;
    fetch(`/api/v1/things/${thing.code}/calendar/`, {
      headers: { 'Authorization': `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setBlockedPeriods(data))
      .catch(() => {});
  }, [thing, token]);

  if (error) {
    return (
      <div className="page-container">
        <Notification label="Error" type="error">{error}</Notification>
      </div>
    );
  }

  if (!thing) {
    return <div className="page-container"><p>Cargando...</p></div>;
  }

  const isOwner = thing.owner === userCode;
  const isDateBased = DATE_TYPES.includes(thing.type);
  const isOrder = thing.type === ORDER_TYPE;
  const needsDialog = isDateBased || isOrder;
  const showButton = !isOwner && thing.status !== 'INACTIVE';
  const buttonDisabled = thing.status === 'TAKEN' || submitting || requested;

  const editPath = code
    ? `/collections/${code}/edit-thing/${thing.code}`
    : `/things/${thing.code}/edit`;

  const collectionCode = code || thing.collection_code;
  const backPath = collectionCode ? `/collections/${collectionCode}` : '/';
  const backLabel = thing.collection_headline || (collectionCode ? 'Colección' : 'Home');

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

  const handleAskQuestion = async () => {
    if (!faqQuestion.trim()) return;
    setFaqSubmitting(true);
    setToast(null);
    try {
      const res = await fetch(`/api/v1/things/${thing.code}/faq/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question: faqQuestion.trim() }),
      });
      if (res.ok) {
        const newFaq = await res.json();
        setFaqs((prev) => [...prev, newFaq]);
        setFaqQuestion('');
        setToast({ type: 'success', message: 'Pregunta enviada.' });
      } else {
        const data = await res.json().catch(() => ({}));
        setToast({ type: 'error', message: data.detail || 'Error al enviar la pregunta.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Error de conexion.' });
    } finally {
      setFaqSubmitting(false);
    }
  };

  const handleAnswer = async (faqCode) => {
    const answer = (answerTexts[faqCode] || '').trim();
    if (!answer) return;
    setAnswerSubmitting((prev) => ({ ...prev, [faqCode]: true }));
    setToast(null);
    try {
      const res = await fetch(`/api/v1/faq/${faqCode}/answer/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ answer }),
      });
      if (res.ok) {
        const updated = await res.json();
        setFaqs((prev) => prev.map((f) => (f.code === faqCode ? { ...f, ...updated } : f)));
        setAnswerTexts((prev) => ({ ...prev, [faqCode]: '' }));
        setToast({ type: 'success', message: 'Respuesta enviada.' });
      } else {
        const data = await res.json().catch(() => ({}));
        setToast({ type: 'error', message: data.detail || 'Error al responder.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Error de conexion.' });
    } finally {
      setAnswerSubmitting((prev) => ({ ...prev, [faqCode]: false }));
    }
  };

  const handleToggleVisibility = async (faq) => {
    const action = faq.is_visible ? 'hide' : 'show';
    setToast(null);
    try {
      const res = await fetch(`/api/v1/faq/${faq.code}/${action}/`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        setFaqs((prev) =>
          prev.map((f) => (f.code === faq.code ? { ...f, is_visible: !faq.is_visible } : f))
        );
      } else {
        setToast({ type: 'error', message: `Error al ${action === 'hide' ? 'ocultar' : 'mostrar'} la pregunta.` });
      }
    } catch {
      setToast({ type: 'error', message: 'Error de conexion.' });
    }
  };

  return (
    <div className="page-container">
      <Link to={backPath} style={{ display: 'inline-block', marginBottom: '1rem' }}>
        &larr; {backLabel}
      </Link>

      <div style={{ display: 'grid', gap: '1rem' }}>
        <img
          src={thing.thumbnail_url || placeholderImg}
          alt={thing.headline}
          style={{ maxWidth: '400px', width: '100%', borderRadius: '4px' }}
        />

        <h1 className="page-title">{thing.headline}</h1>

        {thing.description && <p>{thing.description}</p>}

        <dl style={{ display: 'grid', gap: '0.5rem' }}>
          <dt><strong>Tipo</strong></dt>
          <dd>{TYPE_LABELS[thing.type] || thing.type}</dd>
          <dt><strong>Estado</strong></dt>
          <dd>{thing.status}</dd>
          <dt><strong>Creado</strong></dt>
          <dd>{new Date(thing.created).toLocaleDateString('es-ES')}</dd>
          {thing.fee && (
            <>
              <dt><strong>Precio</strong></dt>
              <dd>{thing.fee} EUR</dd>
            </>
          )}
        </dl>

        {thing.pictures_urls && thing.pictures_urls.length > 0 && (
          <div>
            <h2>Fotos</h2>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {thing.pictures_urls.map((url, i) => (
                <img
                  key={i}
                  src={url}
                  alt={`${thing.headline} foto ${i + 1}`}
                  style={{ maxWidth: '200px', borderRadius: '4px' }}
                />
              ))}
            </div>
          </div>
        )}

        {/* Owner actions */}
        {isOwner && (
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Link to={editPath}>
              <Button>Editar</Button>
            </Link>
          </div>
        )}

        {isOwner && thing.pending_booking && (
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Button
              disabled={bookingAction}
              onClick={async () => {
                setBookingAction(true);
                try {
                  const res = await fetch(`/api/v1/bookings/${thing.pending_booking}/accept/`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` },
                  });
                  if (res.ok) {
                    setThing((prev) => ({ ...prev, status: 'INACTIVE', pending_booking: null }));
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
                setBookingAction(true);
                try {
                  const res = await fetch(`/api/v1/bookings/${thing.pending_booking}/reject/`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` },
                  });
                  if (res.ok) {
                    setThing((prev) => ({ ...prev, status: 'ACTIVE', pending_booking: null }));
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

        {/* Reservation button for invited users */}
        {showButton && (
          <>
            <Button
              style={{ width: 'fit-content' }}
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
          </>
        )}

        {/* FAQs Section */}
        <hr />
        <h2>¿Tienes dudas o comentarios?</h2>

        {faqs.length === 0 ? (
          <p>No hay preguntas todavia.</p>
        ) : (
          <div style={{ display: 'grid', gap: '0.25rem' }}>
            {faqs.map((faq) => (
              <div
                key={faq.code}
                style={{ opacity: faq.is_visible === false ? 0.6 : 1 }}
              >
                <Highlight
                  text={faq.question}
                  reference={faq.answer || undefined}
                />
                <div style={{ padding: '0 1rem 1rem' }}>
                  {!faq.answer && (
                    isOwner && (
                      <div style={{ display: 'grid', gap: '0.5rem' }}>
                        <TextArea
                          label="Responder"
                          value={answerTexts[faq.code] || ''}
                          onChange={(e) =>
                            setAnswerTexts((prev) => ({ ...prev, [faq.code]: e.target.value }))
                          }
                        />
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                          <Button
                            style={{ width: 'fit-content' }}
                            disabled={answerSubmitting[faq.code] || !(answerTexts[faq.code] || '').trim()}
                            onClick={() => handleAnswer(faq.code)}
                          >
                            {answerSubmitting[faq.code] ? 'Enviando...' : 'Responder'}
                          </Button>
                          <Button
                            variant="secondary"
                            onClick={() => handleToggleVisibility(faq)}
                          >
                            {faq.is_visible === false ? 'Mostrar' : 'Ocultar'}
                          </Button>
                          {faq.is_visible === false && (
                            <span style={{ fontSize: '0.8rem', color: '#999' }}>
                              (Oculta)
                            </span>
                          )}
                        </div>
                      </div>
                    )
                  )}
                  {faq.answer && isOwner && (
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                      <Button
                        variant="secondary"
                        onClick={() => handleToggleVisibility(faq)}
                      >
                        {faq.is_visible === false ? 'Mostrar' : 'Ocultar'}
                      </Button>
                      {faq.is_visible === false && (
                        <span style={{ fontSize: '0.8rem', color: '#999' }}>
                          (Oculta)
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}


        {!isOwner && (
          <div style={{ display: 'grid', gap: '0.5rem', marginTop: '1rem' }}>
            <TextArea
              label="Pregunta"
              value={faqQuestion}
              onChange={(e) => setFaqQuestion(e.target.value)}
              placeholder="Escribe tu pregunta aqui..."
            />
            <Button
              style={{ width: 'fit-content' }}
              disabled={faqSubmitting || !faqQuestion.trim()}
              onClick={handleAskQuestion}
            >
              {faqSubmitting ? 'Enviando...' : 'Enviar pregunta'}
            </Button>
          </div>
        )}
      </div>

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
    </div>
  );
}
