import os
import traceback

import oracledb
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.dialects.oracle import NUMBER, TIMESTAMP, VARCHAR2

load_dotenv()

# -------------------------------------------------------
# Configurações de conexão com o banco de dados em nuvem
# -------------------------------------------------------

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
CONNECT_STRING = '(description= (retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1522)(host=adb.sa-saopaulo-1.oraclecloud.com))(connect_data=(service_name=g253a13c6f2211a_dadosaiopslocaweb_low.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))'

def conectar_oracle():
    return oracledb.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        dsn=CONNECT_STRING,
        wallet_location=r"C:/opt/OracleCloud/Wallet_dadosAIOpsLocaweb",
        wallet_password=DB_PASSWORD
    )

# -------------------------------------------------------
# FUNÇÕES DO PIPELINE ETL
# -------------------------------------------------------

# EXTRACT -----------------------------------------------

def extract_data(filepath):
    print("Iniciando processo de extração dos dados brutos...")
    return pd.read_excel(filepath)

# TRANSFORM -----------------------------------------------

def transform_data(df):
    print("Iniciando processo de transformação dos dados...")
    
    # Renomear colunas
    df.rename(columns={
        'Número': 'cd_incidente', 'Prioridade': 'tp_prioridade', 'Produto': 'nm_produto',
        'Categoria': 'nm_categoria', 'Subcategoria': 'nm_subcategoria', 'Grupo designado': 'nm_grupo_designado',
        'Item de configuração': 'nm_item_configuracao', 'Aberto' : 'dt_aberto', 'Resolvido': 'dt_resolvido',
        'Encerrado': 'dt_encerrado', 'Duração': 'nr_duracao', 'Código de fechamento': 'cd_fechamento',
        'Descrição resumida': 'ds_resumida', 'Solução': 'tp_solucao', 'Aberto por': 'tp_aberto_por',
        'Incidente Pai': 'cd_incidente_pai', 'Status': 'tp_status', 'Entrou para KPI?': 'fl_kpi',
        'KPI Violado?': 'fl_kpi_violado'
    }, inplace=True)
    
    # Converter datas
    df['dt_aberto'] = pd.to_datetime(df['dt_aberto'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    df['dt_resolvido'] = pd.to_datetime(df['dt_resolvido'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    df['dt_encerrado'] = pd.to_datetime(df['dt_encerrado'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    
    # Tratamento de Nulos
    if 'nm_produto' in df.columns: df['nm_produto'] = df['nm_produto'].fillna('Nao Informado')
    if 'nm_categoria' in df.columns: df['nm_categoria'] = df['nm_categoria'].fillna('Nao Informado')
    if 'nm_subcategoria' in df.columns: df['nm_subcategoria'] = df['nm_subcategoria'].fillna('Nao Informado')
    if 'nm_item_configuracao' in df.columns: df['nm_item_configuracao'] = df['nm_item_configuracao'].fillna('Nao Informado')
    if 'cd_fechamento' in df.columns: df['cd_fechamento'] = df['cd_fechamento'].fillna('Em andamento')
    if 'tp_solucao' in df.columns: df['tp_solucao'] = df['tp_solucao'].fillna('Nenhuma')
    if 'fl_kpi_violado' in df.columns: df['fl_kpi_violado'] = df['fl_kpi_violado'].fillna('VERIFICAR')
    
    # Regras de Negócio de KPI
    df.loc[df['fl_kpi'] == 'NAO', 'fl_kpi_violado'] = 'NAO'
    df.loc[df[df['tp_prioridade'] == "2 - Alta"].fl_kpi_violado[df['nr_duracao'] > 14400].index, 'fl_kpi_violado'] = 'SIM'
    df.loc[df[df['tp_prioridade'] == "3 - Média"].fl_kpi_violado[df['nr_duracao'] > 43200].index, 'fl_kpi_violado'] = 'SIM'
    
    print(f"Transformação concluída. Total de registros: {len(df)}")
    return df

# LOAD DATA -----------------------------------------------
def load_data(df, table_name):
    print(f"Criando a Engine do SQLAlchemy para carga na tabela {table_name}.")
    engine = create_engine("oracle+oracledb://", creator = conectar_oracle)
    
    tipagem_oracle = {
        'cd_incidente': VARCHAR2(50), 'tp_prioridade': VARCHAR2(20), 'nm_produto': VARCHAR2(100), 
        'nm_categoria': VARCHAR2(100), 'nm_subcategoria': VARCHAR2(100), 'nm_grupo_designado': VARCHAR2(100), 
        'nm_item_configuracao': VARCHAR2(100), 'dt_aberto': TIMESTAMP(timezone=False), 
        'dt_resolvido': TIMESTAMP(timezone=False), 'dt_encerrado': TIMESTAMP(timezone=False), 
        'nr_duracao': NUMBER(precision = 10, scale=0), 'cd_fechamento': VARCHAR2(50), 
        'ds_resumida': VARCHAR2(255), 'tp_solucao': VARCHAR2(10), 'tp_aberto_por': VARCHAR2(20),
        'cd_incidente_pai': VARCHAR2(50), 'tp_status': VARCHAR2(50), 'fl_kpi': VARCHAR2(3), 
        'fl_kpi_violado': VARCHAR2(3)
    }

    df.to_sql(table_name, con=engine, if_exists='replace', dtype = tipagem_oracle, index=False)
    print("Processo concluído. Dados inseridos na Oracle Cloud com sucesso.")

# -------------------------------------------------------
# ORQUESTRAÇÃO
# ------------------------------------------------------- 

def run_etl_pipeline():
    try:
        filepath = "C:/Users/vitor/Data_Projects/EC2026/LW-DATASET.xlsx"
        dest_tb = "tb_incidentes_locaweb"
        
        raw_data = extract_data(filepath)
        processed_data = transform_data(raw_data)
        load_data(processed_data, dest_tb)
        
    except Exception:  # noqa: BLE001
        traceback.print_exc()

if __name__ == "__main__":
    run_etl_pipeline()
    