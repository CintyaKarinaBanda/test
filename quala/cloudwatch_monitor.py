import sys
import os
sys.path.append(os.path.abspath('../funciones'))

from datetime import datetime
from aws_manager import get_cloudwatch_alarms_status
from email_manager import send_email
from config import REGION, CLOUDWATCH_ALARMS, REMITENTE, GMAIL_PASSWORD, DESTINATARIO, COPIAS

def generate_alarm_report(alarms_status):
    """Genera un reporte en texto de las alarmas"""
    report = []
    report.append("=== REPORTE DE ALARMAS CLOUDWATCH ===")
    report.append(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    ok_alarms = []
    problem_alarms = []
    
    for alarm in alarms_status:
        if alarm['state'] == 'OK':
            ok_alarms.append(alarm)
        else:
            problem_alarms.append(alarm)
    
    # Alarmas OK
    if ok_alarms:
        report.append("✅ ALARMAS EN ESTADO OK:")
        for alarm in ok_alarms:
            report.append(f"  • {alarm['name']}")
            report.append(f"    Estado: {alarm['state']}")
            report.append(f"    Última actualización: {alarm['last_updated']}")
            report.append("")
    
    # Alarmas con problemas
    if problem_alarms:
        report.append("⚠️  ALARMAS CON PROBLEMAS:")
        for alarm in problem_alarms:
            report.append(f"  • {alarm['name']}")
            report.append(f"    Estado: {alarm['state']}")
            report.append(f"    Razón: {alarm['reason']}")
            report.append(f"    Última actualización: {alarm['last_updated']}")
            report.append("")
    
    # Resumen
    report.append("=== RESUMEN ===")
    report.append(f"Total de alarmas monitoreadas: {len(alarms_status)}")
    report.append(f"Alarmas OK: {len(ok_alarms)}")
    report.append(f"Alarmas con problemas: {len(problem_alarms)}")
    
    return "\n".join(report)

def send_alarm_email(alarms_status):
    """Envía email con el reporte de alarmas"""
    report_text = generate_alarm_report(alarms_status)
    
    # Determinar el asunto basado en el estado de las alarmas
    problem_count = len([alarm for alarm in alarms_status if alarm['state'] != 'OK'])
    
    if problem_count == 0:
        subject = "✅ CloudWatch Alarms - Todas las alarmas OK"
    else:
        subject = f"⚠️ CloudWatch Alarms - {problem_count} alarma(s) con problemas"
    
    # Crear archivo temporal con el reporte
    temp_filename = f"cloudwatch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(temp_filename, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    try:
        send_email(
            temp_filename, 
            [report_text], 
            REMITENTE, 
            GMAIL_PASSWORD, 
            DESTINATARIO, 
            COPIAS, 
            subject
        )
        print("Email enviado exitosamente")
    except Exception as e:
        print(f"Error enviando email: {e}")
    finally:
        # Limpiar archivo temporal
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

if __name__ == "__main__":
    print("Iniciando monitoreo de alarmas CloudWatch...")
    print(f"Alarmas a monitorear: {CLOUDWATCH_ALARMS}")
    
    # Obtener estado de las alarmas
    alarms_status = get_cloudwatch_alarms_status(REGION, CLOUDWATCH_ALARMS)
    
    # Mostrar reporte en consola
    report = generate_alarm_report(alarms_status)
    print("\n" + report)
    
    # Enviar email
    send_alarm_email(alarms_status)
    
    print("\nMonitoreo completado.")