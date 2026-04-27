// data.jsx — sample texty (mock detections usunięte, real detection przez backend /api/redact)

const SAMPLES = {
  email: {
    title: "Email do społeczności",
    filename: "email_oma.txt",
    text: `From: Marek Kowalski <marek.kowalski@example.com>
To: Robert Szewczyk <robert@creatorhub.pl>
Subject: Zgłoszenie do OMA cohort 4

Cześć Robert,

Pisał do Ciebie Tomek, że może warto się skontaktować w sprawie OMA. Pracuję w firmie Logipol Sp. z o.o. (NIP 5252839110) i chciałbym zapisać się do nowej edycji.

Mój numer telefonu: +48 600 123 456, adres: ul. Słoneczna 12/4, 00-001 Warszawa.

Mogę zapłacić kartą na konto: 12 1140 2004 0000 3502 1234 5678. PESEL do faktury: 90123456789.

Pozdrawiam,
Marek`,
  },

  voice: {
    title: "Notatka głosowa",
    filename: "wispr_note.txt",
    text: `Dzisiaj rano gadałem z Tomkiem Wiśniewskim z firmy Codepoint, mówi że potrzebuje workflow do scrapowania konkurencji. Jego email to t.wisniewski@codepoint.pl, telefon 502 333 444.

Pomysł: zrobić im audyt na podstawie ich strony codepoint.pl/audyt. Stawka 5000 PLN netto, faktura na ich NIP 9512345670.

W piątek 15 maja mam call o 14:00, dodać do kalendarza. Adres ich biura: Aleje Jerozolimskie 100, 00-807 Warszawa.

API key do ich Stripe (z testowej konfiguracji który mi pokazał na ekranie): sk_test_4eC39HqLyjWDarjtT1zdp7dc - przypomnieć żeby zrotował zanim poślą do produkcji.`,
  },

  transcript: {
    title: "Transkrypt rozmowy",
    filename: "transkrypt_yt.txt",
    text: `[00:14] Cześć, tu Anna Nowak z kanału Marketing Garage. Dzisiaj rozmawiam z Pawłem Górskim, founderem startupu Brandbox.

[00:32] Paweł, opowiedz proszę jak Was złapać - strona to brandbox.io, mail kontakt@brandbox.io, biuro macie w Krakowie przy ul. Wielickiej 28.

[01:05] Słuchajcie, na koniec promocja: zapiszcie się na newsletter mailem do mnie - anna@marketinggarage.pl, zadzwońcie +48 501 222 333. Dla pierwszych 50 osób kod RABATOWY10 ważny do 30 maja 2026.

[01:48] PS. Dane do faktury: NIP 6792456789, konto PL12 1140 2004 0000 3502 9876 5432.`,
  },
};

// Kolory + meta dla każdej kategorii (matched z backend pii_service.LABEL_MAP)
const LABEL_META = {
  OSOBA:    { hue: 22,  icon: "◉",  desc: "Imiona i nazwiska" },
  EMAIL:    { hue: 200, icon: "@",  desc: "Adresy e-mail" },
  TELEFON:  { hue: 160, icon: "☎",  desc: "Numery telefonów" },
  ADRES:    { hue: 280, icon: "▲",  desc: "Adresy fizyczne" },
  IBAN:     { hue: 45,  icon: "■",  desc: "Numery kont bankowych" },
  NIP:      { hue: 65,  icon: "■",  desc: "Numery NIP" },
  PESEL:    { hue: 0,   icon: "■",  desc: "Numery PESEL" },
  KOD:      { hue: 110, icon: "▼",  desc: "Kody pocztowe" },
  URL:      { hue: 220, icon: "↗",  desc: "Adresy URL" },
  DATA:     { hue: 140, icon: "▤",  desc: "Daty" },
  SEKRET:   { hue: 350, icon: "✦",  desc: "Klucze API, tokeny" },
};

window.SAMPLES = SAMPLES;
window.LABEL_META = LABEL_META;
