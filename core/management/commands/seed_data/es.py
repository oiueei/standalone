"""
Spanish demo-data text. Merged onto the structural skeleton in common.py by
`seed_demo.load_seed_data`. Use via `python manage.py seed_demo --lang=es`.

Text lengths respect model max_length (headline=64, description=256,
question=64, answer=256).
"""

USERS = [
    {
        "code": "La1aN1",
        "headline": "¡Viva la segunda mano!",
        "about": "## ¡Hola, soy Lala! 👋\n\nDevota de la **segunda mano** de toda la vida — lo que a uno le sobra, a otro le hace ilusión. Ahora vacío el piso antes de un *sabático*, ¡así que todo tiene que salir!\n\n- ♻️ Reutilizar antes que comprar\n- 🤝 Efectivo, recogida y buen rollo",
    },
    {
        "code": "L3L3oo",
        "headline": "¡Aquí! ¡Ahora! ¡Compartiendo!",
        "about": "## La cocina de Lele 🧁\n\nHago tartas **sanas y naturales** para celebraciones conscientes — veganas, sin gluten o bajas en azúcar, tú eliges. Compartir dulzura es mi lenguaje. *¡Aquí! ¡Ahora! ¡Compartiendo!*",
    },
    {
        "code": "l1l13S",
        "headline": "¡Viva la tienda de préstamos! Lili tiene tus herramientas.",
        "about": "## Pide prestado, no compres 🔧\n\nGuardiana de la **biblioteca de herramientas** y manitas de corazón. Si taladra, limpia al vapor, sube o pita, seguro que tengo una para prestar. También intercambio piezas de *Arduino* — ¡la resistencia es fútil!",
    },
    {
        "code": "l0l0oh",
        "headline": "¡El sombrío Heathcliff llama! ¡Club de lectura de Lolo!",
        "about": "## Mamá planta y ratón de biblioteca 🌿📚\n\nDemasiadas crías de **suculenta** y debilidad por *Cumbres Borrascosas*. Pásate por un esqueje gratis y quédate al club de lectura — el sombrío Heathcliff te espera.",
    },
    {
        "code": "1u1ucs",
        "headline": "Conozco a todos y me apunto a todo – ¡la chispa comunitaria!",
        "about": "## La chispa de la comunidad ✨\n\nConozco a todo el mundo y me apunto a todo. Guardiana del **Estante Fantasma** — foto, compartir y a verlo desaparecer. Si algo pasa, *ya estoy allí*.",
    },
]

COLLECTIONS = [
    {
        "code": "La1aC1",
        "headline": "Lala se va de sabático, ¡todo se vende por diez pavos!",
        "description": "Tres reglas, colega: solo efectivo, te lo llevas tú, fecha límite el 25. ¿Queda algo? ¡Al orfanato del barrio de cabeza!",
    },
    {
        "code": "L3L3C1",
        "headline": "¡Las tartas de Lele!",
        "description": "Hago tartas caseras espectaculares con ingredientes 100% naturales y sanos. Perfectas para celebraciones conscientes como cumples, adaptables a dietas veganas, sin gluten o bajas en azúcar—¡escríbeme para personalizar la tuya!",
    },
    {
        "code": "l0l0C1",
        "headline": "El salón verde de Lolo – ¡llévate una suculenta gratis!",
        "description": "¡Mamá planta con demasiadas crías verdes! Pásate a conocer a mi escuadrón suculento – echeverias, jades, sedums – y te regalo un esqueje. Guía fácil de cuidados incluida. Única regla: ¡ponle nombre a tu nueva amiga verde!",
    },
    {
        "code": "l1l1C1",
        "headline": "Préstamos de Lili – ¡hora de las herramientas!",
        "description": "¿Necesitas taladro, limpiador de vapor, escalera sólida, báscula de equipaje o mega kit de magdalenas? La biblioteca de préstamos de Lili te cubre – gratis para tareas de coliving, se devuelve limpio, por orden de llegada. ¡Sin líos!",
    },
    {
        "code": "l1l1C2",
        "headline": "Swap de circuitos de Lili – ¡la resistencia es fútil!",
        "description": "El coliving de Lili funciona con jumpers y Arduinos a medio hacer. ¿Tienes un Nano cogiendo polvo? ¿Un sensor que no era el tuyo? Ponlo en el tablón, elige lo que te guste, propón un swap. Solo componentes — sin dinero ni cortos.",
    },
    {
        "code": "1u1uC1",
        "headline": "Estantería fantasma de Lulu – ¡acecha con tus trastos!",
        "description": "¿Ves algo cogiendo polvo? Hazle una foto y súbelo a la estantería fantasma de Lulu – sin líos, sin precios, solo un feed de descartes del coliving. ¡Email semanal con las novedades! Pero corre, ¡las cosas desaparecen rápido!",
    },
]

THINGS = [
    {
        "code": "stffa1",
        "headline": "Alfombra nórdica peluda",
        "description": "¡Nido de meditación nórdico! Lana suave como oveja escocesa, vibras hygge con aroma a pachuli. ¡Por solo diez pavos!",
    },
    {
        "code": "stffa2",
        "headline": "Juego de tazas",
        "description": '¡Fiesta del té pagana! 12 tazas con "Keep Calm and Chai On". ¡Perfectas para infusiones hippies!',
    },
    {
        "code": "stffa3",
        "headline": "Batidora retro",
        "description": "¡Batidora McBatidora! Este trasto mágico tritura kale y sueños hippies en batidos cósmicos. ¡Paz y zumo por 10 pavos!",
    },
    {
        "code": "stffa4",
        "headline": "Plancha al vapor",
        "description": "¡Doma arrugas como una bestia! Deja las camisetas tie-dye impecables para festivales. ¡Suaviza tu karma por diez pavos!",
    },
    {
        "code": "stffa5",
        "headline": "Lámpara psicodélica disco",
        "description": "¡Guirnalda rasta! Gira como un viaje de Glastonbury, brilla para infusiones de medianoche. ¡Mola por 10 pavos!",
    },
    {
        "code": "cksle1",
        "headline": "Bollos de pistacho divinos",
        "description": "Tres bollos de brioche rellenos de crema de pistacho, espolvoreados con polvo mágico y frutos secos crujientes. ¡Explosión verde de alegría para eventos elegantes! Pide tu tanda hipnótica ya.",
    },
    {
        "code": "cksle2",
        "headline": "Tarta corazón irresistible",
        "description": 'Belleza redonda con "Love" en chocolate, con rosa roja y perlas brillantes. Cremosa y súper romántica. Para San Valentín, aniversarios o porque sí – ¡caerás por su sabor!',
    },
    {
        "code": "cksle3",
        "headline": "Tarta de frambuesa soñadora",
        "description": "Capas rosas de frambuesa sobre crema blanca, en soporte de cristal. Fresca, chispeante y súper adictiva. Estrella del cumple o el brunch – ¡pide y conquista corazones!",
    },
    {
        "code": "cksle4",
        "headline": "Majestad de macarons",
        "description": "Tarta fina y cremosa coronada con macarons gris-oro, flores rosas y volutas perfectas. Ideal para bodas o meriendas: lujo francés con tu toque. Tu evento, ¡tu sabor soñado!",
    },
    {
        "code": "cksle5",
        "headline": "Tarta de zanahoria acogedora",
        "description": "Cuadrados gruesos de zanahoria con glaseado aterciopelado, en plato rosa con taza Marimekko y té. Un abrazo nórdico en forma de tarta – ¡puro hygge! Ideal para cafés acogedores o meriendas post-ruta.",
    },
    {
        "code": "lltl01",
        "headline": "Kit de taladro robusto",
        "description": "¡Bestia sin cables para desastres DIY! Atraviesa paredes como mantequilla, con juego completo de brocas. ¡Pídelo prestado para tu próximo arreglo casero!",
        "documents": [
            {
                "public_id": "lltl01",
                "filename": "Kit de taladro robusto.pdf",
                "content_type": "application/pdf",
            },
        ],
    },
    {
        "code": "lltl02",
        "headline": "Limpiador de vapor mágico",
        "description": "¡Chisporrotea mugre de hornos y sofás! Varita eco-mágica que deja todo reluciente. ¡Perfecto para un repaso pre-fiesta!",
        "documents": [
            {
                "public_id": "lltl02",
                "filename": "Limpiador de vapor mágico.pdf",
                "content_type": "application/pdf",
            },
        ],
    },
    {
        "code": "lltl03",
        "headline": "Escalera sólida como una roca",
        "description": "¡Campeona de seguridad de dos metros, sin bamboleos! Llega a esas telarañas del desván o estanterías altas. ¡Más firme que el apretón de un cura!",
        "documents": [
            {
                "public_id": "lltl03",
                "filename": "Escalera sólida.pdf",
                "content_type": "application/pdf",
            },
        ],
    },
    {
        "code": "lltl04",
        "headline": "Mega kit de magdalenas",
        "description": "¡Moldes de silicona, bandejas y mangas pasteleras! Hornea bombas de arándanos o maravillas veganas. ¡Kit completo para novatos en la cocina!",
        "documents": [
            {
                "public_id": "lltl04",
                "filename": "Mega kit de magdalenas.pdf",
                "content_type": "application/pdf",
            },
        ],
    },
    {
        "code": "lltl05",
        "headline": "Báscula de equipaje pro",
        "description": "¡Héroe de bolsillo que te salva de multas en el aeropuerto! Pesa maletas hasta 50 kg. Esencial para viajeros de vuelos baratos.",
        "documents": [
            {
                "public_id": "lltl05",
                "filename": "Báscula de equipaje pro.pdf",
                "content_type": "application/pdf",
            },
        ],
    },
    {
        "code": "lltl11",
        "headline": "Fondue olvidada",
        "description": "¡Fundidora de queso del 98 para seis! Con tenedores y piloto incluidos. ¡Pilla antes de que vuelva a desaparecer!",
    },
    {
        "code": "lltl12",
        "headline": "Maletas vintage apiladas",
        "description": "¡Tres bellezas de cuero, rozaduras menores! Perfectas para escapadas de fin de semana o almacenamiento chic. ¡Pídelas antes de que desaparezcan!",
    },
    {
        "code": "lltl13",
        "headline": "Bicicleta estática bestial",
        "description": "¡Spinner silencioso con 8 niveles de resistencia! Cardio sin culpa post-confinamiento. Se va en un suspiro – ¡fuerza al pedal!",
    },
    {
        "code": "lltl14",
        "headline": "Macetas de cerámica",
        "description": "¡Trío de terracota hecho a mano, platito incluido! Revive tus suculentas tristes. Estrella del resumen semanal – ¡corre!",
    },
    {
        "code": "lltl15",
        "headline": "Festín de juegos de mesa",
        "description": "¡Monopoly, Cluedo y Pictionary completos! Clásicos del coliving para noches lluviosas. Por orden de llegada – ¡vuelan!",
    },
    {
        "code": "lltl22",
        "headline": "Zebra, Rosie y Jade – ¡mi trío de terracota busca casa!",
    },
    {
        "code": "lltl23",
        "headline": "Su Majestad la Echeveria – corona rosa, ¡crías gratis!",
    },
    {
        "code": "lltl24",
        "headline": "Atardecer en maceta – ¡cría melocotón-lila para adoptar!",
    },
    {
        "code": "lltl25",
        "headline": "La bolita peluda – hojas aterciopeladas, ¡cría gratis!",
    },
    {
        "code": "lltl26",
        "headline": "De mis manos a las tuyas – ¡elige tu cría!",
    },
    {
        "code": "lltl27",
        "headline": "Mi miniprado – ¡cinco suculentas hermanas bajo un techo!",
    },
    {
        "code": "lltl28",
        "headline": "¡Muchas crías y pocas macetas – ven a rescatar una!",
    },
    {
        "code": "La1aW1",
        "headline": "¿Alguien tiene una escalerilla? ¡La estantería alta gana! 🪜",
    },
    {
        "code": "l1sw01",
        "headline": "Grove Shield para Arduino Nano v1.1 (Seeed Studio)",
    },
    {
        "code": "l1sw02",
        "headline": "Grove - Sensor de polvo láser PM2.5 (HM3301)",
    },
    {
        "code": "l1sw03",
        "headline": "MB102 Módulo de alimentación para protoboard (HW-131)",
    },
    {
        "code": "l1sw04",
        "headline": "Adaptador de terminales para Arduino Nano",
    },
    {
        "code": "l1sw05",
        "headline": "Arduino Nano 33 BLE",
    },
    {
        "code": "l1sw06",
        "headline": "CCS811 Sensor de calidad del aire interior",
    },
    {
        "code": "l1sw07",
        "headline": "Grove: Temperatura y humedad, agua, sonido, UV, aire",
    },
    {
        "code": "l1sw08",
        "headline": "DFRobot Sensor UV analógico V2 (Gravity)",
    },
]

FAQS = [
    {
        "thing_code": "stffa1",
        "question": "¿Puedo recogerlo a fin de mes?",
        "answer": "¡Claro que sí, majo!",
    },
    {
        "thing_code": "stffa2",
        "question": "¿Puedo recogerlo a fin de mes?",
        "answer": "¡Claro que sí, majo!",
    },
    {
        "thing_code": "stffa3",
        "question": "¿Puedo recogerlo a fin de mes?",
        "answer": "¡Claro que sí, majo!",
    },
    {
        "thing_code": "stffa4",
        "question": "¿Puedo recogerlo a fin de mes?",
        "answer": "¡Claro que sí, majo!",
    },
    {
        "thing_code": "stffa5",
        "question": "¿Puedo recogerlo a fin de mes?",
        "answer": "¡Claro que sí, majo!",
    },
    {
        "thing_code": "cksle1",
        "question": "¿Cuánto dura en la nevera?",
        "answer": "2-3 días",
    },
    {
        "thing_code": "cksle2",
        "question": "¿Cuánto dura en la nevera?",
        "answer": "2-3 días",
    },
    {
        "thing_code": "cksle3",
        "question": "¿Cuánto dura en la nevera?",
        "answer": "2-3 días",
    },
    {
        "thing_code": "cksle4",
        "question": "¿Cuánto dura en la nevera?",
        "answer": "2-3 días",
    },
    {
        "thing_code": "cksle5",
        "question": "¿Cuánto dura en la nevera?",
        "answer": "2-3 días",
    },
]

WISH_RESPONSES = [
    {
        "wish_code": "La1aW1",
        "message": "En el trastero junto al aparcabicis hay una escalerilla plegable. ¡Pídele la llave a Lolo!",
    },
]
