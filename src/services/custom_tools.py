from typing import Any, Dict, List, Optional
from google.adk.tools import FunctionTool
import requests
import json
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class CustomToolBuilder:
    def __init__(self):
        self.tools = []

    def _create_http_tool(self, tool_config: Dict[str, Any]) -> FunctionTool:
        """Cria uma ferramenta HTTP baseada na configuração fornecida."""
        name = tool_config["name"]
        description = tool_config["description"]
        endpoint = tool_config["endpoint"]
        method = tool_config["method"]
        headers = tool_config.get("headers", {})
        parameters = tool_config.get("parameters", {})
        values = tool_config.get("values", {})
        error_handling = tool_config.get("error_handling", {})

        def http_tool(**kwargs):
            try:
                # Combina valores padrão com valores fornecidos
                all_values = {**values, **kwargs}

                # Substitui placeholders nos headers
                processed_headers = {
                    k: v.format(**all_values) if isinstance(v, str) else v
                    for k, v in headers.items()
                }

                # Processa path parameters
                url = endpoint
                for param, value in parameters.get("path_params", {}).items():
                    if param in all_values:
                        url = url.replace(f"{{{param}}}", str(all_values[param]))

                # Processa query parameters
                query_params = {}
                for param, value in parameters.get("query_params", {}).items():
                    if isinstance(value, list):
                        # Se o valor for uma lista, junta com vírgula
                        query_params[param] = ",".join(value)
                    elif param in all_values:
                        # Se o parâmetro estiver nos valores, usa o valor fornecido
                        query_params[param] = all_values[param]
                    else:
                        # Caso contrário, usa o valor padrão da configuração
                        query_params[param] = value

                # Adiciona valores padrão aos query params se não estiverem presentes
                for param, value in values.items():
                    if param not in query_params and param not in parameters.get("path_params", {}):
                        query_params[param] = value

                # Processa body parameters
                body_data = {}
                for param, param_config in parameters.get("body_params", {}).items():
                    if param in all_values:
                        body_data[param] = all_values[param]

                # Adiciona valores padrão ao body se não estiverem presentes
                for param, value in values.items():
                    if param not in body_data and param not in query_params and param not in parameters.get("path_params", {}):
                        body_data[param] = value

                # Faz a requisição HTTP
                response = requests.request(
                    method=method,
                    url=url,
                    headers=processed_headers,
                    params=query_params,
                    json=body_data if body_data else None,
                    timeout=error_handling.get("timeout", 30)
                )

                if response.status_code >= 400:
                    raise requests.exceptions.HTTPError(
                        f"Erro na requisição: {response.status_code} - {response.text}"
                    )

                # Sempre retorna a resposta como string
                return json.dumps(response.json())

            except Exception as e:
                logger.error(f"Erro ao executar ferramenta {name}: {str(e)}")
                return json.dumps(error_handling.get("fallback_response", {
                    "error": "tool_execution_error",
                    "message": str(e)
                }))

        # Adiciona docstring dinâmica baseada na configuração
        param_docs = []
        
        # Adiciona path parameters
        for param, value in parameters.get("path_params", {}).items():
            param_docs.append(f"{param}: {value}")
            
        # Adiciona query parameters
        for param, value in parameters.get("query_params", {}).items():
            if isinstance(value, list):
                param_docs.append(f"{param}: List[{', '.join(value)}]")
            else:
                param_docs.append(f"{param}: {value}")
                
        # Adiciona body parameters
        for param, param_config in parameters.get("body_params", {}).items():
            required = "Obrigatório" if param_config.get("required", False) else "Opcional"
            param_docs.append(f"{param} ({param_config['type']}, {required}): {param_config['description']}")
                
        # Adiciona valores padrão
        if values:
            param_docs.append("\nValores padrão:")
            for param, value in values.items():
                param_docs.append(f"{param}: {value}")

        http_tool.__doc__ = f"""
        {description}
        
        Parâmetros:
        {chr(10).join(param_docs)}
        
        Retorna:
        String contendo a resposta em formato JSON
        """

        # Define o nome da função para ser usado pelo ADK
        http_tool.__name__ = name

        return FunctionTool(func=http_tool)

    def build_tools(self, tools_config: Dict[str, Any]) -> List[FunctionTool]:
        """Constrói uma lista de ferramentas baseada na configuração fornecida."""
        self.tools = []

        # Processa ferramentas HTTP
        for http_tool_config in tools_config.get("http_tools", []):
            self.tools.append(self._create_http_tool(http_tool_config))

        return self.tools 