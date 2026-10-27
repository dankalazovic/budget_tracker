# Budget Tracker API

REST API za licni budzet, napravljen koristeci Flask i PostgreSQL. Projekat je u
izradi: trenutno su implementirane kategorije, CRUD transakcija i lista
transakcija sa filterima, sortiranjem i paginacijom.

## Pokretanje

Potrebni su Python 3.11 ili noviji i pokrenut PostgreSQL server. U PostgreSQL-u prvo napraviti
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

`init-db` pokrece Alembic `upgrade head`: primenjuje verzionisane migracije na
praznu ili vec verzionisanu bazu. Ponovljen poziv bez novih migracija ne menja
postojece podatke. Aplikacija ne kreira tabele automatski pri pokretanju.

## Struktura projekta

```text
app/
  __init__.py           # create_app i povezivanje delova aplikacije
  extensions.py         # zajednicki SQLAlchemy db i DeclarativeBase
  models/
    category.py        # model kategorije
    transaction.py     # model transakcije
  api/
    categories.py      # rute kategorija
    transactions.py    # rute transakcija
    health.py          # pocetna provera rada
    helpers.py         # zajednicki pomocni kod ruta
  validation.py        # postojece validacije
  commands.py          # CLI komanda za migracije
migrations/
  env.py               # povezivanje Alembic-a sa modelima i bazom
  versions/            # automatski generisane revizije
tests/
alembic.ini
```

Rute su grupisane kroz Flask Blueprint-e. Blueprint organizuje rute jednog
resursa; postojeci URL-ovi i JSON odgovori ostaju isti. `create_app()` pravi
aplikaciju i registruje te grupe. Modeli koriste SQLAlchemy 2 `Mapped` i
`mapped_column`, sa jednim fajlom po tabeli.

## Migracije baze

Alembic ucitava `DATABASE_URL` iz okruzenja ili lokalnog `.env`; lozinka se ne
upisuje u `alembic.ini` ni u migracije.

Za praznu bazu ili primenu novih revizija:

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
```

To isto radi i ranije prikazana Flask komanda `init-db`.

Posle izmene modela generisati novu migraciju, pregledati generisani fajl, pa je
primeniti. Migracije se ne pisu rucno od nule:

```powershell
.\venv\Scripts\python.exe -m alembic revision --autogenerate -m "Opis promene seme"
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m alembic check
```

`check` proverava da li Alembic vidi preostale razlike izmedju modela i baze.
Generisani fajl u `migrations/versions/` cuva se u Gitu zajedno sa izmenom modela.

Provera trenutne revizije i istorije:

```powershell
.\venv\Scripts\python.exe -m alembic current
.\venv\Scripts\python.exe -m alembic history
```

Pocetna revizija je `a128effd0953`. Ako vec postoje tabele iz stare verzije
projekta bez Alembic revizije, `init-db` ih ne prepisuje i odbija nastavak.
Prvo treba uporediti stvarnu semu sa pocetnom migracijom, ukljucujuci kolone,
kljuceve, indekse i CHECK ogranicenja. Tek kada odgovaraju, `alembic stamp`
oznacava odgovarajucu reviziju bez kreiranja tabela ili menjanja podataka.
`stamp` ne proverava niti popravlja semu i ne treba ga primenjivati naslepo.

Postojeca lokalna baza ovog projekta je vec proverena prema pocetnoj migraciji
i oznacena tom revizijom, uz ocuvanje svih dotadasnjih podataka.

Ova prva iteracija menja strukturu i uvodi migracije. Preostala promena
validacionih biblioteka, uklanjanje CHECK ogranicenja i ostale smernice
refaktorisanja rade se u sledecim celinama.

## Automatizovani testovi

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

Testovi koriste Pythonov ugradjeni `unittest` i zasebnu SQLite bazu u memoriji.
Postavljaju testnu konekciju pre ucitavanja aplikacije i ne koriste PostgreSQL
podatke iz `.env`. Baza u memoriji postoji samo tokom testiranja.

Pokriveni su CRUD kategorija i transakcija, lista/filteri/paginacija, validacije,
jedinstvenost i strani kljucevi u bazi, obnova sesije posle odbijenog upisa i
inicijalizacija, ponovljivost migracija i bezbedno odbijanje neversionisane baze.
Testovi ukljucuju SQLite proveru stranih kljuceva. SQLite testovi nisu zamena za
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

Kategorija koja ima transakcije ne moze se obrisati: vraca se `409` sa porukom
`{"error": "Category has transactions and cannot be deleted"}`. Transakcije
ostaju sacuvane. Brisanje budzeta uz kategoriju bice dodato sa modelom budzeta.

### Greske kategorija

| Status | Znacenje | Primer odgovora |
| --- | --- | --- |
| `400` | Neispravan JSON ili polja | `{"error": "Color must be in #RRGGBB format"}` |
| `404` | Kategorija sa zadatim ID-jem ne postoji | `{"error": "Category not found"}` |
| `409` | Naziv je vec zauzet | `{"error": "Category already exists"}` |
| `409` | Kategorija ima transakcije | `{"error": "Category has transactions and cannot be deleted"}` |

Za `PUT` se prvo proverava da li kategorija postoji, pa zatim telo zahteva.

## Model transakcije i veza sa kategorijom

`Transaction` predstavlja jedan prihod ili rashod i cuva se u tabeli
`transactions`. Polje `category_id` je strani kljuc ka `category.id`.
Jedna kategorija moze imati vise transakcija; svaka transakcija ima jednu
postojecu kategoriju.

`transaction.category` daje Python objekat njene kategorije, a
`category.transactions` njene transakcije. To omogucava `relationship` u
SQLAlchemy-u. Sam `ForeignKey` cuva pravilo u bazi: transakcija ne moze upucivati
na nepostojecu kategoriju. `ON DELETE RESTRICT` zabranjuje brisanje kategorije
koja ima transakcije.

Iznos se u Pythonu obradjuje kao `Decimal`, a u bazi kao `Numeric(9, 2)`.
`9` oznacava ukupan broj cifara, a `2` broj cifara iza decimalne tacke.
Posebno ogranicenje u bazi zahteva `0 < amount <= 1000000`.
Provera pre upisa odbija vise od dve decimale umesto zaokruzivanja.

## API: transakcije

Zahtevi sa telom koriste `Content-Type: application/json`. ID-jevi su pozitivni
celi brojevi do `2147483647`. Nepoznata polja u telu se zanemaruju.

### POST /transactions

Pre ovog zahteva kategorija sa navedenim ID-jem mora postojati.

```json
{
  "type": "expense",
  "amount": "12.50",
  "date": "2026-10-27",
  "description": "Rucak",
  "category_id": 1
}
```

| Polje | Pravilo |
| --- | --- |
| `type` | Obavezno, tacno `income` ili `expense`. |
| `amount` | Obavezan JSON broj ili decimalni string, veci od 0, najvise 1000000.00, najvise dve decimale. |
| `date` | Obavezan postojeci kalendarski datum u formatu `YYYY-MM-DD`. |
| `category_id` | Obavezan pozitivan integer ID postojece kategorije. String, decimalni broj i boolean nisu dozvoljeni. |
| `description` | Opciono, string sa najvise 200 znakova ili `null`. Izostavljen ili prazan opis `""` cuva se kao `null`. Razmaci u opisu se zadrzavaju. |

Decimalni string koristi tacku, bez okolnih razmaka ili separatora hiljada.
Vise od dve decimale odbija se i kada su dodatne cifre nule, npr. `"12.500"`.
NUL i neispravni Unicode znakovi u opisu vracaju `400`.

Odgovor `201`:

```json
{
  "id": 1,
  "type": "expense",
  "amount": "12.50",
  "date": "2026-10-27",
  "description": "Rucak",
  "category_id": 1
}
```

Iznos u odgovoru uvek je string sa dve decimale, kako klijent ne bi morao da
se osloni na binarni float zapis novca. Datum je ISO string, a odsutan opis je
JSON `null`.

### GET /transactions

Vraca `200` i jednu stranicu transakcija. Parametri se salju kroz URL, bez JSON
tela. Svi parametri su opcioni:

| Parametar | Pravilo | Podrazumevano |
| --- | --- | --- |
| `date_from` | Ispravan `YYYY-MM-DD`; ukljucuje i taj datum. | Bez donje granice |
| `date_to` | Ispravan `YYYY-MM-DD`; ukljucuje i taj datum. | Bez gornje granice |
| `category_id` | Pozitivan ceo broj do 2147483647. | Sve kategorije |
| `type` | Tacno `income` ili `expense`. | Oba tipa |
| `search` | Deo teksta opisa, nezavisno od velicine slova. | Bez pretrage |
| `page` | Pozitivan ceo broj do 2147483647. | `1` |
| `per_page` | Ceo broj od 1 do 100. | `20` |

Rezultati su sortirani po datumu opadajuce, pa po ID-ju opadajuce: noviji datum
ide prvi; za isti datum poslednje dodata transakcija ide prva. Izmena iznosa ili
opisa ne menja ID niti redosled medju transakcijama istog datuma.

Filteri mogu da se kombinuju i svi moraju biti ispunjeni (AND). Ako su poslata
oba datuma, `date_from` ne sme biti posle `date_to`. Datumsku granicu je moguce
poslati i samostalno. Validan `category_id` koji ne postoji daje praznu listu,
jer nijedna transakcija ne zadovoljava taj filter.

`search` trazi doslovan deo teksta: `%`, `_`, `/` i `\` nisu obrasci za
pretragu. Razmaci se zadrzavaju. Prazan `search=` se tretira kao izostavljena
pretraga; neprazna pretraga ne ukljucuje transakcije bez opisa. NUL i neispravni
Unicode znakovi u tekstu pretrage vracaju `400`.

Primer: rashodi iz oktobra, prva stranica sa najvise 10 stavki:

```text
GET /transactions?type=expense&date_from=2026-10-01&date_to=2026-10-31&page=1&per_page=10
```

Primer odgovora ako postoji samo jedna odgovarajuca transakcija:

```json
{
  "items": [
    {
      "id": 1,
      "type": "expense",
      "amount": "12.50",
      "date": "2026-10-27",
      "description": "Rucak",
      "category_id": 1
    }
  ],
  "page": 1,
  "per_page": 10,
  "total": 1,
  "pages": 1
}
```

- `items`: stavke trazene stranice, u istom obliku kao pojedinacna transakcija.
- `page` i `per_page`: trazeni broj stranice i najveci broj stavki na njoj.
- `total`: ukupan broj transakcija koje zadovoljavaju filtere, pre paginacije.
- `pages`: broj stranica za taj `total` i `per_page`.

Bez rezultata vraca se `items: []`, `total: 0` i `pages: 0`. Stranica iza
poslednje takodje vraca `200` i prazne `items`, uz stvarne `total` i `pages`.
Paginaciju radi baza; ne ucitava se cela lista u Python da bi se zatim delila.

Neispravni parametri vracaju `400` i objasnjenje, na primer:

```json
{"error": "per_page must be an integer between 1 and 100"}
```

Brojevni parametri koriste cifre 0-9, bez razmaka, decimalne tacke ili znaka.
Prazne vrednosti nisu dozvoljene, osim `search=`. Podrzani parametar moze se
poslati samo jednom; npr. `type=income&type=expense` vraca `400`. Nepoznati
parametri se zanemaruju.

### GET /transactions/{id}

Vraca `200` i pojedinacnu transakciju u istom obliku kao odgovor kreiranja.
Nepostojeci ID ili ID van dozvoljenog opsega vraca `404`.

### PUT /transactions/{id}

Menja jedno ili vise polja. Za poslata polja vaze ista pravila kao za kreiranje,
a izostavljena polja ostaju nepromenjena. Prazan objekat `{}` ne menja vrednosti.
Slanjem `{"description": null}` ili `{"description": ""}` uklanja se opis.

Primer zahteva:

```json
{"amount": "20.00", "description": "Rucak i kafa"}
```

Odgovor `200` sadrzi celu azuriranu transakciju:

```json
{
  "id": 1,
  "type": "expense",
  "amount": "20.00",
  "date": "2026-10-27",
  "description": "Rucak i kafa",
  "category_id": 1
}
```

Pri neispravnom unosu transakcija zadrzava prethodne vrednosti. Prvo se proverava
da li transakcija postoji, zatim telo zahteva.

### DELETE /transactions/{id}

Brise samo trazenu transakciju i vraca `204` bez tela odgovora. Njena kategorija
ostaje sacuvana. Nepostojeca transakcija vraca `404`.

### Greske transakcija

| Status | Znacenje | Primer odgovora |
| --- | --- | --- |
| `400` | Neispravan JSON | `{"error": "Invalid JSON data"}` |
| `400` | Neispravna vrednost polja | `{"error": "Amount must have at most 2 decimal places"}` |
| `400` | Navedena kategorija ne postoji | `{"error": "Category not found"}` |
| `404` | Transakcija ne postoji | `{"error": "Transaction not found"}` |

## Preostali delovi zadatka

Budzeti, mesecni pregled i CSV import jos nisu implementirani. Njihova
dokumentacija i testovi bice dodavani uz implementaciju.
