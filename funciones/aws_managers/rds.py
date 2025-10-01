import boto3
from datetime import datetime, timedelta
from .utils import assume_role, get_metric_statistics

# Importar función para agregar comentarios globales
def add_comment(comment):
    from . import GLOBAL_COMMENTS
    GLOBAL_COMMENTS.append(comment)

#Inicio del Proceso para la RDS
def process_rds_metrics(rds_id, REGION, role_arn=None, account_name='Default'):
    from .config import get_account_config
    config = get_account_config(account_name)
    checkSnapshot = config['check_snapshots']
    # Función para ordenar los datos
    if role_arn:
        session = assume_role(role_arn, REGION)
        if not session:
            return (rds_id, 'Error', 'Error', 'Error')
        rds_client = session.client('rds')
        cw_client = session.client('cloudwatch')
    else:
        rds_client = boto3.client('rds', region_name=REGION)
        cw_client = boto3.client('cloudwatch', region_name=REGION)

    response = rds_client.describe_db_instances(DBInstanceIdentifier=rds_id)
    db_instance = response['DBInstances'][0]
    total_storage = db_instance['AllocatedStorage']
    db_status = db_instance['DBInstanceStatus']
    
    # Log del estado de la instancia
    print(f"Estado RDS {rds_id}: {db_status}")
    if db_status != 'available':
        add_comment(f'RDS Status: La instancia está en estado "{db_status}" (no disponible)') 

    # Métricas dinámicas basadas en configuración
    rds_metrics = [(metric, 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}]) 
                   for metric in config['rds_metrics']]

    rds_metrics_data = []
    # Usar configuración nueva si existe, sino usar valores por defecto
    if 'alerts' in config:
        alerts = config['alerts']
    else:
        # Configuración legacy - usar valores por defecto
        alerts = {
            'cpu_alert': True,
            'cpu_threshold': 95,
            'cpu_max_ignore': 100,
            'storage_alert': True,
            'storage_threshold': 5
        }
    
    for metric_name, namespace, dimensions in rds_metrics:
        metric_data = get_metric_statistics(cw_client, namespace, dimensions, metric_name)
        
        # Alerta de CPU
        if (metric_name == 'CPUUtilization' and alerts['cpu_alert'] and len(metric_data) > 1):
            cpu_value = metric_data[1]  # Maximum
            if (cpu_value >= alerts['cpu_threshold'] and cpu_value < alerts['cpu_max_ignore']):
                add_comment(f'CPU Utilization: el porcentaje es {cpu_value}% (mayor a {alerts["cpu_threshold"]}%) en el RDS')
        
        # Alerta de Storage
        if (metric_name == 'FreeStorageSpace' and alerts['storage_alert'] and len(metric_data) >= 3):
            free_storage_gb = metric_data[2] / (1024 ** 3)
            free_storage_percent = (free_storage_gb / total_storage) * 100
            if free_storage_percent < alerts['storage_threshold']:
                add_comment(f'Free Storage Space: el espacio libre es {free_storage_percent:.1f}% (menor al {alerts["storage_threshold"]}%) en el RDS')
            # Convertir todos los valores a GB para mostrar
            metric_data = tuple(round(value / (1024 ** 3), 2) if value != 0 else 0 for value in metric_data)
        
        rds_metrics_data.extend(metric_data)

    latest_snapshot_date = None
    if checkSnapshot:
        response = rds_client.describe_db_snapshots(
            DBInstanceIdentifier=rds_id,
            SnapshotType='automated',
            IncludePublic=False
        )

        snapshots = response.get('DBSnapshots', [])
        from datetime import datetime, timedelta

        if snapshots:
            latest_snapshot = max(snapshots, key=lambda x: x['SnapshotCreateTime'])
            latest_snapshot_date = latest_snapshot['SnapshotCreateTime'].strftime('%Y-%m-%d')
            
            print(f"Último snapshot: {latest_snapshot_date}")
            
            today = datetime.now().strftime('%Y-%m-%d')
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            if latest_snapshot_date != yesterday and latest_snapshot_date != today:
                add_comment(f'Snapshot: último respaldo del {latest_snapshot_date} (esperado: {yesterday} o {today})')
        else:
            latest_snapshot_date = 'No hay snapshots'
            add_comment('Snapshot: No se encontraron snapshots automáticos')


    return (rds_id, *rds_metrics_data, latest_snapshot_date if checkSnapshot else None)

def get_rds_event_logs(rds_id, REGION, role_arn=None):
    if role_arn:
        session = assume_role(role_arn, REGION)
        if not session:
            return "Error asumiendo rol para RDS logs"
        rds_client = session.client('rds')
    else:
        rds_client = boto3.client('rds', region_name=REGION)

    try:
        start_time = datetime.utcnow() - timedelta(days=2)
        end_time = datetime.utcnow()

        response = rds_client.describe_events(
            SourceIdentifier=rds_id,
            SourceType='db-instance',
            StartTime=start_time,
            EndTime=end_time
        )

        events = response.get('Events', [])
        error_found = False

        if events:
            for event in events:
                message = event['Message'].lower()
                if "error" in message or "failure" in message or "down" in message:
                    print(f"Error en RDS: {event['Message']}, Hora: {event['Date']}")
                    error_found = True

        if error_found:
            return "Errores encontrados en los logs de la RDS."
        else:
            return "No se encontraron errores en los logs para la RDS."

    except Exception as e:
        print(f"Error obteniendo los logs de eventos de RDS: {e}")
        return "Error al obtener los logs de eventos de RDS."


def process_rds_dashboard_metrics(rds_id, REGION, role_arn=None):
    if role_arn:
        session = assume_role(role_arn, REGION)
        if not session:
            return [("Error", "Error", "Error", "Error")]
        cw_client = session.client('cloudwatch')
    else:
        cw_client = boto3.client('cloudwatch', region_name=REGION)

    rds_dashboard_metrics = [
        ('DiskQueueDepth', 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}]),
        ('ReadLatency', 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}]),
        ('WriteLatency', 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}]),
        ('ReadThroughput', 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}]),
        ('WriteThroughput', 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}]),
        ('ReplicaLag', 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}]),
    ]

    rds_dashboard_data = []
    for metric_name, namespace, dimensions in rds_dashboard_metrics:
        metric_data = get_metric_statistics(cw_client, namespace, dimensions, metric_name)
        rds_dashboard_data.append((metric_name, *metric_data))

    return rds_dashboard_data

#Fin del Proceso para la RDS