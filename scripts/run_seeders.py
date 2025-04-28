"""
Script principal para executar todos os seeders em sequência.
Verifica as dependências entre os seeders e executa na ordem correta.
"""

import os
import sys
import logging
import argparse
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Importar seeders
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.seeders.admin_seeder import create_admin_user
from scripts.seeders.client_seeder import create_demo_client_and_user
from scripts.seeders.agent_seeder import create_demo_agents
from scripts.seeders.mcp_server_seeder import create_mcp_servers
from scripts.seeders.tool_seeder import create_tools
from scripts.seeders.contact_seeder import create_demo_contacts

def setup_environment():
    """Configura o ambiente para os seeders"""
    load_dotenv()
    
    # Verificar se as variáveis de ambiente essenciais estão definidas
    required_vars = ["POSTGRES_CONNECTION_STRING"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Variáveis de ambiente necessárias não definidas: {', '.join(missing_vars)}")
        return False
        
    return True

def run_seeders(seeders):
    """
    Executa os seeders especificados
    
    Args:
        seeders (list): Lista de seeders para executar
        
    Returns:
        bool: True se todos os seeders foram executados com sucesso, False caso contrário
    """
    all_seeders = {
        "admin": create_admin_user,
        "client": create_demo_client_and_user,
        "agents": create_demo_agents,
        "mcp_servers": create_mcp_servers,
        "tools": create_tools,
        "contacts": create_demo_contacts
    }
    
    # Define a ordem correta de execução (dependências)
    seeder_order = ["admin", "client", "mcp_servers", "tools", "agents", "contacts"]
    
    # Se nenhum seeder for especificado, executar todos
    if not seeders:
        seeders = seeder_order
    else:
        # Verificar se todos os seeders especificados existem
        invalid_seeders = [s for s in seeders if s not in all_seeders]
        if invalid_seeders:
            logger.error(f"Seeders inválidos: {', '.join(invalid_seeders)}")
            logger.info(f"Seeders disponíveis: {', '.join(all_seeders.keys())}")
            return False
        
        # Garantir que seeders sejam executados na ordem correta
        seeders = [s for s in seeder_order if s in seeders]
    
    # Executar seeders
    success = True
    for seeder_name in seeders:
        logger.info(f"Executando seeder: {seeder_name}")
        
        try:
            seeder_func = all_seeders[seeder_name]
            if not seeder_func():
                logger.error(f"Falha ao executar seeder: {seeder_name}")
                success = False
        except Exception as e:
            logger.error(f"Erro ao executar seeder {seeder_name}: {str(e)}")
            success = False
    
    return success

def main():
    """Função principal"""
    parser = argparse.ArgumentParser(description='Executa seeders para popular o banco de dados')
    parser.add_argument('--seeders', nargs='+', help='Seeders para executar (admin, client, agents, mcp_servers, tools, contacts)')
    args = parser.parse_args()
    
    # Configurar ambiente
    if not setup_environment():
        sys.exit(1)
    
    # Executar seeders
    success = run_seeders(args.seeders)
    
    # Saída
    if success:
        logger.info("Todos os seeders foram executados com sucesso")
        sys.exit(0)
    else:
        logger.error("Houve erros ao executar os seeders")
        sys.exit(1)

if __name__ == "__main__":
    main() 