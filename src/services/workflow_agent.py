from datetime import datetime
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai.types import Content, Part

from typing import AsyncGenerator, Dict, Any, List, TypedDict, Annotated
import json
import uuid
import asyncio
import httpx
import threading

from google.adk.runners import Runner
from src.services.agent_service import get_agent

# Remover importação circular
# from src.services.agent_builder import AgentBuilder

from sqlalchemy.orm import Session

from langgraph.graph import StateGraph, END


class State(TypedDict):
    content: List[Event]
    status: str
    session_id: str
    # Additional fields to store any node outputs
    node_outputs: Dict[str, Any]
    # Cycle counter to prevent infinite loops
    cycle_count: int
    conversation_history: List[Event]


class WorkflowAgent(BaseAgent):
    """
    Agente que implementa fluxos de trabalho usando LangGraph.

    Este agente permite definir e executar fluxos complexos entre vários agentes
    utilizando o LangGraph para orquestração.
    """

    # Declarações de campo para Pydantic
    flow_json: Dict[str, Any]
    timeout: int
    db: Session

    def __init__(
        self,
        name: str,
        flow_json: Dict[str, Any],
        timeout: int = 300,
        sub_agents: List[BaseAgent] = [],
        db: Session = None,
        **kwargs,
    ):
        """
        Inicializa o agente de workflow.

        Args:
            name: Nome do agente
            flow_json: Definição do fluxo em formato JSON
            timeout: Tempo máximo de execução (segundos)
            sub_agents: Lista de sub-agentes a serem executados após o agente de workflow
            db: Session
        """
        # Inicializar classe base
        super().__init__(
            name=name,
            flow_json=flow_json,
            timeout=timeout,
            sub_agents=sub_agents,
            db=db,
            **kwargs,
        )

        print(
            f"Agente de workflow inicializado com {len(flow_json.get('nodes', []))} nós"
        )

    async def _create_node_functions(self, ctx: InvocationContext):
        """Cria as funções para cada tipo de nó no fluxo."""

        # Função para o nó inicial
        async def start_node_function(
            state: State,
            node_id: str,
            node_data: Dict[str, Any],
        ) -> AsyncGenerator[State, None]:
            print("\n🏁 NÓ INICIAL")

            content = state.get("content", [])

            if not content:
                content = [
                    Event(
                        author="agent",
                        content=Content(parts=[Part(text="Content not found")]),
                    )
                ]
                yield {
                    "content": content,
                    "status": "error",
                    "node_outputs": {},
                    "cycle_count": 0,
                    "conversation_history": ctx.session.events,
                }
                return
            session_id = state.get("session_id", "")

            # Armazenar resultados específicos para este nó
            node_outputs = state.get("node_outputs", {})
            node_outputs[node_id] = {"started_at": datetime.now().isoformat()}

            yield {
                "content": content,
                "status": "started",
                "node_outputs": node_outputs,
                "cycle_count": 0,
                "session_id": session_id,
                "conversation_history": ctx.session.events,
            }

        # Função genérica para nós de agente
        async def agent_node_function(
            state: State, node_id: str, node_data: Dict[str, Any]
        ) -> AsyncGenerator[State, None]:

            agent_config = node_data.get("agent", {})
            agent_name = agent_config.get("name", "")
            agent_id = agent_config.get("id", "")

            # Incrementar contador de ciclos
            cycle_count = state.get("cycle_count", 0) + 1
            print(f"\n👤 AGENTE: {agent_name} (Ciclo {cycle_count})")

            content = state.get("content", [])
            session_id = state.get("session_id", "")

            # Obter o histórico de conversa
            conversation_history = state.get("conversation_history", [])

            agent = get_agent(self.db, agent_id)

            if not agent:
                yield {
                    "content": [
                        Event(
                            author="agent",
                            content=Content(parts=[Part(text="Agent not found")]),
                        )
                    ],
                    "session_id": session_id,
                    "status": "error",
                    "node_outputs": {},
                    "cycle_count": cycle_count,
                    "conversation_history": conversation_history,
                }
                return

            # Importação movida para dentro da função para evitar circular import
            from src.services.agent_builder import AgentBuilder

            agent_builder = AgentBuilder(self.db)
            root_agent, exit_stack = await agent_builder.build_agent(agent)

            new_content = []
            async for event in root_agent.run_async(ctx):
                conversation_history.append(event)
                new_content.append(event)

            print(f"New content: {str(new_content)}")

            node_outputs = state.get("node_outputs", {})
            node_outputs[node_id] = {
                "processed_by": agent_name,
                "agent_content": new_content,
                "cycle": cycle_count,
            }

            yield {
                "content": new_content,
                "status": "processed_by_agent",
                "node_outputs": node_outputs,
                "cycle_count": cycle_count,
                "conversation_history": conversation_history,
                "session_id": session_id,
            }

            if exit_stack:
                await exit_stack.aclose()

        # Função para nós de condição
        async def condition_node_function(
            state: State, node_id: str, node_data: Dict[str, Any]
        ) -> AsyncGenerator[State, None]:
            label = node_data.get("label", "Condição Sem Nome")
            conditions = node_data.get("conditions", [])
            cycle_count = state.get("cycle_count", 0)

            print(f"\n🔄 CONDIÇÃO: {label} (Ciclo {cycle_count})")

            content = state.get("content", [])
            print(f"Avaliando condição para conteúdo: '{content}'")

            session_id = state.get("session_id", "")
            conversation_history = state.get("conversation_history", [])

            # Verificar todas as condições
            conditions_met = []
            for condition in conditions:
                condition_id = condition.get("id")
                condition_data = condition.get("data", {})
                field = condition_data.get("field")
                operator = condition_data.get("operator")
                expected_value = condition_data.get("value")

                print(
                    f"  Verificando se {field} {operator} '{expected_value}' (valor atual: '{state.get(field, '')}')"
                )
                if self._evaluate_condition(condition, state):
                    conditions_met.append(condition_id)
                    print(f"  ✅ Condição {condition_id} atendida!")

            # Verificar se o ciclo atingiu o limite (segurança extra)
            if cycle_count >= 10:
                print(
                    f"⚠️ ATENÇÃO: Limite de ciclos atingido ({cycle_count}). Forçando término."
                )
                yield {
                    "status": "cycle_limit_reached",
                    "node_outputs": state.get("node_outputs", {}),
                    "cycle_count": cycle_count,
                    "conversation_history": conversation_history,
                    "session_id": session_id,
                }
                return

            # Armazenar resultados específicos para este nó
            node_outputs = state.get("node_outputs", {})
            node_outputs[node_id] = {
                "condition_evaluated": label,
                "content_evaluated": content,
                "conditions_met": conditions_met,
                "cycle": cycle_count,
            }

            yield {
                "status": "condition_evaluated",
                "node_outputs": node_outputs,
                "cycle_count": cycle_count,
                "conversation_history": conversation_history,
                "session_id": session_id,
            }

        return {
            "start-node": start_node_function,
            "agent-node": agent_node_function,
            "condition-node": condition_node_function,
        }

    def _evaluate_condition(self, condition: Dict[str, Any], state: State) -> bool:
        """Avalia uma condição contra o estado atual."""
        condition_type = condition.get("type")
        condition_data = condition.get("data", {})

        if condition_type == "previous-output":
            field = condition_data.get("field")
            operator = condition_data.get("operator")
            expected_value = condition_data.get("value")

            actual_value = state.get(field, "")

            # Tratamento especial para quando content é uma lista de Event
            if field == "content" and isinstance(actual_value, list) and actual_value:
                # Extrai o texto de cada evento para comparação
                extracted_texts = []
                for event in actual_value:
                    if hasattr(event, "content") and hasattr(event.content, "parts"):
                        for part in event.content.parts:
                            if hasattr(part, "text") and part.text:
                                extracted_texts.append(part.text)

                if extracted_texts:
                    actual_value = " ".join(extracted_texts)
                    print(f"  Texto extraído dos eventos: '{actual_value[:100]}...'")

            # Converter valores para string para facilitar comparações
            if actual_value is not None:
                actual_str = str(actual_value)
            else:
                actual_str = ""

            if expected_value is not None:
                expected_str = str(expected_value)
            else:
                expected_str = ""

            # Verificações de definição
            if operator == "is_defined":
                result = actual_value is not None and actual_value != ""
                print(f"  Verificação '{operator}': {result}")
                return result
            elif operator == "is_not_defined":
                result = actual_value is None or actual_value == ""
                print(f"  Verificação '{operator}': {result}")
                return result

            # Verificações de igualdade
            elif operator == "equals":
                result = actual_str == expected_str
                print(f"  Verificação '{operator}': {result}")
                return result
            elif operator == "not_equals":
                result = actual_str != expected_str
                print(f"  Verificação '{operator}': {result}")
                return result

            # Verificações de conteúdo
            elif operator == "contains":
                # Converter ambos para minúsculas para comparação sem diferenciação
                expected_lower = expected_str.lower()
                actual_lower = actual_str.lower()
                print(
                    f"  Comparação 'contains' sem distinção de maiúsculas/minúsculas: '{expected_lower}' em '{actual_lower[:100]}...'"
                )
                result = expected_lower in actual_lower
                print(f"  Verificação '{operator}': {result}")
                return result
            elif operator == "not_contains":
                expected_lower = expected_str.lower()
                actual_lower = actual_str.lower()
                print(
                    f"  Comparação 'not_contains' sem distinção de maiúsculas/minúsculas: '{expected_lower}' em '{actual_lower[:100]}...'"
                )
                result = expected_lower not in actual_lower
                print(f"  Verificação '{operator}': {result}")
                return result

            # Verificações de início e fim
            elif operator == "starts_with":
                result = actual_str.lower().startswith(expected_str.lower())
                print(f"  Verificação '{operator}': {result}")
                return result
            elif operator == "ends_with":
                result = actual_str.lower().endswith(expected_str.lower())
                print(f"  Verificação '{operator}': {result}")
                return result

            # Verificações numéricas (tentando converter para número)
            elif operator in [
                "greater_than",
                "greater_than_or_equal",
                "less_than",
                "less_than_or_equal",
            ]:
                try:
                    actual_num = float(actual_str) if actual_str else 0
                    expected_num = float(expected_str) if expected_str else 0

                    if operator == "greater_than":
                        result = actual_num > expected_num
                    elif operator == "greater_than_or_equal":
                        result = actual_num >= expected_num
                    elif operator == "less_than":
                        result = actual_num < expected_num
                    elif operator == "less_than_or_equal":
                        result = actual_num <= expected_num
                    print(f"  Verificação numérica '{operator}': {result}")
                    return result
                except (ValueError, TypeError):
                    # Se não for possível converter para número, retorna falso
                    print(
                        f"  Erro ao converter valores para comparação numérica: '{actual_str[:100]}...' e '{expected_str}'"
                    )
                    return False

            # Verificações com expressões regulares
            elif operator == "matches":
                import re

                try:
                    pattern = re.compile(expected_str, re.IGNORECASE)
                    result = bool(pattern.search(actual_str))
                    print(f"  Verificação '{operator}': {result}")
                    return result
                except re.error:
                    print(f"  Erro na expressão regular: '{expected_str}'")
                    return False
            elif operator == "not_matches":
                import re

                try:
                    pattern = re.compile(expected_str, re.IGNORECASE)
                    result = not bool(pattern.search(actual_str))
                    print(f"  Verificação '{operator}': {result}")
                    return result
                except re.error:
                    print(f"  Erro na expressão regular: '{expected_str}'")
                    return True  # Se a regex for inválida, consideramos que não houve match

        return False

    def _create_flow_router(self, flow_data: Dict[str, Any]):
        """Cria um roteador baseado nas conexões no flow.json."""
        # Mapear conexões para entender como os nós se conectam
        edges_map = {}

        for edge in flow_data.get("edges", []):
            source = edge.get("source")
            target = edge.get("target")
            source_handle = edge.get("sourceHandle", "default")

            if source not in edges_map:
                edges_map[source] = {}

            # Armazenar o destino para cada handle específico
            edges_map[source][source_handle] = target

        # Mapear nós de condição e suas condições
        condition_nodes = {}
        for node in flow_data.get("nodes", []):
            if node.get("type") == "condition-node":
                node_id = node.get("id")
                conditions = node.get("data", {}).get("conditions", [])
                condition_nodes[node_id] = conditions

        # Função de roteamento para cada nó específico
        def create_router_for_node(node_id: str):
            def router(state: State) -> str:
                print(f"Roteando a partir do nó: {node_id}")

                # Verificar se o limite de ciclos foi atingido
                cycle_count = state.get("cycle_count", 0)
                if cycle_count >= 10:
                    print(
                        f"⚠️ Limite de ciclos ({cycle_count}) atingido. Finalizando o fluxo."
                    )
                    return END

                # Se for um nó de condição, avaliar as condições
                if node_id in condition_nodes:
                    conditions = condition_nodes[node_id]

                    for condition in conditions:
                        condition_id = condition.get("id")

                        # Verificar se a condição é atendida
                        is_condition_met = self._evaluate_condition(condition, state)

                        if is_condition_met:
                            print(
                                f"Condição {condition_id} atendida. Movendo para o próximo nó."
                            )

                            # Encontrar a conexão que usa este condition_id como handle
                            if (
                                node_id in edges_map
                                and condition_id in edges_map[node_id]
                            ):
                                return edges_map[node_id][condition_id]
                        else:
                            print(
                                f"Condição {condition_id} NÃO atendida. Continuando avaliação ou usando caminho padrão."
                            )

                    # Se nenhuma condição for atendida, usar o bottom-handle se disponível
                    if node_id in edges_map and "bottom-handle" in edges_map[node_id]:
                        print(
                            "Nenhuma condição atendida. Usando caminho padrão (bottom-handle)."
                        )
                        return edges_map[node_id]["bottom-handle"]
                    else:
                        print(
                            "Nenhuma condição atendida e não há caminho padrão. Encerrando fluxo."
                        )
                        return END

                # Para nós regulares, simplesmente seguir a primeira conexão disponível
                if node_id in edges_map:
                    # Tentar usar o handle padrão ou bottom-handle primeiro
                    for handle in ["default", "bottom-handle"]:
                        if handle in edges_map[node_id]:
                            return edges_map[node_id][handle]

                    # Se nenhum handle específico for encontrado, usar o primeiro disponível
                    if edges_map[node_id]:
                        first_handle = list(edges_map[node_id].keys())[0]
                        return edges_map[node_id][first_handle]

                # Se não houver conexão de saída, encerrar o fluxo
                print(
                    f"Nenhum caminho a seguir a partir do nó {node_id}. Encerrando fluxo."
                )
                return END

            return router

        return create_router_for_node

    async def _create_graph(
        self, ctx: InvocationContext, flow_data: Dict[str, Any]
    ) -> StateGraph:
        """Cria um StateGraph a partir dos dados do fluxo."""
        # Extrair nós do fluxo
        nodes = flow_data.get("nodes", [])

        # Inicializar StateGraph
        graph_builder = StateGraph(State)

        # Criar funções para cada tipo de nó
        node_functions = await self._create_node_functions(ctx)

        # Dicionário para armazenar funções específicas para cada nó
        node_specific_functions = {}

        # Adicionar nós ao grafo
        for node in nodes:
            node_id = node.get("id")
            node_type = node.get("type")
            node_data = node.get("data", {})

            if node_type in node_functions:
                # Criar uma função específica para este nó
                def create_node_function(node_type, node_id, node_data):
                    async def node_function(state):
                        # Consumir o gerador assíncrono e retornar o último resultado
                        result = None
                        async for item in node_functions[node_type](
                            state, node_id, node_data
                        ):
                            result = item
                        return result

                    return node_function

                # Adicionar função específica ao dicionário
                node_specific_functions[node_id] = create_node_function(
                    node_type, node_id, node_data
                )

                # Adicionar o nó ao grafo
                print(f"Adicionando nó {node_id} do tipo {node_type}")
                graph_builder.add_node(node_id, node_specific_functions[node_id])

        # Criar função para gerar roteadores específicos
        create_router = self._create_flow_router(flow_data)

        # Adicionar conexões condicionais para cada nó
        for node in nodes:
            node_id = node.get("id")

            if node_id in node_specific_functions:
                # Criar dicionário de possíveis destinos
                edge_destinations = {}

                # Mapear todos os possíveis destinos
                for edge in flow_data.get("edges", []):
                    if edge.get("source") == node_id:
                        target = edge.get("target")
                        if target in node_specific_functions:
                            edge_destinations[target] = target

                # Adicionar END como possível destino
                edge_destinations[END] = END

                # Criar roteador específico para este nó
                node_router = create_router(node_id)

                # Adicionar conexões condicionais
                print(f"Adicionando conexões condicionais para o nó {node_id}")
                print(f"Destinos possíveis: {edge_destinations}")

                graph_builder.add_conditional_edges(
                    node_id, node_router, edge_destinations
                )

        # Encontrar o nó inicial (geralmente o start-node)
        entry_point = None
        for node in nodes:
            if node.get("type") == "start-node":
                entry_point = node.get("id")
                break

        # Se não houver start-node, usar o primeiro nó encontrado
        if not entry_point and nodes:
            entry_point = nodes[0].get("id")

        # Definir ponto de entrada
        if entry_point:
            print(f"Definindo ponto de entrada: {entry_point}")
            graph_builder.set_entry_point(entry_point)

        # Compilar o grafo
        return graph_builder.compile()

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Implementação do agente de workflow.

        Este método segue o padrão de implementação de agentes personalizados,
        executando o fluxo de trabalho definido e retornando os resultados.
        """

        try:
            # 1. Extrair a mensagem do usuário do contexto
            user_message = None

            # Procurar a mensagem do usuário nos eventos da sessão
            if ctx.session and hasattr(ctx.session, "events") and ctx.session.events:
                for event in reversed(ctx.session.events):
                    if event.author == "user" and event.content and event.content.parts:
                        user_message = event.content.parts[0].text
                        print("Mensagem encontrada nos eventos da sessão")
                        break

            # Verificar no estado da sessão se a mensagem não foi encontrada nos eventos
            if not user_message and ctx.session and ctx.session.state:
                if "user_message" in ctx.session.state:
                    user_message = ctx.session.state["user_message"]
                elif "message" in ctx.session.state:
                    user_message = ctx.session.state["message"]

            # 2. Usar o ID da sessão como identificador estável
            session_id = (
                str(ctx.session.id)
                if ctx.session and hasattr(ctx.session, "id")
                else str(uuid.uuid4())
            )

            # 3. Criar o grafo de fluxo de trabalho a partir do JSON fornecido
            graph = await self._create_graph(ctx, self.flow_json)

            # 4. Preparar o estado inicial
            initial_state = State(
                content=[
                    Event(
                        author="user",
                        content=Content(parts=[Part(text=user_message)]),
                    )
                ],
                status="started",
                session_id=session_id,
                cycle_count=0,
                node_outputs={},
                conversation_history=ctx.session.events,
            )

            # 5. Executar o grafo
            print("\n🚀 Iniciando execução do fluxo de trabalho:")
            print(f"Conteúdo inicial: {user_message[:100]}...")

            # Executar o grafo com limite de recursão para evitar loops infinitos
            result = await graph.ainvoke(initial_state, {"recursion_limit": 20})

            # 6. Processar e retornar o resultado
            final_content = result.get("content", [])
            print(f"\n✅ RESULTADO FINAL: {final_content[:100]}...")

            for content in final_content:
                yield content

            # Executar sub-agentes
            for sub_agent in self.sub_agents:
                async for event in sub_agent.run_async(ctx):
                    yield event

        except Exception as e:
            # Tratar qualquer erro não capturado
            error_msg = f"Erro ao executar o agente de workflow: {str(e)}"
            print(error_msg)
            yield Event(
                author=self.name,
                content=Content(
                    role="agent",
                    parts=[Part(text=error_msg)],
                ),
            )
