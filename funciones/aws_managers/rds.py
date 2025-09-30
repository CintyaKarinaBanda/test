import boto3
from datetime import datetime, timedelta
from .utils import assume_role, get_metric_statistics

# Importar función para agregar comentarios globales
def add_comment(comment):
    from . import GLOBAL_COMMENTS
    GLOBAL_COMMENTS.append(comment)

#Inicio del Proceso para la RDS
def process_rds_metrics(rds_id, REGION, role_arn=None, checkSnapshot = True ):
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
    total_storage = response['DBInstances'][0]['AllocatedStorage'] 

    rds_metrics = [
        ('CPUUtilization', 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}]),
        ('DatabaseConnections', 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}]),
        ('FreeStorageSpace', 'AWS/RDS', [{'Name': 'DBInstanceIdentifier', 'Value': rds_id}])
    ]

    rds_metrics_data = []
    for metric_name, namespace, dimensions in rds_metrics:
        metric_data = get_metric_statistics(cw_client, namespace, dimensions, metric_name)
        rds_metrics_data.extend(metric_data)
        if metric_name == 'CPUUtilization' and len(metric_data) > 1 and metric_data[1] >= 95:
            add_comment('CPU Utilization: el procentaje es mayor a 95 en el RDS')
        if metric_name == 'FreeStorageSpace' and len(metric_data) >= 3:
            metric_data = [round(value / (1024 ** 3), 2) for value in metric_data]
            free_storage_percent = (metric_data[2] / total_storage) * 100  
            if free_storage_percent < 5:
                add_comment(f'Free Storage Space: el espacio libre es menor al 5% en el RDS')
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
            latest_snapshot_date = latest_snapshot['SnapshotCreateTime'].strftime('%Y-%m-%d %H:%M:%S')

            today = datetime.now().strftime('%Y-%m-%d')
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            snapshot_date = latest_snapshot['SnapshotCreateTime'].strftime('%Y-%m-%d')
            if snapshot_date != yesterday and snapshot_date != today:
                add_comment('Snapshot: hubo un error el crear el respaldo del día de ayer.')


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