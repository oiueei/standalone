"""Catalan email texts (``EMAIL_LANGUAGE=ca``).

Same keys as ``en.py`` (guarded by the parity test); informal, warm tone,
matching the app's Catalan UI vocabulary (reservar, petició, intercanvi)."""

TEXTS = {
    # Shared
    "footer_manage": "Gestiona les teves preferències de correu",
    "dates_label": "Dates",
    "view_collection_cta": "Veure la col·lecció",
    # Substantius d'acció per als correus de reserva — calquen el vocabulari del
    # frontend (thingCard.action / types): una sol·licitud SELL és "sol·licitud
    # de compra", una LEND "sol·licitud de préstec", etc. SWAP té les seves
    # plantilles de sol·licitud/confirmació, però el correu de decisió
    # (send_booking_decision_email) és compartit i interpola {action} també per
    # als intercanvis, així que SWAP necessita el seu substantiu. WISH mai
    # reserva.
    #
    # A DIFERÈNCIA d'en/es, aquí els valors porten la preposició ("de compra",
    # "d'intercanvi") i les plantilles diuen "sol·licitud {action}" — el català
    # elideix "de" davant de vocal, i "sol·licitud de intercanvi" seria
    # incorrecte.
    "action_noun_GIFT_THING": "de regal",
    "action_noun_SELL_THING": "de compra",
    "action_noun_LEND_THING": "de préstec",
    "action_noun_RENT_THING": "de lloguer",
    "action_noun_SHARE_THING": "de traspàs",
    "action_noun_SWAP_THING": "d'intercanvi",
    # Magic link
    "magic_subject": "Hola, et donem la benvinguda a OIUEEI!",
    "magic_subject_collection": "Hola, et donem la benvinguda a '{collection}' - OIUEEI!",
    "magic_plain": "Hola! Fes clic aquí per iniciar sessió: {link}",
    "magic_intro": "Hola! Fes clic aquí per iniciar sessió:",
    "magic_cta": "Iniciar sessió",
    # Collection invite
    "invite_subject": "Tens una invitació a '{collection}' - OIUEEI!",
    "invite_plain": (
        "T'han convidat a veure: {collection}. "
        "Acceptar la invitació: {accept} | Rebutjar la invitació: {reject}"
    ),
    "invite_intro": "{inviter} t'ha convidat a veure:",
    "invite_accept_cta": "Acceptar la invitació",
    "invite_decline_cta": "Rebutjar la invitació",
    # Collection access revoked
    "revoke_subject": "S'ha revocat el teu accés",
    "revoke_plain": "{owner} ha revocat el teu accés a '{collection}'.",
    "revoke_intro": "{owner} ha revocat el teu accés a:",
    "revoke_outro": "Ja no podràs veure aquesta col·lecció.",
    # Collection welcome document (sent once, the first time someone joins)
    "welcome_doc_subject": "Et donem la benvinguda a '{collection}'",
    "welcome_doc_plain": (
        "Et donem la benvinguda a '{collection}'. El grup té un document de "
        "benvinguda i normes — fes-hi una ullada: {url}"
    ),
    "welcome_doc_intro": "Benvinguda! El grup té un document de benvinguda i normes:",
    "welcome_doc_outro": "Fes-hi una ullada abans de començar.",
    # Booking request (to owner)
    "booking_request_subject": "Tens una sol·licitud {action} pendent",
    "booking_request_plain_dated": (
        "{requester} t'ha enviat una sol·licitud {action} per a '{thing}' "
        "del {start} al {end}. "
        "Confirmar la reserva: {accept} | Cancel·lar la reserva: {reject}"
    ),
    "booking_request_plain": (
        "{requester} t'ha enviat una sol·licitud {action} per a '{thing}'. "
        "Confirmar la reserva: {accept} | Cancel·lar la reserva: {reject}"
    ),
    "booking_request_intro": "{requester} t'ha enviat una sol·licitud {action}:",
    "hold_confirm_cta": "Confirmar la reserva",
    "hold_cancel_cta": "Cancel·lar la reserva",
    # Booking decision (to requester)
    "decision_subject": "Tenim notícies",
    "decision_confirmed": "confirmada",
    "decision_cancelled": "cancel·lada",
    "decision_plain_dated": (
        "La teva sol·licitud {action} de '{thing}' del {start} al {end} ha estat {decision}."
    ),
    "decision_plain": "La teva sol·licitud {action} de '{thing}' ha estat {decision}.",
    "decision_intro": "La teva sol·licitud {action} ha estat {decision}:",
    # Booking auto-declined (someone else got it)
    "unavailable_subject": "Algú ha arribat abans",
    "unavailable_plain": (
        "'{thing}' se n'ha anat amb una altra persona aquesta vegada. "
        "No passa res — per aquí les coses van i venen, estigues pendent!"
    ),
    "unavailable_intro": "{thing} se n'ha anat amb una altra persona aquesta vegada.",
    "unavailable_outro": "No passa res — per aquí les coses van i venen, estigues pendent!",
    # Invite declined (to collection owner)
    "invite_rejected_subject": "S'ha rebutjat la teva invitació",
    "invite_rejected_plain": "{invitee} ha rebutjat la invitació a '{collection}'.",
    "invite_rejected_intro": "{invitee} ha rebutjat la teva invitació a:",
    # Booking confirmation (to requester)
    "confirmation_subject": "Sol·licitud {action} enviada",
    "confirmation_plain_dated": (
        "La teva sol·licitud {action} per a '{thing}' del {start} al {end} s'ha enviat. "
        "Hem avisat {owner} — et respondrà aviat. "
        "Veure la cosa: {url}"
    ),
    "confirmation_plain": (
        "La teva sol·licitud {action} per a '{thing}' s'ha enviat. "
        "Hem avisat {owner} — et respondrà aviat. Veure la cosa: {url}"
    ),
    "confirmation_intro": "La teva sol·licitud {action} s'ha enviat:",
    "part_of_label": "Part de",
    "confirmation_outro": "Hem avisat {owner} — et respondrà aviat.",
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
    # FAQ hidden (to questioner)
    "faq_hide_subject": "S'ha amagat la teva pregunta",
    "faq_hide_plain": "{owner} ha amagat la teva pregunta: {question}",
    "faq_hide_intro": "{owner} ha amagat la teva pregunta sobre:",
    # Listing reported (to owner, anonymous)
    "reported_subject": "Algú ha denunciat un dels teus anuncis",
    "reported_plain": (
        "Algú ha denunciat el teu anunci '{thing}'. "
        "No compartim qui l'ha denunciat. Dona-hi un cop d'ull: {url}"
    ),
    "reported_intro": "Algú ha denunciat un dels teus anuncis:",
    "reported_outro": (
        "No compartim qui l'ha denunciat. Dona-hi un cop d'ull i assegura't que tot està en ordre."
    ),
    "reported_review_cta": "Revisar l'anunci",
    # Broadcast (owner → invitees)
    "broadcast_subject": "Ei! {collection}",
    "broadcast_plain": "Missatge de {owner} ({collection}):\n\n{message}\n\nPuc ajudar! {url}",
    "broadcast_intro": "{owner} ha enviat un missatge a {collection}:",
    "broadcast_help_cta": "Puc ajudar!",
    # Wish posted (to group)
    "wish_posted_subject": "Algú del teu grup busca alguna cosa",
    "wish_posted_plain": (
        "{creator} ha publicat una nova petició: '{wish}'. Pots ajudar? Mira-ho: {url}"
    ),
    "wish_posted_intro": "{creator} ha publicat una nova petició:",
    "wish_posted_cta": "Mira si pots ajudar",
    # Wish answered (to creator)
    "wish_response_subject": "Algú ha contestat la teva petició",
    "wish_response_plain": (
        "{responder} ha contestat la teva petició '{wish}'. Veure la resposta: {url}"
    ),
    "wish_response_intro": "{responder} ha contestat la teva petició:",
    "wish_response_cta": "Veure la resposta",
    # Wish resolved — thanks (to accepted responder)
    "wish_thanks_subject": "Gràcies per la teva ajuda",
    "wish_thanks_plain": (
        "{creator} ha marcat la petició '{wish}' com a resolta "
        "i et volia donar les gràcies per la teva ajuda."
    ),
    "wish_thanks_intro": "{creator} ha marcat aquesta petició com a resolta:",
    "wish_thanks_outro": "Gràcies per donar un cop de mà!",
    # Return reminder (to owner)
    "reminder_subject": "Recordatori: una reserva acaba demà",
    "reminder_plain": "Recordatori: la reserva de {requester} sobre '{thing}' acaba el {end}.",
    "reminder_body": "Recordatori: la reserva de {requester} sobre {thing} acaba el {end}.",
    # Swap request (to owner)
    "swap_request_subject": "Tens una proposta d'intercanvi",
    "swap_request_plain": (
        "{requester} vol intercanviar '{thing}' per: {offered}. "
        "Confirmar l'intercanvi: {accept} | Cancel·lar l'intercanvi: {reject}"
    ),
    "swap_request_intro": "{requester} vol intercanviar:",
    "swap_exchange_label": "A canvi de:",
    "swap_confirm_cta": "Confirmar l'intercanvi",
    "swap_cancel_cta": "Cancel·lar l'intercanvi",
    # Swap confirmation (to requester)
    "swap_conf_subject": "Proposta d'intercanvi enviada",
    "swap_conf_plain": (
        "La teva proposta d'intercanvi de '{thing}' (oferint: {offered}) s'ha enviat. "
        "El seu propietari et respondrà aviat."
    ),
    "swap_conf_sent": "La teva proposta d'intercanvi s'ha enviat!",
    "swap_conf_requested_label": "Has demanat:",
    "swap_conf_offered_label": "Has ofert:",
    "swap_conf_outro": "El seu propietari et respondrà aviat.",
    # Digest
    "digest_subject": "Novetats a {collection}",
    "digest_plain": "Coses noves a {collection}:\n\n{things}\n\nVeure la col·lecció: {url}",
    "digest_intro": "Coses noves a {collection}:",
    # Newsletter
    "newsletter_subject": "Butlletí setmanal: {collection}",
    "newsletter_intro": "Butlletí de {collection}:",
    "newsletter_new_things": "Coses noves",
    "newsletter_transfers": "Canvis de propietari",
}

# Frases de creixement que s'afegeixen als correus sortints (sobre el peu de
# preferències) per convertir convidats en creadors. Se'n tria una a l'atzar per
# enviament. El CTA sempre apunta a {frontend_base}/collections/new; ``cta`` és
# només l'etiqueta de l'enllaç.
VIRAL_LINES = [
    {
        "text": (
            "Renoves l'armari? Crea una col·lecció amb la roba que ja no uses "
            "i ofereix-la als teus amics."
        ),
        "cta": "Comença aquí",
    },
    {
        "text": (
            "Un trepant que uses dues vegades l'any? Crea una col·lecció amb les "
            "teves eines i deixa-les als teus veïns."
        ),
        "cta": "Crea la teva col·lecció",
    },
    {
        "text": (
            "Prestatgeries plenes de llibres ja llegits? Munta'ls una col·lecció "
            "i dona'ls una segona vida."
        ),
        "cta": "Així de fàcil",
    },
    {
        "text": (
            "Joguines que ja han quedat petites? Crea una col·lecció i passa-les a altres famílies."
        ),
        "cta": "Crea la teva",
    },
    {
        "text": (
            "Trasllat a la vista? Fes una col·lecció amb el que no t'enduus i "
            "troba-li una nova casa."
        ),
        "cta": "Comença per aquí",
    },
    {
        "text": (
            "Un grup d'amics, l'escala, l'AMPA? Creeu una col·lecció comunitària "
            "i compartiu entre tots."
        ),
        "cta": "Creeu el vostre grup",
    },
]
