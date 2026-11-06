"""Catalan email texts (``EMAIL_LANGUAGE=ca``).

Same keys as ``en.py`` (guarded by the parity test); informal, warm tone,
matching the app's Catalan UI vocabulary (reservar, petició, intercanvi)."""

TEXTS = {
    # Shared
    "footer_manage": "Gestiona les teves preferències de correu",
    # Art. 14 RGPD: tot correu -- també els obligatoris -- enllaça a la
    # pàgina legal: és una obligació d'informació, no una preferència.
    "footer_legal": "Legal i privacitat",
    # How a booking's dates read inside a sentence: a range, or one day said once
    # ("from the 13th to the 13th" was a loan for a single day, 2026-10-02).
    "when_range": "del {start} al {end}",
    "when_day": "el {start}",
    "dates_label": "Dates",
    # Com s'anomena algú que mai no ha posat nom, allà on qui llegeix no té dret
    # a la seva adreça. Vegeu "a_member" a en.py i `_member_name`.
    "a_member": "Un membre",
    # The same stand-in in the middle of a sentence or a list (`_member_name(inline=True)`).
    "a_member_inline": "un membre",
    "view_collection_cta": "Veure la col·lecció",
    # Substantius d'acció per als correus de reserva — calquen el vocabulari del
    # frontend (thingCard.action / types): una sol·licitud SELL és "sol·licitud
    # de compra", una LEND "sol·licitud de préstec", etc.
    #
    # A DIFERÈNCIA d'en/es, aquí els valors porten la preposició ("de compra") i
    # les plantilles diuen "sol·licitud {action}" — el català elideix "de" davant
    # de vocal, així que un tipus nou que hi comenci ha de portar "d'" al valor
    # ("d'intercanvi"), no a la plantilla.
    "action_noun_GIFT_THING": "de regal",
    "action_noun_SELL_THING": "de compra",
    "action_noun_LEND_THING": "de préstec",
    "action_noun_RENT_THING": "de lloguer",
    "action_noun_RESERVE_THING": "de reserva",
    # Magic link
    "magic_subject": "Hola, et donem la benvinguda a OIUEEI!",
    "magic_subject_collection": "Hola, et donem la benvinguda a '{collection}' - OIUEEI!",
    # The greeting repeated at the top of the body — the inbox preview shows
    # only the subject, the body has to stand on its own (see send_magic_link_email).
    "magic_greeting": "Hola, et donem la benvinguda a OIUEEI!",
    "magic_greeting_collection": "Hola, et donem la benvinguda a '{collection}'!",
    "magic_plain": "Fes clic a l'enllaç per iniciar sessió: {link}",
    "magic_cta": "Iniciar sessió →",
    "cta_fallback": "Si ho prefereixes, copia i enganxa aquest enllaç al navegador:",
    # Shared by every CTA (one button or two) that has to spell its link out below it.
    "ctas_fallback": "Si ho prefereixes, copia i enganxa aquests enllaços al navegador:",
    # The one-line "what is this" under the OIUEEI parent title, for the one
    # email a reader may open with no idea what OIUEEI is.
    "generic_parent_pitch": (
        "Comparteix el que tens amb la gent que t'envolta: una paradeta per regalar o vendre, "
        "una biblioteca de les coses per prestar o llogar, un taller per reservar per dies o "
        "per hores. Després, convida la teva gent a demanar el que necessiti."
    ),
    # What a kind of collection is, one sentence each. The same words as
    # `kinds.<K>.what` in the frontend's locale files (the kind chooser): a shared
    # link's card uses them for a collection with no description of its own.
    # `test_kind_what_parity.py` keeps the two copies equal.
    "kind_what_STALL": "Coses per vendre o regalar: qui se l'emporta, se la queda.",
    "kind_what_LIBRARY": "Coses per prestar o llogar: se les emporten a casa i les tornen.",
    "kind_what_SHED": (
        "Màquines i espais que es fan servir on són, amb reserva per dies o per hores."
    ),
    # Collection invite
    "invite_subject": "Tens una invitació a '{collection}' - OIUEEI!",
    "invite_plain": (
        "T'han convidat a {collection}. "
        "Acceptar la invitació: {accept} | Rebutjar la invitació: {reject}"
    ),
    "invite_intro": "{inviter} t'ha convidat a aquest grup.",
    "invite_recommended_by": "{proposer} t'ha proposat per a aquest grup.",
    "invite_accept_cta": "Acceptar la invitació",
    "invite_decline_cta": "Rebutjar la invitació",
    # Art. 14 RGPD: aquest correu el va donar qui convida, no la persona convidada.
    "invite_source_note": (
        "Si has arribat aquí per una invitació, el teu correu ens el va donar qui "
        "et va convidar, i només es fa servir per enviar-te aquesta invitació. Si "
        "la rebutges o no fas res, aquesta persona no et podrà tornar a convidar per correu "
        "durant un any."
    ),
    # Collection access revoked
    "revoke_subject": "S'ha revocat el teu accés",
    "revoke_plain": "{owner} ha revocat el teu accés a '{collection}'.",
    "revoke_intro": "{owner} ha revocat el teu accés a aquest grup.",
    "revoke_outro": "Ja no podràs veure aquesta col·lecció.",
    "revoke_things": "Les teves coses d'aquest grup s'han esborrat amb la teva sortida: {things}.",
    "thing_left_subject": "«{thing}» ja no és a {group}",
    "thing_left_intro": (
        "Qui oferia «{thing}» ja no forma part de {group}, "
        "i la cosa se n'ha anat amb aquesta persona. "
        "La teva sol·licitud o reserva ja no és vigent."
    ),
    "thing_left_holding": "Si la tens tu, torna-la-hi com vau acordar.",
    "thing_withdrawn_subject": "S'ha retirat «{thing}» de {group}",
    "thing_withdrawn_intro": (
        "S'ha retirat «{thing}» de {group}, i la teva sol·licitud queda anul·lada."
    ),
    # Collection welcome document (sent once, the first time someone joins)
    "welcome_doc_subject": "Et donem la benvinguda a '{collection}'",
    "welcome_doc_plain": (
        "Et donem la benvinguda a '{collection}'. El grup té un document de "
        "benvinguda i normes — fes-hi una ullada: {url}"
    ),
    "welcome_doc_intro": "Benvinguda! El grup té un document de benvinguda i normes:",
    "welcome_doc_link_label": "Obrir el document",
    "welcome_doc_outro": "Fes-hi una ullada abans de començar.",
    # Account deletion confirmation (right to erasure)
    "account_delete_subject": "Vols esborrar el teu compte d'OIUEEI?",
    "account_delete_plain": (
        "Has demanat esborrar el teu compte d'OIUEEI. Si confirmes, és immediat i "
        "irreversible: el teu compte, les teves col·leccions, les teves coses amb "
        "les seves fotos i les teves sol·licituds pendents s'esborren per sempre. "
        "Les preguntes que vas fer sobre coses d'altres persones i l'historial de "
        "coses que van passar per les teves mans es conserven, sense el teu nom. "
        "Confirma aquí (l'enllaç funciona durant 24 hores): {link} — si no ho has "
        "demanat tu, ignora aquest correu i no passarà res."
    ),
    "account_delete_intro": (
        "Has demanat esborrar el teu compte d'OIUEEI. Aquest és el pas de "
        "confirmació — encara no s'ha esborrat res."
    ),
    "account_delete_deletes": (
        "Si confirmes, és immediat i irreversible: el teu compte, les teves "
        "col·leccions, les teves coses amb les seves fotos i les teves sol·licituds "
        "pendents s'esborren per sempre."
    ),
    "account_delete_keeps": (
        "Les preguntes que vas fer sobre coses d'altres persones i l'historial de "
        "coses que van passar per les teves mans es conserven, sense el teu nom — "
        "es mostren com a «antic membre»."
    ),
    "account_delete_cta": "Confirmar l'esborrat",
    "account_delete_outro": (
        "L'enllaç funciona durant 24 hores i a la pàgina confirmaràs un cop més. "
        "Si no ho has demanat tu, ignora aquest correu — no passarà res."
    ),
    # Avís d'inactivitat (abans d'esborrar un compte sense fer servir)
    "inactivity_subject": "El teu compte d'OIUEEI fa temps que calla",
    "inactivity_intro": (
        "Fa {months} mesos que no entres a OIUEEI. No guardem comptes que ningú fa "
        "servir, així que aquest és l'avís que va abans."
    ),
    "inactivity_deletes": (
        "D'aquí a {days} dies el teu compte desapareix, per sempre, i amb ell les teves "
        "col·leccions, les teves coses i les seves fotos."
    ),
    "inactivity_keep": "Amb entrar-hi un cop n'hi ha prou per conservar-lo. No cal fer res més.",
    "inactivity_cta": "Entrar",
    "inactivity_outro": "I si prefereixes que se'n vagi, no cal que facis absolutament res.",
    "inactivity_plain": (
        "Fa {months} mesos que no entres a OIUEEI, i no guardem comptes que ningú fa "
        "servir. D'aquí a {days} dies el teu compte desapareix, per sempre, amb les "
        "teves col·leccions, les teves coses i les seves fotos. Amb entrar-hi un cop "
        "n'hi ha prou per conservar-lo: {link} — i si prefereixes que se'n vagi, no cal "
        "que facis res."
    ),
    # El mateix avís per a un compte que NO s'esborrarà perquè hi ha un grup que
    # en depèn. No pot amenaçar amb una cosa que no passarà.
    "inactivity_kept": (
        "El teu compte es queda: hi ha gent fent servir una col·lecció teva i no els la "
        "traurem mentre tu no hi ets. Però en tot aquest temps no l'ha cuidada ningú, i "
        "és teva."
    ),
    "inactivity_kept_outro": (
        "Si prefereixes marxar, pots esborrar el teu compte tu mateix, des del teu "
        "perfil, quan vulguis."
    ),
    "inactivity_kept_plain": (
        "Fa {months} mesos que no entres a OIUEEI. El teu compte es queda —hi ha gent "
        "fent servir una col·lecció teva i no els la traurem mentre tu no hi ets— però "
        "en tot aquest temps no l'ha cuidada ningú. Pots reprendre'l aquí: {link} — o "
        "esborrar el teu compte tu mateix, des del teu perfil, quan vulguis."
    ),
    # Contact form (support channel, to the operator)
    "contact_subject": "Contacte OIUEEI: {sender}",
    "collab_subject": "Col·laboració OIUEEI: {sender}",
    "contact_plain": (
        "Algú ha escrit pel formulari de contacte.\n\nNom: {name}\nEmail: {email}\n\n{message}"
    ),
    "contact_intro": "Algú ha escrit pel formulari de contacte:",
    "contact_name_label": "Nom",
    "contact_email_label": "Email",
    # Booking request (to owner)
    "booking_request_subject": "Tens una sol·licitud {action} pendent",
    "booking_request_plain_dated": (
        "{requester} t'ha enviat una sol·licitud {action} per a '{thing}' "
        "{when}. "
        "Confirmar la sol·licitud: {accept} | Rebutjar la sol·licitud: {reject}"
    ),
    "booking_request_plain": (
        "{requester} t'ha enviat una sol·licitud {action} per a '{thing}'. "
        "Confirmar la sol·licitud: {accept} | Rebutjar la sol·licitud: {reject}"
    ),
    "booking_request_intro": "{requester} t'ha enviat una sol·licitud {action}:",
    # The requester's address travels with the request to whoever manages the thing:
    # shared by the request email and the reservation notice. There is no
    # sentence saying that "Reply" reaches them.
    "requester_email_label": "Email",
    "hold_confirm_cta": "Confirmar la sol·licitud",
    "hold_cancel_cta": "Rebutjar la sol·licitud",
    # Booking decision (to requester)
    "decision_subject_confirmed": "La teva sol·licitud està confirmada",
    "decision_subject_cancelled": "La teva sol·licitud no ha tirat endavant",
    "decision_confirmed": "confirmada",
    "decision_cancelled": "rebutjada",
    "decision_plain_dated": (
        "La teva sol·licitud {action} de '{thing}' {when} ha estat {decision}. "
        "Veure la publicació: {url}"
    ),
    "decision_plain": (
        "La teva sol·licitud {action} de '{thing}' ha estat {decision}. Veure la publicació: {url}"
    ),
    "quantity_times": "{count} × {headline}",
    "decision_by_confirmed": "{who} ha acceptat la teva sol·licitud {action}:",
    "decision_by_declined": "{who} ha rebutjat la teva sol·licitud {action}:",
    "point_name_label": "Punt de recollida",
    "point_address_label": "Adreça",
    "point_hours_label": "Horari",
    "point_contact_label": "Contacte",
    "decision_intro": "La teva sol·licitud {action} ha estat {decision}:",
    # Invite declined (to collection owner)
    "invite_rejected_subject": "S'ha rebutjat la teva invitació",
    "invite_rejected_plain": "{invitee} ha rebutjat la invitació a '{collection}'.",
    "invite_rejected_intro": "{invitee} ha rebutjat la teva invitació a aquest grup.",
    # Booking confirmation (to requester)
    "confirmation_subject": "Sol·licitud {action} enviada",
    "confirmation_plain_dated": (
        "La teva sol·licitud {action} per a '{thing}' {when} s'ha enviat. "
        "{outro} "
        "Veure la cosa: {url}"
    ),
    "confirmation_plain": (
        "La teva sol·licitud {action} per a '{thing}' s'ha enviat. {outro} Veure la cosa: {url}"
    ),
    "confirmation_intro": "La teva sol·licitud {action} s'ha enviat:",
    # Who was told: one person who runs the thing, or more than one (a team) — the
    # person's name is not in it any more.
    "confirmation_outro_one": "Hem avisat qui gestiona aquesta cosa — aviat et respondrà.",
    "confirmation_outro_other": (
        "Hem avisat les persones que gestionen aquesta cosa — aviat et respondran."
    ),
    # Where the requester will be written to: the address they sign in with,
    # which the managers now hold. Said, never printed — the email already arrives there.
    "contact_shared_request": (
        "El teu email va amb la sol·licitud: si cal, t'escriuran aquí, al correu amb què entres a "
        "OIUEEI."
    ),
    # FAQ question (to owner)
    "faq_question_subject": "Hi ha una pregunta per respondre",
    "faq_question_plain": (
        "{questioner} ha preguntat sobre '{thing}': {question} Veure la cosa: {url}"
    ),
    "faq_question_intro": "{questioner} ha fet una pregunta sobre:",
    "question_label": "Pregunta",
    "faq_view_reply_cta": "Veure i respondre",
    # FAQ answer (to questioner)
    "faq_answer_subject": "S'ha respost la teva pregunta",
    "faq_answer_plain": "{owner} ha respost: {answer}. Veure '{thing}': {url}",
    "faq_answer_intro": "{owner} ha respost a la teva pregunta sobre:",
    "your_question_label": "La teva pregunta",
    "reply_label": "Resposta",
    # FAQ answer (to the rest of the managing team — not the answerer, not the asker)
    "faq_answered_team_subject": "Una pregunta sobre '{thing}' ja té resposta",
    "faq_answered_team_plain": (
        "{answerer} ha respost una pregunta sobre '{thing}'. "
        "Resposta: {answer} Veure la cosa: {url}"
    ),
    "faq_answered_team_intro": "{answerer} ha respost una pregunta sobre:",
    # FAQ hidden (to questioner)
    "faq_hide_subject": "S'ha amagat la teva pregunta",
    "faq_hide_plain": "{owner} ha amagat la teva pregunta: {question}",
    "faq_hide_intro": "{owner} ha amagat la teva pregunta sobre:",
    # FAQ hidden (to the rest of the managing team — not the hider, not the asker)
    "faq_hidden_team_subject": "S'ha amagat una pregunta sobre '{thing}'",
    "faq_hidden_team_plain": (
        "{hider} ha amagat una pregunta sobre '{thing}'. Veure la cosa: {url}"
    ),
    "faq_hidden_team_intro": "{hider} ha amagat una pregunta sobre:",
    # Listing reported (to owner, anonymous)
    "reported_subject": "Algú ha denunciat una de les teves coses",
    "reported_plain": (
        "Algú ha denunciat la teva cosa '{thing}'. "
        "No compartim qui l'ha denunciat. Dona-hi un cop d'ull: {url}"
    ),
    "reported_intro": "Algú ha denunciat una de les teves coses:",
    "reported_outro": (
        "No compartim qui l'ha denunciat. Dona-hi un cop d'ull i assegura't que tot està en ordre."
    ),
    "reported_review_cta": "Revisar la cosa",
    "thing_hidden_subject": "{founder} ha amagat una de les teves coses",
    "thing_hidden_plain": (
        "{founder} ha amagat {thing} de {group}. Continua sent teva: pots tornar a "
        "mostrar-la quan vulguis. {url}"
    ),
    "thing_hidden_intro": "{founder} ha amagat aquesta cosa de {group}:",
    "thing_hidden_outro": "Continua sent teva: pots tornar a mostrar-la quan vulguis.",
    "thing_hidden_cta": "Revisar la cosa",
    # Broadcast (owner → invitees)
    "email_note_test_subject": "La teva nota del correu, tal com la veuran — {collection}",
    "email_note_test_intro": (
        "Així es veurà la teva nota als correus que rep qui demana alguna cosa a "
        "{collection}. Aquest només t'ha arribat a tu."
    ),
    "broadcast_subject": "Ei! {collection}",
    "broadcast_plain": "Missatge de {owner}:\n\n{message}\n\nObrir el grup: {url}",
    "broadcast_intro": "{owner} ha enviat un missatge al grup:",
    "broadcast_open_cta": "Obrir el grup",
    # Return reminder (to owner). "Torna" names what a loan does — "reserva" is
    # only RESERVE_THING, which never comes through this email.
    "reminder_subject": "Recordatori: {thing} torna demà",
    "reminder_plain": "Recordatori: {requester} t'ha de tornar '{thing}' el {end}.",
    "reminder_body": "Recordatori: {requester} t'ha de tornar {thing} el {end}.",
    "return_due_subject": "Demà tornes {thing}",
    "return_due_plain": "Un recordatori amable: has de tornar '{thing}' a {owner} el {end}.",
    "return_due_body": "Un recordatori amable: has de tornar {thing} a {owner} el {end}.",
    # Pickup reminders (LEND/RENT, start_date = tomorrow) — the day before the handover
    "pickup_due_subject": "Demà reculls {thing}",
    "pickup_due_plain": "Un recordatori amable: reculls '{thing}' de {owner} el {start}.",
    "pickup_due_body": "Un recordatori amable: reculls {thing} de {owner} el {start}.",
    "pickup_reminder_subject": "Demà lliures {thing}",
    "pickup_reminder_plain": "Recordatori: {requester} recull '{thing}' el {start}.",
    "pickup_reminder_body": "Recordatori: {requester} recull {thing} el {start}.",
    # Manual nudge from /owner-bookings: the return date has already passed
    "return_overdue_subject": "Recordatori: tornar {thing}",
    "return_overdue_plain": (
        "{manager} et recorda que '{thing}' havia de tornar el {end}. "
        "Si ja has fet la devolució, pots ignorar aquest correu."
    ),
    "return_overdue_body": (
        "{manager} et recorda que {thing} havia de tornar el {end}. "
        "Si ja has fet la devolució, pots ignorar aquest correu."
    ),
    "view_thing_cta": "Veure la publicació",
    "demo_note": "Aquest grup és de demostració: les seves coses i persones són d'exemple.",
    # Reserves d'espai (RESERVE_THING) — confirmació automàtica, sense decisió
    "reservation_confirmed_subject": "La teva reserva de '{thing}' està confirmada",
    "reservation_confirmed_plain": (
        "La teva reserva de '{thing}' està confirmada {when}. Veure la publicació: {url}"
    ),
    "reservation_confirmed_intro": "La teva reserva està confirmada:",
    "contact_shared_reservation": "El teu email va amb la reserva.",
    "reservation_fee_label": "Cost",
    "reservation_where_label": "On",
    "reservation_notice_subject": "{requester} ha reservat '{thing}'",
    "reservation_notice_plain": "{requester} ha reservat '{thing}' {when}.",
    "reservation_notice_intro": "{requester} ha reservat:",
    "reservation_notice_phone": (
        "Ha deixat un telèfon de contacte: el tens a la pàgina de reserves, "
        "fins l'endemà de la reserva."
    ),
    "reservation_note_label": "El seu missatge",
    "reservation_cancelled_subject": "Reserva cancel·lada: '{thing}'",
    "reservation_cancelled_to_guest_plain": (
        "{other} ha cancel·lat la teva reserva de '{thing}' ({when})."
    ),
    "reservation_cancelled_to_guest_intro": "{other} ha cancel·lat la teva reserva de:",
    "reservation_cancelled_to_owner_plain": (
        "{other} ha cancel·lat la seva reserva de '{thing}' ({when})."
    ),
    "reservation_cancelled_to_owner_intro": "{other} ha cancel·lat la seva reserva de:",
    "reservation_cancel_confirmation_subject_self": "La teva reserva de '{thing}' està cancel·lada",
    "reservation_cancel_confirmation_subject_other": "Has cancel·lat una reserva de '{thing}'",
    "reservation_cancel_confirmation_intro_self": "La teva reserva està cancel·lada:",
    "reservation_cancel_confirmation_intro_other": "Has cancel·lat la reserva de {member}:",
    "reservation_cancel_confirmation_plain_self": (
        "La teva reserva de '{thing}' ({when}) està cancel·lada."
    ),
    "reservation_cancel_confirmation_plain_other": (
        "Has cancel·lat la reserva de {member} de '{thing}' ({when})."
    ),
    "reservation_reminder_subject": "La teva reserva de '{thing}' comença demà",
    "reservation_reminder_plain": (
        "Un recordatori: la teva reserva de '{thing}' és {when}. Veure la fitxa: {url}"
    ),
    "reservation_reminder_intro": "La teva reserva comença demà:",
    # Digest
    "digest_subject": "Novetats a {collection}",
    "digest_plain": "Coses noves:\n\n{things}\n\n{members}Veure la col·lecció: {url}",
    "digest_new_members_one": "I 1 persona nova s'ha sumat al grup.",
    "digest_new_members_other": "I {count} persones noves s'han sumat al grup.",
    "join_summary_subject_one": "Una persona nova a {group}",
    "join_summary_subject_other": "{count} persones noves a {group}",
    "join_summary_intro_one": "S'ha unit a {group}: {names}.",
    "join_summary_intro_other": "S'han unit a {group}: {names}.",
    "join_summary_more": "i {count} més",
    "join_summary_cta": "Veure els membres",
    "join_summary_and": "i",
    "digest_intro": "Coses noves:",
    "proposal_subject": "{collection}: convidem algú?",
    "proposal_plain": (
        "{proposer} vol convidar algú a {collection}:\n\n  {email}\n\n"
        "Encara no hem contactat amb ningú: només passa si dius que sí.\n\n"
        "Convidar-lo: {approve}\nAra no: {reject}"
    ),
    "proposal_intro": "{proposer} vol convidar algú a {collection}.",
    "proposal_note": "Hi afegeix: {note}",
    "proposal_nobody_told": (
        "Encara no hem contactat amb ningú. La invitació només s'envia si dius que sí i, si dius "
        "que no, la persona proposada no sabrà mai que ho va ser."
    ),
    "proposal_approve_cta": "Convidar-lo",
    "proposal_reject_cta": "Ara no",
    "proposal_declined_subject": "Sobre la teva proposta per a {collection}",
    "proposal_declined_intro": (
        "Gràcies per pensar en algú per a {collection}. {owner} ha decidit "
        "no enviar aquesta invitació de moment:"
    ),
    "proposal_declined_outro": (
        "No hem contactat amb aquesta persona ni ho farem. No canvia res "
        "més: continues formant part del grup."
    ),
    "proposal_declined_body": (
        "Gràcies per pensar en algú per a {collection}. {owner} ha decidit no enviar aquesta "
        "invitació de moment, així que no hem contactat amb {email} ni ho farem. No canvia res "
        "més: continues formant part del grup."
    ),
    "digest_mute_cta": "Deixar de rebre els resums d'aquest grup",
}


# Frases de creixement que s'afegeixen als correus sortints (damunt del peu de
# preferències) per convertir convidats en creadors. En surt una a l'atzar per
# enviament. ``path`` és on porta el CTA, sota la URL base del frontend: el
# formulari del tipus de què parla la frase, o el selector (`/new`) si no parla
# de cap (una frase sense ``path`` hi porta també). Les mateixes destinacions en
# tots els idiomes; ``cta`` és només l'etiqueta de l'enllaç.
VIRAL_LINES = [
    {
        "text": (
            "Renoves l'armari? Obre una paradeta amb la roba que ja no uses i ofereix-la als "
            "teus amics."
        ),
        "cta": "Comença aquí",
        "path": "/stall/new",
    },
    {
        "text": (
            "Un trepant que uses dues vegades l'any? Obre una biblioteca de les coses amb les "
            "teves eines i deixa-les als teus veïns."
        ),
        "cta": "Obre la teva biblioteca",
        "path": "/library/new",
    },
    {
        "text": (
            "Prestatgeries plenes de llibres ja llegits? Posa'ls en una paradeta i dona'ls "
            "una segona vida."
        ),
        "cta": "Així de fàcil",
        "path": "/stall/new",
    },
    {
        "text": (
            "Joguines que ja han quedat petites? Obre una paradeta i passa-les a altres famílies."
        ),
        "cta": "Crea la teva",
        "path": "/stall/new",
    },
    {
        "text": (
            "Trasllat a la vista? Obre una paradeta amb el que no t'enduus i troba-li una "
            "nova casa."
        ),
        "cta": "Comença per aquí",
        "path": "/stall/new",
    },
    {
        "text": (
            "Un grup d'amics, l'escala, l'AMPA? Obriu junts una paradeta, una biblioteca de "
            "les coses o un taller, i compartiu entre tots."
        ),
        "cta": "Creeu el vostre grup",
        "path": "/new",
    },
]
