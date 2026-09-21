import time
import warnings

import pandas as pd
from config import API_GROQ_KEY, conectar_oracle
from dotenv import load_dotenv
from groq import Groq
from sqlalchemy import create_engine
from sqlalchemy.dialects.oracle import NUMBER, TIMESTAMP, VARCHAR2

# Ignora avisos
warnings.filterwarnings('ignore')

# Inicializa o cliente da Groq
client = Groq(api_key=API_GROQ_KEY)

def gerar_recomendacao_aiops(equipe, categoria, prioridade):
    """
    Envia o contexto do incidente para o Llama-3 e retorna a recomendação prescritiva.
    """
    system_prompt = """
    Você é o 'A-EYEHORUS', uma Inteligência Artificial AIOps de nível Sênior atuando na Locaweb.
    Analise o alerta e forneça uma recomendação clara, direta e prescritiva.
    Aja como um gerente técnico orientando sua equipe. Indique qual deve ser a prioridade.
    Não use saudações, apenas forneça a ação. Mantenha o texto em no máximo 3 frases curtas.
    """
    
    user_prompt = f"""
    Alerta Crítico: Risco de quebra de OLA iminente.
    - Equipe Responsável: {equipe}
    - Categoria do Incidente: {categoria}
    - Prioridade: {prioridade}
    
    Prescreva a ação imediata.
    """
    
    try:
        # Fazendo a chamada para a API da Groq (usando o Llama 3.1 8B)
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="openai/gpt-oss-120b",  # Usando o modelo funcional mais recente
            temperature=0.6,
            max_tokens=150
        )
        
        # Extrai a resposta
        resposta = chat_completion.choices[0].message.content
        
        # Tratativa de segurança caso a resposta venha vazia
        if not resposta or resposta.strip() == "":
            return f"ALERTA A-EYEHORUS: Risco de quebra de OLA na equipe {equipe}. Escalar e priorizar fila no Kanban."
        else:
            return f"ALERTA A-EYEHORUS: {resposta.strip()}"
        
    except Exception as e:  # noqa: BLE001
        print(f"Erro na API Groq: {e}")
        return f"ALERTA A-EYEHORUS: Risco sistêmico ({categoria}). Investigar equipe {equipe} urgentemente."

def orquestrar_war_room():
    print("Iniciando o War Room A-EYEHORUS (Conectando ao Llama-3.1)...")
    
    # Carregar a base de alertas gerada pelo XGBoost
    try:
        df_alertas = pd.read_csv('TB_ALERTAS_ITSM.csv')
    except FileNotFoundError:
        print("Erro: Arquivo 'TB_ALERTAS_ITSM.csv' não encontrado. Certifique-se de que ele foi gerado pelo módulo preditivo.")
        return

    # Para o MVP, filtramos apenas os 10 incidentes mais críticos
    df_top_alertas = df_alertas.sample(min(10, len(df_alertas))).copy()
    
    recomendacoes = []
    for index, row in df_top_alertas.iterrows():
        equipe = row.get('NM_GRUPO_DESIGNADO', 'N/A')
        categoria = row.get('NM_CATEGORIA', 'N/A')
        prioridade = row.get('TP_PRIORIDADE', 'N/A')
        
        print(f"Analisando incidente da equipe {equipe} (Categoria: {categoria})...")
        
        texto_llm = gerar_recomendacao_aiops(equipe, categoria, prioridade)
        recomendacoes.append(texto_llm)
        time.sleep(1)  # Pausa para respeitar limites da API
        
    df_top_alertas['TEXTO_PRESCRITIVO_LLM'] = recomendacoes
    
    # Formata a data para o banco de dados Oracle
    df_top_alertas['DT_ABERTO'] = pd.to_datetime(df_top_alertas['DT_ABERTO'], format='%Y-%m-%d %H:%M:%S', errors='coerce')

    print("\nIniciando upload para o Oracle Cloud...")
    engine = create_engine("oracle+oracledb://", creator=conectar_oracle)
    
    tipagem_oracle = {
        'CD_INCIDENTE': VARCHAR2(50),
        'DT_ABERTO': TIMESTAMP(timezone=False),
        'TP_PRIORIDADE': VARCHAR2(20),
        'NM_CATEGORIA': VARCHAR2(100),
        'NM_GRUPO_DESIGNADO': VARCHAR2(100),
        'RISCO_SLA_PREVISTO': NUMBER(precision=15, scale=0),
        'STATUS_REAL': NUMBER(precision=15, scale=0),
        'TEXTO_PRESCRITIVO_LLM': VARCHAR2(4000)
    }
    
    try:
        df_top_alertas.to_sql(
            'TB_ALERTAS_ITSM_IA',
            con=engine,
            if_exists='append',
            dtype=tipagem_oracle, # pyright: ignore[reportArgumentType]
            index=False
        )
        print("- Tabela TB_ALERTAS_ITSM_IA inserida com sucesso no ADB!")
    except Exception as e:  # noqa: BLE001
        print(f"Erro ao enviar dados para o Oracle Cloud: {e}")

if __name__ == "__main__":
    # Carrega variáveis de ambiente, se necessário.
    load_dotenv()
    orquestrar_war_room()