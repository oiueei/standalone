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
        "headline": "¡La resistencia es fútil! Lele y su swap de circuitos.",
        "about": "## El taller de Lele ⚡\n\nManitas de la **electrónica** y cazadora de componentes. Mi coliving funciona con jumpers y Arduinos a medio hacer. ¿Te sobra un Nano o un sensor perdido? Ponlo en el tablón y propón un swap. *¡La resistencia es fútil!*",
    },
    {
        "code": "l1l13S",
        "headline": "¡Viva la tienda de préstamos! Lili lo presta casi todo.",
        "about": "## Pide prestado, no compres 🤝\n\nGuardiana de la **biblioteca del barrio**: de taladros y vaporetas a cosas de cocina, jardín, deporte y crianza. Si solo lo vas a usar de uvas a peras, mejor pídemelo. ¡Reutilizar antes que comprar!",
    },
    {
        "code": "l0l0oh",
        "headline": "Esquejes gratis en el salón verde de Lolo.",
        "about": "## El salón verde 🌿\n\nDemasiadas crías de **suculenta** en el alféizar — echeverias, jades y sedums buscando hogar. Pásate por un esqueje gratis, con guía de cuidados incluida. Única regla: ¡ponle nombre a tu nueva amiga verde!",
    },
    {
        "code": "1u1ucs",
        "headline": "Conozco a todos y me apunto a todo – ¡la chispa comunitaria!",
        "about": "## La chispa de la comunidad ✨\n\nConozco a todo el mundo y me apunto a todo. Guardián del **Estante Fantasma** — foto, compartir y a verlo desaparecer. Si algo pasa, *ya estoy allí*.",
    },
]

COLLECTIONS = [
    {
        "code": "La1aC1",
        "headline": "Lala se va de sabático, ¡todo se vende por diez pavos!",
        "description": "Tres reglas, colega: solo efectivo, te lo llevas tú, fecha límite el 25. ¿Queda algo? ¡Al orfanato del barrio de cabeza!",
    },
    {
        "code": "l0l0C1",
        "headline": "El salón verde de Lolo – ¡llévate una suculenta gratis!",
        "description": "Pásate a conocer a mi escuadrón suculento – echeverias, jades, sedums – y te regalo un esqueje. Guía fácil de cuidados incluida. Única regla: ¡ponle nombre a tu nueva amiga verde!",
    },
    {
        "code": "l1l1C1",
        "headline": "Préstamos de Lili – ¡hora de compartir las cosas!",
        "description": "¿Necesitas taladro, limpiador de vapor, escalera sólida, báscula de equipaje o mega kit de magdalenas? La biblioteca de préstamos de Lili te cubre – ¡todo a un coste simbólico!",
    },
    {
        "code": "L3L3C1",
        "headline": "Swap de circuitos de Lele – ¡la resistencia es fútil!",
        "description": "El coliving de Lele funciona con jumpers y Arduinos a medio hacer. ¿Tienes un Nano cogiendo polvo? ¿Un sensor que no era el tuyo? Ponlo en el tablón, elige lo que te guste, propón un swap. Solo componentes — sin dinero ni cortos.",
    },
    {
        "code": "1u1uC1",
        "headline": "Estantería fantasma de Lulu – ¡acecha con tus trastos!",
        "description": "¿Ves algo cogiendo polvo? Hazle una foto y súbelo a la estantería fantasma de Lulu – sin líos, sin precios, solo un feed de descartes del coliving. ¡Email semanal con las novedades! Pero corre, ¡las cosas desaparecen rápido!",
    },
]

THINGS = [
    {
        "code": "La1a01",
        "headline": "Alfombra nórdica peluda",
        "description": "¡Nido de meditación nórdico! Lana suave como oveja escocesa, vibras hygge con aroma a pachuli. ¡Por solo diez pavos!",
    },
    {
        "code": "La1a02",
        "headline": "Juego de tazas",
        "description": '¡Fiesta del té pagana! 12 tazas con "Keep Calm and Chai On". ¡Perfectas para infusiones hippies!',
    },
    {
        "code": "La1a03",
        "headline": "Batidora retro",
        "description": "¡Batidora McBatidora! Este trasto mágico tritura kale y sueños hippies en batidos cósmicos. ¡Paz y zumo por 10 pavos!",
    },
    {
        "code": "La1a04",
        "headline": "Plancha al vapor",
        "description": "¡Doma arrugas como una bestia! Deja las camisetas tie-dye impecables para festivales. ¡Suaviza tu karma por diez pavos!",
    },
    {
        "code": "La1a05",
        "headline": "Lámpara psicodélica disco",
        "description": "¡Guirnalda rasta! Gira como un viaje de Glastonbury, brilla para infusiones de medianoche. ¡Mola por 10 pavos!",
    },
    {
        "code": "l1l101",
        "headline": "Tren de cartón para jugar",
        "description": "Tren gigante de cartón hecho a mano. Ideal para fiestas juegos imaginativos o photocall infantil. Se monta y desmonta fácil. Una pieza muy original para los peques.",
    },
    {
        "code": "l1l102",
        "headline": "Circuito de tren de madera",
        "description": "Circuito infantil de tren musical con piezas encajables y pasabolas. Madera resistente y colorida. Estimula la motricidad y el juego. Perfecto para primeras edades.",
    },
    {
        "code": "l1l103",
        "headline": "Tres en raya artesanal",
        "description": "Juego de tres en raya hecho con chapas y cartón. Ligero divertido y fácil de transportar. Para jugar en casa o de viaje. Diversión sencilla para todas las edades.",
    },
    {
        "code": "l1l104",
        "headline": "Casita infantil con mesa",
        "description": "Casita de juego de plástico con puerta ventanas mesa y bancos. Resistente para interior o jardín. Horas de juego simbólico para los peques. Fácil de limpiar.",
    },
    {
        "code": "l1l105",
        "headline": "Laberinto de canicas",
        "description": "Laberinto de canicas hecho a mano con cartón y palitos de colores. Pon a prueba el pulso y la paciencia. Un clásico que engancha a grandes y pequeños.",
    },
    {
        "code": "l1l106",
        "headline": "Jardinera vertical de pared",
        "description": "Set de jardineras verticales apilables para colgar en la pared. Perfectas para hierbas aromáticas o plantas pequeñas en balcones y terrazas. Aprovecha el espacio.",
    },
    {
        "code": "l1l107",
        "headline": "Impresora láser HP LaserJet",
        "description": "Impresora láser HP LaserJet en blanco y negro. Fiable para documentos puntuales o impresiones rápidas. Lista para usar. Ideal si solo imprimes de vez en cuando.",
    },
    {
        "code": "l1l108",
        "headline": "Consola Nintendo Game Boy",
        "description": "Consola portátil Nintendo Game Boy clásica. Pura nostalgia para jugar a los títulos de siempre. Funciona con pilas. Una joya retro para echar unas partidas.",
    },
    {
        "code": "l1l109",
        "headline": "Fregona giratoria con cubo",
        "description": "Fregona giratoria con cubo centrifugador. Escurre sin esfuerzo y deja el suelo casi seco. Cómoda y eficaz para la limpieza del día a día. Mango extensible.",
    },
    {
        "code": "l1l110",
        "headline": "Limpiador de vapor de mano",
        "description": "Limpiador de vapor portátil con accesorios. Desinfecta sin productos químicos en baños cocinas y juntas. Práctico para limpiezas a fondo puntuales. Fácil de manejar.",
    },
    {
        "code": "l1l111",
        "headline": "Aspirador seco y húmedo",
        "description": "Aspirador de sólidos y líquidos con ruedas y accesorios. Potente para garajes coches reformas o derrames. Depósito amplio de acero. Para lo que una aspiradora normal no puede.",
    },
    {
        "code": "l1l112",
        "headline": "Taladro atornillador Ryobi",
        "description": "Taladro atornillador a batería Ryobi. Para montar muebles colgar cuadros o pequeñas reformas en casa. Ligero y manejable. Incluye batería. Perfecto para bricolaje básico.",
    },
    {
        "code": "l1l113",
        "headline": "Kit de herramientas básicas",
        "description": "Maletín de herramientas para bricolaje: martillo destornilladores alicates llave nivel y cinta métrica. Lo esencial para apaños y montajes en casa. Bien organizado.",
    },
    {
        "code": "l1l114",
        "headline": "Rueda abdominal",
        "description": "Rueda para ejercitar abdominales y core en casa. Compacta y resistente con agarres acolchados. Ideal para entrenar fuerza sin ir al gimnasio. Fácil de guardar.",
    },
    {
        "code": "l1l115",
        "headline": "Comba para saltar",
        "description": "Cuerda de saltar con mangos ergonómicos. Perfecta para cardio calentamiento o entrenamiento en cualquier sitio. Ligera y ajustable. Pon el corazón a tope.",
    },
    {
        "code": "l1l116",
        "headline": "Mancuernas 1 kg (par)",
        "description": "Par de mancuernas de 1 kg recubiertas de neopreno. Agarre suave y antideslizante. Ideales para tonificar pilates o rehabilitación. Cómodas para empezar.",
    },
    {
        "code": "l1l117",
        "headline": "Esterilla de yoga de corcho",
        "description": "Esterilla de yoga de corcho natural antideslizante con líneas de alineación. Incluye funda de transporte. Buen agarre incluso con sudor. Para yoga pilates o estiramientos.",
    },
    {
        "code": "l1l118",
        "headline": "Set de mancuernas ajustables",
        "description": "Set de mancuernas y kettlebell ajustables con discos y barras. Adapta el peso a cada ejercicio. Todo en uno para entrenar fuerza en casa. Ahorra espacio.",
    },
    {
        "code": "l1l119",
        "headline": "Set utensilios cocina negro",
        "description": "Set de 4 utensilios de nylon: espátula cazo batidor y cuchara ranurada. Aptos para todo tipo de sartenes y ollas.",
    },
    {
        "code": "l1l120",
        "headline": "Set utensilios cocina acero",
        "description": "Set de 6 utensilios de acero inoxidable: espumadera aplastador batidor cazo espátula y tenedor. Completo y resistente.",
    },
    {
        "code": "l1l121",
        "headline": "Cuchillo Santoku Wüsthof",
        "description": "Cuchillo santoku profesional Wüsthof Classic 17cm. Corte preciso para verduras carne y pescado. En muy buen estado.",
    },
    {
        "code": "l1l122",
        "headline": "Set ollas antiadherentes",
        "description": "Set de dos ollas antiadherentes con asas ergonómicas. Perfectas para cocinar sin que se pegue nada. Tallas grande y mediana.",
    },
    {
        "code": "l1l123",
        "headline": "Cazo de acero inoxidable",
        "description": "Cazo de acero inoxidable de calidad profesional. Ideal para salsas y cremas. Fácil de limpiar y muy duradero.",
    },
    {
        "code": "1u1u01",
        "headline": "Fondue olvidada",
        "description": "¡Fundidora de queso del 98 para seis! Con tenedores y piloto incluidos. ¡Pilla antes de que vuelva a desaparecer!",
    },
    {
        "code": "1u1u02",
        "headline": "Maletas vintage apiladas",
        "description": "¡Tres bellezas de cuero, rozaduras menores! Perfectas para escapadas de fin de semana o almacenamiento chic. ¡Pídelas antes de que desaparezcan!",
    },
    {
        "code": "1u1u03",
        "headline": "Bicicleta estática bestial",
        "description": "¡Spinner silencioso con 8 niveles de resistencia! Cardio sin culpa post-confinamiento. Se va en un suspiro – ¡fuerza al pedal!",
    },
    {
        "code": "1u1u04",
        "headline": "Macetas de cerámica",
        "description": "¡Trío de terracota hecho a mano, platito incluido! Revive tus suculentas tristes. Estrella del resumen semanal – ¡corre!",
    },
    {
        "code": "1u1u05",
        "headline": "Festín de juegos de mesa",
        "description": "¡Monopoly, Cluedo y Pictionary completos! Clásicos del coliving para noches lluviosas. Por orden de llegada – ¡vuelan!",
    },
    {
        "code": "l0l001",
        "headline": "Zebra, Rosie y Jade – ¡mi trío de terracota busca casa!",
    },
    {
        "code": "l0l002",
        "headline": "Su Majestad la Echeveria – corona rosa, ¡crías gratis!",
    },
    {
        "code": "l0l003",
        "headline": "Atardecer en maceta – ¡cría melocotón-lila para adoptar!",
    },
    {
        "code": "l0l004",
        "headline": "La bolita peluda – hojas aterciopeladas, ¡cría gratis!",
    },
    {
        "code": "l0l005",
        "headline": "De mis manos a las tuyas – ¡elige tu cría!",
    },
    {
        "code": "l0l006",
        "headline": "Mi miniprado – ¡cinco suculentas hermanas bajo un techo!",
    },
    {
        "code": "l0l007",
        "headline": "¡Muchas crías y pocas macetas – ven a rescatar una!",
    },
    {
        "code": "La1a00",
        "headline": "¿Alguien tiene una escalerilla? ¡La estantería alta gana! 🪜",
    },
    {
        "code": "L3L301",
        "headline": "Grove Shield para Arduino Nano v1.1 (Seeed Studio)",
    },
    {
        "code": "L3L302",
        "headline": "Grove - Sensor de polvo láser PM2.5 (HM3301)",
    },
    {
        "code": "L3L303",
        "headline": "MB102 Módulo de alimentación para protoboard (HW-131)",
    },
    {
        "code": "L3L304",
        "headline": "Adaptador de terminales para Arduino Nano",
    },
    {
        "code": "L3L305",
        "headline": "Arduino Nano 33 BLE",
    },
    {
        "code": "L3L306",
        "headline": "CCS811 Sensor de calidad del aire interior",
    },
    {
        "code": "L3L307",
        "headline": "Grove: Temperatura y humedad, agua, sonido, UV, aire",
    },
    {
        "code": "L3L308",
        "headline": "DFRobot Sensor UV analógico V2 (Gravity)",
    },
]

FAQS = [
    {
        "thing_code": "La1a01",
        "question": "¿Puedo recogerlo a fin de mes?",
        "answer": "¡Claro que sí, majo!",
    },
    {
        "thing_code": "La1a02",
        "question": "¿Puedo recogerlo a fin de mes?",
        "answer": "¡Claro que sí, majo!",
    },
    {
        "thing_code": "La1a03",
        "question": "¿Puedo recogerlo a fin de mes?",
        "answer": "¡Claro que sí, majo!",
    },
    {
        "thing_code": "La1a04",
        "question": "¿Puedo recogerlo a fin de mes?",
        "answer": "¡Claro que sí, majo!",
    },
    {
        "thing_code": "La1a05",
        "question": "¿Puedo recogerlo a fin de mes?",
        "answer": "¡Claro que sí, majo!",
    },
]

WISH_RESPONSES = [
    {
        "wish_code": "La1a00",
        "message": "En el trastero junto al aparcabicis hay una escalerilla plegable. ¡Pídele la llave a Lolo!",
    },
]
