# 🏥 IA-Diabète — Système Expert de Diagnostic

Système expert de prédiction du diabète déployé sur Kubernetes avec pipeline CI/CD automatisé et monitoring via Prometheus/Grafana.

---

## 📋 Table des matières

- [Architecture globale](#architecture-globale)
- [Prérequis](#prérequis)
- [Guide d'installation](#guide-dinstallation)
- [Configuration réseau](#configuration-réseau)
- [CI/CD Pipeline](#cicd-pipeline)
- [Monitoring Grafana](#monitoring-grafana)
- [Dépannage](#dépannage)

---

## Architecture globale

### Vue d'ensemble

```
                        Internet / Réseau local
                               │
                        192.168.56.1:80
                               │
                          [iptables]
                               │ DNAT
                        192.168.49.2:80
                               │
                     [Ingress NGINX Controller]
                               │
              ┌────────────────┴────────────────┐
              │                                 │
         /api/(.*)                           /(.*)
              │                                 │
       [web-service:5000]              [ui-service:80]
              │                                 │
    [diabetes-web Pod]               [diabetes-ui Pod]
     Flask API + ML Model             Nginx + React UI
              │
       [db-service:5432]
              │
     [postgres-db Pod]
      PostgreSQL 15
              │
     [PersistentVolumeClaim]
         postgres-pvc (1Gi)
```

### Composants Kubernetes

| Composant | Type | Image | Port |
|-----------|------|-------|------|
| `postgres-db` | Deployment | postgres:15-alpine | 5432 |
| `diabetes-web` | Deployment | mirfou1/diabete_api:latest | 5000 |
| `diabetes-ui` | Deployment | mirfou1/diabete_ui:latest | 80 |
| `db-service` | Service (ClusterIP) | — | 5432 |
| `web-service` | Service (ClusterIP) | — | 5000 |
| `ui-service` | Service (NodePort) | — | 80/30080 |
| `diabetes-ingress` | Ingress | nginx | 80 |
| `diabetes-ui-hpa` | HorizontalPodAutoscaler | — | — |

### Structure du dépôt

```
projet_cloud_workers/
├── backend/                    # API Flask + modèle ML
│   ├── app.py                  # Application principale
│   ├── Dockerfile              # Image Docker backend
│   ├── requirements.txt
│   ├── diabetes_model.pkl      # Modèle ML entraîné
│   ├── scaler.pkl
│   └── model_metadata.pkl
├── frontend/                   # Interface React
│   ├── Dockerfile              # Image Docker frontend
│   └── src/index.html          # Application React (Babel standalone)
├── k8s/                        # Manifestes Kubernetes
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
├── .github/
│   └── workflows/
│       └── deploy.yml          # Pipeline GitHub Actions
└── README.md
```

---

## Prérequis

### Logiciels requis

| Outil | Version testée | Installation |
|-------|----------------|-------------|
| Minikube | v1.35.0 | [minikube.sigs.k8s.io](https://minikube.sigs.k8s.io) |
| kubectl | v1.35.0 | Inclus avec Minikube |
| Docker | 29.2.0 | [docs.docker.com](https://docs.docker.com) |
| Helm | v3.x | `curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 \| bash` |

### Addons Minikube requis

```bash
minikube addons enable ingress          # Ingress Controller NGINX
minikube addons enable metrics-server   # Métriques pour HPA
```

---

## Guide d'installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/VOTRE_USERNAME/projet_cloud_workers.git
cd projet_cloud_workers
```

### 2. Démarrer Minikube

```bash
minikube start
minikube addons enable ingress
minikube addons enable metrics-server
```

### 3. Créer le secret (mot de passe DB)

```bash
kubectl create secret generic diabetes-secrets \
  --from-literal=POSTGRES_PASSWORD=admin
```

> ⚠️ Ne jamais versionner le fichier `01-secrets.yml` avec des vraies valeurs en production.

### 4. Déployer l'application

```bash
kubectl apply -f k8s/02-configmap.yml
kubectl apply -f k8s/03-pvc.yml
kubectl apply -f k8s/04-db-deployment.yml
kubectl apply -f k8s/05-web-deployment.yml
kubectl apply -f k8s/06-ui-deployment.yml
kubectl apply -f k8s/nginx-conf.yml
kubectl apply -f k8s/07-ingress.yml
kubectl apply -f k8s/08-hpa.yml
```

### 5. Vérifier le déploiement

```bash
kubectl get pods                        # Tous les pods doivent être Running
kubectl get svc                         # Vérifier les services
kubectl get ingress                     # CLASS doit afficher "nginx"
```

### 6. Configurer la résolution DNS locale

```bash
echo "$(minikube ip) diabetes.local" | sudo tee -a /etc/hosts
```

### 7. Accéder à l'application

Ouvrir `http://diabetes.local` dans le navigateur.

Compte administrateur par défaut :
- **Login** : `Dr_Moussa`
- **Password** : `master2_pass`

---

## Configuration réseau

### Accès depuis les machines distantes du même réseau

Par défaut, Minikube n'est accessible que depuis la machine hôte. Pour exposer l'application sur le réseau local, on utilise `iptables` pour rediriger le trafic.

#### Identifier les interfaces réseau

```bash
ip a | grep 192.168.56.1        # Interface réseau local → enp0s9
ip route | grep 192.168.49      # Interface Minikube → br-5e5d70f2799a
```

#### Activer le forwarding IP

```bash
sudo sysctl -w net.ipv4.ip_forward=1
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

#### Ajouter les règles iptables

```bash
# Rediriger port 80 entrant vers Minikube
sudo iptables -t nat -A PREROUTING -i enp0s9 -p tcp --dport 80 \
  -j DNAT --to-destination 192.168.49.2:80

# Autoriser le forwarding aller/retour
sudo iptables -A FORWARD -i enp0s9 -o br-5e5d70f2799a -p tcp --dport 80 -j ACCEPT
sudo iptables -A FORWARD -i br-5e5d70f2799a -o enp0s9 -p tcp --sport 80 -j ACCEPT

# Masquerade pour le retour des paquets
sudo iptables -t nat -A POSTROUTING -j MASQUERADE
```

#### Sauvegarder les règles (persistance après reboot)

```bash
sudo apt-get install -y iptables-persistent
sudo iptables-save | sudo tee /etc/iptables/rules.v4
sudo systemctl enable netfilter-persistent
```

#### Sur les machines distantes

Ajouter dans `/etc/hosts` (Linux/Mac) ou `C:\Windows\System32\drivers\etc\hosts` (Windows) :

```
192.168.56.1   diabetes.local
192.168.56.1   grafana.local
```

---

## CI/CD Pipeline

### Vue d'ensemble du pipeline

```
Push sur main
     │
     ▼
┌─────────────────────────────┐
│  JOB 1 : build-and-push     │  runs-on: ubuntu-latest
│  ─────────────────────────  │
│  1. Checkout du code        │
│  2. Login Docker Hub        │
│  3. Build image backend     │
│  4. Push backend (SHA+latest│
│  5. Build image frontend    │
│  6. Push frontend (SHA+latest│
└────────────┬────────────────┘
             │ needs: build-and-push
             ▼
┌─────────────────────────────┐
│  JOB 2 : deploy             │  runs-on: self-hosted
│  ─────────────────────────  │
│  1. Checkout du code        │
│  2. Décoder KUBECONFIG      │
│  3. kubectl apply (manifests│
│  4. kubectl set image (web) │
│  5. kubectl set image (ui)  │
│  6. rollout status (web)    │
│  7. rollout status (ui)     │
│  8. kubectl get pods        │
└─────────────────────────────┘
```

### Secrets GitHub requis

Configurer dans **Settings → Secrets and variables → Actions** :

| Secret | Description |
|--------|-------------|
| `DOCKER_USERNAME` | Username Docker Hub (`mirfou1`) |
| `DOCKER_PASSWORD` | Token Docker Hub (Account Settings → Security → New Access Token) |
| `KUBECONFIG_B64` | Kubeconfig encodé en base64 : `cat ~/.kube/config \| base64 -w 0` |

### Installer le self-hosted runner

Le runner doit tourner sur la machine hébergeant Minikube car le cluster n'est pas accessible depuis internet.

```bash
# Sur GitHub : Settings → Actions → Runners → New self-hosted runner → Linux x64
mkdir -p ~/actions-runner && cd ~/actions-runner

# Copier-coller les commandes fournies par GitHub (download + extract + config)
./config.sh --url https://github.com/VOTRE_USERNAME/VOTRE_REPO --token VOTRE_TOKEN

# Démarrer le runner
./run.sh
```

> 💡 Pour que le runner survive aux reboots, l'installer comme service : `sudo ./svc.sh install && sudo ./svc.sh start`

### Tags des images Docker

Chaque build produit deux tags :
- `mirfou1/diabete_api:<SHA_COURT>` — tag immuable lié au commit (ex: `94def41`)
- `mirfou1/diabete_api:latest` — toujours la dernière version

---

## Monitoring Grafana

### Installation via Helm

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Installer Prometheus + Grafana + AlertManager
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace

# Installer Loki (collecte de logs)
helm install loki grafana/loki-stack \
  --namespace monitoring \
  --set promtail.enabled=true \
  --set loki.enabled=true
```

### Accéder à Grafana

```bash
# Récupérer le mot de passe admin
kubectl --namespace monitoring get secrets monitoring-grafana \
  -o jsonpath="{.data.admin-password}" | base64 -d ; echo
```

Appliquer l'Ingress Grafana :

```bash
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: grafana-ingress
  namespace: monitoring
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
  - host: grafana.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: monitoring-grafana
            port:
              number: 80
EOF

echo "$(minikube ip) grafana.local" | sudo tee -a /etc/hosts
```

URL : `http://grafana.local` — Login : `admin`

### Dashboards préconfigurés

`kube-prometheus-stack` inclut automatiquement :
- **Kubernetes / Compute Resources / Pod** — CPU et mémoire par pod
- **Kubernetes / Compute Resources / Namespace** — Vue globale par namespace
- **Node Exporter / Full** — Métriques système de la machine hôte

### Requêtes PromQL — Dashboard personnalisé Diabetes

Créer un dashboard via **Dashboards → New → New Dashboard** avec ces panels :

#### CPU des pods (Time Series)
```promql
rate(container_cpu_usage_seconds_total{namespace="default", pod=~"diabetes-.*"}[5m])
```

#### Mémoire utilisée (Time Series + Gauge)
```promql
container_memory_usage_bytes{namespace="default", pod=~"diabetes-.*"}
```

#### Nombre de restarts (Stat)
```promql
kube_pod_container_status_restarts_total{namespace="default"}
```

#### Pods en état Running (Stat)
```promql
kube_pod_status_phase{namespace="default", phase="Running"}
```

| Métrique | Visualisation recommandée | Seuil d'alerte |
|----------|--------------------------|----------------|
| CPU | Time Series | > 80% de la limite |
| Mémoire | Time Series + Gauge | > 400Mi |
| Restarts | Stat (rouge si > 3) | > 3 restarts |
| Pods Running | Stat (vert/rouge) | < nombre attendu |

---

## Dépannage

### Pod en CrashLoopBackOff

```bash
kubectl logs -l app=web --previous      # Logs avant le dernier crash
kubectl describe pod -l app=web         # Voir les events et l'état
```

**Cause fréquente** : `init_db()` échoue car PostgreSQL n'est pas encore prêt. Le pod relance automatiquement jusqu'à 15 tentatives avec 5s d'attente entre chaque.

### Ingress retourne 502/503

```bash
# Vérifier que les endpoints sont actifs
kubectl get endpoints

# Voir les logs de l'ingress controller
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=50

# Vérifier que l'ingress a bien la classe nginx
kubectl get ingress   # La colonne CLASS doit afficher "nginx"
```

### Ingress CLASS affiche `<none>`

Ajouter `ingressClassName: nginx` dans le manifest `07-ingress.yml` sous `spec:` puis réappliquer.

### Kubeconfig vide ou corrompu

```bash
minikube update-context
cat ~/.kube/config | grep server        # Doit afficher https://192.168.49.2:8443
kubectl cluster-info                    # Doit répondre sans erreur
```

### Pod web répond mais login retourne 500

```bash
kubectl logs -l app=web                 # Chercher l'erreur Python exacte
```

**Cause fréquente** : tables DB non créées. Vérifier que `init_db()` est appelé au niveau module dans `app.py`, pas seulement dans `if __name__ == '__main__':`.

### Accès distant impossible (connexion refusée)

```bash
# Vérifier que le forwarding est actif
cat /proc/sys/net/ipv4/ip_forward       # Doit afficher 1

# Vérifier les règles iptables
sudo iptables -t nat -L -n -v | grep DNAT

# Vérifier le firewall
sudo ufw status
sudo ufw allow 80/tcp                   # Si UFW est actif
```

---

## Comptes par défaut

| Rôle | Login | Password |
|------|-------|----------|
| Administrateur | `Dr_Moussa` | `master2_pass` |
| Grafana | `admin` | récupéré via kubectl |

> ⚠️ Changer ces mots de passe en production.
