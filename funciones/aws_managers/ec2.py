import boto3
import concurrent.futures
from .utils import assume_role, get_metric_statistics

# Importar función para agregar comentarios globales
def add_comment(comment):
    from . import GLOBAL_COMMENTS
    GLOBAL_COMMENTS.append(comment)

def return_ec2_comments():
    """Retorna los comentarios generados durante el procesamiento de EC2"""
    return COMENTARIOS.copy()

COMENTARIOS = []

#Inicio del Proceso para las Instancias
def get_instance_status(REGION, include_names=None, exclude_names=None, all_instances=False, ROLE_ARN=None, account_name='Default'):
    #Función para trabajar simultaneamente
    print(f"[DEBUG] Iniciando get_instance_status - Región: {REGION}, Include: {include_names}, Exclude: {exclude_names}")
    
    if ROLE_ARN:
        print(f"[DEBUG] Usando assume_role con ARN: {ROLE_ARN}")
        session = assume_role(ROLE_ARN, REGION)
        ec2_client = session.client('ec2')
        cw_client = session.client('cloudwatch')
    else:
        print(f"[DEBUG] Usando credenciales por defecto")
        ec2_client = boto3.client('ec2', region_name=REGION)
        cw_client = boto3.client('cloudwatch', region_name=REGION)

    response = ec2_client.describe_instances()
    print(f"[DEBUG] Total reservations encontradas: {len(response['Reservations'])}")

    instances_info = []
    total_instances = 0
    filtered_instances = 0
    running_instances = 0
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []

        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                total_instances += 1
                name = next((tag['Value'] for tag in instance.get('Tags', []) if tag.get('Key') == 'Name'), 'Unnamed')
                instance_id = instance['InstanceId']
                state = instance['State']['Name']
                
                print(f"[DEBUG] Instancia {instance_id}: nombre='{name}', estado='{state}'")
                
                # Filtrar instancias
                should_include = False
                
                if all_instances:
                    should_include = True
                    print(f"[DEBUG] Incluida por all_instances=True")
                elif include_names:
                    should_include = any(keyword.lower() in name.lower() for keyword in include_names)
                    print(f"[DEBUG] Filtro include_names: {should_include} (buscando {include_names} en '{name}')")
                
                if exclude_names and should_include:
                    excluded = any(keyword.lower() in name.lower() for keyword in exclude_names)
                    should_include = not excluded
                    print(f"[DEBUG] Filtro exclude_names: excluida={excluded} (buscando {exclude_names} en '{name}')")
                
                if should_include:
                    filtered_instances += 1
                    print(f"[DEBUG] Instancia {name} ({instance_id}) INCLUIDA")
                    if state == "running":
                        running_instances += 1
                        print(f"[DEBUG] Procesando instancia running: {name}")
                        futures.append(executor.submit(process_instance_metrics, cw_client, ec2_client, instance_id, name, account_name))
                    else:
                        print(f"[DEBUG] Instancia {name} no está running (estado: {state})")
                else:
                    print(f"[DEBUG] Instancia {name} ({instance_id}) EXCLUIDA")

        for future in concurrent.futures.as_completed(futures):
            instances_info.append(future.result())

    print(f"[DEBUG] Resumen: {total_instances} total, {filtered_instances} filtradas, {running_instances} running, {len(instances_info)} procesadas")
    return instances_info

def process_ec2_metrics(REGION, ROLE_ARN, include_names=None, exclude_names=None, all_instances=False, account_name='Default'):
    """Función principal para procesar métricas de EC2
    
    Args:
        REGION: Región de AWS
        ROLE_ARN: ARN del rol para assume_role
        include_names: Lista de palabras que deben estar en el nombre de la instancia
        exclude_names: Lista de palabras que NO deben estar en el nombre de la instancia
        all_instances: Si True, incluye todas las instancias (ignora include_names)
        account_name: Nombre de la cuenta para configuración personalizada
    """
    instances_data = get_instance_status(REGION, include_names, exclude_names, all_instances, ROLE_ARN, account_name)
    return instances_data

def process_instance_metrics(cw_client, ec2_client, instance_id, name, account_name='Default'):
    # Obtener configuración por cuenta
    try:
        from .config import get_account_config
        config = get_account_config(account_name)
    except ImportError:
        # Configuración por defecto si falla el import
        config = {
            'ec2_metrics': ['CPUUtilization', 'NetworkIn', 'NetworkOut'],
            'alerts': {
                'cpu_alert': True,
                'cpu_threshold': 85,
                'cpu_max_ignore': 100,  # Valor máximo a ignorar (para auto scaling)
                'cpu_position': 2  # 0=min, 1=max, 2=avg (usar avg por defecto)
            }
        }
    
    # Status checks
    instance_status, system_status = get_status_checks(ec2_client, instance_id)
    if (instance_status != 'ok' and instance_status != 'initializing') or (system_status != 'ok' and system_status != 'initializing'):
        add_comment('Status Check: Uno de los dos check para las instancias no esta bien')

    # Métricas dinámicas basadas en configuración
    instance_metrics = [(metric, 'AWS/EC2', [{'Name': 'InstanceId', 'Value': instance_id}]) 
                       for metric in config.get('ec2_metrics', ['CPUUtilization', 'NetworkIn', 'NetworkOut'])]

    instance_metrics_data = []
    alerts = config.get('alerts', {})
    
    for metric_name, namespace, dimensions in instance_metrics:
        metric_data = get_metric_statistics(cw_client, namespace, dimensions, metric_name)
        instance_metrics_data.extend(metric_data)
        
        # Alerta de CPU configurable (similar a RDS)
        if (metric_name == 'CPUUtilization' and alerts.get('cpu_alert', True) and len(metric_data) > 1):
            position = alerts.get('cpu_position', 2)  # Por defecto usar avg
            threshold = alerts.get('cpu_threshold', 85)
            cpu_max_ignore = alerts.get('cpu_max_ignore', 100)
            cpu_value = metric_data[position] if position < len(metric_data) else metric_data[2]
            
            # Lógica: alertar si avg >= threshold, pero NO alertar si max >= cpu_max_ignore (autoscaling)
            avg_cpu = metric_data[2] if len(metric_data) > 2 else cpu_value
            max_cpu = metric_data[1] if len(metric_data) > 1 else cpu_value
            
            # Solo alertar si avg >= threshold Y max < cpu_max_ignore
            if avg_cpu >= threshold:
                if max_cpu < cpu_max_ignore:
                    add_comment(f'CPU Utilization: el promedio es {avg_cpu}% (mayor a {threshold}%) en la instancia {instance_id}')
                # Si max >= cpu_max_ignore, no alertar (es autoscaling)

    response = ec2_client.describe_volumes(Filters=[{'Name': 'attachment.instance-id', 'Values': [instance_id]}])
    volume_id = None
    volume_status = "Unknown"

    if response.get('Volumes'):
        volume = response['Volumes'][0]
        volume_id = volume.get('VolumeId', 'N/A')

        if volume_id != 'N/A':
            status_response = ec2_client.describe_volume_status(VolumeIds=[volume_id])
            if status_response.get('VolumeStatuses'):
                volume_status = status_response['VolumeStatuses'][0].get('VolumeStatus', {}).get('Status', 'Unknown')
                if volume_status != 'ok':
                    add_comment('Status Check: El check para el volumen de la instancia no esta bien')


    volume_metrics = [
        ('VolumeReadOps', 'AWS/EBS', [{'Name': 'VolumeId', 'Value': volume_id}]),
        ('VolumeWriteOps', 'AWS/EBS', [{'Name': 'VolumeId', 'Value': volume_id}]),
    ]

    volume_metrics_data = []
    if volume_id:
        for metric_name, namespace, dimensions in volume_metrics:
            volume_metrics_data.extend(get_metric_statistics(cw_client, namespace, dimensions, metric_name))

    return (name, instance_status, system_status, *instance_metrics_data, volume_id, volume_status, *volume_metrics_data)

def get_status_checks(ec2_client, instance_id):
    #Función para consultar datos con el SDK de las Intancias
    try:
        response = ec2_client.describe_instance_status(InstanceIds=[instance_id])

        if response['InstanceStatuses']:
            instance_status = response['InstanceStatuses'][0]['InstanceStatus']['Status']
            system_status = response['InstanceStatuses'][0]['SystemStatus']['Status']
        else:
            instance_status = "N/A"
            system_status = "N/A"

        return instance_status, system_status
    except Exception as e:
        print(f"Error getting status checks for {instance_id}: {e}")
        return "-", "-"

#Fin del Proceso para las Instancias
