#!/usr/bin/env bash
# ==============================================================================
# MÉTIS — Orquestrador Unificado do Laboratório Científico
# Ecossistema SisTer · Núcleo C++26 Nativo & Persistência PostgreSQL/PostGIS
#
# Uso:
#   ./run.sh              Inicia o ambiente completo (C++26 + Banco + Web)
#   ./run.sh test         Executa a suíte de testes (CTest C++26 e PostGIS)
#   ./run.sh check        Verifica integridade de compilação, dados e testes
#   ./run.sh build        Compila ou recompila o binário C++26 nativo
#   ./run.sh db [cmd]     Comandos de banco: up, down, migrate, import, status
#   ./run.sh help         Exibe o guia de uso
# ==============================================================================

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# Cores para feedback visual no terminal
BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. Carregar variáveis de ambiente (.env)
if [[ ! -f .env && -f .env.example ]]; then
  echo -e "${YELLOW}Criando arquivo '.env' a partir de '.env.example'...${NC}"
  cp .env.example .env
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
fi

HOST="${METIS_HOST:-${HOST:-0.0.0.0}}"
PORT="${METIS_PORT:-${PORT:-8080}}"
DB_CONTAINER="${METIS_DB_CONTAINER:-metis-db}"
DB_PORT="${METIS_DB_PORT:-5432}"

# ------------------------------------------------------------------------------
# Funções Modulares do Orquestrador
# ------------------------------------------------------------------------------

compilar_nucleo() {
  echo -e "${CYAN}==> [1/4] Verificando núcleo de cálculo C++26...${NC}"
  if [[ ! -f "build/resiliencia-rs" || ! -f "build/resiliencia-test" ]]; then
    echo -e "    Compilando binários nativos com CMake..."
    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
    cmake --build build --parallel
    echo -e "    ${GREEN}✓ Núcleo C++26 compilado com sucesso.${NC}"
  else
    echo -e "    ${GREEN}✓ Binários C++26 já compilados (build/resiliencia-rs).${NC}"
  fi
}

iniciar_banco() {
  echo -e "${CYAN}==> [2/4] Verificando persistência PostgreSQL 17 + PostGIS 3.5...${NC}"
  
  # Verificar se podman ou docker estão disponíveis
  local runtime=""
  if command -v podman &>/dev/null; then
    runtime="podman"
  elif command -v docker &>/dev/null; then
    runtime="docker"
  fi

  if [[ -z "$runtime" ]]; then
    echo -e "    ${YELLOW}Aviso: Nem podman nem docker encontrados. Operando em modo somente-estático.${NC}"
    return 0
  fi

  # Iniciar serviço de banco
  ./scripts/db_up.sh

  # Garantir importação dos dados científicos no banco
  python3 scripts/importar_dados_banco.py
}

preparar_links_web() {
  echo -e "${CYAN}==> [3/4] Sincronizando roteamento seguro da interface web...${NC}"
  # Garantir isolamento rigoroso: o servidor web expõe unicamente o diretório web/
  # Arquivos internos (.env, .git, db/, src/, scripts/) permanecem inacessíveis via HTTP.
  ln -sfn ../results web/results
  ln -sfn ../data web/data
  echo -e "    ${GREEN}✓ Sandbox web configurada: apenas 'web/' é servido.${NC}"
}

executar_testes() {
  compilar_nucleo
  echo -e "\n${BOLD}${BLUE}=== Executando Testes CTest C++26 ===${NC}"
  ctest --test-dir build --output-on-failure

  echo -e "\n${BOLD}${BLUE}=== Executando Testes de Persistência PostGIS ===${NC}"
  METIS_STRICT_TESTS=1 ./scripts/test_persistencia.sh
}

executar_checagem() {
  echo -e "${BOLD}${BLUE}=== Verificação Completa do Ambiente MÉTIS ===${NC}"
  compilar_nucleo
  iniciar_banco
  preparar_links_web
  executar_testes
  echo -e "\n${BOLD}${GREEN}✓ Todos os subsistemas (C++26, PostGIS, Web, Dados) estão 100% íntegros.${NC}"
}

iniciar_servidor_web() {
  echo -e "${CYAN}==> [4/4] Inicializando servidor web seguro do laboratório...${NC}"
  
  local lan_ips
  lan_ips=$(hostname -I 2>/dev/null || echo "127.0.0.1")
  local primary_ip
  primary_ip=$(echo "$lan_ips" | awk '{print $1}')

  local display_host="localhost"
  if [[ "$HOST" != "0.0.0.0" && -n "$HOST" ]]; then
    display_host="$HOST"
  fi

  echo -e "\n${BOLD}============================================================${NC}"
  echo -e " ${BOLD}MÉTIS${NC} — Laboratório Científico Aberto de Resiliência Agroterritorial"
  echo -e " Ecossistema SisTer · Núcleo C++26 Nativo · PostgreSQL/PostGIS"
  echo -e "${BOLD}============================================================${NC}"
  echo -e " ${BOLD}Ambientes disponíveis diretamente (porta ${PORT}):${NC}"
  echo -e "  • ${CYAN}Apresentação & Notícias:${NC}  http://${display_host}:${PORT}/"
  echo -e "  • ${CYAN}Visão Territorial (RS):${NC}   http://${display_host}:${PORT}/mapa.html"
  echo -e "  • ${CYAN}Dashboard Analítico:${NC}      http://${display_host}:${PORT}/dashboard.html"
  echo -e "  • ${CYAN}Modelos & Algoritmos:${NC}     http://${display_host}:${PORT}/modelos.html"
  echo -e "  • ${CYAN}API Pública Estática:${NC}     http://${display_host}:${PORT}/api/public/achados.json"
  if [[ -n "$primary_ip" && "$primary_ip" != "127.0.0.1" ]]; then
    echo -e "  • ${GREEN}Acesso Rede Local (IP):${NC}   http://${primary_ip}:${PORT}/"
  fi
  echo -e "${BOLD}============================================================${NC}"
  echo -e " ${GREEN}Segurança:${NC} Servindo exclusivamente diretório 'web/' (raiz do repo protegida)."
  echo -e " Pressione ${RED}Ctrl+C${NC} para encerrar o servidor web."
  echo

  exec python3 -m http.server "$PORT" --bind "$HOST" --directory web
}

# ------------------------------------------------------------------------------
# Roteamento de Subcomandos
# ------------------------------------------------------------------------------

CMD="${1:-all}"

case "$CMD" in
  all|start|serve)
    compilar_nucleo
    iniciar_banco
    preparar_links_web
    iniciar_servidor_web
    ;;

  test|tests)
    executar_testes
    ;;

  check|status)
    executar_checagem
    ;;

  build)
    echo -e "${CYAN}==> Recompilando núcleo C++26...${NC}"
    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
    cmake --build build --parallel
    echo -e "${GREEN}✓ Núcleo C++26 recompilado com sucesso.${NC}"
    ;;

  db)
    SUBCMD="${2:-status}"
    case "$SUBCMD" in
      up)
        iniciar_banco
        ;;
      down|stop)
        ./scripts/db_down.sh
        ;;
      migrate)
        python3 scripts/db_migrate.py
        ;;
      import)
        python3 scripts/importar_dados_banco.py --force
        ;;
      status)
        if podman container exists "$DB_CONTAINER" 2>/dev/null; then
          echo "Contêiner '$DB_CONTAINER': $(podman inspect -f '{{.State.Status}}' "$DB_CONTAINER")"
        else
          echo "Contêiner '$DB_CONTAINER' não está criado."
        fi
        ;;
      *)
        echo "Uso: ./run.sh db [up|down|migrate|import|status]"
        exit 1
        ;;
    esac
    ;;

  sync|evidencias)
    echo -e "${CYAN}==> Sincronizando Evidências Epistêmicas (AdaptaBrasil + INMET)...${NC}"
    python3 scripts/conectores/sincronizar_evidencias.py
    ;;

  help|-h|--help)
    echo -e "${BOLD}MÉTIS — Orquestrador Unificado do Laboratório${NC}"
    echo
    echo "Uso: ./run.sh [comando]"
    echo
    echo "Comandos disponíveis:"
    echo "  (sem argumentos)  Inicia o ecossistema completo: compila C++26, sobe banco PostGIS, migra, importa e abre servidor web"
    echo "  test              Executa todos os testes automatizados (CTest C++26 e PostGIS)"
    echo "  check             Verifica todo o ambiente e valida testes de integridade"
    echo "  sync              Sincroniza evidências climáticas e alertas (AdaptaBrasil MCTI + INMET)"
    echo "  build             Compila os binários em C++26"
    echo "  db up             Inicia o PostgreSQL/PostGIS e roda migrações"
    echo "  db down           Para o contêiner do banco de dados"
    echo "  db migrate        Aplica migrações SQL pendentes"
    echo "  db import         Reimporta todos os dados censitários e resultados"
    echo "  db status         Inspeciona o estado do banco"
    echo "  help              Exibe esta ajuda"
    echo
    ;;

  *)
    echo -e "${RED}Comando desconhecido: '$CMD'${NC}"
    echo "Execute './run.sh help' para ver as opções disponíveis."
    exit 1
    ;;
esac
