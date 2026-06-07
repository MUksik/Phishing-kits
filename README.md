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