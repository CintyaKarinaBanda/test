import boto3
import concurrent.futures
from .utils import assume_role, get_metric_statistics

COMENTARIOS = []

def get_vpc_status(REGION, vpc_names=None, all_vpcs=False, ROLE_ARN=None):
    """Función para obtener estado de VPCs"""
    if ROLE_ARN:
        session = assume_role(ROLE_ARN, REGION)
        if not session:
            return []
        ec2_client = session.client('ec2')
    else:
        ec2_client = boto3.client('ec2', region_name=REGION)

    vpcs = ec2_client.describe_vpcs()['Vpcs']
    vpcs_info = []
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for vpc in vpcs:
            vpc_id = vpc['VpcId']
            vpc_name = next((tag['Value'] for tag in vpc.get('Tags', []) if tag.get('Key') == 'Name'), 'Unnamed')
            
            # Filtrar VPCs
            should_include = all_vpcs or (vpc_names and any(name.lower() in vpc_name.lower() for name in vpc_names))
            if vpc_name == 'Unnamed':
                should_include = False
            
            if should_include:
                futures.append(executor.submit(process_single_vpc_metrics, ec2_client, vpc_id, vpc_name))

        for future in concurrent.futures.as_completed(futures):
            vpcs_info.append(future.result())

    return vpcs_info

def process_single_vpc_metrics(ec2_client, vpc_id, vpc_name):
    """Procesar métricas de una VPC específica"""
    subnets = check_subnets(ec2_client, vpc_id)
    routes = check_route_tables(ec2_client, vpc_id)
    dns = check_dns_settings(ec2_client, vpc_id)
    vpn_metrics = check_vpn_tunnel_metrics(ec2_client, vpc_id)
    
    return (vpc_name, vpc_id, subnets, routes, dns, *vpn_metrics)

def check_subnets(ec2_client, vpc_id):
    """Verificar subredes"""
    try:
        subnets = ec2_client.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['Subnets']
        if not subnets:
            COMENTARIOS.append(f'VPC {vpc_id}: Sin subredes')
            return 'Sin subredes'
        
        available = [s for s in subnets if s['State'] == 'available']
        if len(available) != len(subnets):
            COMENTARIOS.append(f'VPC {vpc_id}: Subredes no disponibles')
        return f'{len(subnets)} subredes'
    except Exception as e:
        COMENTARIOS.append(f'VPC {vpc_id}: Error subredes')
        return 'Error'

def check_route_tables(ec2_client, vpc_id):
    """Verificar rutas"""
    try:
        tables = ec2_client.describe_route_tables(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['RouteTables']
        if not tables:
            return 'Sin rutas'
        
        active = sum(1 for rt in tables for route in rt['Routes'] if route['State'] == 'active')
        return f'{len(tables)} tablas, {active} rutas'
    except:
        return 'Error'

def check_dns_settings(ec2_client, vpc_id):
    """Verificar DNS"""
    try:
        support = ec2_client.describe_vpc_attribute(VpcId=vpc_id, Attribute='enableDnsSupport')['EnableDnsSupport']['Value']
        hostnames = ec2_client.describe_vpc_attribute(VpcId=vpc_id, Attribute='enableDnsHostnames')['EnableDnsHostnames']['Value']
        return 'DNS OK' if support and hostnames else 'DNS parcial'
    except:
        return 'Error'

def check_vpn_tunnel_metrics(ec2_client, vpc_id):
    """Verificar métricas VPN"""
    try:
        # Obtener VPN connections
        vgws = ec2_client.describe_vpn_gateways(Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}])['VpnGateways']
        if not vgws:
            return ('Sin VPN',) * 9
        
        vpn_connections = []
        for vgw in vgws:
            conns = ec2_client.describe_vpn_connections(Filters=[{'Name': 'vpn-gateway-id', 'Values': [vgw['VpnGatewayId']]}])['VpnConnections']
            vpn_connections.extend(conns)
        
        if not vpn_connections:
            return ('Sin VPN',) * 9
        
        # CloudWatch client
        import boto3
        region = getattr(ec2_client._client_config, 'region_name', 'us-east-1')
        try:
            creds = ec2_client._request_signer._credentials
            cw_client = boto3.client('cloudwatch', region_name=region,
                                   aws_access_key_id=creds.access_key,
                                   aws_secret_access_key=creds.secret_key,
                                   aws_session_token=creds.token)
        except:
            cw_client = boto3.client('cloudwatch', region_name=region)
        
        # Obtener métricas
        data_in_metrics, data_out_metrics, state_metrics = [], [], []
        
        for vpn_conn in vpn_connections:
            vpn_id = vpn_conn['VpnConnectionId']
            dimensions = [{'Name': 'VpnId', 'Value': vpn_id}]
            
            data_in = get_metric_statistics(cw_client, 'AWS/VPN', dimensions, 'TunnelDataIn')
            data_out = get_metric_statistics(cw_client, 'AWS/VPN', dimensions, 'TunnelDataOut')
            state = get_metric_statistics(cw_client, 'AWS/VPN', dimensions, 'TunnelState')
            
            if data_in and any(x != 0 for x in data_in):
                data_in_metrics.append(tuple(round(x / (1024 * 1024), 2) for x in data_in))
            if data_out and any(x != 0 for x in data_out):
                data_out_metrics.append(tuple(round(x / (1024 * 1024), 2) for x in data_out))
            if state:
                state_metrics.append(state)
        
        # Agregar métricas
        def aggregate(metrics):
            if not metrics:
                return (0, 0, 0)
            mins, maxs, avgs = zip(*metrics)
            return (min(mins), max(maxs), sum(avgs)/len(avgs))
        
        final_data_in = aggregate(data_in_metrics)
        final_data_out = aggregate(data_out_metrics)
        final_state = aggregate(state_metrics)
        
        if final_state[2] < 1:
            COMENTARIOS.append(f'VPC {vpc_id}: Túneles VPN desconectados')
        
        return (*final_data_in, *final_data_out, *final_state)
        
    except Exception as e:
        COMENTARIOS.append(f'VPC {vpc_id}: Error VPN')
        return ('Error',) * 9

def process_vpc_metrics(REGION, ROLE_ARN, vpc_names=None, all_vpcs=False):
    """Función principal"""
    try:
        return get_vpc_status(REGION, vpc_names, all_vpcs, ROLE_ARN)
    except Exception as e:
        COMENTARIOS.append(f"Error procesando VPC: {e}")
        return []

def return_vpc_comments():
    """Retorna comentarios"""
    return COMENTARIOS.copy()