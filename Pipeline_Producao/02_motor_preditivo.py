import warnings

import holidays
import numpy as np
import pandas as pd
import xgboost as xgb
from config import conectar_oracle
from sklearn.cluster import KMeans
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sqlalchemy import create_engine
from sqlalchemy.dialects.oracle import NUMBER, TIMESTAMP, VARCHAR2

warnings.filterwarnings('ignore')

def executar_motor_preditivo():
    print("Conectando ao Oracle e puxando a base de incidentes...")
    df = pd.read_sql_query("SELECT * FROM admin.TB_INCIDENTES_LOCAWEB", con=conectar_oracle()) # pyright: ignore[reportArgumentType]
    
    # ---------------------------------------------------------
    # 1. PRÉ-PROCESSAMENTO E DATA TRIMMING
    # ---------------------------------------------------------
    print("Processando datas e realizando cortes...")
    df['DT_ABERTO'] = pd.to_datetime(df['DT_ABERTO'])
    df['DT_ENCERRADO'] = pd.to_datetime(df['DT_ENCERRADO'])
    df['DT_RESOLVIDO'] = pd.to_datetime(df['DT_RESOLVIDO'])
    
    incidentes_dia = df.groupby(df['DT_ABERTO'].dt.date)['TP_PRIORIDADE'].count().reset_index()
    incidentes_dia.rename(columns={'DT_ABERTO': 'data', 'TP_PRIORIDADE': 'vol_total'}, inplace=True)
    incidentes_dia['data'] = pd.to_datetime(incidentes_dia['data'])
    
    data_limite = pd.to_datetime('2025-08-31')
    df_filtrado = incidentes_dia[incidentes_dia['data'] > data_limite].copy()

    # ---------------------------------------------------------
    # 2. FEATURE ENGINEERING (Lags, Médias e Calendário)
    # ---------------------------------------------------------
    print("Iniciando Engenharia de Features...")
    df_filtrado['dia_semana'] = df_filtrado['data'].dt.day_of_week
    df_filtrado['fl_fim_semana'] = df_filtrado['dia_semana'].apply(lambda x: 1 if x >= 5 else 0)
    df_filtrado['dia_mes'] = df_filtrado['data'].dt.day
    df_filtrado['mes'] = df_filtrado['data'].dt.month

    # Features D+1
    df_filtrado['vol_total_lag_1'] = df_filtrado['vol_total'].shift(1)
    df_filtrado['vol_total_lag_2'] = df_filtrado['vol_total'].shift(2)
    df_filtrado['vol_total_lag_3'] = df_filtrado['vol_total'].shift(3)
    df_filtrado['media_movel_3d'] = df_filtrado['vol_total'].rolling(window=3, min_periods=1).mean()
    df_filtrado['media_movel_7d'] = df_filtrado['vol_total'].rolling(window=7, min_periods=1).mean()

    # Features D+7
    df_filtrado['vol_total_lag_7'] = df_filtrado['vol_total'].shift(7)
    df_filtrado['vol_total_lag_14'] = df_filtrado['vol_total'].shift(14)
    df_filtrado['media_movel_7d_deslocada'] = df_filtrado['vol_total'].shift(7).rolling(window=7, min_periods=1).mean()

    # Adicionando Contagens por Categoria e Grupo Designado
    df['DATA'] = df['DT_ABERTO'].dt.floor('D')
    categorias_alvo = ['Nao Informado', 'cat71', 'cat77', 'cat76', 'cat73', 'cat85']
    times_alvo = ['Team14', 'Team05', 'Team11', 'Team12', 'Team09', 'Team10', 'Team03']

    cat_counts = pd.crosstab(df['DATA'], df['NM_CATEGORIA'])
    team_counts = pd.crosstab(df['DATA'], df['NM_GRUPO_DESIGNADO'])

    colunas_cat_reais = [c for c in categorias_alvo if c in cat_counts.columns]
    colunas_team_reais = [t for t in times_alvo if t in team_counts.columns]

    df_final = df_filtrado.set_index('data')
    df_final = df_final.join(cat_counts[colunas_cat_reais], how='left').fillna(0)
    df_final = df_final.join(team_counts[colunas_team_reais], how='left').fillna(0)

    for col in colunas_cat_reais + colunas_team_reais:
        nome_limpo = col.replace(' ', '_').lower()
        df_final[f'vol_{nome_limpo}_lag_1'] = df_final[col].shift(1)
        df_final[f'vol_{nome_limpo}_lag_7'] = df_final[col].shift(7)
        df_final.drop(columns=[col], inplace=True)

    df_final.dropna(inplace=True)

    # ---------------------------------------------------------
    # 3. TREINAMENTO MODELO D+1
    # ---------------------------------------------------------
    print("Treinando modelo XGBoost para previsão D+1...")
    X_d1 = df_final.drop(columns=['vol_total'])
    y_d1 = df_final['vol_total']
    
    tamanho_teste = 30
    X_train_d1, X_test_d1 = X_d1.iloc[:-tamanho_teste], X_d1.iloc[-tamanho_teste:]
    y_train_d1, _y_test_d1 = y_d1.iloc[:-tamanho_teste], y_d1.iloc[-tamanho_teste:]

    modelo_xgb_d1 = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=23)
    modelo_xgb_d1.fit(X_train_d1, y_train_d1)
    previsoes_d1 = modelo_xgb_d1.predict(X_test_d1)

    # ---------------------------------------------------------
    # 4. TREINAMENTO MODELO D+7 (Com ajuste de Feriados)
    # ---------------------------------------------------------
    print("Treinando modelo XGBoost para previsão D+7...")
    colunas_para_dropar_d7 = [col for col in df_final.columns if 'lag_1' in col or 'lag_2' in col or 'lag_3' in col] + ['media_movel_3d']
    df_d7 = df_final.drop(columns=colunas_para_dropar_d7, errors='ignore')

    feriados_2025 = holidays.country_holidays('BR', subdiv='AM', years=2025)
    df_d7['fl_feriado'] = df_d7.index.map(lambda x: 1 if x in feriados_2025 else 0)
    df_d7['fl_vespera_feriado'] = df_d7.index.map(lambda x: 1 if (x + pd.Timedelta(days=1)) in feriados_2025 else 0)

    X_d7 = df_d7.drop(columns=['vol_total'])
    y_d7 = df_d7['vol_total']
    
    X_train_d7, X_test_d7 = X_d7.iloc[:-tamanho_teste], X_d7.iloc[-tamanho_teste:]
    y_train_d7, _y_test_d7 = y_d7.iloc[:-tamanho_teste], y_d7.iloc[-tamanho_teste:]

    modelo_xgb_d7 = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=23)
    modelo_xgb_d7.fit(X_train_d7, y_train_d7)
    previsoes_d7 = modelo_xgb_d7.predict(X_test_d7)

    # Gerando Tabela Consolidada de Previsão Diária
    df_volume = pd.DataFrame({
        'DATA': _y_test_d7.index,
        'VOLUME_REAL': _y_test_d7.values,
        'PREVISAO_D7': np.round(previsoes_d7).astype(int),
        'PREVISAO_D1': np.round(previsoes_d1).astype(int)
    })

    # ---------------------------------------------------------
    # 5. CLUSTERIZAÇÃO K-MEANS (Análise de Causa Raiz)
    # ---------------------------------------------------------
    print("Executando K-Means para segmentação de risco...")
    df_cluster = df[df['DT_ABERTO'] >= '2025-09-01'].copy()
    features_analise = ['TP_PRIORIDADE', 'NM_GRUPO_DESIGNADO', 'NM_CATEGORIA', 'FL_KPI_VIOLADO', 'NR_DURACAO', 'TP_ABERTO_POR']
    df_features = df_cluster[features_analise].dropna()

    X_cluster = pd.get_dummies(df_features, drop_first=True)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_cluster)

    kmeans_final = KMeans(n_clusters=4, random_state=42, n_init=10)
    df_features['Cluster'] = kmeans_final.fit_predict(X_scaled)

    perfil_clusters = df_features.groupby('Cluster').agg({
        'NR_DURACAO': 'mean',
        'TP_PRIORIDADE': lambda x: x.mode()[0] if not x.mode().empty else 'N/A',
        'NM_GRUPO_DESIGNADO': lambda x: x.mode()[0] if not x.mode().empty else 'N/A',
        'NM_CATEGORIA': lambda x: x.mode()[0] if not x.mode().empty else 'N/A',
        'FL_KPI_VIOLADO': lambda x: x.mode()[0] if not x.mode().empty else 'N/A',
        'TP_ABERTO_POR': lambda x: x.mode()[0] if not x.mode().empty else 'N/A'
    }).reset_index()
    
    tamanho_clusters = df_features['Cluster'].value_counts().reset_index()
    tamanho_clusters.columns = ['Cluster', 'Qtd_Incidentes']
    
    df_matriz_risco = pd.merge(tamanho_clusters, perfil_clusters, on='Cluster')
    df_matriz_risco['NR_DURACAO_HORAS'] = (df_matriz_risco['NR_DURACAO'] / 3600).round(0).astype(int)
    df_matriz_risco.drop(columns=['NR_DURACAO'], inplace=True)
    
    df_matriz_risco.rename(columns={
        'Cluster': 'ID_PERSONA',
        'Qtd_Incidentes': 'VOLUME_INCIDENTES',
        'NM_GRUPO_DESIGNADO': 'EQUIPE',
        'NM_CATEGORIA': 'CATEGORIA_CRITICA'
    }, inplace=True)

    # ---------------------------------------------------------
    # 6. MODELO DE CLASSIFICAÇÃO DE OLA E ALERTAS CRÍTICOS
    # ---------------------------------------------------------
    print("Treinando classificador de risco de OLA...")
    df_risco = df[(df['DT_ABERTO'] >= '2025-09-01') & (df['TP_PRIORIDADE'].isin(['2 - Alta', '3 - Média']))].copy()
    df_risco['alvo_kpi'] = df_risco['FL_KPI_VIOLADO'].map({'SIM': 1, 'NAO': 0})
    df_risco['DATA_DIA'] = df_risco['DT_ABERTO'].dt.floor('D')
    
    # Injetando Pressão Operacional
    colunas_pressao = [col for col in df_final.columns if 'lag' in col or 'media_movel' in col]
    df_pressao = df_final[colunas_pressao]
    df_risco = df_risco.merge(df_pressao, left_on='DATA_DIA', right_index=True, how='left')
    df_risco.dropna(inplace=True)

    colunas_proibidas = ['DT_ABERTO', 'DT_RESOLVIDO', 'DT_ENCERRADO', 'DATA', 'NR_DURACAO', 'CD_FECHAMENTO', 
                         'TP_STATUS', 'DS_RESUMIDA', 'FL_KPI_VIOLADO', 'FL_KPI', 'NM_ITEM_CONFIGURACAO', 'CD_INCIDENTE_PAI', 'DATA_DIA']
    
    # Guarda o CD_INCIDENTE e colunas descritivas para a tabela final de alertas
    df_info_alertas = df_risco[['CD_INCIDENTE', 'DT_ABERTO', 'TP_PRIORIDADE', 'NM_CATEGORIA', 'NM_GRUPO_DESIGNADO', 'alvo_kpi']].copy()
    
    df_risco.drop(columns=colunas_proibidas + ['CD_INCIDENTE'], inplace=True, errors='ignore')
    df_risco = pd.get_dummies(df_risco, columns=['NM_CATEGORIA', 'NM_GRUPO_DESIGNADO'], drop_first=True)

    X_clf = df_risco.drop(columns=['alvo_kpi']).select_dtypes(include=['int32', 'int64', 'float32', 'float64', 'bool', 'uint8'])
    y_clf = df_risco['alvo_kpi']

    X_train_c, X_test_c, y_train_c, _y_test_c = train_test_split(X_clf, y_clf, test_size=0.2, shuffle=False)
    peso_c = y_train_c.value_counts()[0] / y_train_c.value_counts()[1]

    modelo_clf = xgb.XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.1, scale_pos_weight=peso_c, random_state=42)
    modelo_clf.fit(X_train_c, y_train_c)
    
    previsoes_clf = modelo_clf.predict(X_test_c)

    # Pegando as informações originais correspondentes ao teste
    indices_teste_c = X_test_c.index
    df_alertas_final = df_info_alertas.loc[indices_teste_c].copy()
    df_alertas_final['RISCO_SLA_PREVISTO'] = previsoes_clf
    df_alertas_final.rename(columns={'alvo_kpi': 'STATUS_REAL'}, inplace=True)
    
    # Filtra apenas quem o modelo previu que vai estourar
    df_alertas_criticos = df_alertas_final[df_alertas_final['RISCO_SLA_PREVISTO'] == 1].copy()

    # ---------------------------------------------------------
    # 7. EXPORTAÇÃO PARA O ORACLE CLOUD
    # ---------------------------------------------------------
    print("Iniciando Upload das Tabelas Geradas para o Banco de Dados...")
    engine = create_engine("oracle+oracledb://", creator=conectar_oracle)

    tipagem_volume = {
        'DATA': TIMESTAMP(timezone=False),
        'VOLUME_REAL': NUMBER(precision=10, scale=0),
        'PREVISAO_D7': NUMBER(precision=10, scale=0),
        'PREVISAO_D1': NUMBER(precision=10, scale=0)
    }

    tipagem_risco = {
        'ID_PERSONA': NUMBER(precision=10, scale=0),
        'VOLUME_INCIDENTES': NUMBER(precision=10, scale=0),
        'TP_PRIORIDADE': VARCHAR2(50),
        'EQUIPE': VARCHAR2(100),
        'CATEGORIA_CRITICA': VARCHAR2(100),
        'FL_KPI_VIOLADO': VARCHAR2(10),
        'TP_ABERTO_POR': VARCHAR2(50),
        'NR_DURACAO_HORAS': NUMBER(10, 0)
    }

    # Salva localmente para o 03_war_room_llm.py consumir depois
    df_alertas_criticos.to_csv('TB_ALERTAS_ITSM.csv', index=False)
    
    try:
        df_volume.to_sql('TB_PREVISAO_DIARIA', con=engine, if_exists='append', dtype=tipagem_volume, index=False) # pyright: ignore[reportArgumentType]
        print("- TB_PREVISAO_DIARIA inserida com sucesso!")
        
        df_matriz_risco.to_sql('TB_RISCO_EQUIPE', con=engine, if_exists='append', dtype=tipagem_risco, index=False) # pyright: ignore[reportArgumentType]
        print("- TB_RISCO_EQUIPE inserida com sucesso!")
        
        print("Módulo Preditivo Executado com Sucesso! Alertas críticos gerados e salvos localmente.")
        
    except Exception as e:  # noqa: BLE001
        print(f"Erro ao inserir tabelas: {e}")

if __name__ == "__main__":
    executar_motor_preditivo()