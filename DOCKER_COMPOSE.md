# Partie 2 : Déploiement Docker Compose

Cette documentation décrit la procédure de déploiement de l'application de prédiction du diabète via Docker Compose.

---

## 1. Architecture

L'environnement est composé de cinq services interconnectés :

| Service | Image | Port exposé | Rôle |
|---|---|---|---|
| `ui` | custom (`nginx:alpine`) | 80 | Serveur web et reverse proxy |
| `web` | custom (`python:3.11-slim`) | 5000 | API Flask / inférence ML |
| `db` | `postgres:15-alpine` | — | Base de données relationnelle |
| `redis` | `redis:alpine` | — | Cache applicatif |
| `adminer` | `adminer:latest` | 8081 | Interface d'administration de la DB (démo) |

`db` et `redis` ne sont pas exposés à l'hôte. Ils sont uniquement accessibles depuis le réseau interne `back-net`.

---

## 2. Prérequis

- Docker Engine >= 20.10
- Docker Compose >= 2.0
- Accès réseau pour le pull des images de base

---

## 3. Configuration

Copier le fichier d'exemple et renseigner les variables :

```bash
cp .env.example .env
```

Variables attendues dans `.env` :

| Variable | Description |
|---|---|
| `POSTGRES_USER` | Nom d'utilisateur PostgreSQL |
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL |
| `POSTGRES_DB` | Nom de la base de données |
| `DATABASE_URL` | URL de connexion complète utilisée par l'API |
| `REDIS_HOST` | Nom d'hôte du service Redis (valeur : `redis`) |

---

## 4. Démarrage

Construction des images et démarrage de tous les services en arrière-plan :

```bash
docker compose up -d --build
```

Vérification de l'état des services (les services avec healthcheck doivent être `Up (healthy)`) :

```bash
docker compose ps
```

L'API (`web`) démarre uniquement après que `db` et `redis` ont passé leur healthcheck respectif. L'interface (`ui`) attend quant à elle que `web` soit démarré.

---

## 5. Persistance des données

Un seul volume nommé est défini :

| Volume | Monté dans | Contenu |
|---|---|---|
| `pgdata` | `/var/lib/postgresql/data` | Données PostgreSQL |

Redis fonctionne sans persistance : le cache est perdu au redémarrage du conteneur, ce qui est le comportement attendu pour un cache applicatif.

Un script `init-db.sql` est monté dans `/docker-entrypoint-initdb.d/` pour l'initialisation initiale du schéma. L'initialisation applicative est également gérée par `app.py`.

---

## 6. Réseau et sécurité

L'architecture repose sur deux réseaux bridge isolés :

- **`front-net`** : relie `ui` et `web`. Permet au reverse proxy Nginx de transmettre les requêtes à l'API.
- **`back-net`** : réseau privé entre `web`, `db`, `redis` et `adminer`. La base de données et le cache ne sont joignables que depuis ce réseau.

> **Note** : L'option `internal: true` sur `back-net` est actuellement commentée dans le fichier Compose. Son activation couperait tout accès Internet depuis les conteneurs du réseau backend, renforçant l'isolation mais nécessitant que toutes les dépendances soient déjà disponibles localement.

### Limitation des ressources

| Service | CPU max | Mémoire max |
|---|---|---|
| `web` | 0.5 core | 512 Mo |
| `ui` | — | 128 Mo |
| `redis` | — | 128 Mo |
| `db` | — | 256 Mo |

---

## 7. Commandes utiles

| Action | Commande |
|---|---|
| Suivre les logs en temps réel | `docker compose logs -f` |
| Logs d'un service spécifique | `docker compose logs -f web` |
| Arrêter les services | `docker compose stop` |
| Supprimer les services et volumes | `docker compose down -v` |
| Ouvrir un shell PostgreSQL | `docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB` |
| Redémarrer un service | `docker compose restart <service>` |
