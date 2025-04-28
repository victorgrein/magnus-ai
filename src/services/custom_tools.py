from typing import Any, Dict, List
from google.adk.tools import FunctionTool
import requests
import json
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class CustomToolBuilder:
    def __init__(self):
        self.tools = []

    def _create_http_tool(self, tool_config: Dict[str, Any]) -> FunctionTool:
        """Create an HTTP tool based on the provided configuration."""
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
                # Combines default values with provided values
                all_values = {**values, **kwargs}

                # Substitutes placeholders in headers
                processed_headers = {
                    k: v.format(**all_values) if isinstance(v, str) else v
                    for k, v in headers.items()
                }

                # Processes path parameters
                url = endpoint
                for param, value in parameters.get("path_params", {}).items():
                    if param in all_values:
                        url = url.replace(f"{{{param}}}", str(all_values[param]))

                # Process query parameters
                query_params = {}
                for param, value in parameters.get("query_params", {}).items():
                    if isinstance(value, list):
                        # If the value is a list, join with comma
                        query_params[param] = ",".join(value)
                    elif param in all_values:
                        # If the parameter is in the values, use the provided value
                        query_params[param] = all_values[param]
                    else:
                        # Otherwise, use the default value from the configuration
                        query_params[param] = value

                # Adds default values to query params if they are not present
                for param, value in values.items():
                    if param not in query_params and param not in parameters.get("path_params", {}):
                        query_params[param] = value

                # Processa body parameters
                body_data = {}
                for param, param_config in parameters.get("body_params", {}).items():
                    if param in all_values:
                        body_data[param] = all_values[param]

                # Adds default values to body if they are not present
                for param, value in values.items():
                    if param not in body_data and param not in query_params and param not in parameters.get("path_params", {}):
                        body_data[param] = value

                # Makes the HTTP request
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
                        f"Error in the request: {response.status_code} - {response.text}"
                    )

                # Always returns the response as a string
                return json.dumps(response.json())

            except Exception as e:
                logger.error(f"Error executing tool {name}: {str(e)}")
                return json.dumps(error_handling.get("fallback_response", {
                    "error": "tool_execution_error",
                    "message": str(e)
                }))

        # Adds dynamic docstring based on the configuration
        param_docs = []
        
        # Adds path parameters
        for param, value in parameters.get("path_params", {}).items():
            param_docs.append(f"{param}: {value}")
            
        # Adds query parameters
        for param, value in parameters.get("query_params", {}).items():
            if isinstance(value, list):
                param_docs.append(f"{param}: List[{', '.join(value)}]")
            else:
                param_docs.append(f"{param}: {value}")
                
        # Adds body parameters
        for param, param_config in parameters.get("body_params", {}).items():
            required = "Required" if param_config.get("required", False) else "Optional"
            param_docs.append(f"{param} ({param_config['type']}, {required}): {param_config['description']}")
                
        # Adds default values
        if values:
            param_docs.append("\nDefault values:")
            for param, value in values.items():
                param_docs.append(f"{param}: {value}")

        http_tool.__doc__ = f"""
        {description}
        
        Parameters:
        {chr(10).join(param_docs)}
        
        Returns:
        String containing the response in JSON format
        """

        # Defines the function name to be used by the ADK
        http_tool.__name__ = name

        return FunctionTool(func=http_tool)

    def build_tools(self, tools_config: Dict[str, Any]) -> List[FunctionTool]:
        """Builds a list of tools based on the provided configuration."""
        self.tools = []

        # Processes HTTP tools
        for http_tool_config in tools_config.get("http_tools", []):
            self.tools.append(self._create_http_tool(http_tool_config))

        return self.tools 