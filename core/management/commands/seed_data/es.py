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
        "headline": "Los domingos monto mercadillo y comida en la cooperativa.",
        "about": "## Domingos en la cooperativa 🥘\n\nVivo en una **cooperativa de viviendas**, y aquí casi nada se hace en solitario. Cada domingo montamos en el patio un **mercadillo-fiesta-comida**: cada cual baja lo que le sobra, alguien pone música y siempre acaba habiendo más comida que gente.\n\n- 🧺 Lo que a ti te sobra, a tu vecina le hace falta\n- 🔧 Herramientas compartidas, escalera incluida\n- 🍲 Trae plato, te vas con receta",
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
        "about": "## La chispa de la comunidad ✨\n\nConozco a todo el mundo y me apunto a todo. Si alguien presta, regala o vende algo por el barrio, *ya estoy allí* — y te aviso. Si algo pasa, me entero la primera.",
    },
]

COLLECTIONS = [
    {
        "code": "La1aC1",
        "headline": "DEMO · Lala se va de sabático, ¡todo se vende por diez pavos!",
        "description": "Tres reglas, colega: solo efectivo, te lo llevas tú, fecha límite el 25. ¿Queda algo? ¡Al orfanato del barrio de cabeza!",
    },
    {
        "code": "l0l0C1",
        "headline": "DEMO · El salón verde de Lolo – ¡llévate una suculenta gratis!",
        "description": "Pásate a conocer a mi escuadrón suculento – echeverias, jades, sedums – y te regalo un esqueje. Guía fácil de cuidados incluida. Única regla: ¡ponle nombre a tu nueva amiga verde!",
    },
    {
        "code": "l1l1C1",
        "headline": "DEMO · Préstamos de Lili – ¡hora de compartir las cosas!",
        "description": "¿Necesitas taladro, limpiador de vapor, escalera sólida, báscula de equipaje o mega kit de magdalenas? La biblioteca de préstamos de Lili te cubre – ¡todo a un coste simbólico!",
    },
    {
        "code": "1u1uC1",
        "headline": "DEMO · ¡Herramientas para nosotros!",
        "description": "Subimos aquí las herramientas que tenemos y las ponemos a disposición del resto del grupo. Cuidadlas bien: son nuestras y las necesitamos entre todas y todos.",
    },
    {
        "code": "L3L3C1",
        "headline": "DEMO · El mercadillo de los domingos en el patio",
        "description": "Cada domingo montamos mercadillo, fiesta y comida en el patio. Baja lo que ya no uses y llévate lo que te haga falta: aquí todo se regala. Solo para vecinas y vecinos de la cooperativa.",
    },
    {
        "code": "1u1uRe",
        "headline": "DEMO · El taller de Lulu — reserva un sitio",
        "description": "Reserva un banco o el rincón de reuniones para usarlo aquí, en el taller. Es tuyo por un día (o hasta tres), nada sale de la sala y la reserva se confirma al momento. Abierto de lunes a viernes.",
    },
    {
        "code": "N3t0C1",
        "headline": "DEMO · La Red de Préstamo: cada entidad presta lo suyo",
        "description": "Varias entidades prestan desde una misma estantería. Cada una guarda sus cosas, su punto de recogida y su horario: busca quién presta qué y recógelo donde te indiquen.",
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
        "code": "1u1u01",
        "headline": "Cepillo de carpintero tipo Stanley",
        "description": "Un clásico entre los clásicos: cuerpo metálico robusto, mango bien conservado y esa viruta fina saliendo de la cuchilla que demuestra un ajuste perfecto. Ideal para quien busca precisión sin depender de la electricidad.",
    },
    {
        "code": "1u1u02",
        "headline": "Pie de rey y compás de precisión",
        "description": "Dos clásicos para medir con exactitud: el calibre metálico mantiene sus escalas legibles y su mecanismo se desliza sin trabas, mientras que el compás conserva la punta firme para trazar círculos sin desviarse.",
    },
    {
        "code": "1u1u03",
        "headline": "Cepillo eléctrico en plena acción",
        "description": "Se ve trabajando sobre una tabla de pino, dejando esa viruta fina que delata un filo bien afilado. Las manos protegidas con guantes confirman que quien lo usa sabe lo que hace y cuida su seguridad.",
    },
    {
        "code": "1u1u04",
        "headline": "Set tradicional de tallado en madera",
        "description": "Una brocha, una navaja de tallar, un martillo de mango desgastado por el uso y una garlopa pequeña de madera maciza forman este conjunto con mucho oficio detrás. Cada pieza tiene su función clara.",
    },
    {
        "code": "1u1u05",
        "headline": "Mini amoladora con set de puntas y cepillos",
        "description": "Una herramienta rotativa compacta acompañada de un buen surtido de puntas abrasivas y cepillos metálicos, ideal para pulir, lijar o dar los últimos retoques a piezas pequeñas. Se ve poco desgaste.",
    },
    {
        "code": "1u1u06",
        "headline": "Ingletadora eléctrica para molduras y rodapiés",
        "description": "Esta ingletadora se usa claramente para trabajos de acabado, ahí está la moldura blanca recién cortada como prueba. El disco luce en buen estado y la base se ve estable para cortes limpios y sin vibraciones.",
    },
    {
        "code": "1u1u07",
        "headline": "Formones y mazo de madera para carpintería",
        "description": "Dos formones con mango de madera y filo bien cuidado, junto a un mazo macizo perfecto para golpes precisos sin dañar el mango. Al fondo se asoma un pequeño cepillo de madera que completa el set.",
    },
    {
        "code": "1u1u08",
        "headline": "Equipo de sopladores de vidrio en plena faena",
        "description": "Aquí vemos el oficio en acción: la vara de soplado sostiene una pieza de vidrio incandescente recién sacada del horno, mientras el artesano la trabaja con calma y control. El delantal de cuero dice el resto.",
    },
    {
        "code": "1u1u09",
        "headline": "Kit de electricista: crimpadora, alicates y grapadora",
        "description": "Todo lo necesario para un cableado limpio: crimpadoras de colores, alicates de corte, un comprobador de tensión y hasta una grapadora manual para fijar cables. Las gafas de protección van incluidas.",
    },
    {
        "code": "1u1u10",
        "headline": "Yunque de fragua con martillo de herrero",
        "description": "Un conjunto clásico de forja: el yunque conserva su forma y solidez a pesar del paso de los años, y el mazo de mango de madera se ve fuerte y bien equilibrado. Se nota el uso real de un taller.",
    },
    {
        "code": "1u1u11",
        "headline": "Set de joyería para trabajar metales finos",
        "description": "Un mini yunque de joyero acompañado de alicates, soplete y una pieza en proceso muestran el detalle milimétrico que exige este oficio. Todo el instrumental se ve cuidado y listo para seguir.",
    },
    {
        "code": "1u1u12",
        "headline": "Maletín de carraca y vasos completo",
        "description": "Un set de llaves de vaso y carraca con bastante recorrido, se nota por el color desgastado del maletín, pero todas las piezas están en su sitio y listas para apretar cualquier tornillo.",
    },
    {
        "code": "1u1u13",
        "headline": "Ingletadora con serrucho de apoyo",
        "description": "Esta ingletadora ha visto bastante trabajo, el serrín acumulado lo confirma, pero el disco y la estructura se mantienen firmes para seguir haciendo cortes en ángulo con precisión.",
    },
    {
        "code": "1u1u14",
        "headline": "Kit de soldadura con careta y electrodos",
        "description": "Careta protectora, guante resistente al calor y varillas de electrodo listas para chispear: todo lo esencial para soldar sin sustos. El equipo se ve completo y en condiciones de seguir dando buenas soldaduras.",
    },
    {
        "code": "1u1u15",
        "headline": "Trío de serruchos de mano multiuso",
        "description": "Tres serruchos con mangos de colores y dientes bien definidos, cada uno pensado para un tipo de corte distinto. Se conservan afilados y sin óxido, listos para entrar en cualquier caja de herramientas.",
    },
    {
        "code": "1u1u16",
        "headline": "Ingletadora amarilla con molduras cortadas",
        "description": "Con varias piezas de madera ya cortadas a su lado, esta ingletadora demuestra que ha estado en pleno rendimiento. El amarillo desgastado y algunas marcas de uso no le quitan mérito: es de fiar.",
    },
    {
        "code": "1u1u17",
        "headline": "Martillo perforador con brocas y puntas SDS",
        "description": "Un martillo perforador robusto acompañado de brocas de distintos grosores, un cincel plano y hasta los lápices de carpintero de toda la vida. Las gafas de protección al lado son un buen recordatorio.",
    },
    {
        "code": "1u1u18",
        "headline": "Taladro atornillador a batería",
        "description": "Un taladro compacto y ligero, con la batería incluida y lista para usar. Se ve algo de polvo de trabajo reciente en la superficie, señal de que ha estado en plena faena y no cogiendo polvo en un cajón.",
    },
    {
        "code": "1u1u19",
        "headline": "Kit básico: martillo, cinta métrica y alicates",
        "description": "El combo esencial para cualquier reparación en casa: un martillo de mango azul, una cinta métrica naranja bien visible, unos alicates multiuso y clavos de sobra. Sencillo, práctico y sin complicaciones.",
    },
    {
        "code": "1u1u20",
        "headline": "Escalera profesional de aluminio",
        "description": "Escalera de trabajo de aluminio en excelente estado, resistente y versátil. Estructura robusta, peldaños seguros y estables.",
    },
    {
        "code": "1u1u21",
        "headline": "Conjunto de brochas y pinceles",
        "description": "Conjunto completo de 6 brochas y pinceles de pintura con mangos de madera natural (amarillos y blancos). Variedad de tamaños y tipos para trabajos de precisión y cobertura.",
    },
    {
        "code": "L3L301",
        "headline": "Batidora amasadora roja",
        "description": "Batidora amasadora de color rojo, con un diseño moderno y elegante. Perfecta para preparar todo tipo de masas y postres. Bol de acero inoxidable.",
    },
    {
        "code": "L3L302",
        "headline": "Bicicleta de aprendizaje para niños",
        "description": "Bicicleta de aprendizaje para niños, ideal para iniciarse en el mundo de las dos ruedas.",
    },
    {
        "code": "L3L303",
        "headline": "Altavoz amplificado Fenton FT212LED",
        "description": "Altavoz amplificado Fenton FT212LED con una potencia de 1400 W. Cuenta con iluminación LED integrada que cambia de color. Bluetooth, USB y dos micros inalámbricos. En perfecto estado.",
    },
    {
        "code": "L3L304",
        "headline": "Raspberry Pi 5 con Recalbox lista para usar",
        "description": "Raspberry Pi 5 de 2 GB completa, con ventilador integrado, cable HDMI, cable de alimentación y microSD de 64 GB con Recalbox listo para usar. Totalmente nueva.",
    },
    {
        "code": "L3L305",
        "headline": "Lote de siete puzzles de 1000 piezas",
        "description": "Lote de siete puzzles de la marca That's Life, cada uno con 1000 piezas. Son ideales para pasar tiempo de ocio. Todos completos y en perfecto estado.",
    },
    {
        "code": "L3L306",
        "headline": "Televisor JVC AV14BM8EPS",
        "description": "Televisor JVC modelo AV14BM8EPS en color plateado. Funciona como monitor a través de la entrada frontal. Sin mando.",
    },
    {
        "code": "L3L307",
        "headline": "Máquina de moler café manual",
        "description": "Máquina de moler café manual, como decoración o para restaurar. Funciona perfectamente.",
    },
    {
        "code": "L3L308",
        "headline": "Paellera de acero pulido de 42 cm",
        "description": "Sartén para hacer paella muy grande, de acero pulido. 42 cm de diámetro. Para 10 personas como mínimo.",
    },
    {
        "code": "L3L309",
        "headline": "Cafetera Nespresso Krups negra",
        "description": "Cafetera Nespresso Krups en color negro. Diseñada para preparar deliciosos cafés.",
    },
    {
        "code": "L3L310",
        "headline": "Microondas Taurus con grill",
        "description": "Microondas Taurus en color blanco con función grill. Ideal para calentar y cocinar. Se encuentra en muy buen estado, limpio y listo para usar.",
    },
    {
        "code": "L3L311",
        "headline": "Nevera portátil para playa y picnic",
        "description": "Nevera portátil con tapa verde y asa gris, ideal para llevar tus bebidas y alimentos frescos a la playa o de picnic. Su diseño es práctico y fácil de transportar.",
    },
    {
        "code": "1u1uRa",
        "headline": "El banco de trabajo grande",
        "description": "El banco de roble macizo, con el tornillo de banco y la buena luz. Resérvalo para un día de trabajo de verdad — pequeña cuota de mantenimiento para hojas y cola. Se queda en el taller.",
    },
    {
        "code": "1u1uRb",
        "headline": "El rincón de reuniones",
        "description": "Mesa, seis sillas y una pantalla para una reunión pequeña o una clase. Reservarlo es gratis, hasta tres días. Déjalo como lo encontraste, por favor.",
    },
    {
        "code": "N3t001",
        "headline": "Taladro inalámbrico con juego de brocas",
        "description": "Un taladro ligero con su cargador y un estuche de brocas para madera, pared y metal. Útil para estantes y barras de cortina.",
    },
    {
        "code": "N3t002",
        "headline": "Vaporeta para suelos y cristales",
        "description": "Vaporeta con las tres boquillas: suelos, cristales y rincones. Se llena con agua del grifo y se deja calentar cinco minutos.",
    },
    {
        "code": "N3t003",
        "headline": "Cortasetos de gasolina",
        "description": "Un cortasetos de 60 cm, muy usado y todavía afilado. Se presta con gafas y guantes; el primer depósito de combustible corre de nuestra cuenta.",
    },
    {
        "code": "N3t004",
        "headline": "Olla a presión de 8 litros",
        "description": "Una olla a presión de 8 litros con junta de repuesto. Va bien para legumbres, guisos y la comida grande de familia.",
    },
    {
        "code": "N3t005",
        "headline": "Manguera de jardín con pistolas",
        "description": "Veinte metros de manguera con pistola de riego y tres conectores. Por favor, vacíala antes de devolverla.",
    },
    {
        "code": "N3t006",
        "headline": "Batidora de pie con gancho de amasar",
        "description": "Una batidora de pie con varillas, pala y gancho de amasar. Pan, bizcochos y merengues sin dolor de brazos.",
    },
    {
        "code": "N3t007",
        "headline": "Escalera plegable de 3 metros",
        "description": "Una escalera de aluminio de tres metros que se pliega sobre sí misma. Tan ligera que la puede llevar una sola persona.",
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

# The pickup points of the demo network: the hours (plain text, follows --lang) and the
# conditions each point writes (localized like every owner text).
NETWORK_POINTS = [
    {
        "code": "N3tP01",
        "about": "Somos una pequeña cooperativa de vecinas y vecinos. Guardamos las herramientas y los juegos de mesa de la calle y los prestamos los martes y los jueves.\n\nDevuelve lo que te lleves **limpio** y avísanos si algo se rompe: pasa.",
        "hours_note": "Martes y jueves de 18 a 20 h",
        "deposit_policy": "",
        "request_info": "",
        "email_note": "",
    },
    {
        "code": "N3tP02",
        "about": "La asociación del Passatge dels Gats Sords, fundada por gente que nunca se puso de acuerdo en un nombre.\n\nPrestamos desde el sótano, los sábados por la mañana, y siempre hay tiempo para charlar con un café.",
        "hours_note": "Sábados de 10 a 13 h",
        "deposit_policy": "20 € de fianza por cosa, que se entregan al recoger y se devuelven en cuanto vuelve limpia.",
        "request_info": "Trae el carné de socio. Solo abrimos los sábados; si no puedes venir, pídele a un vecino que la recoja por ti.",
        "email_note": "Llama dos veces al timbre: estamos en el sótano, bajando los escalones de la izquierda.",
    },
    {
        "code": "N3tP03",
        "about": "Presto desde mi rincón de la plaza, por las tardes entre semana. Escríbeme y quedamos.",
        "hours_note": "Tardes entre semana, por acuerdo",
        "deposit_policy": "",
        "request_info": "",
        "email_note": "",
    },
    {
        "code": "1u1uP1",
        "about": "Un grupo de vecinas y vecinos del rellano. Somos quienes mantenemos esta biblioteca en orden y respondemos a tus preguntas.",
        "hours_note": "",
        "deposit_policy": "",
        "request_info": "",
        "email_note": "",
    },
]
