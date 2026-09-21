import traceback

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.dialects.oracle import NUMBER, TIMESTAMP, VARCHAR2

# Importa a função de conexão do config.py
from config import conectar_oracle

# -------------------------------------------------------
# FUNÇÕES DO PIPELINE ETL
# -------------------------------------------------------

# EXTRACT -----------------------------------------------

def extract_data(filepath):
    """Extrai os dados brutos de um arquivo Excel."""
    print("Iniciando processo de extração dos dados brutos...")
    try:
        return pd.read_excel(filepath)
    except FileNotFoundError:
        print(f"Erro: Arquivo não encontrado no caminho: {filepath}")
        raise
    except Exception as e:
        print(f"Erro durante a extração de dados: {e}")
        raise

# TRANSFORM -----------------------------------------------

def transform_data(df):
    """Transforma e limpa os dados extraídos."""
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
    # Usando o dicionário para mapear as colunas e seus valores padrão
    fill_values = {
        'nm_produto': 'Nao Informado',
        'nm_categoria': 'Nao Informado',
        'nm_subcategoria': 'Nao Informado',
        'nm_item_configuracao': 'Nao Informado',
        'cd_fechamento': 'Em andamento',
        'tp_solucao': 'Nenhuma',
        'fl_kpi_violado': 'VERIFICAR'
    }
    
    for col, value in fill_values.items():
        if col in df.columns:
            df[col] = df[col].fillna(value)
            
    # Regras de Negócio de KPI
    df.loc[df['fl_kpi'] == 'NAO', 'fl_kpi_violado'] = 'NAO'
    
    # Corrigindo a lógica de atribuição para evitar avisos
    cond_alta = (df['tp_prioridade'] == "2 - Alta") & (df['nr_duracao'] > 14400)
    df.loc[cond_alta, 'fl_kpi_violado'] = 'SIM'
    
    cond_media = (df['tp_prioridade'] == "3 - Média") & (df['nr_duracao'] > 43200)
    df.loc[cond_media, 'fl_kpi_violado'] = 'SIM'
    
    print(f"Transformação concluída. Total de registros prontos: {len(df)}")
    return df

# LOAD DATA -----------------------------------------------

def load_data(df, table_name):
    """Carrega o DataFrame processado para o banco de dados Oracle."""
    print(f"Criando a Engine do SQLAlchemy para carga na tabela {table_name}...")
    
    # A função conectar_oracle agora vem do config.py
    try:
        engine = create_engine("oracle+oracledb://", creator=conectar_oracle)
    except Exception as e:
         print(f"Erro ao criar engine de banco de dados: {e}")
         raise
    
    tipagem_oracle = {
        'cd_incidente': VARCHAR2(50), 
        'tp_prioridade': VARCHAR2(20), 
        'nm_produto': VARCHAR2(100), 
        'nm_categoria': VARCHAR2(100), 
        'nm_subcategoria': VARCHAR2(100), 
        'nm_grupo_designado': VARCHAR2(100), 
        'nm_item_configuracao': VARCHAR2(100), 
        'dt_aberto': TIMESTAMP(timezone=False), 
        'dt_resolvido': TIMESTAMP(timezone=False), 
        'dt_encerrado': TIMESTAMP(timezone=False), 
        'nr_duracao': NUMBER(precision=10, scale=0), 
        'cd_fechamento': VARCHAR2(50), 
        'ds_resumida': VARCHAR2(255), 
        'tp_solucao': VARCHAR2(50), # Aumentado para 50 para garantir segurança
        'tp_aberto_por': VARCHAR2(50), # Aumentado para 50 para garantir segurança
        'cd_incidente_pai': VARCHAR2(50), 
        'tp_status': VARCHAR2(50), 
        'fl_kpi': VARCHAR2(10), # Aumentado para acomodar 'SIM' ou 'NAO'
        'fl_kpi_violado': VARCHAR2(10) # Aumentado para acomodar 'SIM' ou 'NAO'
    }

    try:
        print("Iniciando upload de dados...")
        df.to_sql(table_name, con=engine, if_exists='replace', dtype=tipagem_oracle, index=False)
        print("Processo concluído. Dados inseridos na Oracle Cloud com sucesso.")
    except Exception as e:
         print(f"Erro durante o upload dos dados para o banco: {e}")
         raise

# -------------------------------------------------------
# ORQUESTRAÇÃO
# ------------------------------------------------------- 

def run_etl_pipeline():
    """Orquestra o pipeline ETL."""
    try:
        # Caminho e nome da tabela podem vir de variáveis de ambiente no futuro
        filepath = "C:/Users/vitor/Data_Projects/EC2026/LW-DATASET.xlsx"
        dest_tb = "tb_incidentes_locaweb"
        
        raw_data = extract_data(filepath)
        processed_data = transform_data(raw_data)
        load_data(processed_data, dest_tb)
        
    except Exception:
        print("Pipeline ETL falhou. Detalhes do erro:")
        traceback.print_exc()

if __name__ == "__main__":
    run_etl_pipeline()