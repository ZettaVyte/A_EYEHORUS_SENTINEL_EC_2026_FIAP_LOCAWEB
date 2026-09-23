# 👁️ A-EYEHORUS SENTINEL

**FIAP Enterprise Challenge - Sprint 4 | Parceiro: Locaweb**

O **A-EYEHORUS SENTINEL** é um pipeline completo de AIOps (Artificial Intelligence for IT Operations) projetado para transformar a gestão de incidentes de TI de um modelo reativo para uma operação preditiva e prescritiva.

Através da combinação de engenharia de dados, modelos matemáticos e Inteligência Artificial Generativa, a solução antecipa gargalos operacionais, prevê o volume de chamados, identifica riscos de quebra de OLA (Operational Level Agreement) no "minuto zero" e prescreve ações corretivas em tempo real.

---

## 🎯 Objetivos e Entregas de Valor

* **Previsão de Demanda (Macro):** Estima o volume futuro de incidentes no curto e médio prazo (D+1 e D+7) cruzando o histórico com a "pressão operacional" das equipes e calendário de feriados.
* **Guardião de OLA (Micro):** Analisa a abertura de cada novo chamado crítico (P2 e P3) e detecta com **79% de precisão (Recall)** o risco de estouro de prazo.
* **Análise de Causa Raiz (Clusterização):** Isola os ofensores crônicos da operação (ex: *Team05* focado na *cat76*; *Team11* com tempo de fila de 175 horas).
* **War Room Guiado por IA:** Integração com LLM (Llama-3.1) para leitura do contexto dos incidentes críticos e geração de recomendações de mitigação para os Analistas de Suporte.

---

## 🛠️ Arquitetura e Tecnologias Utilizadas

A arquitetura foi desenhada em formato de microsserviços modulares em Python, integrando armazenamento em nuvem e Data Viz:

* **Linguagem:** Python 3.13
* **Processamento de Dados:** Pandas, NumPy
* **Machine Learning:** Scikit-Learn (K-Means) e XGBoost (Classifier e Regressor)
* **Inteligência Generativa (LLM):** Groq API (Modelo: `gpt-oss-120b`)
* **Banco de Dados:** Oracle Autonomous Database (Cloud) via SQLAlchemy e oracledb
* **Visualização:** Microsoft Power BI

---

## 📂 Estrutura do Repositório

O projeto está dividido em duas frentes: **Notebooks** (onde a exploração e descoberta de dados ocorreu) e **Produção** (scripts refatorados para deploy).

```text
📁 A-EYEHORUS_SENTINEL
│
├── 📁 notebooks/             # Notebooks originais de pesquisa e testes
│   ├── lab_for_ETL.ipynb               # Exploração inicial e regras de negócio de KPI
│   ├── EDA_ARIMA_Prophet.ipynb         # Testes preditivos iniciais (séries temporais)
│   ├── XGBoost_Kmeans.ipynb            # Feature Eng., treinamento XGBoost e K-Means
│   └── integracao_llm.ipynb            # Testes e refinamento de prompts com a Groq API
│
├── 📁 Pipeline_Producao/             # Scripts executáveis do ecossistema final
│   ├── config.py                       # Gestão de credenciais (Oracle e Groq)
│   ├── 01_etl_nuvem.py                 # Ingestão, limpeza e carga da base original no ADB
│   ├── 02_motor_preditivo.py           # ML Pipeline: Lags, XGBoost (D+1/D+7/OLA) e K-Means
│   └── 03_war_room_llm.py              # LLM Pipeline: Consulta ao Llama-3.1 e upload final
│
├── .env.example                        # Exemplo do arquivo de variáveis de ambiente
├── requirements.txt                    # Dependências do projeto
├── run_pipeline.py                     # Orquestrador mestre para execução sequencial
└── EC_Sprint_4_Apresentacao.pptx       # Pitch Deck e defesa do projeto

```

---

## 🚀 Como Executar o Pipeline de Produção

### 1. Pré-requisitos

Certifique-se de ter o Python 3.13+ instalado e instale as dependências do projeto:

```bash
pip install -r requirements.txt

```

### 2. Configuração de Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto (use o `.env.example` como base) e insira suas credenciais:

```text
DB_USER=seu_usuario_oracle
DB_PASSWORD=sua_senha_oracle
API_GROK_KEY=sua_chave_api_groq

```

*Nota: A Wallet do Oracle Cloud deve estar extraída e mapeada no caminho correspondente no arquivo `config.py`.*

### 3. Execução

Para rodar a solução de ponta a ponta, simulando a operação em produção, execute o orquestrador na raiz do projeto:

```bash
python run_pipeline.py

```

O console exibirá o log de cada etapa:

1. Limpeza dos dados em Excel e envio da `TB_INCIDENTES_LOCAWEB` para a nuvem.
2. Treinamento em lote, predição e inserção da `TB_PREVISAO_DIARIA` e `TB_RISCO_EQUIPE`.
3. Análise da IA Generativa e inserção final da `TB_ALERTAS_ITSM_IA` pronta para o consumo do Power BI.

---

## 👨‍💻 Autor

**Vitor Fernandes Antunes**

* **RM:** 563053
* **Curso:** Superior de Tecnologia em Data Science
* **Instituição:** FIAP