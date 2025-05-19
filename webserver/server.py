from enum import Enum
import traceback
import random
import os
import sys
import getopt
import logging
import argparse

from flask import Flask, render_template, url_for, make_response
import boto3

# Conditionally import ec2_metadata
try:
    from ec2_metadata import ec2_metadata
except ImportError:
    ec2_metadata = None

region = 'us-east-2'

try:
    region = ec2_metadata.region
except:
    pass

logger = logging.getLogger(__name__)
logging.basicConfig(format='[%(levelname)s] %(asctime)s - %(message)s')
logger.setLevel(logging.DEBUG)

app = Flask(__name__)

# --- Configuração do Modo DEBUG e Região AWS ---
DEBUG_MODE = bool(os.environ.get('DEBUG_MODE', False))
MOCKED_RECOMMENDATIONS = None

if DEBUG_MODE:
    logger.info("****************************************************")
    logger.info("*** MODO DE DEBUG ATIVADO              ***")
    logger.info("*** As chamadas à AWS serão mockadas.            ***")
    logger.info("****************************************************")
    # Mock data for recommendations
    MOCKED_RECOMMENDATIONS = {
        "1": {"Result": {"S": "Viagem à Lua (Mock)"}, "UserName": {"S": "Jorge Méliès (Mock)"}},
        "2": {"Result": {"S": "O Gabinete do Dr. Caligari (Mock)"}, "UserName": {"S": "Robert Wiene (Mock)"}},
        "3": {"Result": {"S": "Nosferatu (Mock)"}, "UserName": {"S": "F.W. Murnau (Mock)"}},
        "4": {"Result": {"S": "Metropolis (Mock)"}, "UserName": {"S": "Fritz Lang (Mock)"}},
        "0": {"Result": {"S": "test"}, "UserName": {"S": "test"}} # For healthcheck
    }

class HealthCheckMode(Enum):
    NO_ERROR_HANDLING = 1,
    ERROR_HANDLING = 2, 
    DEEP_HEALTHCHECK = 3

HEALTHCHECK_MODE = HealthCheckMode.DEEP_HEALTHCHECK

# --- Funções Auxiliares ---
def call_getRecommendation(region, user_id):
    """
    Busca uma recomendação de TV.
    Se DEBUG_MODE=1, retorna dados mockados.
    Caso contrário, busca de uma tabela DynamoDB, simulando uma chamada a um serviço de recomendação.
    A disponibilidade do serviço (não debug) é controlada por um parâmetro no AWS SSM.
    """
    if DEBUG_MODE:
        logger.debug(f"[DEBUG] Chamando getRecommendation para UserID: {user_id} (mockado)")
        if str(user_id) in MOCKED_RECOMMENDATIONS:
            return {
                'Item': {
                    'ServiceAPI': {'S': 'getRecommendation'},
                    'UserID': {'N': str(user_id)},
                    **MOCKED_RECOMMENDATIONS[str(user_id)] # Merge user-specific mock data
                }
            }
        else:
            logger.debug(f"[DEBUG] UserID {user_id} não encontrado nos mocks. Retornando vazio.")
            return {} # Simula item não encontrado

    session = boto3.Session()
    ddb_client = session.client('dynamodb', region_name=region)
    ssm_client = session.client('ssm', region_name=region)

    dependency_enabled = True
    parameter_name = 'RecommendationServiceEnabled'
    try:
        value = ssm_client.get_parameter(Name=parameter_name)
        dependency_enabled = value['Parameter']['Value'].lower() == "true"
    except Exception as e:
        logger.warning(f"Aviso: Não foi possível obter o parâmetro SSM '{parameter_name}'. Assumindo que o serviço está habilitado. Erro: {e}")

    table_name = "RecommendationService" if dependency_enabled else "dependencyShouldFail"
    logger.debug(f"Tentando buscar recomendação da tabela: {table_name} para UserID: {user_id} na região {region}")

    try:
        response = ddb_client.get_item(
            TableName=table_name,
            Key={
                'ServiceAPI': {'S': 'getRecommendation'},
                'UserID': {'N': str(user_id)}
            }
        )
        if 'Item' not in response:
            logger.warning(f"Alerta: Nenhum item encontrado para UserID {user_id} na tabela {table_name}.")
            return {}
        return response
    except Exception as e:
        logger.error(f"Erro ao chamar DynamoDB (tabela: {table_name}): {e}")
        raise


def get_formatted_ec2_metadata():
    """
    Formata os metadados da instância EC2 para exibição.
    Se DEBUG_MODE=1, retorna dados mockados.
    Retorna uma string com os metadados ou uma mensagem se não estiver em EC2/ec2_metadata não disponível.
    """
    if DEBUG_MODE:
        metadata = {
            'account_id': 'mock-account-id',
            'region': 'mock-region',
            'az': 'mock-az',
            'ec2_instance_id': 'mock-instance-id',
            'ec2_instance_type': 'mock-instance-type',
            'ec2_ami_id': 'mock-ami-id',
            'private_hostname': 'mock-private-hostname',
            'private_ipv4': '10.0.0.1 (mock)'
        }
        return metadata

    if not ec2_metadata:
        return {'error': "Metadados EC2 não disponíveis (biblioteca ec2-metadata não encontrada ou não está em ambiente EC2)."}

    metadata_parts = []
    try:
        metadata = {
            'account_id': ec2_metadata.account_id,
            'region': ec2_metadata.region,
            'az': ec2_metadata.availability_zone,
            'ec2_instance_id': ec2_metadata.instance_id,
            'ec2_instance_type': ec2_metadata.instance_type,
            'ec2_ami_id': ec2_metadata.ami_id,
            'private_hostname': ec2_metadata.private_hostname,
            'private_ipv4': ec2_metadata.private_ipv4
        }
        return metadata
    
    except Exception as e:
        logger.error(f"Erro ao buscar metadados EC2: {e}")
        return {'error': "Metadados EC2 não disponíveis (erro ao buscar ou não está rodando em EC2)."}

# --- Rotas Flask ---
@app.route('/')
def home():
    global region
    """
    Rota principal que exibe recomendações de TV.
    """
    user_id = str(random.randint(1, 4))

    # Error handling:
    # surround the call to RecommendationService in a try catch
    tv_show = 'I Love Lucy'
    user_name = 'Valued Customer'
    diagnostic_info = None
    
    try:
        # Call the getRecommendation API on the RecommendationService
        response = call_getRecommendation(region, user_id)

        # Parses value of recommendation from DynamoDB JSON return value
        # {'Item': {
        #     'ServiceAPI': {'S': 'getRecommendation'}, 
        #     'UserID': {'N': '1'}, 
        #     'Result': {'S': 'M*A*S*H'},  ...
        tv_show = response['Item']['Result']['S']
        user_name = response['Item']['UserName']['S']

    # Error handling:
    # If the service dependency fails, and we cannot make a personalized recommendation
    # then give a pre-selected (static) recommendation
    # and report diagnostic information
    except Exception as e:
        diagnostic_info = \
        "We are unable to provide personalized recommendations.\nIf this persists, please report the following info to us:\n" \
        + str(traceback.format_exception_only(e.__class__, e))
        
        if HEALTHCHECK_MODE == HealthCheckMode.NO_ERROR_HANDLING:
            raise

    ec2_meta_content = get_formatted_ec2_metadata()
    
    response = render_template(
        'index.html',
        user_name=user_name,
        movie_title=tv_show,
        aws_metadata=ec2_meta_content,
        diagnostic_info=diagnostic_info
    )
    
    return response

@app.route('/healthcheck')
def healthcheck():
    """
    Rota de verificação de saúde. Verifica a dependência do serviço de recomendação.
    """
    global region
    is_healthy = True
    diagnostic_info = ''
    TEST = 'test'
    
    ec2_meta_content = get_formatted_ec2_metadata()

    if HEALTHCHECK_MODE == HealthCheckMode.DEEP_HEALTHCHECK:
        # Make a request to RecommendationService using a predefined 
        # test call as part of health assessment for this server
        try:
            # call RecommendationService using the test user
            user_id = str(0)
            response = call_getRecommendation(region, user_id)

            # Parses value of recommendation from DynamoDB JSON return value
            tv_show = response['Item']['Result']['S']
            user_name = response['Item']['UserName']['S']
            
            # Server is healthy of RecommendationService returned the expected response
            is_healthy = (tv_show == TEST) and (user_name == TEST)

        # If the service dependency fails, capture diagnostic info
        except Exception as e:
            is_healthy = False
            diagnostic_info = "Error message: \n"+ str(traceback.format_exception_only(e.__class__, e))

    # Based on the health assessment
    # If it succeeded return a healthy code
    # If it failed return a server failure code
    health_status = 'Healthy' if is_healthy else 'Unhealthy'
    response = None
    status_code = None
    
    if is_healthy:
        status_code = 200
        response = make_response(
            render_template(
                'healthcheck.html',
                health_status=health_status,
                is_healthy=is_healthy,
                diagnostic_info=diagnostic_info,
                aws_metadata=ec2_meta_content
            ), 
            status_code
        )
    else:
        status_code = 503
        response = make_response(
            render_template(
                'healthcheck.html',
                health_status=health_status,
                diagnostic_info=diagnostic_info,
                aws_metadata=ec2_meta_content
            ), 
            status_code
        )
    
    response.headers.set('Cache-Control', 'no-cache, no-store, must-revalidate')
    response.headers.set('Pragma', 'no-cache')
    response.headers.set('Expires', '0')
    
    return response

# Initialize server
def run(argv):
    global HEALTHCHECK_MODE
    global region

    parser = argparse.ArgumentParser(
                    prog='ProgramName',
                    description='What the program does',
                    epilog='Text at the bottom of help')
    
    # Default value - will be over-written if supplied via args
    server_port = 80
    server_ip = '0.0.0.0'
    HEALTHCHECK_MODE = HealthCheckMode.DEEP_HEALTHCHECK 
    try:
        region = ec2_metadata.region
    except:
        region = 'us-east-2'

    parser.add_argument('-s', '--server_ip', help="Server IP", required=False, type=str)
    parser.add_argument('-p', '--server_port', help="Server port", required=False, type=int)
    parser.add_argument('-o', '--operation_mode', help="Operation mode (1,2,3)", required=False, type=int)
    parser.add_argument('-r', '--region', help="AWS Region", required=False, type=str)
    
    args = parser.parse_args()
    
    if args.server_ip:
        server_ip = args.server_ip
    
    if args.server_port:
        server_port = args.server_port
    
    if args.region:
        region = args.region
    
    if args.operation_mode:
        mode = args.operation_mode
        if mode == 1:
            HEALTHCHECK_MODE = HealthCheckMode.NO_ERROR_HANDLING
        if mode == 2:
            HEALTHCHECK_MODE = HealthCheckMode.ERROR_HANDLING
        if mode == 3:
            HEALTHCHECK_MODE = HealthCheckMode.DEEP_HEALTHCHECK            

    # start server

    # debug=True do Flask é diferente do nosso DEBUG_MODE.
    # Manter o debug do Flask como True para desenvolvimento é útil.
    logger.info(f"Servidor Flask iniciando em http://{server_ip}:{server_port}, no modo {HEALTHCHECK_MODE}, região {region}")
    if DEBUG_MODE:
        logger.info("Rodando em MODO DEBUG. Chamadas à AWS serão mockadas.")
        
    app.run(host=server_ip, port=server_port, debug=False)

if __name__ == "__main__":
    run(sys.argv[1:])