# MÉTIS — Diretriz de Reorientação Metodológica
**Documento:** METIS-DIR-MUN-001  
**Versão proposta:** 0.1.0  
**Data:** 28/10/2026  
**Natureza:** Orientação científica e técnica para implementação  
**Prioridade:** Alta  

## 1. Decisão metodológica

O MÉTIS deverá adotar, nesta etapa de desenvolvimento, o **município como unidade individual de investigação**, sem utilizar os resultados de outros municípios para determinar suas pontuações.

A finalidade do sistema permanece inalterada: constituir um laboratório computacional para formular, parametrizar, experimentar, confrontar e revisar hipóteses sobre as relações entre condições ecológicas, produtivas e sociais e a resiliência de sistemas agroterritoriais.

Não pretendemos estabelecer uma classificação dos municípios gaúchos nem identificar quais seriam mais ou menos resilientes.

Pretendemos investigar, para cada município, como determinadas características e relações poderiam contribuir para sua capacidade de responder a perturbações.

### Princípio obrigatório

> A alteração dos dados de outro município não poderá modificar o resultado calculado para o município em análise, mantendo-se constantes seus próprios dados, a versão do modelo e seus parâmetros experimentais.

Esta condição deverá ser verificável por testes automatizados.

## 2. Preservação da hipótese original

Manter a formulação experimental:

\[
R_m = E_m(P_m + S_m)
\]

Na qual:

- **E:** representação experimental da dimensão ecológica, com função multiplicadora.
- **P:** representação experimental da dimensão produtiva.
- **S:** representação experimental da dimensão social.
- **R:** indicador experimental resultante das relações hipotetizadas.

A escolha de E como multiplicador é intencional e constitui uma hipótese científica a ser investigada.

Não alterar essa estrutura sem a formulação explícita de uma nova hipótese e seu respectivo versionamento.

Os resultados não devem ser apresentados como medidas empiricamente validadas de resiliência.

## 3. Remoção da normalização intermunicipal

### 3.1. Dimensão produtiva

Remover da implementação ativa a utilização dos percentis q10 e q90 calculados a partir dos municípios do Rio Grande do Sul.

A expressão atual:

\[
P_m = 50\operatorname{clip}\left(\frac{\ln(1+d_m)-q_{10}}{q_{90}-q_{10}},0,1\right)
\]

deixará de ser a formulação ativa para a análise municipal.

Preservar o observável original:

\[
d_m = \frac{VP_m}{A_m}
\]

Onde VP representa o valor da produção e A a área dos estabelecimentos agropecuários.

A variável \(d_m\), expressa em R$/ha, será identificada como **densidade monetária da produção**, e não como medida direta de produtividade física ou resiliência.

### 3.2. Nova parametrização de P

A equipe deverá implementar a possibilidade de testar funções de transformação que utilizem exclusivamente os dados do município e parâmetros experimentais explicitamente declarados.

Uma função candidata, apenas para experimentação, é:

\[
P_m(k) = 50\frac{d_m}{d_m+k},\qquad k>0
\]

Nessa formulação, \(k\) possui unidade R$/ha e representa um parâmetro de escala definido pela hipótese experimental, não pela distribuição dos municípios.

O parâmetro não deve receber um valor arbitrário oculto. Sua escolha deverá ser registrada, justificada e submetida a análise de sensibilidade.

Não presumir que essa função seja cientificamente superior à anterior.

Até a definição de uma parametrização válida para determinado experimento, apresentar os dados produtivos observados e indicar P e R como não calculados nessa configuração. Não substituir valores ausentes por zero.

### 3.3. Dimensões E e S

Preservar provisoriamente suas formulações atuais, pois utilizam proporções calculadas a partir de dados do próprio município.

Documentar suas limitações e manter aberta a possibilidade de futuras parametrizações.

## 4. Adequação da interface territorial

Preservar o mapa SVG do Rio Grande do Sul, a seleção de municípios, a busca por nome ou código IBGE e o zoom municipal.

O mapa passará a funcionar prioritariamente como instrumento de **localização, seleção e contextualização territorial**, não como classificação dos municípios por desempenho.

Remover da experiência ativa:

- Mapas coropléticos que classifiquem municípios pelos valores de R, E, P ou S.
- Médias estaduais de R e rankings municipais.
- Referências comparativas aos melhores ou piores municípios.
- Legendas ou textos que interpretem P como posição relativa na distribuição estadual.

Preservar a possibilidade de consultar os 497 municípios individualmente.

A seleção de um município deverá abrir um ambiente analítico específico, contendo seus dados observados, dimensões experimentais, parâmetros, equações, resultados e limitações.

## 5. Estrutura proposta para a análise municipal

Organizar a interface em quatro áreas:

**A — Observações do município**  
Dados de origem, ano, unidades, abrangência territorial, valores censitários e respectivos metadados.

**B — Parametrização experimental**  
Funções selecionadas para E, P e S, valores dos parâmetros e justificativas.

**C — Hipótese relacional**  
Equação selecionada para R, permitindo futuramente experimentar outras funções sem alterar os dados observados.

**D — Resultados e confronto**  
Resultados produzidos, comportamento diante da alteração de parâmetros, incertezas, limitações e registro de hipóteses alternativas.

O usuário deverá conseguir diferenciar visualmente observações, transformações matemáticas e interpretações científicas.

## 6. Arquivos e componentes a revisar

**Núcleo de cálculo**
- `src/model.cpp`: desacoplar P da calibração estadual.
- `include/resiliencia/model.hpp`: adequar os contratos de dados e parâmetros.
- `src/main.cpp`: atualizar execução, resultados e manifestos de proveniência.

**Interface web**
- `web/app.js`: retirar o uso ativo de q10/q90, textos comparativos, médias e coloração classificatória.
- Componentes HTML e CSS: preservar a exploração municipal e implementar a configuração das hipóteses.

**Documentação e testes**
- `tests/test_model.cpp`: ampliar os testes de cálculo e invariância municipal.
- `docs/EXPLORACAO-TERRITORIAL_v0.1.1.md`: registrar a revisão metodológica em nova versão.
- `README.md`: atualizar a descrição científica e funcional do MÉTIS.

Preservar os arquivos de dados originais do Censo Agropecuário 2017.

Não sobrescrever os resultados do modelo anterior. Preservá-los com seus manifestos para garantir rastreabilidade e reprodução dos experimentos históricos.

## 7. Critérios de aceite

A implementação somente será considerada concluída quando:

1. O cálculo do município A produzir o mesmo resultado independentemente da presença ou alteração dos dados dos municípios B, C ou D, mantendo-se os mesmos parâmetros.
2. Nenhuma função ativa de P depender de percentis, médias, mínimos ou máximos calculados sobre outros municípios.
3. As funções de transformação e seus parâmetros estiverem explícitos e versionados.
4. O mapa permitir a navegação e análise individual, sem induzir interpretações classificatórias.
5. A hipótese \(R=E(P+S)\) permanecer disponível e reproduzível.
6. A interface distinguir dados observados, indicadores transformados e resultados hipotéticos.
7. Alterações nos parâmetros de um experimento puderem ser executadas sem modificar os dados originais.
8. Resultados anteriores permanecerem preservados, identificados e reproduzíveis.
9. Testes automatizados verificarem dados ausentes, parâmetros inválidos, valores extremos e independência entre municípios.
10. A documentação declarar explicitamente que a resiliência ainda não foi validada empiricamente.

## 8. Orientação de execução

Implementar a alteração em uma nova branch, mediante revisão por pull request, sem modificar diretamente a versão histórica do modelo.

Recomenda-se registrar a mudança metodológica em uma nova versão experimental do MÉTIS, com identificação própria para as funções de parametrização.

A implementação deverá preservar os princípios de governança leve, rastreabilidade científica e reprodutibilidade já adotados no ecossistema LABECO.

**Diretriz final**

O MÉTIS não deverá atribuir a um município uma condição de resiliência porque ele apresenta valores superiores ou inferiores aos de outros municípios.

Seu papel será investigar, dentro de cada sistema agroterritorial municipal, as relações que sustentam hipóteses sobre resiliência, reconhecendo que essas hipóteses precisarão ser confrontadas com evidências históricas e respostas observadas a perturbações.

**Sempre pronto. Sempre incompleto.**
