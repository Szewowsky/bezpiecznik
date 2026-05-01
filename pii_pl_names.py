"""
Polski słownik PERSON gating + ORG/brand blocklist + alias normalization.

Embedded data dla detection gating (Phase 2.1a) i alias normalization
(Phase 2.1b). Soft dependency: dane embedded w kodzie, zero pip install.

Iteracja: dodać imię/nazwisko/brand → edit listy → bump VERSION poniżej.

Zakres v1.0 (2026-05-01): top-50 polskich imion (25 męskich + 25 żeńskich)
z 4-5 najczęstszymi formami odmienionymi (mianownik + dopełniacz + celownik
+ narzędnik + miejscownik).

Zakres v1.1 (2026-05-01 wieczór): per-position normalize_pl_tokens() dla
aliasingu. Imiona = whitelist lookup (pos 0), nazwiska = regex transform
rules dla rodzin -ski/-cki/-wicz (pos > 0).

Format Pythona zamiast JSON dla:
- importu jako moduł (zero load overhead)
- inline komentarzy gramatycznych
- frozenset (immutable, fast lookup)
"""

import re

VERSION = "1.1.0"  # bump przy zmianie listy

# ── Imiona męskie (mianownik). Top 25 najpopularniejszych w Polsce. ────────
PL_FIRST_NAMES_M = frozenset({
    "Jan", "Piotr", "Paweł", "Tomasz", "Krzysztof",
    "Andrzej", "Marek", "Michał", "Adam", "Jakub",
    "Robert", "Maciej", "Łukasz", "Marcin", "Krystian",
    "Dawid", "Kamil", "Mateusz", "Filip", "Sebastian",
    "Damian", "Patryk", "Wojciech", "Stanisław", "Rafał",
})

# ── Imiona żeńskie (mianownik). Top 25. ──────────────────────────────────
PL_FIRST_NAMES_F = frozenset({
    "Anna", "Maria", "Katarzyna", "Małgorzata", "Agnieszka",
    "Krystyna", "Barbara", "Ewa", "Elżbieta", "Joanna",
    "Magdalena", "Monika", "Aleksandra", "Karolina", "Natalia",
    "Zofia", "Teresa", "Beata", "Marta", "Iwona",
    "Justyna", "Wanda", "Halina", "Irena", "Dorota",
})

# ── Mapa odmian → forma podstawowa (mianownik). ──────────────────────────
# Format: "Imię_mianownik": [forma_dopełniacz, forma_celownik, forma_narzędnik,
#                            forma_miejscownik]
# Pomijamy biernik (kogo) bo dla większości męskich = dopełniacz.
PL_FIRST_NAME_INFLECTIONS = {
    # ── Męskie zakończone na spółgłoskę ─────────────────────────────────
    "Jan": ["Jana", "Janowi", "Janem", "Janie"],
    "Piotr": ["Piotra", "Piotrowi", "Piotrem", "Piotrze"],
    "Paweł": ["Pawła", "Pawłowi", "Pawłem", "Pawle"],
    "Tomasz": ["Tomasza", "Tomaszowi", "Tomaszem", "Tomaszu"],
    "Krzysztof": ["Krzysztofa", "Krzysztofowi", "Krzysztofem", "Krzysztofie"],
    "Andrzej": ["Andrzeja", "Andrzejowi", "Andrzejem", "Andrzeju"],
    "Marek": ["Marka", "Markowi", "Markiem", "Marku"],
    "Michał": ["Michała", "Michałowi", "Michałem", "Michale"],
    "Adam": ["Adama", "Adamowi", "Adamem", "Adamie"],
    "Jakub": ["Jakuba", "Jakubowi", "Jakubem", "Jakubie"],
    "Robert": ["Roberta", "Robertowi", "Robertem", "Robercie"],
    "Maciej": ["Macieja", "Maciejowi", "Maciejem", "Macieju"],
    "Łukasz": ["Łukasza", "Łukaszowi", "Łukaszem", "Łukaszu"],
    "Marcin": ["Marcina", "Marcinowi", "Marcinem", "Marcinie"],
    "Krystian": ["Krystiana", "Krystianowi", "Krystianem", "Krystianie"],
    "Dawid": ["Dawida", "Dawidowi", "Dawidem", "Dawidzie"],
    "Kamil": ["Kamila", "Kamilowi", "Kamilem", "Kamilu"],
    "Mateusz": ["Mateusza", "Mateuszowi", "Mateuszem", "Mateuszu"],
    "Filip": ["Filipa", "Filipowi", "Filipem", "Filipie"],
    "Sebastian": ["Sebastiana", "Sebastianowi", "Sebastianem", "Sebastianie"],
    "Damian": ["Damiana", "Damianowi", "Damianem", "Damianie"],
    "Patryk": ["Patryka", "Patrykowi", "Patrykiem", "Patryku"],
    "Wojciech": ["Wojciecha", "Wojciechowi", "Wojciechem", "Wojciechu"],
    "Stanisław": ["Stanisława", "Stanisławowi", "Stanisławem", "Stanisławie"],
    "Rafał": ["Rafała", "Rafałowi", "Rafałem", "Rafale"],

    # ── Żeńskie zakończone na -a ────────────────────────────────────────
    # Dopełniacz/miejscownik często takie same: "Anny", "Annie"
    "Anna": ["Anny", "Annie", "Annę", "Anną"],
    "Maria": ["Marii", "Marii", "Marię", "Marią"],
    "Katarzyna": ["Katarzyny", "Katarzynie", "Katarzynę", "Katarzyną"],
    "Małgorzata": ["Małgorzaty", "Małgorzacie", "Małgorzatę", "Małgorzatą"],
    "Agnieszka": ["Agnieszki", "Agnieszce", "Agnieszkę", "Agnieszką"],
    "Krystyna": ["Krystyny", "Krystynie", "Krystynę", "Krystyną"],
    "Barbara": ["Barbary", "Barbarze", "Barbarę", "Barbarą"],
    "Ewa": ["Ewy", "Ewie", "Ewę", "Ewą"],
    "Elżbieta": ["Elżbiety", "Elżbiecie", "Elżbietę", "Elżbietą"],
    "Joanna": ["Joanny", "Joannie", "Joannę", "Joanną"],
    "Magdalena": ["Magdaleny", "Magdalenie", "Magdalenę", "Magdaleną"],
    "Monika": ["Moniki", "Monice", "Monikę", "Moniką"],
    "Aleksandra": ["Aleksandry", "Aleksandrze", "Aleksandrę", "Aleksandrą"],
    "Karolina": ["Karoliny", "Karolinie", "Karolinę", "Karoliną"],
    "Natalia": ["Natalii", "Natalii", "Natalię", "Natalią"],
    "Zofia": ["Zofii", "Zofii", "Zofię", "Zofią"],
    "Teresa": ["Teresy", "Teresie", "Teresę", "Teresą"],
    "Beata": ["Beaty", "Beacie", "Beatę", "Beatą"],
    "Marta": ["Marty", "Marcie", "Martę", "Martą"],
    "Iwona": ["Iwony", "Iwonie", "Iwonę", "Iwoną"],
    "Justyna": ["Justyny", "Justynie", "Justynę", "Justyną"],
    "Wanda": ["Wandy", "Wandzie", "Wandę", "Wandą"],
    "Halina": ["Haliny", "Halinie", "Halinę", "Haliną"],
    "Irena": ["Ireny", "Irenie", "Irenę", "Ireną"],
    "Dorota": ["Doroty", "Dorocie", "Dorotę", "Dorotą"],
}

# ── Reverse lookup: forma_odmiana → forma_podstawowa ────────────────────
# Generated on import. Używane przez Phase 2.1b w `_is_alias_of()` do
# canonical normalization ("Pawłem" → "Paweł" → match z "Paweł Górski").
PL_INFLECTED_TO_BASE = {
    inflected: base
    for base, forms in PL_FIRST_NAME_INFLECTIONS.items()
    for inflected in forms
}

# ── Wszystkie akceptowalne formy imienia (mianownik + odmiany). ─────────
# Używane przez detector jako whitelist gate: pierwszy token MUSI być w tym
# secie żeby sekwencja kwalifikowała się jako PERSON.
PL_ALL_FIRST_NAMES = frozenset(
    PL_FIRST_NAMES_M | PL_FIRST_NAMES_F | frozenset(PL_INFLECTED_TO_BASE.keys())
)


# ── ORG/Brand blocklist ─────────────────────────────────────────────────
# Tokeny które NIE są imionami nawet gdy wyglądają jak Capital Word.
# Z Codex review: "Marketing Garage", "Sheriff Octopus", "Open Source" itp.
# nie powinny być wykryte jako PERSON.
ORG_BRAND_TOKENS = frozenset({
    # Generic brand/product terms
    "Marketing", "Garage", "Studio", "Labs", "Software", "Digital",
    "Solutions", "Tech", "Group", "Media", "Systems", "Cloud",
    "Data", "Analytics", "Platform", "Service", "Services", "Partners",
    "Agency", "Consulting", "Network", "Networks", "Innovation",
    # Tech brands & products
    "Open", "Source", "Apple", "Silicon", "Intel", "AMD",
    "Google", "Microsoft", "Amazon", "Meta", "Netflix",
    "OpenAI", "Anthropic", "GitHub", "GitLab", "Bitbucket",
    "Spotify", "Slack", "Discord", "Telegram", "WhatsApp",
    "Linear", "Notion", "Asana", "Trello",
    # Frameworks/tools
    "React", "Vue", "Angular", "Svelte", "Next", "Remix",
    "Python", "JavaScript", "TypeScript", "Rust",
    "Docker", "Kubernetes", "Postgres", "MySQL", "Redis",
    # Polish ORG / brands (rosnąca lista)
    "Sheriff", "Octopus", "Brandbox", "Codepoint",
    "Allegro", "InPost", "Żabka", "Biedronka",
    # Generic words które wyglądają jak imiona ale nie są
    "Mac", "Windows", "Linux", "iOS", "Android",
})

# ── Trigger words dla negatywnego kontekstu ─────────────────────────────
# Jeśli sekwencja "Imię Nazwisko" pojawia się BEZPOŚREDNIO PO jednym z tych
# słów w 30-znakowym oknie przed, NIE traktuj jako PERSON.
# Przykład: "kanał Marketing Garage" → "Marketing Garage" nie jest PERSON.
ORG_CONTEXT_TRIGGERS_BEFORE = frozenset({
    "firma", "firmy", "firmie", "firmę", "firmą",
    "startup", "startupu", "startupowi", "startupie",
    "marka", "marki", "marce", "markę", "marką",
    "kanał", "kanału", "kanale", "kanałowi",
    "projekt", "projektu", "projekcie",
    "produkt", "produktu", "produkcie",
    "usługa", "usługi", "usłudze", "usługę",
    "platforma", "platformy", "platformie",
    "narzędzie", "narzędzia", "narzędziu",
    "agencja", "agencji",
    "spółka", "spółki", "spółce", "spółkę",
    "grupa", "grupy", "grupie",
    "organizacja", "organizacji",
    "fundacja", "fundacji",
})


# ── Końcówki nazwisk fleksyjnych ────────────────────────────────────────
# Sortowane longest-first dla regex greedy match (ważne!).
# Pokrywają najczęstsze rodziny: -ski/-cki (przymiotnikowe), -wicz, -ow.
PL_LAST_NAME_SUFFIXES_INFLECTED = (
    # 6 liter
    "skiego", "ckiego", "skiej", "ckiej", "skich", "ckich",
    "wiczem", "wiczow", "wiczow",
    # 5 liter
    "wicza", "wiczu",
    # 4 litery
    "skim", "ckim", "skiego",
    "ską", "cką",
    "owej", "owem", "owym", "owi",
    # 3 litery
    "iem", "ego",
    "emu",
    # 2 litery (uważnie - tu największy ryzyko over-match)
    "em", "im", "ie", "ej",
)

# ── Pattern 2. tokenu w wariancie A (imię odmienione + nazwisko mianownik) ─
# Capital + min 2 lowercase letters (zapobiega matchom typu "Anna A").
# Hyphenated surnames od razu: "Górski-Kowalski".
LAST_NAME_NOMINATIVE_PATTERN = (
    r"[A-ZŁŚŻŹĆŃĄĘÓ][a-ząęółśżźćń]{2,}"
    r"(?:-[A-ZŁŚŻŹĆŃĄĘÓ][a-ząęółśżźćń]{2,})?"
)


# ── Phase 2.1b: alias normalization (per-position dispatch) ─────────────
# Reverse lookup imion: lowercase forma odmieniona → lowercase mianownik.
# Generated z PL_INFLECTED_TO_BASE na import. Używane w normalize_pl_tokens
# żeby "pawłem" → "paweł", "anny" → "anna", "marii" → "maria".
PL_INFLECTED_TO_BASE_LOWER = {
    k.lower(): v.lower() for k, v in PL_INFLECTED_TO_BASE.items()
}

# Heurystyczne reguły dla nazwisk -ski/-cki/-wicz. Sortowane longest-first
# (regex pierwszy match wygrywa).
# Świadomie WĄSKIE - tylko najczęstsze rodziny adjektywno-fleksyjne i -wicz.
# Nie próbujemy obsłużyć każdego polskiego nazwiska - tylko te 3 rodziny które
# pokrywają ~70% przypadków, bez ryzyka over-match na pojedynczych tokenach.
SURNAME_NORMALIZATION_RULES: tuple[tuple[re.Pattern, str], ...] = (
    # Adjektywne -ski/-cki: dopełniacz/celownik/miejscownik/narzędnik (męskie)
    (re.compile(r"skiego$"), "ski"),    # Kowalskiego → Kowalski
    (re.compile(r"ckiego$"), "cki"),    # Mickiewickiego → Mickiewicki
    (re.compile(r"skiemu$"), "ski"),
    (re.compile(r"ckiemu$"), "cki"),
    (re.compile(r"skich$"), "ski"),
    (re.compile(r"ckich$"), "cki"),
    (re.compile(r"skim$"), "ski"),       # Górskim → Górski
    (re.compile(r"ckim$"), "cki"),
    # Żeńskie -ska/-cka
    (re.compile(r"skiej$"), "ska"),      # Skłodowskiej → Skłodowska
    (re.compile(r"ckiej$"), "cka"),
    (re.compile(r"ską$"), "ska"),        # Skłodowską → Skłodowska
    (re.compile(r"cką$"), "cka"),
    # -wicz family (męskie)
    (re.compile(r"wiczowi$"), "wicz"),
    (re.compile(r"wiczem$"), "wicz"),    # Mickiewiczem → Mickiewicz
    (re.compile(r"wicza$"), "wicz"),
    (re.compile(r"wiczu$"), "wicz"),
)


def normalize_pl_tokens(tokens: list[str]) -> list[str]:
    """Per-position PL fleksja normalize na liście tokens.

    Tokeny MUSZĄ być już lowercase (output `_tokenize_for_alias` z casefold).

    Logika per pozycja:
      - Pos 0 (imię): whitelist lookup `PL_INFLECTED_TO_BASE_LOWER`
      - Pos > 0 (nazwisko): regex transform `SURNAME_NORMALIZATION_RULES`
      - Brak match → token bez zmian

    Decyzja per-position (po Codex review runda 2):
    Surname rules NIE są stosowane na pos 0 żeby uniknąć over-match na
    single-token spans (np. samotne "górskim" zostaje "górskim", nie
    fałszywie matchuje z "górski").

    Examples:
      ["pawłem"] → ["paweł"]                 # imię lookup
      ["pawłem", "górskim"] → ["paweł", "górski"]
      ["górskim"] → ["górskim"]              # NIE stosujemy surname rules na pos 0
      ["jan", "górskim", "kowalskim"] → ["jan", "górski", "kowalski"]
      ["brandbox"] → ["brandbox"]            # no match
      ["marek"] → ["marek"]                  # mianownik base, no change
    """
    out = []
    for idx, token in enumerate(tokens):
        if idx == 0:
            # Pierwsza pozycja: imię lookup (whitelist)
            out.append(PL_INFLECTED_TO_BASE_LOWER.get(token, token))
        else:
            # Kolejna pozycja: surname regex transform
            transformed = token
            for pattern, replacement in SURNAME_NORMALIZATION_RULES:
                new_token, count = pattern.subn(replacement, token)
                if count > 0:
                    transformed = new_token
                    break  # pierwszy match wygrywa
            out.append(transformed)
    return out
