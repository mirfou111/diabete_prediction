#!/bin/bash
# =============================================================================
# Script de déploiement - Docker Swarm
# Application de prédiction du diabète
# Usage : ./deploy.sh [init|deploy|status|scale|update|teardown]
# =============================================================================

set -e  # Arrêt immédiat en cas d'erreur

STACK_NAME="diabete"
COMPOSE_FILE="docker-stack.yml"
ENV_FILE=".env"

# --- Couleurs pour les logs ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()   { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# =============================================================================
# Fonctions
# =============================================================================

check_prerequisites() {
  log "Vérification des prérequis..."
  command -v docker >/dev/null 2>&1 || error "Docker n'est pas installé."
  [ -f "$COMPOSE_FILE" ] || error "Fichier $COMPOSE_FILE introuvable."
  [ -f "$ENV_FILE" ] || error "Fichier $ENV_FILE introuvable. Exécuter : cp .env.example .env"
}

init_swarm() {
  log "Initialisation du Swarm..."

  # Récupère l'IP de la machine courante pour l'advertise-addr
  MANAGER_IP=$(hostname -I | awk '{print $1}')
  log "IP détectée pour le manager : $MANAGER_IP"

  if docker info --format '{{.Swarm.LocalNodeState}}' | grep -q "active"; then
    warn "Ce nœud fait déjà partie d'un Swarm. Étape ignorée."
  else
    docker swarm init --advertise-addr "$MANAGER_IP"
    log "Swarm initialisé."
  fi

  echo ""
  log "Commande pour ajouter des workers :"
  docker swarm join-token worker
}

load_env() {
  log "Chargement des variables d'environnement depuis $ENV_FILE..."
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
  log "Variables chargées."
}

deploy_stack() {
  check_prerequisites
  load_env

  log "Déploiement de la stack '$STACK_NAME'..."
  docker stack deploy -c "$COMPOSE_FILE" "$STACK_NAME" --with-registry-auth

  log "Attente de la stabilisation des services (30s)..."
  sleep 30
  status_stack
}

status_stack() {
  log "État de la stack '$STACK_NAME' :"
  docker stack services "$STACK_NAME"
  echo ""
  log "Répartition des tâches par nœud :"
  docker stack ps "$STACK_NAME" --format "table {{.Name}}\t{{.Node}}\t{{.CurrentState}}\t{{.Error}}"
}

scale_service() {
  local service=$1
  local replicas=$2
  [ -z "$service" ] || [ -z "$replicas" ] && error "Usage : ./deploy.sh scale <service> <replicas>"
  log "Mise à l'échelle de '${STACK_NAME}_${service}' à $replicas réplicas..."
  docker service scale "${STACK_NAME}_${service}=${replicas}"
}

rolling_update() {
  log "Mise à jour rolling de l'API backend..."
  docker service update \
    --image mirfou1/diabete_api:v0.0.2 \
    --update-parallelism 1 \
    --update-delay 10s \
    --update-failure-action rollback \
    "${STACK_NAME}_web"

  log "Mise à jour rolling du Frontend..."
  docker service update \
    --image mirfou1/diabete_ui:v0.0.2 \
    --update-parallelism 2 \
    --update-delay 5s \
    --update-failure-action rollback \
    "${STACK_NAME}_ui"
}

teardown_stack() {
  warn "Suppression de la stack '$STACK_NAME'..."
  docker stack rm "$STACK_NAME"
  log "Stack supprimée. Les volumes persistants (pgdata_swarm) sont conservés."
  warn "Pour supprimer les volumes : docker volume rm ${STACK_NAME}_pgdata_swarm"
}

# =============================================================================
# Point d'entrée
# =============================================================================

case "$1" in
  init)     init_swarm ;;
  deploy)   deploy_stack ;;
  status)   status_stack ;;
  scale)    scale_service "$2" "$3" ;;
  update)   rolling_update ;;
  teardown) teardown_stack ;;
  *)
    echo "Usage : $0 [init|deploy|status|scale <service> <n>|update|teardown]"
    echo ""
    echo "  init        Initialise le Swarm sur ce nœud (manager)"
    echo "  deploy      Charge le .env et déploie la stack"
    echo "  status      Affiche l'état des services et la répartition des tâches"
    echo "  scale       Met à l'échelle un service (ex: ./deploy.sh scale web 5)"
    echo "  update      Rolling update vers la version v0.0.2"
    echo "  teardown    Supprime la stack (volumes conservés)"
    exit 1
    ;;
esac
