# Budget Tracker API

REST API za licni budzet, napravljen koristeci Flask i PostgreSQL. Projekat je u
izradi: trenutno su implementirane kategorije i pojedinacne CRUD operacije
nad transakcijama.

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

Pokriveni su CRUD kategorija i transakcija, validacije, jedinstvenost i strani
kljucevi u bazi, obnova sesije posle odbijenog upisa i priprema postojece baze.
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

Lista transakcija (`GET /transactions`), kombinovani filteri i paginacija,
budzeti, mesecni pregled i CSV import jos nisu implementirani. Njihova
dokumentacija i testovi bice dodavani uz implementaciju.
