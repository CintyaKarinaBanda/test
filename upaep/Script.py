import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'funciones'))

import shutil
import requests
from datetime import datetime

#Funciones extraidas dentro del mismo proyecto
from email_manager import send_email
from bd_manager import send_status
from excel_manager import write_report, write_column
from aws_managers import return_comments, process_vpc_metrics, return_vpc_comments
from config import SOURCE_FILENAME, REGION, ROLE_ARN, API_LINK, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, CUENTA, PROJECT, host, database, user, password

if __name__ == "__main__":
    print("Script iniciado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    today = datetime.now().strftime("%Y-%m-%d")
    target_filename = f"excel/CheckList_{today}.xlsx"
    shutil.copy(SOURCE_FILENAME, target_filename)

    # VPC metrics para UPAEP
    vpc_data = process_vpc_metrics(REGION, ROLE_ARN, vpc_names=['upaep'])
    print(f"VPCs UPAEP encontradas: {len(vpc_data)}")
    for vpc in vpc_data:
        print(f"VPC: {vpc[0]} ({vpc[1]}) - VPN DataIn: Max={vpc[7] if len(vpc) > 7 else 'N/A'}MB, DataOut: Max={vpc[10] if len(vpc) > 10 else 'N/A'}MB")
    
    write_report(vpc_data, start_row=5, start_col=2, target_filename=target_filename)
    
    #Finalizar el CheckList
    comentarios = return_comments()
    comentarios.extend(return_vpc_comments())
    if not comentarios:
        comentarios.append('Todo Ok')
    write_column(comentarios, start_row=11, start_col=2, target_filename=target_filename)

    #Actualizacion en Xoc
    send_status(comentarios, CUENTA, PROJECT, host, database, user, password)
    
    parametros = {
        "VPC": ("Conectividad, DNS y seguridad de red", "Funcionando correctamente", "Requiere atención")
    }
    #Envio de correo
    send_email(target_filename, comentarios, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, parametros)

    print("Script terminado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))