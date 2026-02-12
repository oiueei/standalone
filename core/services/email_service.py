"""
Centralized email service for OIUEEI.

All email composition and sending is handled here to avoid
duplicating email logic across views.
"""

from django.core.mail import send_mail
from django.utils.html import escape


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
    safe_requester_name = escape(requester_name)
    safe_headline = escape(thing.headline)

    if booking.start_date and booking.end_date:
        safe_start = escape(str(booking.start_date))
        safe_end = escape(str(booking.end_date))
        message = (
            f"{requester_name} ha solicitado reservar '{thing.headline}' "
            f"del {booking.start_date} al {booking.end_date}. "
            f"Aceptar: {accept_link} | Rechazar: {reject_link}"
        )
        html_extra = f"<p>Fechas: {safe_start} - {safe_end}</p>"
        subject = f"{requester_name} quiere reservar: {thing.headline}"
    elif booking.delivery_date:
        safe_quantity = escape(str(booking.quantity))
        safe_delivery = escape(str(booking.delivery_date))
        message = (
            f"{requester_name} ha solicitado {booking.quantity}x '{thing.headline}' "
            f"para el {booking.delivery_date}. "
            f"Aceptar: {accept_link} | Rechazar: {reject_link}"
        )
        html_extra = f"<p>Cantidad: {safe_quantity}</p>" f"<p>Fecha de entrega: {safe_delivery}</p>"
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
            <p><strong>{safe_requester_name}</strong> ha solicitado:</p>
            <p><strong>{safe_headline}</strong></p>
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

    safe_decision_strong = escape(decision_strong)
    safe_headline = escape(thing.headline)

    if booking.start_date and booking.end_date:
        safe_start = escape(str(booking.start_date))
        safe_end = escape(str(booking.end_date))
        message = (
            f"Tu solicitud de reserva para '{thing.headline}' "
            f"del {booking.start_date} al {booking.end_date} ha sido {decision_word}."
        )
        html_extra = f"<p>Fechas: {safe_start} - {safe_end}</p>"
        subject = f"Tu reserva ha sido {decision_word}: {thing.headline}"
    elif booking.delivery_date:
        safe_quantity = escape(str(booking.quantity))
        safe_delivery = escape(str(booking.delivery_date))
        order_decision = "aceptado" if accepted else "rechazado"
        message = (
            f"Tu pedido de {booking.quantity}x '{thing.headline}' "
            f"para el {booking.delivery_date} ha sido {order_decision}."
        )
        html_extra = f"<p>Cantidad: {safe_quantity}</p>" f"<p>Fecha de entrega: {safe_delivery}</p>"
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
            <p>Tu solicitud ha sido <strong>{safe_decision_strong}</strong>:</p>
            <p><strong>{safe_headline}</strong></p>
            {html_extra}
            </html>
            """,
    )


def send_collection_invite_email(inviter_name, collection_headline, email, accept_link, reject_link):
    """Send collection invitation email with accept and reject links."""
    safe_inviter = escape(inviter_name)
    safe_headline = escape(collection_headline)

    send_mail(
        subject=f"{inviter_name} te ha invitado a una colección",
        message=(
            f"Has sido invitado a ver: {collection_headline}. "
            f"Aceptar: {accept_link} | Rechazar: {reject_link}"
        ),
        from_email=None,
        recipient_list=[email],
        html_message=f"""
            <html>
            <p>{safe_inviter} te ha invitado a ver:</p>
            <p><strong>{safe_headline}</strong></p>
            <p>
                <a href="{accept_link}">Aceptar invitación</a> |
                <a href="{reject_link}">Rechazar invitación</a>
            </p>
            </html>
            """,
    )


def send_invite_rejected_email(invitee_name, collection_headline, owner_email):
    """Send notification to collection owner that an invite was declined."""
    safe_invitee = escape(invitee_name)
    safe_headline = escape(collection_headline)

    send_mail(
        subject=f"{invitee_name} ha rechazado tu invitación",
        message=f"{invitee_name} ha rechazado la invitación a '{collection_headline}'.",
        from_email=None,
        recipient_list=[owner_email],
        html_message=f"""
            <html>
            <p><strong>{safe_invitee}</strong> ha rechazado tu invitación a:</p>
            <p><strong>{safe_headline}</strong></p>
            </html>
            """,
    )


def send_collection_revoke_email(owner_name, collection_headline, email):
    """Send collection access revoked notification email."""
    safe_owner = escape(owner_name)
    safe_headline = escape(collection_headline)

    send_mail(
        subject=f"Tu acceso a '{collection_headline}' ha sido revocado",
        message=f"{owner_name} ha revocado tu acceso a la colección " f"'{collection_headline}'.",
        from_email=None,
        recipient_list=[email],
        html_message=f"""
            <html>
            <p>{safe_owner} ha revocado tu acceso a:</p>
            <p><strong>{safe_headline}</strong></p>
            <p>Ya no podrás ver el contenido de esta colección.</p>
            </html>
            """,
    )


def send_faq_question_email(questioner_name, thing_headline, question, owner_email):
    """Send FAQ question notification email to thing owner."""
    safe_questioner = escape(questioner_name)
    safe_headline = escape(thing_headline)
    safe_question = escape(question)

    send_mail(
        subject=f"Nueva pregunta sobre: {thing_headline}",
        message=f"{questioner_name} ha preguntado: {question}",
        from_email=None,
        recipient_list=[owner_email],
        html_message=f"""
            <html>
            <p><strong>{safe_questioner}</strong> ha hecho una pregunta sobre:</p>
            <p><strong>{safe_headline}</strong></p>
            <p>Pregunta: {safe_question}</p>
            </html>
            """,
    )


def send_faq_answer_email(owner_name, thing_headline, question, answer, questioner_email):
    """Send FAQ answer notification email to questioner."""
    safe_owner = escape(owner_name)
    safe_headline = escape(thing_headline)
    safe_question = escape(question)
    safe_answer = escape(answer)

    send_mail(
        subject=f"Tu pregunta ha sido respondida: {thing_headline}",
        message=f"{owner_name} ha respondido: {answer}",
        from_email=None,
        recipient_list=[questioner_email],
        html_message=f"""
            <html>
            <p><strong>{safe_owner}</strong> ha respondido tu pregunta sobre:</p>
            <p><strong>{safe_headline}</strong></p>
            <p>Tu pregunta: {safe_question}</p>
            <p>Respuesta: {safe_answer}</p>
            </html>
            """,
    )


def send_faq_hide_email(owner_name, thing_headline, question, questioner_email):
    """Send FAQ hidden notification email to questioner."""
    safe_owner = escape(owner_name)
    safe_headline = escape(thing_headline)
    safe_question = escape(question)

    send_mail(
        subject=f"Tu pregunta ha sido ocultada: {thing_headline}",
        message=f"{owner_name} ha ocultado tu pregunta: {question}",
        from_email=None,
        recipient_list=[questioner_email],
        html_message=f"""
            <html>
            <p><strong>{safe_owner}</strong> ha ocultado tu pregunta sobre:</p>
            <p><strong>{safe_headline}</strong></p>
            <p>Tu pregunta: {safe_question}</p>
            </html>
            """,
    )
