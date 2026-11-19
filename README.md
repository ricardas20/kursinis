# Filmų apžvalgos sistema

Kursinio darbo programa: UAB „Forum Cinemas“ filmų apžvalgų, moderavimo ir reitingų sistema.

## Paleidimas

Reikia įdiegto [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
git clone https://github.com/ricardas20/kursinis.git
cd kursinis
docker compose up --build
```

Naršyklėje atidarykite http://localhost:5055

Pirmą kartą paleidus sukuriama demonstracinė duomenų bazė. Duomenys išlieka, kol neištrinamas Docker tomas.

Norint pradėti iš naujo su pradiniais duomenimis:

```bash
docker compose down -v
docker compose up --build
```

Sustabdyti sistemą: `docker compose down`

## Prisijungimas

Visų paskyrų slaptažodis: `Apzvalga2026`

| Prisijungimo vardas | Pareigos |
| --- | --- |
| specialistas | klientų aptarnavimo specialistas, įveda ir redaguoja apžvalgas |
| moderatorius | tikrina ir publikuoja apžvalgas, perskaičiuoja reitingą |
| vadybininkas | sudaro ataskaitas ir tvarko filmus, žanrus, žiūrovus bei paskyras |
