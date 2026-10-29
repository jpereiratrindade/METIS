# MÉTIS — Marco Legal Brasileiro, Governança de Dados e Responsabilidade Científica
**Documento:** METIS-DIR-LEG-001  
**Versão:** 1.0.0  
**Data:** 29/10/2026  
**Natureza:** Diretriz normativa de conformidade legal, governança de dados e salvaguardas éticas  
**Status:** Vigente e Homologado  

---

## 1. Identificação e Natureza Jurídico-Institucional

O **MÉTIS** é um laboratório computacional científico público e aberto integrado ao **Ecossistema SisTer**, concebido para formular, parametrizar, simular, confrontar e revisar hipóteses sobre relações entre condições ecológicas, produtivas e sociais e a capacidade adaptativa de sistemas agroterritoriais.

Por sua natureza estritamente acadêmica, investigativa e aberta, suas operações de software, tratamento de dados e disponibilização pública de interfaces orientam-se pelos preceitos do ordenamento jurídico brasileiro, com ênfase nas seguintes legislações:

1. **Lei Geral de Proteção de Dados Pessoais (LGPD)** — Lei Federal nº 13.709/2018.
2. **Lei de Acesso à Informação (LAI)** — Lei Federal nº 12.527/2011.
3. **Lei do Governo Digital e Transparência de Dados** — Lei Federal nº 14.129/2021 e Decreto Federal nº 8.777/2016 (Política de Dados Abertos do Poder Executivo Federal).
4. **Marco Civil da Internet** — Lei Federal nº 12.965/2014 e Decreto Federal nº 8.771/2016.
5. **Legislação de Propriedade Intelectual e Software** — Lei Federal nº 9.609/1998 (Proteção da Propriedade Intelectual de Programas de Computador) e Lei Federal nº 9.610/1998 (Direitos Autorais).
6. **Marco Legal da Ciência, Tecnologia e Inovação** — Lei Federal nº 13.243/2016 e Emenda Constitucional nº 85/2015.

---

## 2. Conformidade com a Lei Geral de Proteção de Dados (LGPD — Lei nº 13.709/2018)

### 2.1. Não Tratamento de Dados Pessoais (Art. 5º, I e Art. 12)
O MÉTIS opera **exclusivamente com dados públicos estatísticos agregados por município**. 
- Nos termos do **art. 5º, inciso I da LGPD**, dado pessoal é a *informação relacionada a pessoa natural identificada ou identificável*.
- Conforme o **art. 12 da LGPD**, *os dados anonimizados não serão considerados dados pessoais para os fins desta Lei*.
- As bases consumidas (Censo Agropecuário 2017 do IBGE / plataforma SIDRA) apresentam valores consolidados para o conjunto de cada um dos 497 municípios do Rio Grande do Sul (ex: área total de estabelecimentos, valor global da produção, número total de propriedades assistidas).
- O sistema **não coleta, não armazena e não processa** nomes, CPFs, coordenadas geográficas de sedes privadas, dados de produtores individuais, endereços ou qualquer outro atributo capaz de reidentificar indivíduos ou famílias rurais.

### 2.2. Princípio da Privacidade por Padrão e por Design (*Privacy by Design & by Default*)
- **Acesso Universal sem Cadastro:** Conforme definido na diretriz `METIS-OPEN-001`, o acesso a todas as ferramentas, dashboards, mapas e APIs públicas dispensa autenticação, login, e-mail ou criação de conta.
- **Ausência de Rastreadores (Tracking):** As páginas web do MÉTIS não utilizam cookies analíticos intrusivos de terceiros, pixels de rastreamento de redes sociais, impressão digital de navegador (*browser fingerprinting*) ou armazenamento local de dados com finalidade publicitária ou de perfilamento de usuários.
- **Armazenamento de Sessão Transparente:** As preferências selecionadas pelo usuário durante o uso do dashboard (como município ativo ou valores de parâmetros experimentais) residem temporariamente na memória volátil do navegador ou em `localStorage` estritamente técnico e local, nunca sendo transmitidas a servidores remotos para perfilamento.

### 2.3. Não Aplicação de Decisões Automatizadas Vinculantes (Art. 20)
O MÉTIS não realiza decisões automatizadas individuais ou coletivas de efeito jurídico, creditício, fiscal ou sancionatório (ver Seção 6).

---

## 3. Lei de Acesso à Informação (LAI — Lei nº 12.527/2011) e Política de Dados Abertos

O MÉTIS adere integralmente aos princípios de transparência pública ativa:

### 3.1. Transparência Ativa e Acesso Irrestrito (Art. 8º e Art. 10, § 3º da LAI)
- O art. 10, § 3º da LAI veda *quaisquer exigências relativas aos motivos determinantes da solicitação de informações de interesse público*, bem como identificações prévias que limitem o acesso.
- No MÉTIS, qualquer cidadão, gestor público, pesquisador ou organização pode acessar, inspecionar, auditar e baixar tanto os dados censitários brutos quanto os resultados calculados e equações aplicadas, sem necessidade de justificação de motivo.

### 3.2. Formatos Abertos, Estruturados e Legíveis por Máquina (Decreto nº 8.777/2016 e Lei nº 14.129/2021)
Em atendimento aos padrões da Infraestrutura Nacional de Dados Abertos (INDA):
- **Formatos Não-Proprietários:** Todos os conjuntos de dados são disponibilizados em formatos de especificação pública aberta (`.csv`, `.json`, `.geojson`, `.svg`).
- **APIs Abertas:** Distribuição de metadados, resumos em linguagem acessível e achados de pesquisa via rotas REST estáticas abertas (`GET /api/public/*`).
- **Manifestos de Integridade Científica:** Todo cálculo exportado inclui um arquivo de manifesto (`.manifest.json`) com parâmetros utilizados, identificação da versão formal do modelo e soma de verificação (hash de integridade).

---

## 4. Direitos Autorais, Licenciamento Livre e Atribuição de Fontes Oficiais

### 4.1. Código-Fonte Aberto (Software Livre sob GNU GPL v3.0)
- O código-fonte integral do MÉTIS (núcleo matemático em C++26, scripts de processamento e interfaces web) é distribuído sob a licença **GNU General Public License v3.0 (GPL v3.0)**.
- Essa licença assegura as quatro liberdades fundamentais do software livre: liberdade de executar, estudar e modificar o programa, bem como de redistribuir cópias ou versões modificadas, garantindo que o conhecimento desenvolvido permaneça perpetuamente em domínio público compartilhado (*copyleft*).

### 4.2. Atribuição de Autoria das Fontes Censitárias Oficiais (IBGE)
- As variáveis agropecuárias e malhas cartográficas utilizadas pelo MÉTIS têm como fonte primária o **Instituto Brasileiro de Geografia e Estatística (IBGE)**, autarquia federal brasileira.
- O uso e citação dessas informações obedecem às normas de atribuição e integridade previstas na Lei nº 9.610/1998 e nos termos de uso público das informações estatísticas do IBGE.
- **Bases Homologadas:**
  - *Censo Agropecuário 2017:* Tabelas SIDRA nº 6881 (uso das terras), 6898 (valor da produção agropecuária), 6780 (orientação técnica) e 6773 (cooperativismo).
  - *Malha Municipal Digital do Brasil:* Municípios do Estado do Rio Grande do Sul (UF 43), geocódigos oficiais de 7 dígitos.
- **Ressalva Estatística:** O MÉTIS não altera nem distorce os valores apurados e publicados pelo IBGE. Casos em que dados censitários não foram divulgados pelo IBGE (por sigilo estatístico ou ausência de declaração) são preservados como `dados_incompletos`, sem atribuição arbitrária de valor zero.

---

## 5. Marco Legal da Ciência, Tecnologia e Inovação (Lei nº 13.243/2016) e Ciência Aberta

Em conformidade com as diretrizes internacionais e nacionais de **Ciência Aberta (Open Science)** e com o Marco Legal de CT&I:
1. **Princípios FAIR:** Os dados e modelos do laboratório foram estruturados para serem:
   - *Findable* (Localizáveis): rotas bem documentadas, identificadores canônicos para modelos e municípios.
   - *Accessible* (Acessíveis): protocolos HTTP padrão, sem barreiras de autenticação ou chaves proprietárias.
   - *Interoperable* (Interoperáveis): formatos universais padronizados (JSON, CSV).
   - *Reusable* (Reutilizáveis): licença GPL v3.0 clara, metadados de proveniência completos e versionamento estrito.
2. **Auditabilidade Epistêmica:** Qualquer pesquisador pode reproduzir localmente os cálculos executando o binário nativo compilado em C++26 contra as bases homologadas, atestando a reprodutibilidade dos resultados publicados.

---

## 6. Cláusula de Responsabilidade e Salvaguardas Éticas (Scientific Disclaimer)

### 6.1. Natureza Exploratória e Hipotética das Pontuações
> **Aviso Científico e Regulatório Fundamental:**  
> Os indicadores calculados pelo MÉTIS ($R, E, P, S$) constituem **índices computacionais experimentais** destinados ao teste, comparação e falseabilidade de hipóteses teóricas sobre sistemas socioecológicos.  
> **Eles não constituem medidas empiricamente validadas de resiliência territorial real.**

### 6.2. Vedação de Uso para Decisões Administrativas Vinculantes e Sancionatórias
Em respeito aos princípios do devido processo legal e razoabilidade:
1. **Não-utilização como base creditícia:** As pontuações geradas pelo MÉTIS **não devem ser utilizadas de forma isolada** como critério para concessão, negação ou gradação de crédito rural (como Pronaf, Pronamp ou linhas de financiamento de bancos públicos e privados).
2. **Não-utilização para sanções fiscais ou tributárias:** Os valores de densidade monetária ou indicadores não equivalem a lucro tributável, produtividade agronômica plena ou conformidade com função social da propriedade rural.
3. **Não-utilização para decisões sancionatórias ambientais:** O indicador $E$ é baseado estritamente na declaração censitária de áreas de matas e pastagens naturais dos estabelecimentos e não substitui diagnósticos de campo, imagens de sensoriamento remoto em alta resolução, Cadastro Ambiental Rural (CAR) ou fiscalização oficial dos órgãos ambientais (IBAMA, FEPAM, Secretarias de Meio Ambiente).

### 6.3. Diretriz Expressa Anti-Ranqueamento Territorial
- Em conformidade estrita com as diretrizes `METIS-DIR-MUN-001` e `METIS-OPEN-001`, o MÉTIS **proíbe a geração e divulgação de rankings competitivos entre municípios**.
- O sistema não ordena municípios de "melhor para pior" nem premia ou estigmatiza territórios.
- A divergência entre resultados decorrentes de diferentes modelos matemáticos expressa os limites teóricos e a sensibilidade de cada formulação, devendo servir como convite ao aprofundamento investigativo interdisciplinar.

---

## 7. Canal de Contato e Governança

Para esclarecimentos metodológicos, reporte de inconsistências em dados censitários ou questões relativas à governança de dados:
- **Repositório do Código e Documentos:** `https://github.com/jpereiratrindade/METIS`
- **Ecossistema:** SisTer (SisTer, MORFO, SisTer-Git)
- **Regime de Governança:** Revisão por pares, controle de versões Git e abertura comunitária.
