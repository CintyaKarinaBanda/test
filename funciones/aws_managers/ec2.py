import boto3
import concurrent.futures
from .utils import assume_role, get_metric_statistics

def return_ec2_comments():
    """Retorna los comentarios generados durante el procesamiento de EC2"""
    return COMENTARIOS.copy()

COMENTARIOS = []

#Inicio del Proceso para las Instancias
def get_instance_status(REGION, include_names=None, exclude_names=None, all_instances=False, ROLE_ARN=None):
    #Función para trabajar simultaneamente
    if ROLE_ARN:
        credentials = assume_role(ROLE_ARN, REGION)
        ec2_client = boto3.client('ec2', region_name=REGION, **credentials)
        cw_client = boto3.client('cloudwatch', region_name=REGION, **credentials)
    else:
        ec2_client = boto3.client('ec2', region_name=REGION)
        cw_client = boto3.client('cloudwatch', region_name=REGION)

    response = ec2_client.describe_instances()

    instances_info = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []

        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                name = next((tag['Value'] for tag in instance.get('Tags', []) if tag.get('Key') == 'Name'), 'Unnamed')
                
                # Filtrar instancias
                should_include = False
                
                if all_instances:
                    should_include = True
                elif include_names:
                    should_include = any(keyword.lower() in name.lower() for keyword in include_names)
                
                if exclude_names and should_include:
                    should_include = not any(keyword.lower() in name.lower() for keyword in exclude_names)
                
                if should_include:
                    state = instance['State']['Name']
                    if state == "running":
                        instance_id = instance['InstanceId']
                        futures.append(executor.submit(process_instance_metrics, cw_client, ec2_client, instance_id, name, include_names or []))

        for future in concurrent.futures.as_completed(futures):
            instances_info.append(future.result())

    return instances_info

def process_ec2_metrics(REGION, ROLE_ARN, include_names=None, exclude_names=None, all_instances=False):
    """Función principal para procesar métricas de EC2
    
    Args:
        REGION: Región de AWS
        ROLE_ARN: ARN del rol para assume_role
        include_names: Lista de palabras que deben estar en el nombre de la instancia
        exclude_names: Lista de palabras que NO deben estar en el nombre de la instancia
        all_instances: Si True, incluye todas las instancias (ignora include_names)
    """
    instances_data = get_instance_status(REGION, include_names, exclude_names, all_instances, ROLE_ARN)
    return instances_data

def process_instance_metrics(cw_client, ec2_client, instance_id, name, ACOUNT_NAME):
    #Funcion para ordenar los datos
    instance_status, system_status = get_status_checks(ec2_client, instance_id)
    if (instance_status != 'ok' and instance_status != 'initializing') or (system_status != 'ok' and system_status != 'initializing'):
        COMENTARIOS.append('Status Check: Uno de los dos check para las instancias no esta bien')

    instance_metrics = [
        ('CPUUtilization', 'AWS/EC2', [{'Name': 'InstanceId', 'Value': instance_id}]),
        ('NetworkIn', 'AWS/EC2', [{'Name': 'InstanceId', 'Value': instance_id}]),
        ('NetworkOut', 'AWS/EC2', [{'Name': 'InstanceId', 'Value': instance_id}]),
    ]

    instance_metrics_data = []
    for metric_name, namespace, dimensions in instance_metrics:
        metric_data = get_metric_statistics(cw_client, namespace, dimensions, metric_name)
        instance_metrics_data.extend(metric_data)
        position = 2 if 'darrow' in ACOUNT_NAME else 1
        porcentaje = 70 if 'darrow' in ACOUNT_NAME else 85
        if metric_name == 'CPUUtilization' and len(metric_data) > 1 and metric_data[position] >= porcentaje:
            COMENTARIOS.append(f'CPU Utilization: el procentaje es mayor a {porcentaje} en la instancia {instance_id}')

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
                    COMENTARIOS.append('Status Check: El check para el volumen de la instancia no esta bien')


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
