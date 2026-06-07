# Raport czastkowy - Maciej Małecki (Analiza wynikow)

## Zakres zadania
Celem mojego etapu bylo zautomatyzowanie analizy uruchomionego phishing kitu po stronie lokalnego sandboxa, aby:
- przechwycic wywolania PHP `mail()`,
- znalezc adres e-mail atakujacego,
- wykryc potencjalne pliki z danymi ofiar (`victims.txt`, `logs.txt`, `result.txt`, `passwords.txt`),
- wygenerowac raport koncowy dla analizy.

## Co zostalo wykonane
W module `auto_runner.py` dodano logike analityczna uruchamiana po zasymulowaniu formularzy Selenium:

1. Przechwytywanie `mail()`
- Skrypt zapisuje stan logow mailowych przed uruchomieniem kitu.
- Po wykonaniu interakcji z formularzem odczytywany jest nowy stan logow.
- Roznica (nowe pliki `.eml`) traktowana jest jako efekt dzialania phishing kitu.

2. Wykrywanie adresu e-mail atakujacego
- Adresy e-mail sa wyciagane regexem:
  - z plikow zestawu (np. `.php`, `.html`, `.txt`, `.ini`, `.conf`),
  - z nowo przechwyconych logow `mail()`.
- Wynik jest scalany i deduplikowany.

3. Wykrywanie plikow credentiali
- Rekurencyjne skanowanie drzewa kitu pod katem nazw:
  - `victims.txt`
  - `logs.txt`
  - `result.txt`
  - `passwords.txt`
- Raport zawiera znalezione sciezki wzgledne.

4. Generowanie raportu
- Dla kazdego przebiegu tworzony jest plik:
  - `logs/auto_runner/<nazwa_kitu>/analysis_report.txt`
- Raport zawiera:
  - nazwe kitu,
  - znalezione e-maile atakujacego,
  - znalezione pliki credentiali,
  - liste nowo przechwyconych logow maila,
  - katalog roboczy analizy.

## Przykladowy oczekiwany wynik

Kit:
office365.zip

Attacker email:
evil@example.com

Credential file:
logs/passwords.txt

## Ocena zgodnosci z wymaganiami projektu
Zrealizowana czesc pokrywa wymagania dla etapu analizy wynikow:
- przechwytywanie `mail()` -> TAK,
- identyfikacja adresu e-mail atakujacego -> TAK,
- wykrywanie plikow z danymi ofiar -> TAK,
- automatyczny raport -> TAK.

## Ograniczenia i uwagi
- Dokladnosc wykrywania e-maili zalezy od tego, czy kit zapisuje je jawnie (w kodzie lub tresci wiadomosci).
- Nie wszystkie kity korzystaja z nazw plikow wskazanych w wymaganiach, dlatego mozliwe sa przypadki bez trafienia.
- Analiza zaklada uruchomienie w izolowanym srodowisku (sandbox/Docker) zgodnie z zaleceniami projektu.

## Moj wklad
- zaprojektowanie i implementacja etapu post-analizy uruchomionego kitu,
- integracja analizy z istniejacym przeplywem `auto_runner.py`,
- przygotowanie formatu raportu pod oddanie projektu.