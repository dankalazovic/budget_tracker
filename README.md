# Budget Tracker API

REST API za licni budzet, napravljen koristeci Flask i PostgreSQL. Projekat je u
izradi: trenutno su implementirane kategorije, CRUD transakcija, lista
transakcija sa filterima, sortiranjem i paginacijom i mesecni budzeti kategorija.

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
  database.py           # zivotni ciklus sesije tokom zahteva
  errors.py             # centralna obrada HTTP i baza gresaka
  constants.py          # zajednicke poruke, nazivi ogranicenja i konstante
  logging.py            # Loguru konfiguracija
  models/
    category.py        # model kategorije
    transaction.py     # model transakcije
    budget.py          # mesecni budzet kategorije
  api/
    categories.py      # rute kategorija
    transactions.py    # rute transakcija
    budgets.py         # postavljanje, lista i uklanjanje budzeta
    health.py          # pocetna provera rada
    helpers.py         # zajednicki pomocni kod ruta
  schemas/
    common.py          # zajednicki Pydantic tipovi i provere
    category.py        # ulazne i izlazne seme kategorija
    transaction.py     # seme transakcija, liste i filtera
    budget.py          # seme iznosa, meseca i odgovora budzeta
  commands.py          # CLI komanda za migracije
migrations/
  env.py               # povezivanje Alembic-a sa modelima i bazom
  versions/            # automatski generisane revizije
tests/
alembic.ini
```

Rute su grupisane kroz Flask Blueprint-e. Blueprint organizuje rute jednog
resursa; postojeci URL-ovi i oblik uspesnih JSON odgovora ostaju isti. `create_app()` pravi
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

Lanac migracija trenutno je:

```text
a128effd0953  Pocetna sema kategorija i transakcija
      |
4a0687671733  Uklonjena CHECK ogranicenja transakcija
      |
43a98f115024  Dodati budzeti po kategoriji i mesecu
```

Druga revizija uklanja samo imenovana CHECK ogranicenja za tip i opseg iznosa.
Ne brise poslovne redove, kolone, strane kljuceve niti jedinstveni indeks
kategorija. Poslovna pravila sada proveravaju Pydantic ulazne seme.

Treca revizija dodaje tabelu `budgets`, strani kljuc ka kategoriji sa
`ON DELETE CASCADE` i jedinstvenost para kategorija/mesec. Ne menja postojece
redove kategorija ili transakcija i ne dodaje poslovna CHECK ogranicenja.

Konfiguracija ukljucuje Alembic-ov ugradjeni `checkconstraint_byname` dodatak,
kako bi `revision --autogenerate` prepoznao uklanjanje imenovanih CHECK
ogranicenja. Revizija koristi generisani batch oblik: PostgreSQL izvrsava
ALTER operacije. API i migracioni testovi koriste PostgreSQL.
Generisana migracija se i dalje pregleda pre primene.

## Validacija i serijalizacija kroz Pydantic

SQLAlchemy model opisuje cuvanje podatka u bazi. Pydantic sema opisuje ulaz
ili izlaz API-ja: dozvoljene tipove, vrednosti i format odgovora.

`CategoryCreate`, `TransactionInput` i `BudgetInput` proveravaju unos kroz
`model_validate(data)`. Rezultat ima proverena, tipizirana polja: na primer,
iznos je `Decimal`, a datum je Python `date`. Nepoznata ulazna polja se
zanemaruju. Tip transakcije je enum sa vrednostima `income` i `expense`.

`CategoryResponse`, `TransactionResponse`, `TransactionListResponse` i `BudgetResponse`
pripremaju izlaz. Njihov `model_dump(mode="json")` pravi recnik pogodan za
JSON odgovor, sa iznosom u obliku `"12.50"`. Datum transakcije je `YYYY-MM-DD`,
a mesec budzeta `YYYY-MM`. Podesavanje
`from_attributes=True` dozvoljava da sema procita atribute SQLAlchemy objekta,
umesto da prvo rucno pravimo recnik za svako polje.

JSON parser cita decimalne brojeve kao `Decimal` pre validacije. Time cuvamo
sve poslate decimale i mozemo da odbijemo i unos poput `1.00000000000000001`,
umesto da ga obican float parser prethodno skrati na `1.0`.

Za delimicni PUT kategorija i transakcija prvo spojimo postojece vrednosti sa poslatim poljima, pa
validiramo ceo rezultat. Izostavljeno polje zadrzava vrednost; izricito `null`
nije dozvoljeno za obavezna polja. Opis moze biti `null`.

Seme ne pristupaju bazi. Da li kategorija sa zadatim ID-jem zaista postoji
proverava ruta nakon validacije tipa ID-ja. FK i jedinstveni indeks ostaju
zastita u bazi; direktan SQL upis zaobilazi Pydantic poslovne validacije.

Neispravan ulaz se pretvara u `400` sa imenom polja i objasnjenjem. Izlazne
greske seme ostaju serverske greske; ne predstavljaju se kao los korisnicki
unos. URL-ovi i uspesni odgovori ostaju kao u dokumentaciji ispod.

## Automatizovani testovi

Potreban je pokrenut PostgreSQL. API i migracioni testovi koriste zasebnu semu
`tracker_test_<uuid>` koju naprave pre ucitavanja aplikacije. Na urednom zavrsetku
test procesa ta sema se uklanja. Poslovne tabele van testne seme se ne menjaju.
Korisnik baze mora imati dozvolu da kreira seme u izabranoj bazi.

Konekcija se cita iz `TEST_DATABASE_URL` ako je zadat, inace iz `DATABASE_URL`
u okruzenju ili lokalnom `.env`. Opciono se moze koristiti posebna testna baza:

```powershell
$env:TEST_DATABASE_URL = "postgresql://postgres:YOUR_PASSWORD@localhost:5432/budget_tracker_test"
```

Komanda za pokretanje svih testova:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

Testovi koriste Pythonov ugradjeni `unittest`. Pokriveni su CRUD kategorija i
transakcija, lista/filteri/paginacija, budzeti po mesecu i kategoriji, Pydantic seme, poslovne validacije,
jedinstvenost i strani kljucevi, centralni odgovori na greske, ciscenje sesije
posle zahteva i Alembic migracije sa ocuvanjem podataka.

## Greske, sesija i logovanje

Greske imaju JSON oblik `{"error": "opis"}`. Centralni handler obradjuje
Werkzeug HTTP izuzetke i PostgreSQL greske ogranicenja. HTTP zaglavlja se
zadrzavaju, ukljucujuci `Allow` kod odgovora `405`. Nepoznata interna greska
vraca `500` sa generickom porukom `Internal server error`, bez SQL upita,
parametara ili detalja exception-a u odgovoru.

Poslovne poruke i nazivi ogranicenja definisani su u `app/constants.py`, a
statusi se koriste kroz `HTTPStatus`. Jedinstvenost imena kategorije daje
`409`; nepostojeca kategorija pri upisu transakcije daje `400`, a pokusaj
brisanja kategorije sa transakcijama daje `409`. Paralelni pokusaj kreiranja
drugog budzeta za isti par kategorija/mesec daje `409`.

Na pocetku zahteva inicijalizuje se SQLAlchemy sesija. Rute eksplicitno
pozivaju `commit()` posle uspesne promene. Teardown zahteva radi `rollback()`
preostalog nepotvrdjenog rada i uklanja sesiju pomocu `remove()`. Time se
pokrivaju i vec obradjene greske, a prethodno potvrdeni commit ostaje sacuvan.
Engine i pool konekcija su zajednicki; aktivna sesija se ne deli izmedju zahteva.

Loguru podrazumevano zapisuje `INFO` i vise nivoe na standardni izlaz za greske
(`stderr`). Zapisi zahteva koriste metod, sablon rute i status. Za interne
greske zapisuje se tip exception-a. U logove ne upisujemo telo zahteva, query
parametre, lozinke, konekcioni URL niti SQL parametre. Log fajlovi se ne prave.
Nivo logovanja podesava se promenljivom `LOG_LEVEL`, npr. `INFO` ili `ERROR`.

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
ostaju sacuvane, kao i njeni budzeti. Ako kategorija nema transakcije, njeno
brisanje automatski uklanja sve njene budzete, u svim mesecima.

### Greske kategorija

| Status | Znacenje | Primer odgovora |
| --- | --- | --- |
| `400` | Neispravan JSON ili polja | `{"error": "name: String should have at least 1 character"}` |
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
Pydantic sema zahteva `0 < amount <= 1000000` i odbija vise od dve decimale
pre upisa, umesto zaokruzivanja. CHECK pravila za tip i iznos uklanja druga
migracija; ova poslovna validacija obavlja se u kodu.

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
{"error": "per_page: Input should be less than or equal to 100"}
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
| `400` | Neispravna vrednost polja | `{"error": "amount: Value error, Amount must have at most 2 decimal places"}` |
| `400` | Navedena kategorija ne postoji | `{"error": "Category not found"}` |
| `404` | Transakcija ne postoji | `{"error": "Transaction not found"}` |

## API: budzeti

Budzet predstavlja planirani rashod jedne kategorije u jednom mesecu.
Kombinacija `category_id` i `month` je jedinstvena. Mesec se u zahtevima i
odgovorima pise kao `YYYY-MM`, a u bazi cuva kao datum prvog dana tog meseca.

Iznos ima ista pravila kao iznos transakcije: mora biti veci od 0, najvise
`1000000.00`, sa najvise dve decimale. Moze se poslati kao JSON broj ili
decimalni string sa tackom, bez separatora hiljada i okolnih razmaka. Dodatne
decimale odbijaju se i kada su nule, na primer `"200.000"`.

### PUT /budgets/{month}/{category_id}

Postavlja ili menja budzet postojece kategorije za zadati mesec. Kategorija i
mesec odredjeni su URL-om; telo sadrzi obavezni `amount`:

```text
PUT /budgets/2026-10/1
```

```json
{"amount": "200.00"}
```

Ako budzet za taj par jos ne postoji, vraca se `201`:

```json
{
  "id": 1,
  "month": "2026-10",
  "category_id": 1,
  "amount": "200.00"
}
```

Ako vec postoji, vraca se `200` i azurirani budzet istog oblika i istog ID-ja.
Ponovljen isti zahtev ne pravi dodatni red. Nepoznata polja u telu se
zanemaruju; slanje `month` ili `category_id` u telu ne menja par iz URL-a.

### GET /budgets?month=YYYY-MM

Obavezan je jedan parametar `month`. Vraca `200` i listu budzeta samo za taj
mesec, sortiranu po imenu kategorije rastuce:

```text
GET /budgets?month=2026-10
```

```json
[
  {"id": 1, "month": "2026-10", "category_id": 1, "amount": "200.00"}
]
```

Ako taj mesec nema budzete, odgovor je `[]`. Lista nema paginaciju.
Izostavljen, neispravan ili ponovljen `month` vraca `400`. Mesec mora imati
ispravan kalendarski oblik `YYYY-MM`; npr. `2026-13`, `2026-1` i `0000-01`
nisu dozvoljeni.

### DELETE /budgets/{month}/{category_id}

Uklanja budzet tog para i vraca `204` bez tela odgovora. Kategorija i njene
transakcije ostaju sacuvane. Ako budzet ne postoji, vraca se `404`.

### Greske budzeta

| Status | Znacenje | Primer odgovora |
| --- | --- | --- |
| `400` | Neispravan JSON, iznos ili mesec | `{"error": "Invalid JSON data"}` |
| `404` | Kategorija pri postavljanju ne postoji | `{"error": "Category not found"}` |
| `404` | Budzet za trazeni par ne postoji pri brisanju | `{"error": "Budget not found"}` |
| `409` | Paralelni upis je vec napravio budzet istog para | `{"error": "Budget already exists for this category and month"}` |

Budzet je povezan sa kategorijom stranim kljucem `ON DELETE CASCADE`. Zato
brisanje kategorije bez transakcija uklanja njene budzete, dok kategorija sa
transakcijama i dalje ne moze da se obrise.

## Status implementacije

Zavrseni su kategorije, pojedinacni CRUD transakcija, njihova sortirana lista
sa kombinovanim filterima i paginacijom, mesecni budzeti kategorija, modularna struktura, SQLAlchemy 2
modeli, Alembic migracije, Pydantic validacija/serijalizacija, centralna obrada
gresaka, sesija po zahtevu i Loguru. Postoje testovi i dokumentacija tih delova.
Projekat jos nije kompletan prema PDF zadatku.

Preostale funkcionalnosti su:

- Mesecni pregled prihoda, rashoda, salda i potrosnje naspram budzeta.
- CSV import do milion redova, sa prijavom neuspelih redova i razloga.
- Testovi i dokumentacija novih celina, pa zavrsna provera svih zahteva PDF-a.

Cist SQLAlchemy, `uv` i dodatni slojevi ostaju opcije za procenu, a ne uslov da
se funkcionalnosti zadatka zavrse.
