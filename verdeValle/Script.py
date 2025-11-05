import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'funciones'))

import shutil
from datetime import datetime

#Funciones extraidas dentro del mismo proyecto
from email_manager import send_email
from bd_manager import send_status
from excel_manager import write_report, write_column
from aws_managers import return_comments
from aws_managers.ec2 import process_ec2_metrics, return_ec2_comments
from config import SOURCE_FILENAME, REGION, ROLE_ARN, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, CUENTA, PROJECT, host, database, user, password

if __name__ == "__main__":
    print("Script iniciado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    today = datetime.now().strftime("%Y-%m-%d")
    target_filename = f"excel/CheckList_{today}.xlsx"
    shutil.copy(SOURCE_FILENAME, target_filename)

    comentarios = []

    try:
        # Monitoreo EC2
        print(f"Consultando EC2 en región {REGION} con filtros: include=['lealtad'], exclude=['bastion']")
        ec2_data = process_ec2_metrics(REGION, ROLE_ARN, include_names=['lealtad'], exclude_names=['bastion'])
        print(f"EC2 data obtenida: {len(ec2_data) if ec2_data else 0} instancias")
        if ec2_data:
            for i, instance in enumerate(ec2_data):
                print(f"Instancia {i+1}: {instance[0] if instance else 'Sin nombre'}")
        write_report(ec2_data, start_row=5, start_col=2, target_filename=target_filename)
        
    except Exception as e:
        print(f"Error consultando EC2: {e}")
        comentarios.append("Error EC2")

    #Finalizar el CheckList
    global_comments = return_comments()
    ec2_comments = return_ec2_comments()
    print(f"Comentarios globales: {global_comments}")
    print(f"Comentarios EC2: {ec2_comments}")
    comentarios.extend(global_comments)
    comentarios.extend(ec2_comments)
    final_comments = comentarios if comentarios else ['Todo Ok']
    print(f"Comentarios finales: {final_comments}")
    write_column(final_comments, start_row=20, start_col=15, target_filename=target_filename)

    #Actualizacion en Xoc
    send_status(final_comments, CUENTA, PROJECT, host, database, user, password)
    
    parametros = {
        "Status Check": ("Estado de instancia, sistema y volumen", "Ok", "NoK"),
        "CPU Utilization": ("Menor al 85% en las instancias", "Ok", "NoK"),
    }
    
    #Envio de correo
    send_email(target_filename, final_comments, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, parametros)

    print("Script terminado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))