# MCP — Acesso ao MÉTIS via ChatGPT e Clientes Locais

A integração segue o mesmo padrão do **NOESE** e do **CONTINUUM**: subconjunto da revisão **2025-11-25** do Model Context Protocol via **stdio** e **Streamable HTTP** (`/mcp`, negociando também `2025-06-18` e `2025-03-26`), somente leitura por padrão, escrita candidata opt-in e operações de domínio compartilhadas.

---

## 1. Modos de Execução

### Modo `stdio` (clientes locais: Antigravity, Claude Desktop, etc.)

```bash
# Somente leitura e simulações determinísticas:
./scripts/mcp.sh
# ou:
./run.sh mcp

# Habilitar propostas candidatas (propose_investigation_note):
./scripts/mcp.sh --allow-writes
```

Veja [`config/mcp.example.json`](../config/mcp.example.json) para o modelo de `mcpServers`. Em `stdio`, `stdout` emite apenas JSON-RPC delimitado por nova linha e diagnósticos vão para `stderr`.

### Modo Streamable HTTP (ChatGPT via túnel HTTPS)

O servidor [`scripts/api_server.py`](../scripts/api_server.py) expõe diretamente:

- `POST /mcp` (e `/mcp/<TOKEN>`) — endpoint JSON-RPC Streamable HTTP (suporta `Mcp-Session-Id` e fallback *stateless*).
- `OPTIONS /mcp` / `DELETE /mcp` — negociação e encerramento de sessão.
- `GET /api/v1/tools` — catálogo inspecionável das ferramentas e estado do transporte (não executa ferramentas).

Variáveis de ambiente em `.env`:

- `METIS_MCP_TOKEN=<segredo>`: exige `Authorization: Bearer <segredo>` ou `/mcp/<segredo>` em tempo constante. **Recomendado ao expor via túnel HTTPS para o ChatGPT.**
- `METIS_MCP_ALLOW_WRITES=0|1`: mantém somente leitura por padrão (`0`). Quando `1`, habilita `propose_investigation_note`.

Para conectar no ChatGPT (Developer Mode / Conector customizado), exponha `http://127.0.0.1:8080` por um túnel HTTPS (ex.: Cloudflare Tunnel, Tailscale Funnel ou ngrok) apontando para `https://<seu-dominio>/mcp` com Bearer token (ou `https://<seu-dominio>/mcp/<TOKEN>`).

---

## 2. Catálogo de Ferramentas

Ferramentas somente leitura (`readOnlyHint: true`, sempre disponíveis):

| Ferramenta | Finalidade |
| :--- | :--- |
| `capabilities` | Versão, modelos, anos censitários, frescor do INMET e regras epistêmicas. |
| `search_municipalities` | Busca por nome parcial, prefixo IBGE ou apenas municípios com aviso INMET ativo. |
| `municipality_dossier` | Dossiê completo: Censo 2006/2017, AdaptaBrasil, avisos INMET, episódios e propostas. |
| `confront_models` | Confronto intramunicipal dos 4 modelos (`EPS-REF-001` a `EPS-EXP-004`) e trajetória 2006→2017. |
| `simulate_scenario` | Simulação paramétrica com sumário estatístico e paginação por `codigo_ibge` (**sem ranking competitivo**). |
| `inmet_alerts` | Avisos ativos/futuros, histórico temporal de versões ou auditoria das coletas. |
| `investigation_episodes` | Episódios de investigação (`METIS-DIR-EVID-001`) filtráveis por município, fase e desfecho. |
| `scientific_catalog` | Catálogo público (`modelos.json`, `achados.json`, `resumos.json`, `noticias.json`). |
| `proposals` | Lista propostas candidatas registradas via MCP em `propostas_investigacao_mcp`. |
| `verify` | Integridade técnica (497 municípios, geometrias PostGIS, execuções imutáveis e migrações). |

Com `--allow-writes` / `METIS_MCP_ALLOW_WRITES=1`:

| Ferramenta | Finalidade |
| :--- | :--- |
| `propose_investigation_note` | Registra nota ou hipótese candidata (`pendente_revisao`) com `request_id` UUID idempotente, `limitacoes` obrigatórias e origem `mcp:<cliente>`, sem alterar tabelas canônicas ou imutáveis. |

---

## 3. Estresse de Uso e Avaliação de Melhorias

1. **Testes automatizados de contrato, paridade C++26 e concorrência:**
   ```bash
   ./run.sh test
   # ou isoladamente:
   python3 -m unittest tests/test_mcp.py -v
   ```
2. **Estresse de carga e avaliador de melhorias:**
   ```bash
   ./run.sh stress-mcp --concurrency 8 --iterations 48
   ```
   Executa fluxos investigativos completos em paralelo, confere paridade numérica com `results/RS_497_RESULTADOS.csv`, mede latências (`p50`/`p95`/`max`), estima custo de contexto (~tokens) por ferramenta e gera `results/mcp_eval/latest_report.json` e `results/mcp_eval/latest_report.md` com recomendações priorizadas.
3. **Ensaio opcional com LLM local (Ollama) para testar aderência a schema e regras epistêmicas:**
   ```bash
   ./run.sh stress-mcp --ollama-model qwen2.5:3b
   ```
