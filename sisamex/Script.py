import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'funciones'))

from datetime import datetime

#Funciones extraidas dentro del mismo proyecto
from email_manager import send_email
from bd_manager import send_status
from config import REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, CUENTA, PROJECT, host, database, user, password


if __name__ == "__main__":
    print("Script iniciado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    monthList = [5, 6, 7]
    if (datetime.now().month not in monthList):
        #Actualizacion en Xoc
        send_status(["Todo Ok"], CUENTA, PROJECT, host, database, user, password)
        #Actualizacion en Xoc
    else:
        #Actualizacion en Xoc
        send_status(["Todo Ok"], CUENTA, PROJECT, host, database, user, password)
        
        parametros = {
            "Chats": ("Actividad en el chat", "Ok", "Nok")
        }
        #Envio de correo
        #send_email(None, ['Todo Ok'], REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS, SUBJECT, parametros)

        print("Script terminado, ",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))