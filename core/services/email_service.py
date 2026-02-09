"""
Centralized email service for OIUEEI.

All email composition and sending is handled here to avoid
duplicating email logic across views.
"""

from django.core.mail import send_mail


def send_magic_link_email(email, magic_link):
    """Send magic link authentication email."""
    send_mail(
        subject="Tu enlace de acceso a OIUEEI",
        message=f"Hola! Haz clic aquí para acceder: {magic_link}",
        from_email=None,
        recipient_list=[email],
        html_message=f"""
            <html>
            <p>Hola! Haz clic aquí para acceder:</p>
            <a href="{magic_link}">Acceder</a>
            </html>
            """,
    )


def send_booking_request_email(requester, thing, booking, owner_email, accept_link, reject_link):
    """Send booking request email to owner with accept/reject links."""
    requester_name = requester.name or requester.email

    if booking.start_date and booking.end_date:
        message = (
            f"{requester_name} ha solicitado reservar '{thing.headline}' "
            f"del {booking.start_date} al {booking.end_date}. "
            f"Aceptar: {accept_link} | Rechazar: {reject_link}"
        )
        html_extra = f"<p>Fechas: {booking.start_date} - {booking.end_date}</p>"
        subject = f"{requester_name} quiere reservar: {thing.headline}"
    elif booking.delivery_date:
        message = (
            f"{requester_name} ha solicitado {booking.quantity}x '{thing.headline}' "
            f"para el {booking.delivery_date}. "
            f"Aceptar: {accept_link} | Rechazar: {reject_link}"
        )
        html_extra = (
            f"<p>Cantidad: {booking.quantity}</p>"
            f"<p>Fecha de entrega: {booking.delivery_date}</p>"
        )
        subject = f"{requester_name} quiere pedir: {thing.headline}"
    else:
        message = (
            f"{requester_name} ha solicitado reservar '{thing.headline}'. "
            f"Aceptar: {accept_link} | Rechazar: {reject_link}"
        )
        html_extra = ""
        subject = f"{requester_name} quiere reservar: {thing.headline}"

    send_mail(
        subject=subject,
        message=message,
        from_email=None,
        recipient_list=[owner_email],
        html_message=f"""
            <html>
            <p><strong>{requester_name}</strong> ha solicitado:</p>
            <p><strong>{thing.headline}</strong></p>
            {html_extra}
            <p>
                <a href="{accept_link}">Aceptar</a> |
                <a href="{reject_link}">Rechazar</a>
            </p>
            </html>
            """,
    )


def send_booking_decision_email(booking, thing, accepted=True):
    """Send booking accept/reject notification email to requester."""
    if accepted:
        decision_word = "aceptada"
        decision_strong = "aceptada"
    else:
        decision_word = "rechazada"
        decision_strong = "rechazada"

    if booking.start_date and booking.end_date:
        message = (
            f"Tu solicitud de reserva para '{thing.headline}' "
            f"del {booking.start_date} al {booking.end_date} ha sido {decision_word}."
        )
        html_extra = f"<p>Fechas: {booking.start_date} - {booking.end_date}</p>"
        subject = f"Tu reserva ha sido {decision_word}: {thing.headline}"
    elif booking.delivery_date:
        order_decision = "aceptado" if accepted else "rechazado"
        message = (
            f"Tu pedido de {booking.quantity}x '{thing.headline}' "
            f"para el {booking.delivery_date} ha sido {order_decision}."
        )
        html_extra = (
            f"<p>Cantidad: {booking.quantity}</p>"
            f"<p>Fecha de entrega: {booking.delivery_date}</p>"
        )
        subject = f"Tu pedido ha sido {order_decision}: {thing.headline}"
    else:
        message = f"Tu solicitud de reserva para '{thing.headline}' ha sido {decision_word}."
        html_extra = ""
        subject = f"Tu reserva ha sido {decision_word}: {thing.headline}"

    send_mail(
        subject=subject,
        message=message,
        from_email=None,
        recipient_list=[booking.requester_email],
        html_message=f"""
            <html>
            <p>Tu solicitud ha sido <strong>{decision_strong}</strong>:</p>
            <p><strong>{thing.headline}</strong></p>
            {html_extra}
            </html>
            """,
    )


def send_collection_invite_email(inviter_name, collection_headline, email, invite_link):
    """Send collection invitation email."""
    send_mail(
        subject=f"{inviter_name} te ha invitado a una colección",
        message=f"Has sido invitado a ver: {collection_headline}. " f"Accede aquí: {invite_link}",
        from_email=None,
        recipient_list=[email],
        html_message=f"""
            <html>
            <p>{inviter_name} te ha invitado a ver:</p>
            <p><strong>{collection_headline}</strong></p>
            <p><a href="{invite_link}">Aceptar invitación</a></p>
            </html>
            """,
    )


def send_collection_revoke_email(owner_name, collection_headline, email):
    """Send collection access revoked notification email."""
    send_mail(
        subject=f"Tu acceso a '{collection_headline}' ha sido revocado",
        message=f"{owner_name} ha revocado tu acceso a la colección " f"'{collection_headline}'.",
        from_email=None,
        recipient_list=[email],
        html_message=f"""
            <html>
            <p>{owner_name} ha revocado tu acceso a:</p>
            <p><strong>{collection_headline}</strong></p>
            <p>Ya no podrás ver el contenido de esta colección.</p>
            </html>
            """,
    )


def send_faq_question_email(questioner_name, thing_headline, question, owner_email):
    """Send FAQ question notification email to thing owner."""
    send_mail(
        subject=f"Nueva pregunta sobre: {thing_headline}",
        message=f"{questioner_name} ha preguntado: {question}",
        from_email=None,
        recipient_list=[owner_email],
        html_message=f"""
            <html>
            <p><strong>{questioner_name}</strong> ha hecho una pregunta sobre:</p>
            <p><strong>{thing_headline}</strong></p>
            <p>Pregunta: {question}</p>
            </html>
            """,
    )


def send_faq_answer_email(owner_name, thing_headline, question, answer, questioner_email):
    """Send FAQ answer notification email to questioner."""
    send_mail(
        subject=f"Tu pregunta ha sido respondida: {thing_headline}",
        message=f"{owner_name} ha respondido: {answer}",
        from_email=None,
        recipient_list=[questioner_email],
        html_message=f"""
            <html>
            <p><strong>{owner_name}</strong> ha respondido tu pregunta sobre:</p>
            <p><strong>{thing_headline}</strong></p>
            <p>Tu pregunta: {question}</p>
            <p>Respuesta: {answer}</p>
            </html>
            """,
    )


def send_faq_hide_email(owner_name, thing_headline, question, questioner_email):
    """Send FAQ hidden notification email to questioner."""
    send_mail(
        subject=f"Tu pregunta ha sido ocultada: {thing_headline}",
        message=f"{owner_name} ha ocultado tu pregunta: {question}",
        from_email=None,
        recipient_list=[questioner_email],
        html_message=f"""
            <html>
            <p><strong>{owner_name}</strong> ha ocultado tu pregunta sobre:</p>
            <p><strong>{thing_headline}</strong></p>
            <p>Tu pregunta: {question}</p>
            </html>
            """,
    )
