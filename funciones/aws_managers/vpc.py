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

    # 2. Resolución DNS
    dns_status = check_dns_settings(ec2_client, vpc_id)
    
    # 4. Métricas de túneles VPN
    tunnel_metrics = check_vpn_tunnel_metrics(ec2_client, vpc_id)
    
    return (vpc_name, vpc_id, subnets_status, route_tables_status, dns_status, *tunnel_metrics)

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

def check_vpn_tunnel_metrics(ec2_client, vpc_id):
    """Verificar métricas de túneles VPN con Min, Max, Avg"""
    try:
        # Obtener VPN Gateways asociados a la VPC
        vgw_response = ec2_client.describe_vpn_gateways(
            Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}]
        )
        
        if not vgw_response['VpnGateways']:
            return ('Sin VPN',) * 9  # 3 métricas x 3 valores cada una
        
        # Obtener conexiones VPN para estos VGWs
        vpn_connections = []
        for vgw in vgw_response['VpnGateways']:
            vpn_response = ec2_client.describe_vpn_connections(
                Filters=[{'Name': 'vpn-gateway-id', 'Values': [vgw['VpnGatewayId']]}]
            )
            vpn_connections.extend(vpn_response['VpnConnections'])
        
        if not vpn_connections:
            return ('Sin VPN',) * 9
        
        # Crear cliente CloudWatch usando la misma sesión que ec2_client
        import boto3
        if hasattr(ec2_client, '_client_config') and hasattr(ec2_client._client_config, 'region_name'):
            region = ec2_client._client_config.region_name
        else:
            region = 'us-east-1'
        
        # Si ec2_client tiene credenciales de sesión, usar las mismas
        try:
            # Intentar usar las mismas credenciales que ec2_client
            cw_client = boto3.client('cloudwatch', 
                                   region_name=region,
                                   aws_access_key_id=ec2_client._request_signer._credentials.access_key,
                                   aws_secret_access_key=ec2_client._request_signer._credentials.secret_key,
                                   aws_session_token=ec2_client._request_signer._credentials.token)
        except:
            # Fallback a cliente por defecto
            cw_client = boto3.client('cloudwatch', region_name=region)
        
        # Acumuladores para todas las métricas
        vpn_data_in_metrics = []
        vpn_data_out_metrics = []
        vpn_state_metrics = []
        
        from .utils import get_metric_statistics
        
        for vpn_conn in vpn_connections:
            vpn_id = vpn_conn['VpnConnectionId']
            print(f"Procesando VPN: {vpn_id}")
            
            # Obtener IPs de los túneles
            tunnel_ips = []
            for tunnel in vpn_conn.get('Options', {}).get('TunnelOptions', []):
                if 'TunnelInsideIpv4' in tunnel:
                    tunnel_ips.append(tunnel['TunnelInsideIpv4'])
            
            # Si no hay IPs específicas, usar solo VpnId
            if not tunnel_ips:
                tunnel_ips = [None]
            
            for tunnel_ip in tunnel_ips:
                dimensions = [{'Name': 'VpnId', 'Value': vpn_id}]
                if tunnel_ip:
                    dimensions.append({'Name': 'TunnelIpAddress', 'Value': tunnel_ip})
                
                # TunnelDataIn (Min, Max, Avg)
                data_in = get_metric_statistics(
                    cw_client, 'AWS/VPN', dimensions, 'TunnelDataIn'
                )
                if data_in and any(x != 0 for x in data_in):
                    # Convertir a MB
                    data_in_mb = tuple(round(x / (1024 * 1024), 2) for x in data_in)
                    vpn_data_in_metrics.append(data_in_mb)
                    print(f"TunnelDataIn: Min={data_in_mb[0]}, Max={data_in_mb[1]}, Avg={data_in_mb[2]} MB")
                
                # TunnelDataOut (Min, Max, Avg)
                data_out = get_metric_statistics(
                    cw_client, 'AWS/VPN', dimensions, 'TunnelDataOut'
                )
                if data_out and any(x != 0 for x in data_out):
                    # Convertir a MB
                    data_out_mb = tuple(round(x / (1024 * 1024), 2) for x in data_out)
                    vpn_data_out_metrics.append(data_out_mb)
                    print(f"TunnelDataOut: Min={data_out_mb[0]}, Max={data_out_mb[1]}, Avg={data_out_mb[2]} MB")
                
                # TunnelState (Min, Max, Avg)
                state = get_metric_statistics(
                    cw_client, 'AWS/VPN', dimensions, 'TunnelState'
                )
                if state:
                    vpn_state_metrics.append(state)
                    print(f"TunnelState: Min={state[0]}, Max={state[1]}, Avg={state[2]}")
        
        # Agregar métricas de todos los túneles
        def aggregate_metrics(metrics_list):
            if not metrics_list:
                return (0, 0, 0)
            mins = [m[0] for m in metrics_list]
            maxs = [m[1] for m in metrics_list]
            avgs = [m[2] for m in metrics_list]
            return (min(mins), max(maxs), sum(avgs)/len(avgs))
        
        final_data_in = aggregate_metrics(vpn_data_in_metrics)
        final_data_out = aggregate_metrics(vpn_data_out_metrics)
        final_state = aggregate_metrics(vpn_state_metrics)
        
        # Alertas
        if final_state[2] < 1:  # Average state
            COMENTARIOS.append(f'VPC {vpc_id}: Túneles VPN desconectados (estado promedio: {final_state[2]:.2f})')
        
        print(f"Resumen VPC {vpc_id}: DataIn={final_data_in}, DataOut={final_data_out}, State={final_state}")
        
        # Retornar 9 valores: 3 para cada métrica (Min, Max, Avg)
        return (*final_data_in, *final_data_out, *final_state)
        
    except Exception as e:
        COMENTARIOS.append(f'VPC {vpc_id}: Error verificando métricas VPN - {e}')
        return ('Error',) * 9

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