import boto3
import concurrent.futures
from .utils import assume_role

COMENTARIOS = []

def get_vpc_status(REGION, vpc_names=None, all_vpcs=False, ROLE_ARN=None):
    """Función para obtener estado de VPCs"""
    if ROLE_ARN:
        session = assume_role(ROLE_ARN, REGION)
        if not session:
            print(f"Error: No se pudo asumir el rol {ROLE_ARN}")
            return []
        ec2_client = session.client('ec2')
    else:
        ec2_client = boto3.client('ec2', region_name=REGION)

    response = ec2_client.describe_vpcs()
    
    vpcs_info = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []

        for vpc in response['Vpcs']:
            vpc_id = vpc['VpcId']
            vpc_name = next((tag['Value'] for tag in vpc.get('Tags', []) if tag.get('Key') == 'Name'), 'Unnamed')
            
            # Filtrar VPCs
            should_include = False
            if all_vpcs:
                should_include = True
            elif vpc_names:
                should_include = any(name.lower() in vpc_name.lower() for name in vpc_names)
            
            if should_include:
                futures.append(executor.submit(process_single_vpc_metrics, ec2_client, vpc_id, vpc_name))

        for future in concurrent.futures.as_completed(futures):
            vpcs_info.append(future.result())

    return vpcs_info

def process_single_vpc_metrics(ec2_client, vpc_id, vpc_name):
    """Procesar métricas de una VPC específica"""
    
    # 1. Conectividad de red
    subnets_status = check_subnets(ec2_client, vpc_id)
    route_tables_status = check_route_tables(ec2_client, vpc_id)
    gateways_status = check_gateways(ec2_client, vpc_id)
    
    # 2. Resolución DNS
    dns_status = check_dns_settings(ec2_client, vpc_id)
    
    # 3. Seguridad
    security_groups_status = check_security_groups(ec2_client, vpc_id)
    nacls_status = check_nacls(ec2_client, vpc_id)
    
    # 4. Métricas de túneles VPN
    tunnel_metrics = check_vpn_tunnel_metrics(ec2_client, vpc_id)
    
    return (vpc_name, vpc_id, subnets_status, route_tables_status, 
            gateways_status, dns_status, security_groups_status, nacls_status, *tunnel_metrics)

def check_subnets(ec2_client, vpc_id):
    """Verificar subredes de la VPC"""
    try:
        response = ec2_client.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
        subnets = response['Subnets']
        
        if not subnets:
            COMENTARIOS.append(f'VPC {vpc_id}: No tiene subredes configuradas')
            return 'Sin subredes'
        
        available_subnets = [s for s in subnets if s['State'] == 'available']
        if len(available_subnets) != len(subnets):
            COMENTARIOS.append(f'VPC {vpc_id}: Algunas subredes no están disponibles')
            return f'{len(available_subnets)}/{len(subnets)} disponibles'
        
        return f'{len(subnets)} subredes OK'
    except Exception as e:
        COMENTARIOS.append(f'VPC {vpc_id}: Error verificando subredes - {e}')
        return 'Error'

def check_route_tables(ec2_client, vpc_id):
    """Verificar tablas de rutas"""
    try:
        response = ec2_client.describe_route_tables(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
        route_tables = response['RouteTables']
        
        if not route_tables:
            COMENTARIOS.append(f'VPC {vpc_id}: No tiene tablas de rutas')
            return 'Sin rutas'
        
        # Verificar rutas activas
        active_routes = 0
        for rt in route_tables:
            for route in rt['Routes']:
                if route['State'] == 'active':
                    active_routes += 1
        
        if active_routes == 0:
            COMENTARIOS.append(f'VPC {vpc_id}: No hay rutas activas')
            return 'Sin rutas activas'
        
        return f'{len(route_tables)} tablas, {active_routes} rutas activas'
    except Exception as e:
        COMENTARIOS.append(f'VPC {vpc_id}: Error verificando rutas - {e}')
        return 'Error'

def check_gateways(ec2_client, vpc_id):
    """Verificar gateways (IGW, NAT, VGW)"""
    try:
        gateways = []
        
        # Internet Gateway
        igw_response = ec2_client.describe_internet_gateways(
            Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}]
        )
        if igw_response['InternetGateways']:
            gateways.append('IGW')
        
        # NAT Gateway
        nat_response = ec2_client.describe_nat_gateways(
            Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
        )
        available_nats = [n for n in nat_response['NatGateways'] if n['State'] == 'available']
        if available_nats:
            gateways.append(f'NAT({len(available_nats)})')
        
        # VPN Gateway
        vpn_response = ec2_client.describe_vpn_gateways(
            Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}]
        )
        if vpn_response['VpnGateways']:
            gateways.append('VGW')
        
        if not gateways:
            return 'Sin gateways'
        
        return ', '.join(gateways)
    except Exception as e:
        COMENTARIOS.append(f'VPC {vpc_id}: Error verificando gateways - {e}')
        return 'Error'

def check_dns_settings(ec2_client, vpc_id):
    """Verificar configuración DNS"""
    try:
        response = ec2_client.describe_vpc_attribute(VpcId=vpc_id, Attribute='enableDnsSupport')
        dns_support = response['EnableDnsSupport']['Value']
        
        response = ec2_client.describe_vpc_attribute(VpcId=vpc_id, Attribute='enableDnsHostnames')
        dns_hostnames = response['EnableDnsHostnames']['Value']
        
        if not dns_support:
            COMENTARIOS.append(f'VPC {vpc_id}: DNS Support deshabilitado')
        if not dns_hostnames:
            COMENTARIOS.append(f'VPC {vpc_id}: DNS Hostnames deshabilitado')
        
        if dns_support and dns_hostnames:
            return 'DNS OK'
        elif dns_support:
            return 'Solo DNS Support'
        else:
            return 'DNS deshabilitado'
    except Exception as e:
        COMENTARIOS.append(f'VPC {vpc_id}: Error verificando DNS - {e}')
        return 'Error'

def check_security_groups(ec2_client, vpc_id):
    """Verificar Security Groups"""
    try:
        response = ec2_client.describe_security_groups(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
        security_groups = response['SecurityGroups']
        
        if not security_groups:
            COMENTARIOS.append(f'VPC {vpc_id}: No tiene Security Groups')
            return 'Sin SGs'
        
        # Verificar reglas restrictivas
        restrictive_sgs = 0
        for sg in security_groups:
            if sg['GroupName'] == 'default':
                continue
            if not sg['IpPermissions'] and not sg['IpPermissionsEgress']:
                restrictive_sgs += 1
        
        if restrictive_sgs > 0:
            COMENTARIOS.append(f'VPC {vpc_id}: {restrictive_sgs} Security Groups sin reglas')
        
        return f'{len(security_groups)} SGs'
    except Exception as e:
        COMENTARIOS.append(f'VPC {vpc_id}: Error verificando Security Groups - {e}')
        return 'Error'

def check_nacls(ec2_client, vpc_id):
    """Verificar Network ACLs"""
    try:
        response = ec2_client.describe_network_acls(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
        nacls = response['NetworkAcls']
        
        if not nacls:
            COMENTARIOS.append(f'VPC {vpc_id}: No tiene NACLs')
            return 'Sin NACLs'
        
        # Verificar NACLs muy restrictivos
        restrictive_nacls = 0
        for nacl in nacls:
            if nacl['IsDefault']:
                continue
            # Verificar si tiene reglas DENY explícitas
            deny_rules = [e for e in nacl['Entries'] if e['RuleAction'] == 'deny' and e['RuleNumber'] < 32766]
            if deny_rules:
                restrictive_nacls += 1
        
        if restrictive_nacls > 0:
            COMENTARIOS.append(f'VPC {vpc_id}: {restrictive_nacls} NACLs con reglas restrictivas')
        
        return f'{len(nacls)} NACLs'
    except Exception as e:
        COMENTARIOS.append(f'VPC {vpc_id}: Error verificando NACLs - {e}')
        return 'Error'



def check_vpn_tunnel_metrics(ec2_client, vpc_id):
    """Verificar métricas de túneles VPN"""
    try:
        # Obtener conexiones VPN asociadas a la VPC
        vpn_response = ec2_client.describe_vpn_connections(
            Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
        )
        
        if not vpn_response['VpnConnections']:
            return ('Sin VPN', 'Sin VPN', 'Sin VPN')
        
        # Crear cliente CloudWatch
        from .utils import assume_role
        session = assume_role(None, ec2_client.meta.region_name) if hasattr(ec2_client, 'meta') else None
        if session:
            cw_client = session.client('cloudwatch')
        else:
            import boto3
            cw_client = boto3.client('cloudwatch', region_name='us-east-1')
        
        tunnel_data_in = 0
        tunnel_data_out = 0
        tunnel_state = 0
        
        for vpn_conn in vpn_response['VpnConnections']:
            vpn_id = vpn_conn['VpnConnectionId']
            
            # Métricas de túnel
            from .utils import get_metric_statistics
            
            # TunnelDataIn (Sum)
            data_in = get_metric_statistics(
                cw_client, 'AWS/VPN', 
                [{'Name': 'VpnId', 'Value': vpn_id}], 
                'TunnelDataIn', ['Sum']
            )
            tunnel_data_in += data_in[0] if data_in else 0
            
            # TunnelDataOut (Sum)
            data_out = get_metric_statistics(
                cw_client, 'AWS/VPN', 
                [{'Name': 'VpnId', 'Value': vpn_id}], 
                'TunnelDataOut', ['Sum']
            )
            tunnel_data_out += data_out[0] if data_out else 0
            
            # TunnelState (Average)
            state = get_metric_statistics(
                cw_client, 'AWS/VPN', 
                [{'Name': 'VpnId', 'Value': vpn_id}], 
                'TunnelState', ['Average']
            )
            tunnel_state = max(tunnel_state, state[0] if state else 0)
        
        # Alertas
        if tunnel_state < 1:
            COMENTARIOS.append(f'VPC {vpc_id}: Túneles VPN desconectados (estado: {tunnel_state})')
        
        return (round(tunnel_data_in/1024/1024, 2), round(tunnel_data_out/1024/1024, 2), round(tunnel_state, 2))
        
    except Exception as e:
        COMENTARIOS.append(f'VPC {vpc_id}: Error verificando métricas VPN - {e}')
        return ('Error', 'Error', 'Error')

def process_vpc_metrics(REGION, ROLE_ARN, vpc_names=None, all_vpcs=False):
    """Función principal para procesar métricas de VPC"""
    try:
        vpcs_data = get_vpc_status(REGION, vpc_names, all_vpcs, ROLE_ARN)
        return vpcs_data
    except Exception as e:
        print(f"Error procesando VPC: {e}")
        COMENTARIOS.append(f"Error procesando VPC: {e}")
        return []

def return_vpc_comments():
    """Retorna los comentarios generados durante el procesamiento de VPC"""
    return COMENTARIOS.copy()