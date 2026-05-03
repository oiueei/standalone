"""
Spanish demo data — users, collections, things, FAQs with Spanish text.
Use via `python manage.py seed_demo --lang=es`.

Text lengths respect model max_length constraints:
  headline=64, description=256, question=64, answer=256, location=32.
"""

from datetime import datetime

from .common import TZ_PLUS2

USERS = [
    {
        "code": "La1aN1",
        "email": "lala@mail.com",
        "name": "Lala",
        "headline": "¡Viva la segunda mano!",
        "theeeme_id": "BUU331",
    },
    {
        "code": "L3L3oo",
        "email": "lele@mail.com",
        "name": "Lele",
        "headline": "¡Aquí! ¡Ahora! ¡Compartiendo!",
        "theeeme_id": "K0P4R1",
    },
    {
        "code": "l1l13S",
        "email": "lili@mail.com",
        "name": "Lili",
        "headline": "¡Viva la tienda de préstamos! Lili tiene tus herramientas.",
        "theeeme_id": "BUU331",
    },
    {
        "code": "l0l0oh",
        "email": "lolo@mail.com",
        "name": "Lolo",
        "headline": "¡El sombrío Heathcliff llama! ¡Club de lectura de Lolo!",
        "theeeme_id": "BUU331",
    },
    {
        "code": "1u1ucs",
        "email": "lulu@mail.com",
        "name": "Lulu",
        "headline": "Conozco a todos y me apunto a todo – ¡la chispa comunitaria!",
        "theeeme_id": "BUU331",
    },
]

COLLECTIONS = [
    {
        "code": "La1aC1",
        "owner_code": "La1aN1",
        "headline": "Lala se va de sabático, ¡todo se vende por diez pavos!",
        "description": (
            "Tres reglas, colega: solo efectivo, te lo llevas tú, fecha límite el 25. "
            "¿Queda algo? ¡Al orfanato del barrio de cabeza!"
        ),
        "invites": ["L3L3oo"],
        "is_onboarding": True,
        "allowed_thing_types": ["SELL_THING"],
        "thumbnail": "La1aC1",
    },
    {
        "code": "La1aC2",
        "owner_code": "La1aN1",
        "headline": "Vanlife a la carta – ¡nuestra furgo hippie os espera!",
        "description": (
            "¿Hay que mover un sofá? ¿Perseguir un atardecer? Nuestra furgo comunitaria "
            "está lista. Resérvala para recados, viajes o aventuras espontáneas. "
            "El gasóleo lo pones tú, el buen rollo corre por la casa. "
            "¡Pero nada de toallas con arena en los asientos!"
        ),
        "mode": "COMMUNITY",
        "invites": ["L3L3oo", "l1l13S", "l0l0oh", "1u1ucs"],
        "is_onboarding": True,
        "thumbnail": "La1aC2",
    },
    {
        "code": "L3L3C1",
        "owner_code": "L3L3oo",
        "headline": "¡Las tartas de Lele!",
        "description": (
            "Hago tartas caseras espectaculares con ingredientes 100% naturales y sanos. "
            "Perfectas para celebraciones conscientes como cumples, adaptables a dietas "
            "veganas, sin gluten o bajas en azúcar—¡escríbeme para personalizar la tuya!"
        ),
        "invites": ["La1aN1"],
        "is_onboarding": True,
        "allowed_thing_types": ["ORDER_THING"],
        "thumbnail": "L3L3C1",
    },
    {
        "code": "L3L3C2",
        "owner_code": "L3L3oo",
        "headline": "El salón verde de Lele – ¡llévate una suculenta gratis!",
        "description": (
            "¡Mamá planta con demasiadas crías verdes! Pásate a conocer a mi escuadrón "
            "suculento – echeverias, jades, sedums – y te regalo un esqueje. Guía fácil "
            "de cuidados incluida. Única regla: ¡ponle nombre a tu nueva amiga verde!"
        ),
        "is_minimalist": True,
        "invites": ["La1aN1", "l1l13S", "l0l0oh"],
        "is_onboarding": True,
        "allowed_thing_types": ["GIFT_THING"],
        "thumbnail": "L3L3C2",
    },
    {
        "code": "l0l0C1",
        "owner_code": "l0l0oh",
        "headline": "¡El melancólico Heathcliff llama! ¡Club del libro de Lolo!",
        "description": (
            "¿Ganas de páramos ventosos y amantes atormentados? Sumérgete en romances "
            "ingleses como Cumbres borrascosas en el club de lectura de Lolo. Llévate "
            "clásicos, comparte emociones con un té – ¡apúntate para la próxima lectura!"
        ),
        "invites": ["La1aN1", "L3L3oo", "l1l13S"],
        "is_onboarding": True,
        "allowed_thing_types": ["EVENT_THING"],
        "thumbnail": "l0l0C1",
    },
    {
        "code": "l0l0C2",
        "owner_code": "l0l0oh",
        "headline": "Sesiones de dulcémele con Lolo – ¡música como meditación!",
        "description": (
            "¿Te apetece aprender un instrumento solo por gusto? Lolo enseña el dulcémele "
            "– esa arpa trapezoidal soñadora que se toca con mazos pequeños. Clases "
            "tranquis, sin recitales ni notas. Solo tú, dos palillos y un sonido precioso."
        ),
        "mode": "PROPRIETARY",
        "invites": ["La1aN1", "L3L3oo", "l1l13S", "1u1ucs"],
        "is_onboarding": True,
        "allowed_thing_types": ["APPOINTMENT_THING"],
        "thumbnail": "l0l0C2",
    },
    {
        "code": "l1l1C1",
        "owner_code": "l1l13S",
        "headline": "Préstamos de Lili – ¡hora de las herramientas!",
        "description": (
            "¿Necesitas taladro, limpiador de vapor, escalera sólida, báscula de equipaje "
            "o mega kit de magdalenas? La biblioteca de préstamos de Lili te cubre – "
            "gratis para tareas de coliving, se devuelve limpio, por orden de llegada. "
            "¡Sin líos!"
        ),
        "invites": ["La1aN1"],
        "is_onboarding": True,
        "allowed_thing_types": ["LEND_THING"],
        "thumbnail": "l1l1C1",
    },
    {
        "code": "l1l1C2",
        "owner_code": "l1l13S",
        "headline": "Swap de circuitos de Lili – ¡la resistencia es fútil!",
        "description": (
            "El coliving de Lili funciona con jumpers y Arduinos a medio hacer. "
            "¿Tienes un Nano cogiendo polvo? ¿Un sensor que no era el tuyo? "
            "Ponlo en el tablón, elige lo que te guste, propón un swap. "
            "Solo componentes — sin dinero ni cortos."
        ),
        "mode": "COMMUNITY",
        "is_swap": True,
        "invites": ["La1aN1", "L3L3oo", "l0l0oh", "1u1ucs"],
        "is_onboarding": True,
        "thumbnail": "l1l1C2",
    },
    {
        "code": "1u1uC1",
        "owner_code": "1u1ucs",
        "headline": "Estantería fantasma de Lulu – ¡acecha con tus trastos!",
        "description": (
            "¿Ves algo cogiendo polvo? Hazle una foto y súbelo a la estantería fantasma "
            "de Lulu – sin líos, sin precios, solo un feed de descartes del coliving. "
            "¡Email semanal con las novedades! Pero corre, ¡las cosas desaparecen rápido!"
        ),
        "mode": "COMMUNITY",
        "is_share": True,
        "newsletter_enabled": True,
        "digest_frequency": "WEEKLY",
        "invites": ["La1aN1", "L3L3oo", "l1l13S", "l0l0oh"],
        "is_onboarding": True,
        "thumbnail": "1u1uC1",
    },
]

THINGS = [
    # --- Lala: sabbatical sale ---
    {
        "code": "stffa1",
        "type": "SELL_THING",
        "owner_code": "La1aN1",
        "collections": ["La1aC1"],
        "headline": "Alfombra nórdica peluda",
        "description": "¡Nido de meditación nórdico! Lana suave como oveja escocesa, vibras hygge con aroma a pachuli. ¡Por solo diez pavos!",
        "thumbnail": "stffa1",
        "fee": "20.00",
        "condition": "NEW",
    },
    {
        "code": "stffa2",
        "type": "SELL_THING",
        "owner_code": "La1aN1",
        "collections": ["La1aC1"],
        "headline": "Juego de tazas",
        "description": '¡Fiesta del té pagana! 12 tazas con "Keep Calm and Chai On". ¡Perfectas para infusiones hippies!',
        "thumbnail": "stffa2",
        "fee": "30.00",
        "availability": "IMMEDIATE",
    },
    {
        "code": "stffa3",
        "type": "SELL_THING",
        "owner_code": "La1aN1",
        "collections": ["La1aC1"],
        "headline": "Batidora retro",
        "description": "¡Batidora McBatidora! Este trasto mágico tritura kale y sueños hippies en batidos cósmicos. ¡Paz y zumo por 10 pavos!",
        "thumbnail": "stffa3",
        "fee": "10.00",
        "condition": "GOOD",
        "availability": "NEXT_WEEK",
    },
    {
        "code": "stffa4",
        "type": "SELL_THING",
        "owner_code": "La1aN1",
        "collections": ["La1aC1"],
        "headline": "Plancha al vapor",
        "description": "¡Doma arrugas como una bestia! Deja las camisetas tie-dye impecables para festivales. ¡Suaviza tu karma por diez pavos!",
        "thumbnail": "stffa4",
        "fee": "10.00",
        "availability": "IMMEDIATE",
        "location": "Barcelona",
    },
    {
        "code": "stffa5",
        "type": "SELL_THING",
        "owner_code": "La1aN1",
        "collections": ["La1aC1"],
        "headline": "Lámpara psicodélica disco",
        "description": "¡Guirnalda rasta! Gira como un viaje de Glastonbury, brilla para infusiones de medianoche. ¡Mola por 10 pavos!",
        "thumbnail": "stffa5",
        "fee": "20.00",
        "condition": "NEW",
    },
    # --- Lele: bakery orders ---
    {
        "code": "cksle1",
        "type": "ORDER_THING",
        "owner_code": "L3L3oo",
        "collections": ["L3L3C1"],
        "headline": "Bollos de pistacho divinos",
        "description": "Tres bollos de brioche rellenos de crema de pistacho, espolvoreados con polvo mágico y frutos secos crujientes. ¡Explosión verde de alegría para eventos elegantes! Pide tu tanda hipnótica ya.",
        "thumbnail": "cksle1",
        "fee": "5.00",
    },
    {
        "code": "cksle2",
        "type": "ORDER_THING",
        "owner_code": "L3L3oo",
        "collections": ["L3L3C1"],
        "headline": "Tarta corazón irresistible",
        "description": 'Belleza redonda con "Love" en chocolate, con rosa roja y perlas brillantes. Cremosa y súper romántica. Para San Valentín, aniversarios o porque sí – ¡caerás por su sabor!',
        "thumbnail": "cksle2",
        "fee": "40.00",
    },
    {
        "code": "cksle3",
        "type": "ORDER_THING",
        "owner_code": "L3L3oo",
        "collections": ["L3L3C1"],
        "headline": "Tarta de frambuesa soñadora",
        "description": "Capas rosas de frambuesa sobre crema blanca, en soporte de cristal. Fresca, chispeante y súper adictiva. Estrella del cumple o el brunch – ¡pide y conquista corazones!",
        "thumbnail": "cksle3",
        "fee": "60.00",
    },
    {
        "code": "cksle4",
        "type": "ORDER_THING",
        "owner_code": "L3L3oo",
        "collections": ["L3L3C1"],
        "headline": "Majestad de macarons",
        "description": "Tarta fina y cremosa coronada con macarons gris-oro, flores rosas y volutas perfectas. Ideal para bodas o meriendas: lujo francés con tu toque. Tu evento, ¡tu sabor soñado!",
        "thumbnail": "cksle4",
        "fee": "45.00",
    },
    {
        "code": "cksle5",
        "type": "ORDER_THING",
        "owner_code": "L3L3oo",
        "collections": ["L3L3C1"],
        "headline": "Tarta de zanahoria acogedora",
        "description": "Cuadrados gruesos de zanahoria con glaseado aterciopelado, en plato rosa con taza Marimekko y té. Un abrazo nórdico en forma de tarta – ¡puro hygge! Ideal para cafés acogedores o meriendas post-ruta.",
        "thumbnail": "cksle5",
        "fee": "5.00",
    },
    # --- Lili: tool library ---
    {
        "code": "lltl01",
        "type": "LEND_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "headline": "Kit de taladro robusto",
        "description": "¡Bestia sin cables para desastres DIY! Atraviesa paredes como mantequilla, con juego completo de brocas. ¡Pídelo prestado para tu próximo arreglo casero!",
        "condition": "NEW",
        "documents": [
            {
                "public_id": "lltl01",
                "filename": "Kit de taladro robusto.pdf",
                "content_type": "application/pdf",
            }
        ],
    },
    {
        "code": "lltl02",
        "type": "LEND_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "headline": "Limpiador de vapor mágico",
        "description": "¡Chisporrotea mugre de hornos y sofás! Varita eco-mágica que deja todo reluciente. ¡Perfecto para un repaso pre-fiesta!",
        "condition": "GOOD",
        "documents": [
            {
                "public_id": "lltl02",
                "filename": "Limpiador de vapor mágico.pdf",
                "content_type": "application/pdf",
            }
        ],
    },
    {
        "code": "lltl03",
        "type": "LEND_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "headline": "Escalera sólida como una roca",
        "description": "¡Campeona de seguridad de dos metros, sin bamboleos! Llega a esas telarañas del desván o estanterías altas. ¡Más firme que el apretón de un cura!",
        "condition": "NEW",
        "documents": [
            {
                "public_id": "lltl03",
                "filename": "Escalera sólida.pdf",
                "content_type": "application/pdf",
            }
        ],
    },
    {
        "code": "lltl04",
        "type": "LEND_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "headline": "Mega kit de magdalenas",
        "description": "¡Moldes de silicona, bandejas y mangas pasteleras! Hornea bombas de arándanos o maravillas veganas. ¡Kit completo para novatos en la cocina!",
        "condition": "USED",
        "documents": [
            {
                "public_id": "lltl04",
                "filename": "Mega kit de magdalenas.pdf",
                "content_type": "application/pdf",
            }
        ],
    },
    {
        "code": "lltl05",
        "type": "LEND_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C1"],
        "headline": "Báscula de equipaje pro",
        "description": "¡Héroe de bolsillo que te salva de multas en el aeropuerto! Pesa maletas hasta 50 kg. Esencial para viajeros de vuelos baratos.",
        "condition": "FAIR",
        "documents": [
            {
                "public_id": "lltl05",
                "filename": "Báscula de equipaje pro.pdf",
                "content_type": "application/pdf",
            }
        ],
    },
    # --- Lolo: book club events ---
    {
        "code": "lltl06",
        "type": "EVENT_THING",
        "owner_code": "l0l0oh",
        "collections": ["l0l0C1"],
        "headline": "Club de lectura – Cumbres Borrascosas clásica",
        "description": "¡La obra tormentosa de Brontë! El corazón salvaje de Heathcliff en páramos ventosos. ¡Elige para nuestra próxima charla melancólica!",
        "thumbnail": "lltl06",
        "condition": "NEW",
        "event_date": datetime(2027, 1, 5, 16, 0, 0, tzinfo=TZ_PLUS2),
    },
    {
        "code": "lltl07",
        "type": "EVENT_THING",
        "owner_code": "l0l0oh",
        "collections": ["l0l0C1"],
        "headline": "Club de lectura – Jane Eyre gótica",
        "description": "De huérfana a obsesión – ¡puro fuego Brontë! La loca del ático te espera. ¡Perfecta para nuestra inmersión en el romance oscuro!",
        "thumbnail": "lltl07",
        "condition": "GOOD",
        "event_date": datetime(2027, 2, 5, 16, 0, 0, tzinfo=TZ_PLUS2),
    },
    {
        "code": "lltl08",
        "type": "EVENT_THING",
        "owner_code": "l0l0oh",
        "collections": ["l0l0C1"],
        "headline": "Club de lectura – Rebecca atemporal",
        "description": "¡El misterio de Manderley de Du Maurier! La segunda esposa contra la primera fantasmal – escalofríos y emociones. ¡Únete a la sesión de chismes!",
        "thumbnail": "lltl08",
        "condition": "NEW",
        "event_date": datetime(2027, 3, 5, 16, 0, 0, tzinfo=TZ_PLUS2),
    },
    {
        "code": "lltl09",
        "type": "EVENT_THING",
        "owner_code": "l0l0oh",
        "collections": ["l0l0C1"],
        "headline": "Club de lectura – Orgullo y Prejuicio chispeante",
        "description": "¡El baile ingenioso de Darcy de Austen! Las hermanas Bennet contra solteros elegibles. ¡Aligera nuestro gótico con humor de Regencia!",
        "thumbnail": "lltl09",
        "condition": "USED",
        "event_date": datetime(2027, 4, 5, 16, 0, 0, tzinfo=TZ_PLUS2),
    },
    {
        "code": "lltl10",
        "type": "EVENT_THING",
        "owner_code": "l0l0oh",
        "collections": ["l0l0C1"],
        "headline": "Club de lectura – Tess de los D'Urberville",
        "description": "¡La trágica belleza rural de Hardy! Mujer pura injustamente culpada. Profunda y devastadora – ¡ideal para nuestra juerga literaria emocional!",
        "thumbnail": "lltl10",
        "condition": "FAIR",
        "event_date": datetime(2027, 5, 5, 16, 0, 0, tzinfo=TZ_PLUS2),
    },
    # --- Lulu: share collection (ownership transferred below in TRANSFERS) ---
    {
        "code": "lltl11",
        "type": "SHARE_THING",
        "owner_code": "La1aN1",
        "collections": ["1u1uC1"],
        "headline": "Fondue olvidada",
        "description": "¡Fundidora de queso del 98 para seis! Con tenedores y piloto incluidos. ¡Pilla antes de que vuelva a desaparecer!",
        "thumbnail": "lltl11",
        "condition": "NEW",
    },
    {
        "code": "lltl12",
        "type": "SHARE_THING",
        "owner_code": "L3L3oo",
        "collections": ["1u1uC1"],
        "headline": "Maletas vintage apiladas",
        "description": "¡Tres bellezas de cuero, rozaduras menores! Perfectas para escapadas de fin de semana o almacenamiento chic. ¡Pídelas antes de que desaparezcan!",
        "thumbnail": "lltl12",
        "condition": "GOOD",
    },
    {
        "code": "lltl13",
        "type": "SHARE_THING",
        "owner_code": "l1l13S",
        "collections": ["1u1uC1"],
        "headline": "Bicicleta estática bestial",
        "description": "¡Spinner silencioso con 8 niveles de resistencia! Cardio sin culpa post-confinamiento. Se va en un suspiro – ¡fuerza al pedal!",
        "thumbnail": "lltl13",
        "condition": "NEW",
    },
    {
        "code": "lltl14",
        "type": "SHARE_THING",
        "owner_code": "l0l0oh",
        "collections": ["1u1uC1"],
        "headline": "Macetas de cerámica",
        "description": "¡Trío de terracota hecho a mano, platito incluido! Revive tus suculentas tristes. Estrella del resumen semanal – ¡corre!",
        "thumbnail": "lltl14",
        "condition": "USED",
    },
    {
        "code": "lltl15",
        "type": "SHARE_THING",
        "owner_code": "1u1ucs",
        "collections": ["1u1uC1"],
        "headline": "Festín de juegos de mesa",
        "description": "¡Monopoly, Cluedo y Pictionary completos! Clásicos del coliving para noches lluviosas. Por orden de llegada – ¡vuelan!",
        "thumbnail": "lltl15",
        "condition": "FAIR",
    },
    # --- Lele: succulent gifts (minimalist, is_endless) ---
    {
        "code": "lltl22",
        "type": "GIFT_THING",
        "owner_code": "L3L3oo",
        "collections": ["L3L3C2"],
        "headline": "Zebra, Rosie y Jade – ¡mi trío de terracota busca casa!",
        "thumbnail": "lltl22",
        "is_endless": True,
    },
    {
        "code": "lltl23",
        "type": "GIFT_THING",
        "owner_code": "L3L3oo",
        "collections": ["L3L3C2"],
        "headline": "Su Majestad la Echeveria – corona rosa, ¡crías gratis!",
        "thumbnail": "lltl23",
        "is_endless": True,
    },
    {
        "code": "lltl24",
        "type": "GIFT_THING",
        "owner_code": "L3L3oo",
        "collections": ["L3L3C2"],
        "headline": "Atardecer en maceta – ¡cría melocotón-lila para adoptar!",
        "thumbnail": "lltl24",
        "is_endless": True,
    },
    {
        "code": "lltl25",
        "type": "GIFT_THING",
        "owner_code": "L3L3oo",
        "collections": ["L3L3C2"],
        "headline": "La bolita peluda – hojas aterciopeladas, ¡cría gratis!",
        "thumbnail": "lltl25",
        "is_endless": True,
    },
    {
        "code": "lltl26",
        "type": "GIFT_THING",
        "owner_code": "L3L3oo",
        "collections": ["L3L3C2"],
        "headline": "De mis manos a las tuyas – ¡elige tu cría!",
        "thumbnail": "lltl26",
        "is_endless": True,
    },
    {
        "code": "lltl27",
        "type": "GIFT_THING",
        "owner_code": "L3L3oo",
        "collections": ["L3L3C2"],
        "headline": "Mi miniprado – ¡cinco suculentas hermanas bajo un techo!",
        "thumbnail": "lltl27",
        "is_endless": True,
    },
    {
        "code": "lltl28",
        "type": "GIFT_THING",
        "owner_code": "L3L3oo",
        "collections": ["L3L3C2"],
        "headline": "¡Muchas crías y pocas macetas – ven a rescatar una!",
        "thumbnail": "lltl28",
        "is_endless": True,
    },
    # --- Lolo: dulcimer appointment ---
    {
        "code": "lltl29",
        "type": "APPOINTMENT_THING",
        "owner_code": "l0l0oh",
        "collections": ["l0l0C2"],
        "headline": "¡Clases todas las tardes!",
        "description": "Trae tu propio dulcémele si tienes uno. Si no, no te agobies – ¡el mío está aquí para que lo uses prestado!",
        "thumbnail": "lltl29",
        "slot_duration": 60,
        "availability_schedule": [{"days": [2, 3, 4], "start_time": "14:00", "end_time": "18:00"}],
        "location": "Casa de Lolo, Zona Franca, BCN",
    },
    # --- Lala: shared van (hourly asset) ---
    {
        "code": "lltl30",
        "type": "ASSET_THING",
        "owner_code": "La1aN1",
        "collections": ["La1aC2"],
        "headline": "Vayas donde vayas, ¡ella lo hace más bonito!",
        "thumbnail": "lltl30",
        "booking_unit": "HOUR",
    },
    # --- Lulu's wish posted by Lala ---
    {
        "code": "La1aW1",
        "type": "WISH_THING",
        "owner_code": "La1aN1",
        "collections": ["1u1uC1"],
        "headline": "¿Alguien tiene una escalerilla? ¡La estantería alta gana! 🪜",
    },
    # --- Lili's circuit swap ---
    {
        "code": "l1sw01",
        "type": "SWAP_THING",
        "owner_code": "La1aN1",
        "collections": ["l1l1C2"],
        "headline": "Grove Shield para Arduino Nano v1.1 (Seeed Studio)",
        "thumbnail": "l1sw01",
    },
    {
        "code": "l1sw02",
        "type": "SWAP_THING",
        "owner_code": "L3L3oo",
        "collections": ["l1l1C2"],
        "headline": "Grove - Sensor de polvo láser PM2.5 (HM3301)",
        "thumbnail": "l1sw02",
    },
    {
        "code": "l1sw03",
        "type": "SWAP_THING",
        "owner_code": "l0l0oh",
        "collections": ["l1l1C2"],
        "headline": "MB102 Módulo de alimentación para protoboard (HW-131)",
        "thumbnail": "l1sw03",
    },
    {
        "code": "l1sw04",
        "type": "SWAP_THING",
        "owner_code": "1u1ucs",
        "collections": ["l1l1C2"],
        "headline": "Adaptador de terminales para Arduino Nano",
        "thumbnail": "l1sw04",
    },
    {
        "code": "l1sw05",
        "type": "SWAP_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C2"],
        "headline": "Arduino Nano 33 BLE",
        "thumbnail": "l1sw05",
    },
    {
        "code": "l1sw06",
        "type": "SWAP_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C2"],
        "headline": "CCS811 Sensor de calidad del aire interior",
        "thumbnail": "l1sw06",
    },
    {
        "code": "l1sw07",
        "type": "SWAP_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C2"],
        "headline": "Grove: Temperatura y humedad, agua, sonido, UV, aire",
        "thumbnail": "l1sw07",
    },
    {
        "code": "l1sw08",
        "type": "SWAP_THING",
        "owner_code": "l1l13S",
        "collections": ["l1l1C2"],
        "headline": "DFRobot Sensor UV analógico V2 (Gravity)",
        "thumbnail": "l1sw08",
    },
]

FAQS = [
    {
        "thing_code": "stffa1",
        "questioner_code": "L3L3oo",
        "question": "¿Puedo recogerlo a fin de mes?",
        "answer": "¡Claro que sí, majo!",
    },
    {
        "thing_code": "stffa2",
        "questioner_code": "L3L3oo",
        "question": "¿Puedo recogerlo a fin de mes?",
        "answer": "¡Claro que sí, majo!",
    },
    {
        "thing_code": "stffa3",
        "questioner_code": "L3L3oo",
        "question": "¿Puedo recogerlo a fin de mes?",
        "answer": "¡Claro que sí, majo!",
    },
    {
        "thing_code": "stffa4",
        "questioner_code": "L3L3oo",
        "question": "¿Puedo recogerlo a fin de mes?",
        "answer": "¡Claro que sí, majo!",
    },
    {
        "thing_code": "stffa5",
        "questioner_code": "L3L3oo",
        "question": "¿Puedo recogerlo a fin de mes?",
        "answer": "¡Claro que sí, majo!",
    },
    {
        "thing_code": "cksle1",
        "questioner_code": "La1aN1",
        "question": "¿Cuánto dura en la nevera?",
        "answer": "2-3 días",
    },
    {
        "thing_code": "cksle2",
        "questioner_code": "La1aN1",
        "question": "¿Cuánto dura en la nevera?",
        "answer": "2-3 días",
    },
    {
        "thing_code": "cksle3",
        "questioner_code": "La1aN1",
        "question": "¿Cuánto dura en la nevera?",
        "answer": "2-3 días",
    },
    {
        "thing_code": "cksle4",
        "questioner_code": "La1aN1",
        "question": "¿Cuánto dura en la nevera?",
        "answer": "2-3 días",
    },
    {
        "thing_code": "cksle5",
        "questioner_code": "La1aN1",
        "question": "¿Cuánto dura en la nevera?",
        "answer": "2-3 días",
    },
]
