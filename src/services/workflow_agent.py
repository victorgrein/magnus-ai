"""
┌──────────────────────────────────────────────────────────────────────────────┐
│ @author: Davidson Gomes                                                      │
│ @file: run_seeders.py                                                        │
│ Developed by: Davidson Gomes                                                 │
│ Creation date: May 13, 2025                                                  │
│ Contact: contato@evolution-api.com                                           │
├──────────────────────────────────────────────────────────────────────────────┤
│ @copyright © Evolution API 2025. All rights reserved.                        │
│ Licensed under the Apache License, Version 2.0                               │
│                                                                              │
│ You may not use this file except in compliance with the License.             │
│ You may obtain a copy of the License at                                      │
│                                                                              │
│    http://www.apache.org/licenses/LICENSE-2.0                                │
│                                                                              │
│ Unless required by applicable law or agreed to in writing, software          │
│ distributed under the License is distributed on an "AS IS" BASIS,            │
│ WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.     │
│ See the License for the specific language governing permissions and          │
│ limitations under the License.                                               │
├──────────────────────────────────────────────────────────────────────────────┤
│ @important                                                                   │
│ For any future changes to the code in this file, it is recommended to        │
│ include, together with the modification, the information of the developer    │
│ who changed it and the date of modification.                                 │
└──────────────────────────────────────────────────────────────────────────────┘
"""

from datetime import datetime
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai.types import Content, Part

from typing import AsyncGenerator, Dict, Any, List, TypedDict
import uuid

from src.services.agent_service import get_agent

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
    Agent that implements workflow flows using LangGraph.

    This agent allows defining and executing complex workflows between multiple agents
    using LangGraph for orchestration.
    """

    # Field declarations for Pydantic
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
        Initializes the workflow agent.

        Args:
            name: Agent name
            flow_json: Workflow definition in JSON format
            timeout: Maximum execution time (seconds)
            sub_agents: List of sub-agents to be executed after the workflow agent
            db: Session
        """
        # Initialize base class
        super().__init__(
            name=name,
            flow_json=flow_json,
            timeout=timeout,
            sub_agents=sub_agents,
            db=db,
            **kwargs,
        )

        print(
            f"Workflow agent initialized with {len(flow_json.get('nodes', []))} nodes"
        )

    async def _create_node_functions(self, ctx: InvocationContext):
        """Creates functions for each type of node in the flow."""

        # Function for the initial node
        async def start_node_function(
            state: State,
            node_id: str,
            node_data: Dict[str, Any],
        ) -> AsyncGenerator[State, None]:
            print("\n🏁 INITIAL NODE")

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

            # Store specific results for this node
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

        # Generic function for agent nodes
        async def agent_node_function(
            state: State, node_id: str, node_data: Dict[str, Any]
        ) -> AsyncGenerator[State, None]:

            agent_config = node_data.get("agent", {})
            agent_name = agent_config.get("name", "")
            agent_id = agent_config.get("id", "")

            # Increment cycle counter
            cycle_count = state.get("cycle_count", 0) + 1
            print(f"\n👤 AGENT: {agent_name} (Cycle {cycle_count})")

            content = state.get("content", [])
            session_id = state.get("session_id", "")

            # Get conversation history
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

            # Import moved to inside the function to avoid circular import
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

            content = content + new_content

            yield {
                "content": content,
                "status": "processed_by_agent",
                "node_outputs": node_outputs,
                "cycle_count": cycle_count,
                "conversation_history": conversation_history,
                "session_id": session_id,
            }

            if exit_stack:
                await exit_stack.aclose()

        # Function for condition nodes
        async def condition_node_function(
            state: State, node_id: str, node_data: Dict[str, Any]
        ) -> AsyncGenerator[State, None]:
            label = node_data.get("label", "No name condition")
            conditions = node_data.get("conditions", [])
            cycle_count = state.get("cycle_count", 0)

            print(f"\n🔄 CONDITION: {label} (Cycle {cycle_count})")

            content = state.get("content", [])
            conversation_history = state.get("conversation_history", [])

            latest_event = None
            if content and len(content) > 0:
                for event in reversed(content):
                    if (
                        event.author != "agent"
                        or not hasattr(event.content, "parts")
                        or not event.content.parts
                    ):
                        latest_event = event
                        break
                if latest_event:
                    print(
                        f"Evaluating condition only for the most recent event: '{latest_event}'"
                    )

            # Use only the most recent event for condition evaluation
            evaluation_state = state.copy()
            if latest_event:
                evaluation_state["content"] = [latest_event]

            session_id = state.get("session_id", "")

            # Check all conditions
            conditions_met = []
            condition_details = []
            for condition in conditions:
                condition_id = condition.get("id")
                condition_data = condition.get("data", {})
                field = condition_data.get("field")
                operator = condition_data.get("operator")
                expected_value = condition_data.get("value")

                print(
                    f"  Checking if {field} {operator} '{expected_value}' (current value: '{evaluation_state.get(field, '')}')"
                )
                if self._evaluate_condition(condition, evaluation_state):
                    conditions_met.append(condition_id)
                    condition_details.append(
                        f"{field} {operator} '{expected_value}' ✅"
                    )
                    print(f"  ✅ Condition {condition_id} met!")
                else:
                    condition_details.append(
                        f"{field} {operator} '{expected_value}' ❌"
                    )

            # Check if the cycle reached the limit (extra security)
            if cycle_count >= 10:
                print(
                    f"⚠️ ATTENTION: Cycle limit reached ({cycle_count}). Forcing termination."
                )

                condition_content = [
                    Event(
                        author="agent",
                        content=Content(parts=[Part(text="Cycle limit reached")]),
                    )
                ]
                content = content + condition_content
                yield {
                    "content": content,
                    "status": "cycle_limit_reached",
                    "node_outputs": state.get("node_outputs", {}),
                    "cycle_count": cycle_count,
                    "conversation_history": conversation_history,
                    "session_id": session_id,
                }
                return

            # Store specific results for this node
            node_outputs = state.get("node_outputs", {})
            node_outputs[node_id] = {
                "condition_evaluated": label,
                "content_evaluated": content,
                "conditions_met": conditions_met,
                "condition_details": condition_details,
                "cycle": cycle_count,
            }

            # Prepare a more descriptive message about the conditions
            conditions_result_text = "\n".join(condition_details)
            condition_summary = "TRUE" if conditions_met else "FALSE"

            condition_content = [
                Event(
                    author="agent",
                    content=Content(
                        parts=[
                            Part(
                                text=f"Condition evaluated: {label}\nResult: {condition_summary}\nDetails:\n{conditions_result_text}"
                            )
                        ]
                    ),
                )
            ]
            content = content + condition_content

            yield {
                "content": content,
                "status": "condition_evaluated",
                "node_outputs": node_outputs,
                "cycle_count": cycle_count,
                "conversation_history": conversation_history,
                "session_id": session_id,
            }

        async def message_node_function(
            state: State, node_id: str, node_data: Dict[str, Any]
        ) -> AsyncGenerator[State, None]:
            message_data = node_data.get("message", {})
            message_type = message_data.get("type", "text")
            message_content = message_data.get("content", "")

            print(f"\n💬 MESSAGE-NODE: {message_content}")

            content = state.get("content", [])
            session_id = state.get("session_id", "")
            conversation_history = state.get("conversation_history", [])

            new_event = Event(
                author="agent",
                content=Content(parts=[Part(text=message_content)]),
            )
            content = content + [new_event]

            node_outputs = state.get("node_outputs", {})
            node_outputs[node_id] = {
                "message_type": message_type,
                "message_content": message_content,
            }

            yield {
                "content": content,
                "status": "message_added",
                "node_outputs": node_outputs,
                "cycle_count": state.get("cycle_count", 0),
                "conversation_history": conversation_history,
                "session_id": session_id,
            }

        return {
            "start-node": start_node_function,
            "agent-node": agent_node_function,
            "condition-node": condition_node_function,
            "message-node": message_node_function,
        }

    def _evaluate_condition(self, condition: Dict[str, Any], state: State) -> bool:
        """Evaluates a condition against the current state."""
        condition_type = condition.get("type")
        condition_data = condition.get("data", {})

        if condition_type == "previous-output":
            field = condition_data.get("field")
            operator = condition_data.get("operator")
            expected_value = condition_data.get("value")

            actual_value = state.get(field, "")

            # Special treatment for when content is a list of Events
            if field == "content" and isinstance(actual_value, list) and actual_value:
                # Extract text from each event for comparison
                extracted_texts = []
                for event in actual_value:
                    if hasattr(event, "content") and hasattr(event.content, "parts"):
                        for part in event.content.parts:
                            if hasattr(part, "text") and part.text:
                                extracted_texts.append(part.text)

                if extracted_texts:
                    actual_value = " ".join(extracted_texts)
                    print(f"  Extracted text from events: '{actual_value[:100]}...'")

            # Convert values to string for easier comparisons
            if actual_value is not None:
                actual_str = str(actual_value)
            else:
                actual_str = ""

            if expected_value is not None:
                expected_str = str(expected_value)
            else:
                expected_str = ""

            # Checks for definition
            if operator == "is_defined":
                result = actual_value is not None and actual_value != ""
                print(f"  Check '{operator}': {result}")
                return result
            elif operator == "is_not_defined":
                result = actual_value is None or actual_value == ""
                print(f"  Check '{operator}': {result}")
                return result

            # Checks for equality
            elif operator == "equals":
                result = actual_str == expected_str
                print(f"  Check '{operator}': {result}")
                return result
            elif operator == "not_equals":
                result = actual_str != expected_str
                print(f"  Check '{operator}': {result}")
                return result

            # Checks for content
            elif operator == "contains":
                # Convert both to lowercase for case-insensitive comparison
                expected_lower = expected_str.lower()
                actual_lower = actual_str.lower()
                print(
                    f"  Comparison 'contains' without case distinction: '{expected_lower}' in '{actual_lower[:100]}...'"
                )
                result = expected_lower in actual_lower
                print(f"  Check '{operator}': {result}")
                return result
            elif operator == "not_contains":
                expected_lower = expected_str.lower()
                actual_lower = actual_str.lower()
                print(
                    f"  Comparison 'not_contains' without case distinction: '{expected_lower}' in '{actual_lower[:100]}...'"
                )
                result = expected_lower not in actual_lower
                print(f"  Check '{operator}': {result}")
                return result

            # Checks for start and end
            elif operator == "starts_with":
                result = actual_str.lower().startswith(expected_str.lower())
                print(f"  Check '{operator}': {result}")
                return result
            elif operator == "ends_with":
                result = actual_str.lower().endswith(expected_str.lower())
                print(f"  Check '{operator}': {result}")
                return result

            # Numeric checks (attempting to convert to number)
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
                    print(f"  Numeric check '{operator}': {result}")
                    return result
                except (ValueError, TypeError):
                    # If it's not possible to convert to number, return false
                    print(
                        f"  Error converting values for numeric comparison: '{actual_str[:100]}...' and '{expected_str}'"
                    )
                    return False

            # Checks with regular expressions
            elif operator == "matches":
                import re

                try:
                    pattern = re.compile(expected_str, re.IGNORECASE)
                    result = bool(pattern.search(actual_str))
                    print(f"  Check '{operator}': {result}")
                    return result
                except re.error:
                    print(f"  Error in regular expression: '{expected_str}'")
                    return False
            elif operator == "not_matches":
                import re

                try:
                    pattern = re.compile(expected_str, re.IGNORECASE)
                    result = not bool(pattern.search(actual_str))
                    print(f"  Check '{operator}': {result}")
                    return result
                except re.error:
                    print(f"  Error in regular expression: '{expected_str}'")
                    return True  # If the regex is invalid, we consider that there was no match

        return False

    def _create_flow_router(self, flow_data: Dict[str, Any]):
        """Creates a router based on the connections in flow.json."""
        # Map connections to understand how nodes are connected
        edges_map = {}

        for edge in flow_data.get("edges", []):
            source = edge.get("source")
            target = edge.get("target")
            source_handle = edge.get("sourceHandle", "default")

            if source not in edges_map:
                edges_map[source] = {}

            # Store the destination for each specific handle
            edges_map[source][source_handle] = target

        # Map condition nodes and their conditions
        condition_nodes = {}
        for node in flow_data.get("nodes", []):
            if node.get("type") == "condition-node":
                node_id = node.get("id")
                conditions = node.get("data", {}).get("conditions", [])
                condition_nodes[node_id] = conditions

        # Routing function for each specific node
        def create_router_for_node(node_id: str):
            def router(state: State) -> str:
                print(f"Routing from node: {node_id}")

                # Check if the cycle limit has been reached
                cycle_count = state.get("cycle_count", 0)
                if cycle_count >= 10:
                    print(
                        f"⚠️ Cycle limit ({cycle_count}) reached. Finalizing the flow."
                    )
                    return END

                # If it's a condition node, evaluate the conditions
                if node_id in condition_nodes:
                    conditions = condition_nodes[node_id]
                    any_condition_met = False

                    for condition in conditions:
                        condition_id = condition.get("id")

                        # Get latest event for evaluation, ignoring condition node informational events
                        content = state.get("content", [])
                        latest_event = None
                        for event in reversed(content):
                            # Skip events generated by condition nodes
                            if (
                                event.author != "agent"
                                or not hasattr(event.content, "parts")
                                or not event.content.parts
                            ):
                                latest_event = event
                                break

                        evaluation_state = state.copy()
                        if latest_event:
                            evaluation_state["content"] = [latest_event]

                        # Check if the condition is met
                        is_condition_met = self._evaluate_condition(
                            condition, evaluation_state
                        )

                        if is_condition_met:
                            any_condition_met = True
                            print(
                                f"Condition {condition_id} met. Moving to the next node."
                            )

                            # Find the connection that uses this condition_id as a handle
                            if (
                                node_id in edges_map
                                and condition_id in edges_map[node_id]
                            ):
                                return edges_map[node_id][condition_id]
                        else:
                            print(
                                f"Condition {condition_id} not met. Continuing evaluation or using default path."
                            )

                    # If no condition is met, use the bottom-handle if available
                    if not any_condition_met:
                        if (
                            node_id in edges_map
                            and "bottom-handle" in edges_map[node_id]
                        ):
                            print(
                                "No condition met. Using default path (bottom-handle)."
                            )
                            return edges_map[node_id]["bottom-handle"]
                        else:
                            print(
                                "No condition met and no default path. Closing the flow."
                            )
                            return END

                # For regular nodes, simply follow the first available connection
                if node_id in edges_map:
                    # Try to use the default handle or bottom-handle first
                    for handle in ["default", "bottom-handle"]:
                        if handle in edges_map[node_id]:
                            return edges_map[node_id][handle]

                    # If no specific handle is found, use the first available
                    if edges_map[node_id]:
                        first_handle = list(edges_map[node_id].keys())[0]
                        return edges_map[node_id][first_handle]

                # If there is no output connection, close the flow
                print(f"No output connection from node {node_id}. Closing the flow.")
                return END

            return router

        return create_router_for_node

    async def _create_graph(
        self, ctx: InvocationContext, flow_data: Dict[str, Any]
    ) -> StateGraph:
        """Creates a StateGraph from the flow data."""
        # Extract nodes from the flow
        nodes = flow_data.get("nodes", [])

        # Initialize StateGraph
        graph_builder = StateGraph(State)

        # Create functions for each node type
        node_functions = await self._create_node_functions(ctx)

        # Dictionary to store specific functions for each node
        node_specific_functions = {}

        # Add nodes to the graph
        for node in nodes:
            node_id = node.get("id")
            node_type = node.get("type")
            node_data = node.get("data", {})

            if node_type in node_functions:
                # Create a specific function for this node
                def create_node_function(node_type, node_id, node_data):
                    async def node_function(state):
                        # Consume the asynchronous generator and return the last result
                        result = None
                        async for item in node_functions[node_type](
                            state, node_id, node_data
                        ):
                            result = item
                        return result

                    return node_function

                # Add specific function to the dictionary
                node_specific_functions[node_id] = create_node_function(
                    node_type, node_id, node_data
                )

                # Add node to the graph
                print(f"Adding node {node_id} of type {node_type}")
                graph_builder.add_node(node_id, node_specific_functions[node_id])

        # Create function to generate specific routers
        create_router = self._create_flow_router(flow_data)

        # Add conditional connections for each node
        for node in nodes:
            node_id = node.get("id")

            if node_id in node_specific_functions:
                # Create dictionary of possible destinations
                edge_destinations = {}

                # Map all possible destinations
                for edge in flow_data.get("edges", []):
                    if edge.get("source") == node_id:
                        target = edge.get("target")
                        if target in node_specific_functions:
                            edge_destinations[target] = target

                # Add END as a possible destination
                edge_destinations[END] = END

                # Create specific router for this node
                node_router = create_router(node_id)

                # Add conditional connections
                print(f"Adding conditional connections for node {node_id}")
                print(f"Possible destinations: {edge_destinations}")

                graph_builder.add_conditional_edges(
                    node_id, node_router, edge_destinations
                )

        # Find the initial node (usually the start-node)
        entry_point = None
        for node in nodes:
            if node.get("type") == "start-node":
                entry_point = node.get("id")
                break

        # If there is no start-node, use the first node found
        if not entry_point and nodes:
            entry_point = nodes[0].get("id")

        # Define the entry point
        if entry_point:
            print(f"Defining entry point: {entry_point}")
            graph_builder.set_entry_point(entry_point)

        # Compile the graph
        return graph_builder.compile()

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Implementation of the workflow agent.

        This method follows the pattern of custom agent implementation,
        executing the defined workflow and returning the results.
        """

        try:
            # 1. Extract the user message from the context
            user_message = None

            # Search for the user message in the session events
            if ctx.session and hasattr(ctx.session, "events") and ctx.session.events:
                for event in reversed(ctx.session.events):
                    if event.author == "user" and event.content and event.content.parts:
                        user_message = event.content.parts[0].text
                        print("Message found in session events")
                        break

            # Check in the session state if the message was not found in the events
            if not user_message and ctx.session and ctx.session.state:
                if "user_message" in ctx.session.state:
                    user_message = ctx.session.state["user_message"]
                elif "message" in ctx.session.state:
                    user_message = ctx.session.state["message"]

            # 2. Use the session ID as a stable identifier
            session_id = (
                str(ctx.session.id)
                if ctx.session and hasattr(ctx.session, "id")
                else str(uuid.uuid4())
            )

            # 3. Create the workflow graph from the provided JSON
            graph = await self._create_graph(ctx, self.flow_json)

            # 4. Prepare the initial state
            user_event = Event(
                author="user",
                content=Content(parts=[Part(text=user_message)]),
            )

            # If the conversation history is empty, add the user message
            conversation_history = ctx.session.events or []
            if not conversation_history or (len(conversation_history) == 0):
                conversation_history = [user_event]

            initial_state = State(
                content=[user_event],
                status="started",
                session_id=session_id,
                cycle_count=0,
                node_outputs={},
                conversation_history=conversation_history,
            )

            # 5. Execute the graph
            print("\n🚀 Starting workflow execution:")
            print(f"Initial content: {user_message[:100]}...")

            sent_events = 0  # Count of events already sent

            async for state in graph.astream(initial_state, {"recursion_limit": 100}):
                # The state can be a dict with the node name as a key
                for node_state in state.values():
                    content = node_state.get("content", [])
                    # Only send new events
                    for event in content[sent_events:]:
                        if event.author != "user":
                            yield event
                    sent_events = len(content)

            # Execute sub-agents
            for sub_agent in self.sub_agents:
                async for event in sub_agent.run_async(ctx):
                    yield event

        except Exception as e:
            # Handle any uncaught errors
            error_msg = f"Error executing the workflow agent: {str(e)}"
            print(error_msg)
            yield Event(
                author=self.name,
                content=Content(
                    role="agent",
                    parts=[Part(text=error_msg)],
                ),
            )
