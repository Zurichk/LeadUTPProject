"""Diccionario es ⇄ ca de vocabulario infantil.

Motivo de existir: los modelos de lenguaje pequeños disponibles en una
suscripción educativa no son fiables para traducir palabra por palabra (se
han medido errores como "menuda → música"). Enseñar una traducción incorrecta
a una niña que está aprendiendo a leer es peor que no traducir, así que la
aplicación traduce con este diccionario y solo recurre al modelo para las
palabras que no aparecen aquí.

Cada entrada es un par ``(castellano, valenciano)``; el servicio construye las
dos direcciones automáticamente. Los términos son de uso cotidiano en las
fichas de lectura de 5 años.
"""

from __future__ import annotations

import unicodedata
from types import MappingProxyType

#: Pares (castellano, valenciano) de vocabulario infantil frecuente.
WORD_PAIRS: tuple[tuple[str, str], ...] = (
    # --- familia -----------------------------------------------------------
    ("mamá", "mama"),
    ("papá", "papa"),
    ("abuela", "àvia"),
    ("abuelo", "avi"),
    ("hermana", "germana"),
    ("hermano", "germà"),
    ("hija", "filla"),
    ("hijo", "fill"),
    ("familia", "família"),
    ("bebé", "nadó"),
    # --- animales ----------------------------------------------------------
    ("perro", "gos"),
    ("gato", "gat"),
    ("pájaro", "ocell"),
    ("mariposa", "papallona"),
    ("conejo", "conill"),
    ("oso", "os"),
    ("lobo", "llop"),
    ("zorro", "guineu"),
    ("ratón", "ratolí"),
    ("vaca", "vaca"),
    ("cerdo", "porc"),
    ("oveja", "ovella"),
    ("caballo", "caball"),
    ("burro", "burro"),
    ("cordero", "anyell"),
    ("cachorro", "criadet"),
    ("cría", "cria"),
    ("serpiente", "serp"),
    ("tortuga", "tortuga"),
    ("pez", "peix"),
    ("ballena", "balena"),
    ("elefante", "elefant"),
    ("león", "lleó"),
    ("tigre", "tigre"),
    ("mono", "mico"),
    ("camello", "camell"),
    ("rana", "granota"),
    ("abeja", "abella"),
    ("hormiga", "formiga"),
    ("araña", "arany"),
    ("gaviota", "gaviota"),
    ("pingüino", "pingüí"),
    ("delfín", "delfí"),
    # --- casa --------------------------------------------------------------
    ("casa", "casa"),
    ("puerta", "porta"),
    ("ventana", "finestra"),
    ("cama", "llit"),
    ("mesa", "taula"),
    ("silla", "cadira"),
    ("sofá", "sofà"),
    ("cocina", "cuina"),
    ("baño", "bany"),
    ("escalera", "escala"),
    ("llave", "clau"),
    ("espejo", "mirall"),
    ("lámpara", "llàmpada"),
    ("cobre", "gorra"),
    ("sábana", "llençal"),
    ("almohada", "coixí"),
    ("suelo", "terra"),
    ("pared", "paret"),
    ("techo", "teulada"),
    ("cocina", "cuina"),
    ("horno", "forn"),
    ("nevera", "frigor"),
    # --- comida ------------------------------------------------------------
    ("leche", "llet"),
    ("pan", "pa"),
    ("agua", "aigua"),
    ("manzana", "poma"),
    ("pera", "pera"),
    ("plátano", "plàtan"),
    ("naranja", "taronja"),
    ("uva", "raïm"),
    ("fresa", "maduixa"),
    ("cereza", "cirera"),
    ("limón", "llimona"),
    ("tomate", "tomàquet"),
    ("papa", "patata"),
    ("zanahoria", "pastanaga"),
    ("calabacín", "carbassó"),
    ("huevo", "ou"),
    ("queso", "formatge"),
    ("miel", "mel"),
    ("galleta", "galeta"),
    ("bizcocho", "pastís"),
    ("chocolate", "xocolata"),
    ("arroz", "arròs"),
    ("pasta", "pasta"),
    ("sopa", "sopa"),
    ("carne", "carn"),
    ("pescado", "peix"),
    ("sal", "sal"),
    ("azúcar", "sucre"),
    ("harina", "farina"),
    ("aceite", "oli"),
    ("fruta", "fruita"),
    ("verdura", "verdura"),
    ("bebida", "beguda"),
    ("desayuno", "esmorzar"),
    ("cena", "sopar"),
    # --- colores -----------------------------------------------------------
    ("rojo", "roig"),
    ("azul", "blau"),
    ("verde", "verd"),
    ("amarillo", "groc"),
    ("negro", "negre"),
    ("blanco", "blanc"),
    ("gris", "gris"),
    ("rosa", "rosa"),
    ("marrón", "marró"),
    ("morado", "morat"),
    ("naranja", "taronja"),
    # --- números -----------------------------------------------------------
    ("uno", "un"),
    ("una", "una"),
    ("dos", "dos"),
    ("tres", "tres"),
    ("cuatro", "quatre"),
    ("cinco", "cinc"),
    ("seis", "sis"),
    ("siete", "set"),
    ("ocho", "vuit"),
    ("nueve", "nou"),
    ("diez", "deu"),
    ("muchos", "molts"),
    ("pocos", "pocs"),
    # --- naturaleza --------------------------------------------------------
    ("sol", "sol"),
    ("luna", "lluna"),
    ("estrella", "estrella"),
    ("cielo", "cel"),
    ("nube", "núvol"),
    ("lluvia", "pluja"),
    ("viento", "vent"),
    ("nieve", "neu"),
    ("día", "dia"),
    ("noche", "nit"),
    ("mañana", "demà"),
    ("tarde", "tarda"),
    ("árbol", "arbre"),
    ("flor", "flor"),
    ("hoja", "fulla"),
    ("hierba", "herba"),
    ("bosque", "bosc"),
    ("montaña", "muntanya"),
    ("río", "riu"),
    ("mar", "mar"),
    ("isla", "illa"),
    ("piedra", "pedra"),
    ("agua", "aigua"),
    ("fuego", "foc"),
    ("campo", "camp"),
    ("playa", "platja"),
    # --- escuela ------------------------------------------------------------
    ("escuela", "escola"),
    ("colegio", "col·legi"),
    ("maestro", "mestre"),
    ("maestra", "mestra"),
    ("aula", "aula"),
    ("pizarra", "pissarra"),
    ("cuaderno", "quadern"),
    ("lápiz", "llapis"),
    ("goma", "goma"),
    ("bolígrafo", "boligraf"),
    ("tijeras", "tisores"),
    ("mochila", "motxilla"),
    ("mesa", "taula"),
    ("deberes", "deures"),
    ("leer", "llegir"),
    ("escribir", "escriure"),
    ("contar", "comptar"),
    ("aprender", "aprendre"),
    ("jugar", "jugar"),
    ("dibujar", "dibuixar"),
    ("cantar", "cantar"),
    ("bailar", "ballar"),
    # --- ropa --------------------------------------------------------------
    ("ropa", "roba"),
    ("camisa", "camisa"),
    ("pantalón", "pantalons"),
    ("falda", "faldilla"),
    ("vestido", "vestit"),
    ("zapato", "sabata"),
    ("calcetín", "mitj"),
    ("sombrero", "barret"),
    ("guante", "guant"),
    ("bufanda", "bufanda"),
    ("abrigo", "abric"),
    # --- cuerpo ------------------------------------------------------------
    ("cabeza", "cap"),
    ("mano", "mà"),
    ("brazo", "braç"),
    ("pierna", "cama"),
    ("pie", "peu"),
    ("ojo", "ull"),
    ("boca", "boca"),
    ("nariz", "nas"),
    ("oreja", "orella"),
    ("bello", "cabell"),
    ("diente", "dent"),
    ("corazón", "cor"),
    ("cuerpo", "cos"),
    # --- animales de granja /ocabulario ------------------------------------
    ("granja", "granja"),
    ("pollito", "pollet"),
    ("gallina", "gallina"),
    ("caballo", "caball"),
    ("jirafa", "girafa"),
    ("elefante", "elefant"),
    ("oso", "os"),
    # --- verbos comunes ----------------------------------------------------
    ("ser", "ser"),
    ("estar", "estar"),
    ("tener", "tenir"),
    ("hacer", "fer"),
    ("ir", "anar"),
    ("venir", "vindre"),
    ("ver", "veure"),
    ("mirar", "mirar"),
    ("oír", "escoltar"),
    ("decir", "dir"),
    ("hablar", "parlar"),
    ("comer", "menjar"),
    ("beber", "beure"),
    ("dormir", "dormir"),
    ("correr", "correr"),
    ("saltar", "saltar"),
    ("abrir", "obrir"),
    ("cerrar", "tancar"),
    ("dar", "donar"),
    ("querer", "vols"),
    ("poder", "poder"),
    ("saber", "saber"),
    ("ayudar", "ajudar"),
    ("amar", "estimar"),
    ("volar", "volar"),
    ("nadar", "nadar"),
    ("comprar", "comprar"),
    ("buscar", "buscar"),
    ("encontrar", "trobar"),
    ("perder", "perdre"),
    ("ganar", "guanyar"),
    ("empezar", "començar"),
    ("terminar", "acabar"),
    ("vive", "viu"),
    ("ama", "estima"),
    ("salta", "salta"),
    ("habla", "parla"),
    ("come", "menja"),
    ("bebe", "beu"),
    ("corre", "corre"),
    ("lee", "llegeix"),
    # --- adjetivos ---------------------------------------------------------
    ("grande", "gran"),
    ("pequeño", "menut"),
    ("alto", "alt"),
    ("bajo", "baix"),
    ("largo", "llarg"),
    ("corto", "curt"),
    ("nuevo", "nou"),
    ("viejo", "vell"),
    ("bonito", "bonic"),
    ("feo", "lleig"),
    ("limpio", "net"),
    ("sucio", "brut"),
    ("rico", "ric"),
    ("dulce", "dolç"),
    ("salado", "salat"),
    ("fuerte", "fort"),
    ("débil", "dèbil"),
    ("rápido", "ràpid"),
    ("lento", "lent"),
    ("feliz", "feliç"),
    ("triste", "trist"),
    ("cansado", "cansat"),
    ("malo", "dolent"),
    ("bueno", "bo"),
    ("frío", "fred"),
    ("caliente", "calent"),
    ("mucho", "molt"),
    ("poco", "poc"),
    ("todos", "tots"),
    ("nadie", "ningú"),
    # --- colores y formas -------------------------------------------------
    ("círculo", "cercle"),
    ("cuadrado", "quadrat"),
    ("triángulo", "triangle"),
    ("línea", "línia"),
    ("punto", "punt"),
    # --- pronouns / function words that matter in sentences ---------------
    ("y", "i"),
    ("o", "o"),
    ("pero", "però"),
    ("porque", "perquè"),
    ("también", "també"),
    ("siempre", "sempre"),
    ("nunca", "mai"),
    ("ahora", "ara"),
    ("después", "després"),
    ("antes", "abans"),
    ("hoy", "hui"),
    ("ayer", "ahir"),
    ("con", "amb"),
    ("sin", "sense"),
    ("para", "per a"),
    ("sobre", "sobre"),
    ("entre", "entre"),
    ("hasta", "fins a"),
    ("cuando", "quan"),
    ("donde", "on"),
    # --- ciudad y sitios ---------------------------------------------------
    ("parque", "parc"),
    ("luz", "llum"),
    ("ciudad", "ciutat"),
    ("pueblo", "poble"),
    ("calle", "carrer"),
    ("tienda", "botiga"),
    ("mercado", "mercat"),
    ("escuela", "escola"),
    ("hospital", "hospital"),
    ("iglesia", "església"),
    ("banco", "banc"),
    ("biblioteca", "biblioteca"),
    ("museo", "museu"),
    ("cine", "cinema"),
    ("piscina", "piscina"),
    ("gimnasio", "gimnàs"),
    ("estación", "estació"),
    ("tren", "tren"),
    ("coche", "cotxe"),
    ("bicicleta", "bicicleta"),
    ("barco", "vaixell"),
    ("avión", "avió"),
    ("camino", "camin"),
    ("puente", "pont"),
    ("jardín", "jardí"),
    ("parque", "parc"),
    # --- salud -------------------------------------------------------------
    ("doctor", "metge"),
    ("enfermo", "malalt"),
    ("pastilla", "pastilla"),
    ("hospital", "hospital"),
    ("dolor", "dolor"),
    ("fiebre", "febre"),
    ("descanso", "descans"),
    # --- más fiesta --------------------------------------------------------
    ("fiesta", "festa"),
    ("cumpleaños", "aniversari"),
    ("regalo", "regal"),
    ("fiesta", "festa"),
    ("canción", "cançó"),
    ("música", "música"),
    ("pintura", "pintura"),
    ("color", "color"),
    ("historia", "història"),
    ("libro", "llibre"),
    ("palabra", "paraula"),
    ("letra", "lletra"),
    ("número", "nombre"),
    ("foto", "foto"),
    ("camara", "càmera"),
    ("video", "vídeo"),
    # --- verbos y sustantivos frecuentes en fichas -------------------------
    ("amigo", "amic"),
    ("amiga", "amiga"),
    ("vecino", "veí"),
    ("gente", "gent"),
    ("niño", "nen"),
    ("niña", "nena"),
    ("chico", "xic"),
    ("chica", "xica"),
    ("hombre", "home"),
    ("mujer", "dona"),
    ("señor", "senyor"),
    ("señora", "senyora"),
    ("nombre", "nom"),
    ("casa", "casa"),
    ("mundo", "món"),
    ("aire", "aire"),
    ("viento", "vent"),
    ("barco", "vaixell"),
    ("mano", "mà"),
    ("año", "any"),
    ("vez", "vegada"),
    ("día", "dia"),
    # --- formas variables frecuentes (el par SIEMPRE es castellano, valenciano) --
    ("de los", "dels"),
    ("dentro", "dins"),
    ("esos", "eixos"),
    ("aquellos", "aquells"),
    ("aquellas", "aquelles"),
    ("pequeña", "menuda"),
    ("pequeño", "menut"),
    ("grande", "grandota"),
    ("roja", "rossa"),
    ("verde", "verda"),
    ("azul", "blava"),
    ("amarilla", "groga"),
    ("bonita", "bonica"),
    ("feo", "lleig"),
    ("joven", "jove"),
    ("viejo", "vell"),
    ("nueva", "nova"),
    ("limpio", "net"),
    ("sucio", "brut"),
    ("dulce", "dolç"),
    ("feliz", "feliç"),
    ("triste", "trist"),
    ("cansado", "cansat"),
    ("bueno", "bo"),
    ("frío", "fred"),
    ("caliente", "calent"),
    ("fuerte", "fort"),
    ("débil", "dèbil"),
    ("rápido", "ràpid"),
    ("aburrido", "molest"),
    ("tiene", "té"),
    ("hace", "fa"),
    ("puede", "pot"),
    ("quiere", "vols"),
    ("va", "va"),
    ("sabe", "sap"),
)


def _fold(word: str) -> str:
    """Normaliza una palabra para poder compararla.

    Args:
        word: Palabra de entrada.

    Returns:
        Palabra en minúsculas, sin tildes ni signos de puntuación.
    """
    decomposed = unicodedata.normalize("NFD", word.strip().casefold())
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    cleaned = "".join(
        char for char in without_accents if unicodedata.category(char)[0] != "P"
    )
    return " ".join(cleaned.split())


def _build_index() -> dict[tuple[str, str], str]:
    """Construye el índice bidireccional del diccionario.

    Returns:
        Mapa ``(palabra_normalizada, idioma_destino)`` con la traducción.
    """
    index: dict[tuple[str, str], str] = {}
    for spanish, valencian in WORD_PAIRS:
        key_es = (_fold(spanish), "ca")
        key_ca = (_fold(valencian), "es")
        # La primera entrada gana: las repeticiones intencionadas comparten
        # traducción y las variantes (p. ej. "zapato"/"sabata") se priorizan.
        index.setdefault(key_es, valencian.strip())
        index.setdefault(key_ca, spanish.strip())
    return index


INDEX: MappingProxyType[tuple[str, str], str] = MappingProxyType(_build_index())


def lookup(word: str, target_language: str) -> str | None:
    """Busca la traducción de una palabra en el diccionario.

    Args:
        word: Palabra a traducir.
        target_language: Idioma de destino (``"es"`` o ``"ca"``).

    Returns:
        La traducción, o ``None`` si la palabra no está en el diccionario.
    """
    return INDEX.get((_fold(word), target_language))


def lookup_direct(
    spanish: str,
    valencian: str,
    target_language: str,
) -> str | None:
    """Traduce una palabra usando una dirección concreta del par.

    Args:
        spanish: Forma en castellano del par del diccionario.
        valencian: Forma en valenciano del par.
        target_language: Idioma al que se traduce.

    Returns:
        La traducción si el par está en el diccionario; ``None`` si no.
    """
    if target_language == "ca":
        return INDEX.get((_fold(spanish), "ca"))
    return INDEX.get((_fold(valencian), "es"))
