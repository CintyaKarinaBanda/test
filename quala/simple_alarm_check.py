import sys
import os
sys.path.append(os.path.abspath('../funciones'))

import boto3
from datetime import datetime
from email_manager import send_email
from config import REGION, CLOUDWATCH_ALARMS, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS

def check_alarms_simple():
    """Verificación simple de alarmas - solo reporta si están OK"""
    cw_client = boto3.client('cloudwatch', region_name=REGION)
    
    try:
        response = cw_client.describe_alarms(AlarmNames=CLOUDWATCH_ALARMS)
        
        ok_alarms = []
        problem_alarms = []
        
        for alarm in response['MetricAlarms']:
            if alarm['StateValue'] == 'OK':
                ok_alarms.append(alarm['AlarmName'])
            else:
                problem_alarms.append({
                    'name': alarm['AlarmName'],
                    'state': alarm['StateValue'],
                    'reason': alarm['StateReason']
                })
        
        return ok_alarms, problem_alarms
        
    except Exception as e:
        print(f"Error consultando alarmas: {e}")
        return [], []

def send_simple_report():
    """Envía reporte simple por email"""
    ok_alarms, problem_alarms = check_alarms_simple()
    
    # Crear mensaje simple
    message_lines = []
    message_lines.append(f"Reporte de Alarmas CloudWatch - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    message_lines.append("")
    
    if ok_alarms:
        message_lines.append("✅ Alarmas en estado OK:")
        for alarm in ok_alarms:
            message_lines.append(f"  • {alarm}")
        message_lines.append("")
    
    if problem_alarms:
        message_lines.append("⚠️ Alarmas con problemas:")
        for alarm in problem_alarms:
            message_lines.append(f"  • {alarm['name']}: {alarm['state']} - {alarm['reason']}")
        message_lines.append("")
    
    message_lines.append(f"Total OK: {len(ok_alarms)}/{len(CLOUDWATCH_ALARMS)}")
    
    message_text = "\n".join(message_lines)
    
    # Determinar asunto
    if len(problem_alarms) == 0:
        subject = "✅ Alarmas CloudWatch - Todas OK"
    else:
        subject = f"⚠️ Alarmas CloudWatch - {len(problem_alarms)} con problemas"
    
    # Crear archivo temporal
    temp_file = f"alarm_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write(message_text)
    
    try:
        send_email(
            temp_file,
            [message_text],
            REMITENTE,
            GMAIL_PASSWORD, 
            DESTINATARIO,
            COPIAS,
            subject
        )
        print("✅ Email enviado exitosamente")
    except Exception as e:
        print(f"❌ Error enviando email: {e}")
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

if __name__ == "__main__":
    print("🔍 Verificando alarmas CloudWatch...")
    print(f"Alarmas: {CLOUDWATCH_ALARMS}")
    
    ok_alarms, problem_alarms = check_alarms_simple()
    
    print(f"\n✅ Alarmas OK: {len(ok_alarms)}")
    for alarm in ok_alarms:
        print(f"  • {alarm}")
    
    if problem_alarms:
        print(f"\n⚠️ Alarmas con problemas: {len(problem_alarms)}")
        for alarm in problem_alarms:
            print(f"  • {alarm['name']}: {alarm['state']}")
    
    print(f"\n📧 Enviando reporte por email...")
    send_simple_report()
    print("✅ Proceso completado")