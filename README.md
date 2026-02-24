# Projet Diabète — Partie 1 : Dockerisation

Application de prédiction du diabète composée d'une API Python (Flask) et d'une interface web servie par Nginx. Ce document couvre uniquement la Partie 1 : la construction et l'organisation des images Docker.

> **Note** : Les dossiers `k8s/` (Partie 4 — Kubernetes) et `.github/` (Partie 5 — CI/CD) font l'objet de documentations séparées et ne sont pas couverts ici.

---

## Structure du projet

```
projet_cloud_workers/
├── .dockerignore
├── .env.example
├── .gitignore
├── docker-compose.yml          # Partie 2
├── docker-stack.yml            # Partie 3
├── README.md
├── backend/                    # API Flask + modèle ML
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py
│   ├── diabetes_model.pkl
│   ├── scaler.pkl
│   └── model_metadata.pkl
├── frontend/                   # Interface React
│   ├── Dockerfile
│   └── src/
│       └── index.html
├── k8s/                        # Partie 4 — non couvert ici
│   ├── 00-namespace.yml
│   ├── 01-secrets.yml
│   ├── 02-configmap.yml
│   ├── 03-pvc.yml
│   ├── 04-db-deployment.yml
│   ├── 05-web-deployment.yml
│   ├── 06-ui-deployment.yml
│   ├── 07-ingress.yml
│   ├── 08-hpa.yml
│   └── nginx-conf.yml
└── .github/
    └── workflows/
        └── deploy.yml          # Partie 5 — CI/CD GitHub Actions
```

---

## Prérequis

- Docker >= 24.x
- Docker Compose >= 2.x

---

## 1. Backend (API Flask)

### Image de base

L'image repose sur `python:3.11-slim`. La variante `slim` supprime les outils système non nécessaires à l'exécution de Python, ce qui allège l'image finale d'environ 60 % par rapport à l'image standard.

### Build multi-stage

Le Dockerfile utilise deux stages distincts pour éviter d'embarquer les outils de compilation dans l'image de production.

Le premier stage (`builder`) installe `gcc` et `libpq-dev` — nécessaires pour compiler certaines dépendances — puis installe tous les packages Python dans un répertoire isolé (`/install`). Le second stage repart d'une image `slim` vierge et ne copie que ce répertoire, laissant derrière lui les outils de compilation. L'image finale est ainsi plus légère et présente une surface d'attaque réduite.

### Dépendances Python

```
flask
flask-cors
psycopg2-binary
pandas
scikit-learn==1.6.1
sqlalchemy
joblib
pyjwt
werkzeug
```

Les packages sont installés avec `--no-cache-dir` pour ne pas stocker de fichiers temporaires dans les couches de l'image.

### Healthcheck

Une sonde de santé interroge l'endpoint `/health` toutes les 30 secondes. L'orchestrateur (Compose ou Swarm) attend que ce check soit positif avant de considérer le conteneur comme prêt à recevoir du trafic.

---

## 2. Frontend (Nginx)

### Image de base

L'image `nginx:alpine` est utilisée pour sa très faible empreinte (environ 5 Mo). Un build multi-stage permet d'isoler la phase de préparation des assets statiques avant de les copier dans `/usr/share/nginx/html`, le seul répertoire servi par Nginx.

### Reverse proxy

La configuration Nginx injectée redirige toutes les requêtes vers `/api/` au service backend via son nom DNS interne (`http://web:5000/`). Cette approche résout deux problèmes courants :

**CORS** : du point de vue du navigateur, le frontend et l'API partagent la même origine, ce qui supprime les erreurs de cross-origin.

**Abstraction réseau** : le frontend n'a aucune connaissance de l'adresse IP ou du port réel du backend. La résolution de nom est entièrement gérée par le réseau interne Docker.

---

## 3. Bonnes pratiques

### Réduction de la taille des images

| Image | Stratégie |
|---|---|
| Backend | `python:3.11-slim`, multi-stage build, `--no-cache-dir`, suppression des caches APT |
| Frontend | `nginx:alpine`, multi-stage build, suppression des fichiers Nginx par défaut |

### `.dockerignore`

Le fichier `.dockerignore` à la racine exclut les éléments suivants du contexte de build, ce qui accélère les transferts et évite d'exposer des fichiers sensibles dans les couches de l'image : `.git`, `__pycache__`, `.env` et `.venv`.

### Gestion des secrets

Aucun secret n'est écrit en dur dans les Dockerfiles. Les variables sensibles (identifiants base de données, clés JWT, etc.) sont injectées au moment du démarrage du conteneur via des variables d'environnement, conformément aux principes de la [12-Factor App](https://12factor.net/). Le fichier `.env.example` documente l'ensemble des variables attendues.

---

## Lancer les builds

```bash
# Backend
docker build -t <username>/diabete_api:v1.0.0 ./backend

# Frontend
docker build -t <username>/diabete_ui:v1.0.0 ./frontend
```
## Pusher les builds

```bash
# Backend
docker push <username>/diabete_api:v1.0.0 

# Frontend
docker push <username>/diabete_ui:v1.0.0 
```

Remplacer `<username>` par votre identifiant Docker Hub.
