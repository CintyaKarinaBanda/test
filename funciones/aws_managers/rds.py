import boto3
from datetime import datetime, timedelta
import pytz
from .utils import assume_role, get_metric_statistics

# Importar función para agregar comentarios globales
def add_comment(comment):
    from . import GLOBAL_COMMENTS
    GLOBAL_COMMENTS.append(comment)

#Inicio del Proceso para la RDS
def get_rds_status(rds_id, REGION, role_arn=None):
    """Verifica el estado de la instancia RDS"""
    if role_arn:
        session = assume_role(role_arn, REGION)
        if not session:
            return 'Error'
        rds_client = session.client('rds')
    else:
        rds_client = boto3.client('rds', region_name=REGION)
    
    try:
        response = rds_client.describe_db_instances(DBInstanceIdentifier=rds_id)
        db_status = response['DBInstances'][0]['DBInstanceStatus']
        print(f"Estado RDS {rds_id}: {db_status}")
        return db_status
    except Exception as e:
        print(f"Error obteniendo estado de RDS {rds_id}: {e}")
        return 'Error'

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

    # Verificar estado de la instancia
    db_status = get_rds_status(rds_id, REGION, role_arn)
    
    if db_status != 'available':
        add_comment(f'RDS Status: La instancia está en estado "{db_status}" (no disponible)')
        num_metrics = len(config['rds_metrics']) * 3 
        unavailable_data = ['N/A'] * num_metrics
        return (rds_id, db_status, *unavailable_data, 'No disponible' if config['check_snapshots'] else None)
    
    # Si está disponible, obtener información completa
    response = rds_client.describe_db_instances(DBInstanceIdentifier=rds_id)
    db_instance = response['DBInstances'][0]
    total_storage = db_instance['AllocatedStorage'] 

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
            if (cpu_value >= alerts['cpu_threshold'] and cpu_value != alerts['cpu_max_ignore']):
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
        print(f"DEBUG: Verificando snapshots para RDS {rds_id}")
        
        # Primero intentar como instancia DB
        try:
            response = rds_client.describe_db_snapshots(
                DBInstanceIdentifier=rds_id,
                SnapshotType='automated',
                IncludePublic=False
            )
            snapshots = response.get('DBSnapshots', [])
            print(f"DEBUG: Encontrados {len(snapshots)} snapshots de instancia DB")
        except Exception as e:
            print(f"DEBUG: No es una instancia DB o error: {e}")
            snapshots = []
        
        # Si no hay snapshots de instancia, intentar como cluster
        if not snapshots:
            try:
                print(f"DEBUG: Buscando snapshots de cluster para {rds_id}")
                response = rds_client.describe_db_cluster_snapshots(
                    DBClusterIdentifier=rds_id,
                    SnapshotType='automated',
                    IncludePublic=False
                )
                cluster_snapshots = response.get('DBClusterSnapshots', [])
                print(f"DEBUG: Encontrados {len(cluster_snapshots)} snapshots de cluster")
                
                # Convertir formato de cluster a formato de instancia para compatibilidad
                snapshots = [{
                    'DBSnapshotIdentifier': snap['DBClusterSnapshotIdentifier'],
                    'SnapshotCreateTime': snap['SnapshotCreateTime'],
                    'Status': snap['Status']
                } for snap in cluster_snapshots]
                
            except Exception as e:
                print(f"DEBUG: Tampoco es un cluster o error: {e}")
                snapshots = []
        
        from datetime import datetime, timedelta

        if snapshots:
            print(f"DEBUG: Total de snapshots encontrados: {len(snapshots)}")
            # Debug: mostrar todos los snapshots encontrados
            for i, snap in enumerate(snapshots[:3]):  # Solo los primeros 3
                snap_date = snap['SnapshotCreateTime'].strftime('%Y-%m-%d %H:%M')
                print(f"DEBUG: Snapshot {i+1}: {snap['DBSnapshotIdentifier']} - {snap_date} - Status: {snap['Status']}")
            
            latest_snapshot = max(snapshots, key=lambda x: x['SnapshotCreateTime'])
            latest_snapshot_date = latest_snapshot['SnapshotCreateTime'].strftime('%Y-%m-%d')
            
            print(f"DEBUG: Último snapshot seleccionado: {latest_snapshot['DBSnapshotIdentifier']} - {latest_snapshot_date}")
            
            today = datetime.now().strftime('%Y-%m-%d')
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            print(f"DEBUG: Comparando fechas - Snapshot: {latest_snapshot_date}, Hoy: {today}, Ayer: {yesterday}")
            
            if latest_snapshot_date != yesterday and latest_snapshot_date != today:
                print(f"DEBUG: Snapshot desactualizado detectado")
                add_comment(f'Snapshot: último respaldo del {latest_snapshot_date} (esperado: {yesterday} o {today})')
            else:
                print(f"DEBUG: Snapshot está actualizado")
        else:
            print(f"DEBUG: No se encontraron snapshots automáticos para {rds_id} (ni instancia ni cluster)")
            latest_snapshot_date = 'No hay snapshots'
            add_comment('Snapshot: No se encontraron snapshots automáticos (verificado instancia y cluster)')


    return (rds_id, db_status, *rds_metrics_data, latest_snapshot_date if checkSnapshot else None)

def get_rds_event_logs(rds_id, REGION, role_arn=None):
    # Verificar estado primero
    db_status = get_rds_status(rds_id, REGION, role_arn)
    
    if db_status != 'available':
        return [f"RDS {rds_id} no está disponible (estado: {db_status}). No se pueden obtener logs."]
    
    if role_arn:
        session = assume_role(role_arn, REGION)
        if not session:
            return ["Error asumiendo rol para RDS logs"]
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
        error_logs = []

        if events:
            for event in events:
                message = event['Message'].lower()
                if "error" in message or "failure" in message or "down" in message:
                    # Convertir UTC a hora local
                    utc_time = event['Date']
                    if utc_time.tzinfo is None:
                        utc_time = pytz.utc.localize(utc_time)
                    local_time = utc_time.astimezone()
                    
                    error_logs.append(f"{local_time.strftime('%Y-%m-%d %H:%M')}: {event['Message']}")
                    print(f"Error en RDS: {event['Message']}, Hora: {local_time.strftime('%Y-%m-%d %H:%M')}")

        if error_logs:
            return error_logs
        else:
            return ["No se encontraron errores en los logs para la RDS."]

    except Exception as e:
        print(f"Error obteniendo los logs de eventos de RDS: {e}")
        return ["Error al obtener los logs de eventos de RDS."]


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