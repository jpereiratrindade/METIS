# RESILIÊNCIA-SISTEMA-EXP-001 — Constituição do laboratório computacional do estado de referência

**Versão:** 0.1.0  
**Data:** 2026-10-28  
**Estágio da engenharia:** prova executável do núcleo de cálculo + visualizador web local  
**Estágio da ciência:** modelo candidato, NÃO validado empiricamente  
**Estágio dos dados:** sem integração de micro/agregados oficiais; apenas fixtures sintéticas no pacote  
**Princípio:** Sempre pronto. Sempre incompleto!

## 1. Propósito

Materializar uma experiência territorial com 497 municípios do RS, permitindo calcular, representar, explicar, confrontar e rever o estado experimental de referência da resiliência como função das dimensões Ecológica (E), Produtiva (P) e Social (S). O sistema não equipara um índice de condições a capacidade observada de recuperação após choque. Uma etapa posterior deverá avaliar eventos, persistência, reorganização e trajetórias.

### Princípio de modelagem

\[R_m(t;\theta,v)=E_m(t;\theta_E,v)\,[P_m(t;\theta_P,v)+S_m(t;\theta_S,v)]\]

- E > 0; E = 1 é o elemento neutro; abaixo de 1 atenua; acima de 1 amplifica.
- P e S >= 0; escalas experimentais [0,50]; R >= 0 e pode exceder 100, sem teto artificial.
- Valor menor que a unidade é *fator multiplicativo de atenuação*, equivalente à divisão por seu inverso; multiplicar por 0,7 equivale a dividir por 1/0,7 ≈ 1,4286, **não** dividir por 0,7.
- θ inclui limites de normalização, funções e coeficientes. v identifica o modelo, impedindo reinterpretação silenciosa de resultados.
- R não é uma probabilidade e não tem interpretação causal automática.

## 2. Primeiro recorte: Censo Agropecuário 2017

O primeiro conjunto usa **exclusivamente variáveis do Censo Agropecuário 2017**, com denominadores pertencentes ao universo dos *estabelecimentos agropecuários*. Assim, o índice é **agroterritorial**, não retrata integralmente a sociedade nem a ecologia municipal. Acessibilidade municipal, saúde, educação, renda de toda a população e dinâmica dos ecossistemas além dos estabelecimentos estão ausentes nesta versão.

| Dimensão | Dado bruto e unidade | Tabela candidata SIDRA | Operação protótipo | Limite do proxy |
|---|---|---|---|---|
| E | Área dos estabelecimentos (ha); pastagens naturais (ha); matas e florestas naturais (ha) | **6881** | `e = (pastagem_natural + mata_natural) / area_estabelecimentos`; `E = 0.5 + e` | Classe de uso da terra NÃO é medida de integridade ecológica, diversidade ou conservação; não inclui toda a área municipal |
| P | Valor da produção dos estabelecimentos (R$ correntes de 2017) | **6898** | `L=log1p(valor_producao_reais / area_estabelecimentos)`; `P=50×clamp((L−q10)/(q90−q10),0,1)` | Valor por hectare não é sustentabilidade, eficiência física, renda líquida ou estabilidade da produção |
| S | Total de estabelecimentos, com orientação técnica e com produtor associado | **6780, 6848, 6773** (verificar categorias exatas) | `S=25×(N_orientados/N_estab+N_associados/N_estab)` | Captura organização/acesso agroinstitucional, NÃO bem-estar social amplo |

**Atenção à seleção no SIDRA:** tabelas e temas acima foram identificados, porém códigos de variável, classificações, totais, unidades e categorias precisam de uma consulta de metadados e homologação **antes** de construir o primeiro arquivo municipal oficial. Cada numerador deve referir o mesmo universo e ano que seu denominador. Não somar categorias potencialmente sobrepostas; não duplicar valor de produção animal e vegetal se houver total. Conferir se *associação do produtor* é medida como número de estabelecimentos, e se orientação técnica do produtor/estabelecimento é identificada sem contagem dupla por origens distintas. Na dúvida, registrar lacuna e não pontuar.

### Regras de cálculo nesta prova

- `E = 0.5 + clamp((pastagem_natural + mata_natural)/area_total,0,1)`; esperado intervalo [0.5,1.5].
- `P = 50 * clamp((log1p(VP/area) - q10)/(q90-q10),0,1)`; q10 e q90 calculados sobre os municípios com dados válidos no conjunto de referência. Se q10=q90, usar P=25 como convenção **não discriminante**, com ressalva no manifesto.
- `S = 25*(orientados/total_estabelecimentos + associados/total_estabelecimentos)`.
- `R=E*(P+S)` sem cap em 100. Não interpretar 100 como limite máximo ou meta.
- Se falta numerador, denominador ou valor válido, registrar `dados_incompletos` e R nulo. Se partes excedem totais, `inconsistencia`. Zero observado é zero; zero ausente NÃO é zero.
- Para comparação temporal posterior, preservar os **mesmos q10/q90 de referência**, unidades monetárias comparáveis (deflacionar antes da normalização), conceitos censitários compatíveis, malha territorial versionada e função versão imutável.

### Um problema de escala que não pode ser escondido

A soma de pastagens naturais e matas naturais considera ambos como favoráveis, inclusive no Pampa. Isso evita presumir que somente floresta é ecologicamente positiva. Contudo, extensão de pastagem natural não garante estado de conservação do campo nativo, assim como o registro de mata natural não mede sua condição ambiental. A função E deve evoluir com composição, qualidade, conservação, pressões, conectividade, solo, clima e contexto do bioma — observáveis externos futuros, inclusive MapBiomas, dados experimentais e sensoriamento remoto, com origem e metodologia próprias.

## 3. Base territorial e relação com sistemas existentes

**TERRITÓRIO-RS**: serviço independente de referência que fornece 497 municípios por geocódigo IBGE string (sete dígitos, UF 43), geometria versionada, eventualmente COREDE/RF/bioma. **RESILIÊNCIA** consome seu contrato — não deve incorporar listas próprias ad hoc, nem assumir dados ambientais municipais homologados em base preliminar.

**SisTer / AlertaSD**: fontes futuras de séries de uso da terra, NDVI, relevo e informação H3, com escala e incerteza declaradas; a granularidade H3 não deve ser automaticamente atribuída ao município sem agregação espacial validada.

**MORFO / SisTer-Git**: referências de identidade visual e de práticas de revisão, rastreabilidade, contratos de API e versionamento. A aplicação Resiliência é independente; não altera nem exige abertura de portas dos serviços existentes.

**MPRR**: organizar o ciclo observar / deslocar / relacionar / problematizar / confrontar / reposicionar, separando dados, hipóteses, decisões e resultados. O sistema **não** representa resiliência total do ecossistema como mero fenômeno de software; sua própria infraestrutura também precisa ser testável e revisável.

## 4. Arquitetura pretendida

```text
        [ IBGE SIDRA 2017: 6881 / 6898 / 6780 / 6848 / 6773 ]
                       |
             [ aquisição verificável ]
                       |
            [ arquivos brutos + SHA256 ]
                       |
       [ adaptadores por tabela/categoria/unidade ]
                       |
       [ catálogo TERRITÓRIO-RS: 497 municípios ]
                       |
            [ validação e harmonização ]
                       |
      [ banco local SQLite: snapshot + proveniência ]
                       |
     +-----------------+-----------------+
     |                                   |
[ núcleo C++26 de funções E/P/S/R ]  [ registros de experimentos ]
     |                                   |
     +-----------------+-----------------+
                       |
        [ API REST C++ de leitura / exportação ]
                       |
 [ Home + dashboard mapa por dimensão + história de versões ]
```

**Material implementado neste pacote:** `resiliencia_core`, `resiliencia-rs` CLI, testes CTest, interface web sem dependências externas para carregar CSV calculado e GeoJSON. **Ainda não implementado:** importador SIDRA direto, armazenamento SQLite, servidor/API, gestão de múltiplos experimentos, série temporal, registro de auditoria persistido. Isso não é anunciado como concluído.

O frontend pode evoluir para React/Vite + Leaflet ou MapLibre, preservando a identidade visual compartilhada. Backend e regras científicas permanecem em **C++26**. Sem PHP.

## 5. Contratos planejados (NÃO implementados ainda)

| Rota | Responsabilidade |
|---|---|
| `GET /v1/health` | Versões do sistema e integridade do snapshot |
| `GET /v1/territorio/municipios` | Catálogo e geocódigos do serviço territorial |
| `GET /v1/modelos` | Versões, equações, parâmetros e metadados |
| `GET /v1/datasets` | Fontes, datas, anos e cobertura |
| `GET /v1/estados?modelo=EPS-REF-001&referencia=2017&dimensao=R` | Estados dos municípios e lacunas |
| `GET /v1/municipios/{ibge}/evidencias` | Numeradores, denominadores e proveniência |
| `GET /v1/experimentos/{id}/relatorio` | Auditoria, comparação e status epistêmico |

Uma resposta de estado deve trazer `municipio_ibge`, `referencia`, `modelo_id`, `calibracao_id`, `E`, `P`, `S`, `R`, `status`, `fonte`, `conjunto` e `evidencias` (quando existirem). Nunca exibir uma nota sem tornar verificáveis suas origens.

## 6. Home e dashboard

**Home:** visão geral, ano e proveniência ativos, total 497, disponibilidade de dados, distribuição não ponderada das notas com ressalva, resultados calculáveis, pendências e modelo em vigor.

**Mapa municipal:** mapa único com quatro camadas opcionais: `R`, `E`, `P`, `S`, sem interpolação fictícia. Clique exibe valor bruto, transformação, anos, unidade, status e data de aquisição. Municípios incompletos são cinza (não recebem zero). Fonte geográfica: Malha Municipal IBGE 2022 (SIRGAS 2000) para uma referência territorial explícita. Em comparações históricas, controlar mudanças territoriais.

**Tempo:** nesta versão, apenas 2017. O seletor temporal será habilitado somente quando existirem *dois períodos compatíveis* e plenamente rastreados. Não produzir uma curva contínua misturando Censo Agro 2017 com Demográfico 2022 como se ambos descrevessem o mesmo instante.

**Camada de entendimento:** explicitar o fato de índice, hipóteses candidatas e limites de interpretação. Resiliência é conceito relacional e processual; um escalar pode representar um estado de referência, mas não o esgota.

## 7. Invariantes para homologação inicial

| Dimensão | Evidência exigida |
|---|---|
| Territorial | Exatamente 497 municípios; códigos 43xxxxx únicos; geometria e números do mesmo catálogo; nenhuma área operacional contada como município |
| Científica | Equação `R=E(P+S)` fiel; E>0; E=1 neutro; P,S>=0; sem saturação escondida; parâmetros versionados |
| Estatística | 2017; unidades, categorias e totais reconciliados; sem agregação cruzada indevida; ausente != zero |
| Proveniência | Arquivos brutos, URL, data de obtenção, hash SHA-256, transformações, variáveis/categorias SIDRA, versão da malha, compilador e versão do código |
| Software | CMake build C++26; CTest; sem PHP; offline em execução; serviço read-only por padrão quando implementado |
| Epistemológica | Rótulo *experimental* até análise de sensibilidade, confronto com fatos e exame externo; não afirmar resiliência observada |

## 8. Experimentos mínimos e critério de pronto

**EXP-001-A — Fator multiplicador:** com P=35 e S=30, E=0,7 deve produzir R=45,5; E=1 produz 65; E=1,3 produz 84,5. Passível de reprodução automática no teste C++.

**EXP-001-B — Robustez dos insumos:** zero e ausente distintos; ano não suportado é rejeitado; código duplicado é rejeitado; incoerência (área natural maior que área total, orientados acima do total) é marcada.

**EXP-001-C — Abrangência:** modo normal falha se forem fornecidos menos de 497 municípios; `--prototype` permite testes sintéticos explicitamente identificados.

**EXP-001-D — Sensibilidade:** comparar ranks com/sem fator E e funções alternativas, sem tratar ranking como propriedade intrínseca dos municípios. **Pendente**.

**EXP-001-E — Confronto:** pesquisar eventos conhecidos e evidências independentes de reação e reorganização dos sistemas socioecológicos. **Pendente**.

Nesta entrega, a condição "pronto" diz respeito ao **núcleo operacional do protótipo e à interface de exploração local**, não à disponibilização de 497 notas oficiais ou à validação da resiliência.

## 9. Links e fontes primárias

- [IBGE — Censo Agropecuário 2017](https://www.ibge.gov.br/estatisticas/economicas/agricultura-e-pecuaria/21814-2017-censoagropecuario.html)
- [SIDRA — Uso da terra, tabela 6881](https://sidra.ibge.gov.br/tabela/6881)
- [SIDRA — Valor da produção, tabela 6898](https://sidra.ibge.gov.br/tabela/6898)
- [SIDRA — Orientação técnica, tabela 6780](https://sidra.ibge.gov.br/tabela/6780)
- [SIDRA — Orientação e associação, tabela 6848](https://sidra.ibge.gov.br/tabela/6848)
- [SIDRA — Associação, tabela 6773](https://sidra.ibge.gov.br/tabela/6773)
- [IBGE — Malha Municipal 2022, RS](https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2022/UFs/RS/RS_Municipios_2022.zip)
- [IBGE — Documentação malhas territoriais](https://www.ibge.gov.br/geociencias/organizacao-do-territorio/malhas-territoriais/15774-malhas.html)

**Nota de procedência:** URLs referem recursos oficiais; este pacote não incorpora downloads oficiais porque não foi possível executá-los no ambiente desta elaboração. A identificação das tabelas não substitui auditoria dos metadados e dos dados originais.

## 10. Prioridade do próximo incremento (v0.2.0)

Criar importador C++26 nativo das extrações SIDRA selecionadas, `metadata.csv` por variável/categoria/unidade, conferência de 497 geocódigos via TERRITÓRIO-RS, hash por fonte, instantâneo transacional SQLite, elaboração do CSV completo, servidor C++ somente leitura e visualização automática. Só então divulgar cartografia quantitativa municipal com notas reais e incerteza documentada.
