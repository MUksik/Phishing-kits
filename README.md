# Phishing Kit

Projekt zespołowy mający na celu bezpieczne pobieranie i analizę phishing kits z podanych adresów URL w celu wykrywania skradzionych danych i e-maili przestępców.

## Struktura plików modułu
* `input_urls.txt` - lista URL-i do przeskanowania (1 adres na linię).
* `url_scanner.py` - główny skrypt automatycznie pobierający archiwa ZIP.
* `downloaded_kits/` - katalog, do którego zapisywane są pobrane pakiety.
* `requirements.txt` -zależności projektu.

###  Git Bash 
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
python url_scanner.py input_urls.txt

#### Przeglądarka
Przed uruchomieniem programu należy zainstalować przeglądarkę Chrome lub Firefox.

## Analiza phishing kitu
Skrypt `auto_runner.py` po uruchomieniu kitu:
- automatycznie wypełnia formularze Selenium,
- przechwytuje nowe wywołania `mail()` z logów fake-sendmail (`*.eml`),
- szuka adresów e-mail atakującego,
- wykrywa pliki: `victims.txt`, `logs.txt`, `result.txt`, `passwords.txt`,
- generuje raport per kit.

Raport zapisywany jest do:
- `logs/auto_runner/<nazwa_kitu>/analysis_report.txt`

Przykład uruchomienia:

```bash
python auto_runner.py --zip downloaded_kits/office365.zip --deploy-path kits --deploy-base-url http://127.0.0.1:8080 --mail-log-dir logs/php-mail --headless
```

### PowerShell
W systemie Windows komenda `python` moze wskazywac na niedzialajacy alias systemowy.
Jesli tak jest, uruchamiaj skrypty bezposrednio interpreterem z wirtualnego srodowiska:

```powershell
.\.venv\Scripts\python.exe url_scanner.py input_urls.txt
.\.venv\Scripts\python.exe auto_runner.py --zip downloaded_kits\office365.zip --headless
.\.venv\Scripts\python.exe auto_runner.py --zip downloaded_kits\office365.zip --deploy-path kits --deploy-base-url http://127.0.0.1:8080 --mail-log-dir logs\php-mail --headless
```

Opcjonalnie, na czas biezacej sesji PowerShell, mozna ustawic alias:

```powershell
Set-Alias python .\.venv\Scripts\python.exe
```

Minimalny format raportu:

```
Kit:
office365.zip

Attacker email:
evil@example.com

Credential file:
logs/passwords.txt
```