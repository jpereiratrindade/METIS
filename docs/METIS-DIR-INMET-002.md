# METIS-DIR-INMET-002 — Sincronização, Versionamento e Histórico de Evidências Meteorológicas

**Versão:** 1.0.0  
**Estado:** implementada  
**Data:** 04/11/2026  
**Diretriz preservada:** METIS-DIR-EVID-001

## 1. Objetivo

Garantir que toda afirmação baseada no INMET possa ser reconstruída: qual payload foi
consultado, quando, com qual resultado, quais atributos mudaram e quais municípios estavam
associados àquela versão. O INMET permanece evidência externa; não altera a formulação de R.

## 2. Regras normativas

1. PostgreSQL/PostGIS é fonte de verdade. JSON é exportação e arquivo de intercâmbio.
2. Toda tentativa gera uma linha em `inmet_coletas`, inclusive falhas e feeds vazios.
3. Payload aceito é arquivado com SHA-256; snapshots distintos são append-only.
4. `avisos_meteorologicos_inmet` projeta o estado mais recente. Histórico reside em
   `inmet_avisos_versoes`.
5. Associação territorial é congelada por versão em `inmet_avisos_municipios`.
6. Ausência em feed ativo não significa cancelamento. Somente sinal explícito do provedor
   define `cancelado`; término da janela define `expirado`.
7. Falha de rede, validação ou persistência nunca prova ausência de avisos.
8. Estado público informa última coleta e desatualização. Padrão: 30 minutos.
9. Exclusão mútua usa advisory lock PostgreSQL compartilhado por CLI, API e agendador.
10. Cancelamento meteorológico não conclui episódio científico.
11. Dados legados sem prova de cancelamento recebem estado `indeterminado`.

## 3. Operações

- **Atualizar visualização:** navegador relê dados persistidos; não acessa INMET.
- **Sincronizar INMET:** `POST /api/v1/admin/inmet/sincronizar`, protegido por
  `Authorization: Bearer <METIS_ADMIN_TOKEN>`.
- **Agendamento:** 15 minutos por padrão, configurável por
  `METIS_INMET_INTERVAL_SECONDS`. AdaptaBrasil mantém ciclo independente.

Nunca inserir token administrativo em HTML ou JavaScript público.

## 4. API pública

| Rota | Finalidade |
|---|---|
| `GET /api/v1/inmet/status` | Última coleta, validade e status |
| `GET /api/v1/inmet/avisos` | Estado vigente/futuro persistido |
| `GET /api/v1/inmet/coletas?limite=50` | Trilha de auditoria |
| `GET /api/v1/inmet/avisos/{codigo}/versoes` | Evolução do aviso |
| `GET /api/v1/inmet/historico?...` | Consulta histórica paginada e filtrada |
| `GET /api/v1/municipios/{ibge}/evidencias` | Evidências municipais sob demanda |

## 5. Estados

- `ativo`: provedor não declarou cancelamento.
- `futuro`: ativo e ainda não iniciado.
- `vigente`: ativo dentro da janela temporal.
- `expirado`: ativo, mas janela terminou naturalmente.
- `cancelado`: cancelamento explícito do provedor.

## 6. Recuperação e reprodutibilidade

Cada versão referencia coleta e fingerprint SHA-256 de atributos normalizados. Uma versão é
acrescentada quando difere da versão imediatamente anterior, preservando inclusive A→B→A. Cada coleta
referencia hash e caminho do payload original. Episódios continuam vinculados à identidade
estável do aviso e preservam snapshots científicos definidos em METIS-DIR-EVID-001.
