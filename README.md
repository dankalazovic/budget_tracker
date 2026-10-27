# Budget Tracker API

REST API za licni budzet, napravljen koristeci Flask i PostgreSQL. Projekat je u
izradi: trenutno su implementirane kategorije.

## Pokretanje

Potrebni su Python 3 i pokrenut PostgreSQL server. U PostgreSQL-u prvo napraviti
praznu bazu `budget_tracker`, ako vec ne postoji.

Iz korena projekta, u PowerShell-u:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Ako vec imas `.env`, zadrzi ga. U `.env` upisi odgovarajuci `DATABASE_URL` sa
svojim PostgreSQL korisnikom, lozinkom i nazivom baze. `.env` se ne cuva u Gitu.
Ako lozinka sadrzi posebne URL znakove, moraju biti URL-kodirani u konekcionom
stringu.

Zatim pripremi tabele i pokreni aplikaciju:

```powershell
.\venv\Scripts\python.exe -m flask --app app init-db
.\venv\Scripts\python.exe -m flask --app app run
```

API je dostupan na `http://127.0.0.1:5000`.

`init-db` pravi nedostajuce tabele i dodaje jedinstveni indeks za nazive
kategorija. Ne brise postojece podatke i moze se pokrenuti vise puta. Ako u staroj
bazi postoje duplikati naziva nezavisno od velicine slova, komanda prijavljuje
gresku; ne brise ih i ne spaja ih automatski.

Ovo nije opsta komanda za sve buduce izmene seme. Trenutno pokriva postojece
modele i dodavanje indeksa kategorija.

## Automatizovani testovi

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

Testovi koriste Pythonov ugradjeni `unittest` i zasebnu SQLite bazu u memoriji.
Postavljaju testnu konekciju pre ucitavanja aplikacije i ne koriste PostgreSQL
podatke iz `.env`. Baza u memoriji postoji samo tokom testiranja.

Pokriveni su CRUD kategorija, validacije, jedinstvenost u bazi, obnova sesije
posle odbijenog upisa i priprema postojece baze. SQLite testovi nisu zamena za
proveru PostgreSQL specificnosti; SQLite `lower()` podrazumevano obradjuje samo
ASCII slova.

## API: kategorije

Zahtevi sa telom koriste `Content-Type: application/json`. Odgovori su JSON,
osim uspesnog brisanja koje vraca prazno telo. `id` dodeljuje baza.

### GET /

Odgovor `200`:

```json
{"message": "Budget Tracker API is running"}
```

### POST /categories

Obavezna su oba polja:

```json
{"name": "Hrana", "color": "#12AB34"}
```

- `name`: string, 1-30 znakova posle uklanjanja pocetnih i zavrsnih razmaka;
  jedinstven nezavisno od velicine slova. NUL i neispravni Unicode znakovi se
  odbijaju jer ih baza ne moze sacuvati.
- `color`: string u obliku `#RRGGBB`, sa velikim ili malim heksadecimalnim slovima.

Odgovor `201`:

```json
{"id": 1, "name": "Hrana", "color": "#12AB34"}
```

### GET /categories

Vraca `200` i listu kategorija sortiranu po imenu. Prazna baza vraca `[]`.

```json
[{"id": 1, "name": "Hrana", "color": "#12AB34"}]
```

### PUT /categories/{id}

Menja ime, boju ili oba. Izostavljena polja zadrzavaju stare vrednosti. Za
poslata polja vaze ista pravila kao za kreiranje. Prazan objekat `{}` zadrzava
obe vrednosti.

Primer zahteva:

```json
{"color": "#FFFFFF"}
```

Odgovor `200` sadrzi celu azuriranu kategoriju:

```json
{"id": 1, "name": "Hrana", "color": "#FFFFFF"}
```

### DELETE /categories/{id}

Brise kategoriju i vraca `204` bez tela odgovora.

Pravila zabrane brisanja kategorije sa transakcijama i brisanja njenih budzeta
bice dodata zajedno sa tim modelima.

### Greske kategorija

| Status | Znacenje | Primer odgovora |
| --- | --- | --- |
| `400` | Neispravan JSON ili polja | `{"error": "Color must be in #RRGGBB format"}` |
| `404` | Kategorija sa zadatim ID-jem ne postoji | `{"error": "Category not found"}` |
| `409` | Naziv je vec zauzet | `{"error": "Category already exists"}` |

Za `PUT` se prvo proverava da li kategorija postoji, pa zatim telo zahteva.

## Preostali delovi zadatka

Transakcije, kombinovani filteri i paginacija, budzeti, mesecni pregled i CSV
import jos nisu implementirani. Njihova dokumentacija i testovi bice dodavani
uz implementaciju.
