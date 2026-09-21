import os

print("Iniciando o A-EYEHORUS Sentinel Pipeline...")
os.system("python Pipeline_Producao/01_etl_nuvem.py")
os.system("python Pipeline_Producao/02_motor_preditivo.py")
os.system("python Pipeline_Producao/03_war_room_llm.py")
print("Pipeline executado com sucesso. Dashboards prontos para atualização!")