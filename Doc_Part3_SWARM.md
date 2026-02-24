# Partie 3 : Docker Swarm

Cette documentation couvre l'initialisation du cluster, le déploiement de la stack et les tests de résilience.

---

## 1. Initialisation du cluster

### Topologie cible

| Nœud | Rôle | Contraintes |
|---|---|---|
| `node-manager` | Manager | Héberge `db` et `visualizer` |
| `node-worker-1` | Worker | Réplicas `web` et `ui` |
| `node-worker-2` | Worker | Réplicas `web` et `ui` |

### Commandes d'initialisation

**Sur le manager :**
```bash
docker swarm init --advertise-addr <IP_MANAGER>
```

Cette commande retourne un token à copier pour les workers. Pour le récupérer ultérieurement :
```bash
docker swarm join-token worker
```

**Sur chaque worker :**
```bash
docker swarm join --token <TOKEN> <IP_MANAGER>:2377
```

**Vérification du cluster :**
```bash
docker node ls
```

Tous les nœuds doivent apparaître avec le statut `Ready`.

---

## 2. Déploiement de la stack

### Script de déploiement automatisé

Un script `deploy.sh` est fourni à la racine du projet. Il expose les commandes suivantes :

```bash
chmod +x deploy.sh

./deploy.sh init        # Initialise le Swarm sur ce nœud (manager)
./deploy.sh deploy      # Charge le .env et déploie la stack
./deploy.sh status      # État des services et répartition des tâches
./deploy.sh scale web 5 # Met web à 5 réplicas
./deploy.sh update      # Rolling update vers v0.0.2
./deploy.sh teardown    # Supprime la stack (volumes conservés)
```

### Déploiement manuel

```bash
# Charger les variables d'environnement
export $(grep -v '^#' .env | xargs)

# Déployer la stack
docker stack deploy -c docker-stack.yml diabete --with-registry-auth

# Vérifier l'état
docker stack services diabete
docker stack ps diabete
```

---

## 3. Configuration des services

### Réplicas et placement

| Service | Réplicas | Contrainte de placement |
|---|---|---|
| `web` | 3 | Aucune (distribués automatiquement) |
| `ui` | 3 | Aucune (distribués automatiquement) |
| `db` | 1 | `node.role == manager` |
| `redis` | 1 | Aucune |
| `adminer` | 1 | Aucune |
| `visualizer` | 1 | `node.role == manager` |

`db` est contraint sur le manager pour garantir l'accès au volume persistant `pgdata_swarm`. En production, un volume distribué (NFS, Ceph) lèverait cette contrainte.

### Stratégies de mise à jour (rolling updates)

| Service | Parallélisme | Délai entre batches | Action si échec |
|---|---|---|---|
| `web` | 1 réplica à la fois | 10 secondes | `rollback` |
| `ui` | 2 réplicas à la fois | 5 secondes | Non définie |

Le `web` utilise un parallélisme de 1 pour garantir qu'au moins 2 réplicas sur 3 restent disponibles pendant la mise à jour.

### Politique de redémarrage

Le service `web` est configuré avec `restart_policy: condition: on-failure` : le Swarm recrée automatiquement les conteneurs qui s'arrêtent anormalement, sans redémarrer les arrêts propres.

---

## 4. Tests de résilience

### Test 1 — Panne d'un worker

**Objectif** : vérifier que le Swarm redistribue les tâches automatiquement lors de la perte d'un nœud.

```bash
# État initial
docker node ls
docker stack ps diabete

# Simuler une panne sur un worker (depuis le manager)
docker node update --availability drain node-worker-1

# Observer la redistribution (attendre ~15s)
watch docker stack ps diabete
```

**Résultat attendu** : les tâches du nœud drainé passent à l'état `Shutdown` et sont replanifiées sur les nœuds restants. Le service reste accessible.

**Restauration du nœud :**
```bash
docker node update --availability active node-worker-1
```

---

### Test 2 — Montée en charge manuelle

**Objectif** : vérifier la mise à l'échelle horizontale du backend.

```bash
# Passer web à 5 réplicas
docker service scale diabete_web=5

# Observer la répartition
docker service ps diabete_web
```

**Résultat attendu** : 5 tâches réparties sur les nœuds disponibles, toutes à l'état `Running`.

**Retour à 3 réplicas :**
```bash
docker service scale diabete_web=3
```

---

### Test 3 — Rolling update et rollback

**Objectif** : vérifier qu'une mise à jour défectueuse déclenche un rollback automatique.

```bash
# Mise à jour vers une image inexistante (simule un échec)
docker service update \
  --image mirfou1/diabete_api:inexistant \
  --update-failure-action rollback \
  diabete_web

# Observer le rollback automatique
docker service ps diabete_web
```

**Résultat attendu** : les tâches en échec déclenchent un rollback. Le service revient à la version précédente sans interruption.

**Mise à jour réussie vers v0.0.2 :**
```bash
./deploy.sh update
```

---

### Test 4 — Redémarrage forcé d'un conteneur

**Objectif** : vérifier la politique `on-failure` du service `web`.

```bash
# Identifier l'ID d'un conteneur web sur un worker
docker service ps diabete_web

# Sur le worker concerné, tuer le conteneur brutalement
docker kill <container_id>

# Observer le redémarrage depuis le manager
watch docker service ps diabete_web
```

**Résultat attendu** : le Swarm détecte l'arrêt anormal et recrée le conteneur automatiquement. Le nombre de réplicas actifs revient à 3.

---

### Test 5 — Visualisation du cluster

Le service `visualizer` est accessible sur le manager à l'adresse :

```
http://<IP_MANAGER>:8080
```

Il affiche en temps réel la répartition de tous les conteneurs sur les nœuds du cluster. Utiliser cette interface pendant les tests 1 à 4 pour observer visuellement les redistributions.

---

## 5. Commandes de diagnostic

| Action | Commande |
|---|---|
| État global de la stack | `docker stack services diabete` |
| Détail des tâches avec erreurs | `docker stack ps diabete --no-trunc` |
| Logs d'un service | `docker service logs -f diabete_web` |
| Inspection d'un service | `docker service inspect diabete_web --pretty` |
| Liste des nœuds | `docker node ls` |
| Tâches sur un nœud | `docker node ps node-worker-1` |
| Supprimer la stack | `docker stack rm diabete` |
| Supprimer le volume persistant | `docker volume rm diabete_pgdata_swarm` |
