# src/carrier/runtime/continuous_runtime.py
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# Import SDK components needed
from agents import Agent, RunContextWrapper, Tool
from agents.tool import FunctionTool # Specifically need FunctionTool

# Assuming Agent, Tool, MCPServer types are available from the SDK/project
# This might require adjustments based on actual import paths
# from agents import Agent # Placeholder
# from agents.mcp import MCPServer # Placeholder

logger = logging.getLogger(__name__)

# NocoDB Table Names (adjust if different in your NocoDB setup)
NOCODB_AGENT_TASKS_TABLE = "AgentTasks"
NOCODB_SOPS_TABLE = "SOPs"
NOCODB_SOP_STEPS_TABLE = "SOP_Steps"


class ContinuousRuntime:
    """
    Manages the proactive, goal-driven execution loop for an agent
    based on Standard Operating Procedures (SOPs) defined in NocoDB.
    """
    def __init__(
        self,
        agent: Agent,
        agent_name: str,
        goals: List[Dict[str, str]],
        nocodb_mcp: Any, # Keep reference for potential direct use if needed, though primary path is via agent tools
        all_tools: List[Tool], # Changed from nocodb_tools_list
        context_wrapper: Optional[RunContextWrapper] # Added context_wrapper
    ):
        """
        Initializes the Continuous Runtime for an agent.

        Args:
            agent: The initialized agent instance.
            agent_name: The name of the agent.
            goals: List of goals from the character file.
            nocodb_mcp: The active MCP server instance for NocoDB interaction (kept for reference).
            all_tools: The complete list of Tool objects (built-in + MCP) available to the agent.
            context_wrapper: The RunContextWrapper for the agent run.
        """
        self.agent = agent
        self.agent_name = agent_name
        self.goals = goals
        self.nocodb_mcp = nocodb_mcp # Keep for potential direct calls if needed
        self.context_wrapper = context_wrapper or RunContextWrapper(context=None) # Use default wrapper if None
        self.tracked_task_ids: List[str] = []
        self.loop_interval_seconds: int = 5

        # Store tools in a dictionary for quick lookup
        self.tools_map: Dict[str, Tool] = {tool.name: tool for tool in all_tools}
        logger.info(f"[{self.agent_name}] ContinuousRuntime initialized with {len(self.tools_map)} tools: {', '.join(self.tools_map.keys())}")

        # --- NocoDB Tool Validation (using the tools_map) ---
        required_nocodb_tools = {'retrieve_records', 'update_records'}
        missing_tools = required_nocodb_tools - set(self.tools_map.keys())
        if missing_tools:
            error_msg = f"[{self.agent_name}] ContinuousRuntime cannot start: Missing required NocoDB tools in agent's tool list: {', '.join(missing_tools)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        else:
             logger.info(f"[{self.agent_name}] Required NocoDB tools validated successfully via agent's tool list.")

    async def run_continuously(self):
        """Main async loop that periodically checks and processes agent tasks."""
        logger.info(f"[{self.agent_name}] ContinuousRuntime starting...")
        # Initialize tracked tasks after successful validation in __init__
        await self._initialize_tasks()

        while True:
            try:
                # Create a copy of tracked IDs in case the list is modified during iteration
                current_tasks_to_check = list(self.tracked_task_ids)
                if not current_tasks_to_check:
                    logger.debug(f"[{self.agent_name}] No active tasks being tracked. Sleeping.")
                else:
                    logger.debug(f"[{self.agent_name}] Checking {len(current_tasks_to_check)} tracked tasks.")
                    # Process tasks concurrently? For now, sequentially.
                    for task_id in current_tasks_to_check:
                        await self._process_task(task_id)

            except asyncio.CancelledError:
                logger.info(f"[{self.agent_name}] ContinuousRuntime loop cancelled.")
                break
            except Exception as e:
                logger.error(f"[{self.agent_name}] Error in ContinuousRuntime loop: {e}", exc_info=True)
                # Avoid tight loop on persistent error, sleep longer
                await asyncio.sleep(self.loop_interval_seconds * 5)

            await asyncio.sleep(self.loop_interval_seconds)

    async def _initialize_tasks(self):
        """Checks NocoDB for existing active tasks for this agent on startup."""
        logger.info(f"[{self.agent_name}] Initializing tasks from NocoDB...")
        try:
            # Query AgentTasks for tasks assigned to this agent with active statuses
            active_statuses = ["Running", "Waiting", "Paused", "Pending"]
            # NocoDB query syntax might require careful formatting for 'in' operator
            # Example: (status,in,Running,Waiting,Paused,Pending)
            where_clause = f"(agent_name,eq,{self.agent_name})~and(status,in,{','.join(active_statuses)})"
            # NocoDB tool expects 'params' within the 'arguments' dict, not directly
            arguments = {
                'table_name': NOCODB_AGENT_TASKS_TABLE,
                # The nocodb tool schema expects arguments directly, not nested under 'params'
                "fields": "task_id",
                "where": where_clause
                # 'params': {
                #     "fields": "task_id",
                #     "where": where_clause
                # }
            }
            response = await self._call_nocodb_tool('retrieve_records', arguments)


            if response and isinstance(response, list):
                # NocoDB list response structure might vary based on tool version/implementation
                # Adjust parsing as needed. Assuming it might return a list of dicts directly
                # or a dict containing a 'list' key.
                task_list = response
                if isinstance(response[0], dict) and 'list' in response[0]:
                     task_list = response[0]['list']

                self.tracked_task_ids = [task['task_id'] for task in task_list if isinstance(task, dict) and 'task_id' in task]
                logger.info(f"[{self.agent_name}] Resuming tracking for {len(self.tracked_task_ids)} tasks: {self.tracked_task_ids}")
            else:
                 logger.info(f"[{self.agent_name}] No active tasks found to resume or failed to parse response: {response}")
                 self.tracked_task_ids = []

            # Optional: Automatically start tasks for goals if not already running
            # Needs logic to query AgentTasks for existing tasks per goal_name for this agent.

        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to initialize tasks from NocoDB: {e}", exc_info=True)
            self.tracked_task_ids = [] # Ensure list is empty on error

    async def _process_task(self, task_id: str):
        """Fetches the state of a single task and processes its current step if applicable."""
        logger.debug(f"[{self.agent_name}] Processing task_id: {task_id}")
        task_state = None
        try:
            # 1. Fetch latest task state
            task_state = await self._fetch_task_state(task_id)
            if not task_state:
                logger.warning(f"[{self.agent_name}] Task {task_id} not found or failed to fetch. Removing from tracking.")
                if task_id in self.tracked_task_ids: self.tracked_task_ids.remove(task_id)
                return

            # 2. Check Control Signal
            control_signal = task_state.get('control_signal', 'None')
            if control_signal == 'Stop':
                logger.info(f"[{self.agent_name}] Task {task_id} received Stop signal.")
                await self._update_task_state(task_id, {'status': 'Stopped', 'control_signal': 'None'}) # Reset signal
                if task_id in self.tracked_task_ids: self.tracked_task_ids.remove(task_id)
                return
            if control_signal == 'Pause':
                # Only update status if it's not already Paused
                if task_state.get('status') != 'Paused':
                    logger.info(f"[{self.agent_name}] Task {task_id} received Pause signal.")
                    await self._update_task_state(task_id, {'status': 'Paused', 'control_signal': 'None'}) # Reset signal
                else:
                    # Already paused, just ensure signal is reset if needed
                    if control_signal != 'None': # Avoid unnecessary update if already None
                        await self._update_task_state(task_id, {'control_signal': 'None'})
                return # Skip processing this cycle

            # 3. Check Status
            current_status = task_state.get('status')
            if current_status == 'Waiting':
                wait_until_str = task_state.get('wait_until')
                if wait_until_str:
                    try:
                        # Attempt to parse ISO format, handle potential 'Z'
                        wait_until_dt = datetime.fromisoformat(wait_until_str.replace('Z', '+00:00'))
                        # Ensure comparison is timezone-aware
                        if datetime.now(timezone.utc) >= wait_until_dt:
                            logger.info(f"[{self.agent_name}] Task {task_id} wait complete. Setting status to Running.")
                            await self._update_task_state(task_id, {'status': 'Running', 'wait_until': None})
                            current_status = 'Running' # Update status for current execution
                        else:
                            logger.debug(f"[{self.agent_name}] Task {task_id} still waiting until {wait_until_dt}.")
                            return # Still waiting
                    except ValueError as date_err:
                         logger.warning(f"[{self.agent_name}] Task {task_id} has invalid wait_until format '{wait_until_str}': {date_err}. Setting to Error.")
                         await self._update_task_state(task_id, {'status': 'Error', 'error_message': f'Invalid wait_until format: {wait_until_str}'})
                         if task_id in self.tracked_task_ids: self.tracked_task_ids.remove(task_id)
                         return
                else:
                    logger.warning(f"[{self.agent_name}] Task {task_id} has status Waiting but no wait_until time. Setting to Error.")
                    await self._update_task_state(task_id, {'status': 'Error', 'error_message': 'Waiting status without wait_until timestamp.'})
                    if task_id in self.tracked_task_ids: self.tracked_task_ids.remove(task_id)
                    return

            # Only proceed if status is Running (or just became Running after wait)
            if current_status != 'Running':
                logger.debug(f"[{self.agent_name}] Task {task_id} has status {current_status}. Skipping step execution.")
                # If status indicates completion/stop/error, remove from tracking
                if current_status in ['Completed', 'Stopped', 'Error']:
                     if task_id in self.tracked_task_ids: self.tracked_task_ids.remove(task_id)
                return

            # 4. Fetch SOP Step definition
            # NocoDB LinkToRecord fields return an object, need to extract the ID
            current_step_ref = task_state.get('current_step_id')
            # Handle case where ref might be None or not a dict/str
            current_step_id = None
            if isinstance(current_step_ref, str): # If it's just the ID string
                current_step_id = current_step_ref
            elif isinstance(current_step_ref, dict): # If it's a NocoDB link object
                current_step_id = current_step_ref.get('id') # NocoDB often uses 'id' for linked record PK

            if not current_step_id:
                 logger.error(f"[{self.agent_name}] Task {task_id} is Running but has no valid current_step_id reference. Ref: {current_step_ref}. Setting to Error.")
                 await self._update_task_state(task_id, {'status': 'Error', 'error_message': 'Missing or invalid current_step_id reference.'})
                 if task_id in self.tracked_task_ids: self.tracked_task_ids.remove(task_id)
                 return

            step_definition = await self._fetch_sop_step(current_step_id)
            if not step_definition:
                logger.error(f"[{self.agent_name}] Failed to fetch step definition for step_id {current_step_id} (Task {task_id}). Setting to Error.")
                await self._update_task_state(task_id, {'status': 'Error', 'error_message': f'Could not fetch step definition for {current_step_id}.'})
                if task_id in self.tracked_task_ids: self.tracked_task_ids.remove(task_id)
                return

            # 5. Execute Step
            logger.info(f"[{self.agent_name}] Task {task_id}: Executing step {current_step_id} ({step_definition.get('action')})")
            step_success = False
            step_result_package = None # To hold {'tool_output': ..., 'environment_updates': ..., 'log_message': ...}
            error_message = None
            next_step_id_override = None # For error handling jumps

            try:
                step_result_package = await self._execute_step(task_state, step_definition)
                step_success = True
            except Exception as e:
                logger.error(f"[{self.agent_name}] Task {task_id}: Error executing step {current_step_id}: {e}", exc_info=True)
                error_message = f"Error in step {current_step_id}: {str(e)}"
                # Check for error handling jump (LinkToRecord needs ID extraction)
                error_jump_ref = step_definition.get('error_handling_step_id')
                error_jump_step_id = None
                if isinstance(error_jump_ref, str):
                    error_jump_step_id = error_jump_ref
                elif isinstance(error_jump_ref, dict):
                    error_jump_step_id = error_jump_ref.get('id')

                if error_jump_step_id:
                    logger.warning(f"[{self.agent_name}] Task {task_id}: Jumping to error handling step {error_jump_step_id}")
                    next_step_id_override = error_jump_step_id
                    # Keep status as Running to execute the error step
                else:
                    # No error step defined, mark task as Error
                    await self._update_task_state(task_id, {'status': 'Error', 'error_message': error_message, 'last_result': None})
                    if task_id in self.tracked_task_ids: self.tracked_task_ids.remove(task_id)
                    return # Stop processing this task

            # 6. Update Task State based on outcome
            updates: Dict[str, Any] = {}
            # Parse current environment safely
            current_env_str = task_state.get('current_environment', '{}')
            try:
                # Assume it's stored as JSON string, parse it
                current_env = json.loads(current_env_str) if isinstance(current_env_str, str) else (current_env_str or {})
                if not isinstance(current_env, dict): # Ensure it's a dict after potential parsing
                     logger.warning(f"[{self.agent_name}] Task {task_id}: Parsed current_environment is not a dict. Resetting to empty dict. Content: {current_env_str}")
                     current_env = {}
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"[{self.agent_name}] Task {task_id}: Failed to parse current_environment JSON. Resetting to empty dict. Content: {current_env_str}")
                current_env = {}


            if isinstance(step_result_package, dict):
                 # Store raw tool output if available (ensure it's serializable)
                 tool_output = step_result_package.get('tool_output')
                 try:
                     # Store as JSON string in NocoDB 'last_result' (TEXT type)
                     updates['last_result'] = json.dumps(tool_output) if tool_output is not None else None
                 except TypeError:
                     logger.warning(f"[{self.agent_name}] Task {task_id}: Tool output for step {current_step_id} is not JSON serializable. Storing as string.")
                     updates['last_result'] = str(tool_output)


                 # Apply environment updates derived from step execution
                 env_updates = step_result_package.get('environment_updates')
                 if isinstance(env_updates, dict):
                     current_env.update(env_updates)
                     # Store updated environment as JSON string
                     updates['current_environment'] = json.dumps(current_env)

                 # Add progress details from step execution
                 log_msg = step_result_package.get('log_message')
                 if isinstance(log_msg, str):
                     current_progress = task_state.get('progress_details', '') or ""
                     # Prepend new log message for chronological order (newest first)
                     updates['progress_details'] = f"[{datetime.now(timezone.utc).isoformat()}] {log_msg}\n{current_progress}".strip()

                 # Handle wait time update
                 wait_until_iso = step_result_package.get('wait_until')
                 if isinstance(wait_until_iso, str):
                      updates['wait_until'] = wait_until_iso
                      updates['status'] = 'Waiting' # Set status explicitly for wait action

            else: # If step didn't return a dict, clear last_result
                 updates['last_result'] = None


            if next_step_id_override: # Error jump
                 updates['current_step_id'] = next_step_id_override
                 updates['error_message'] = error_message # Keep the error message for context
                 updates['status'] = 'Running' # Ensure it runs the error step
            elif step_success:
                # Only update step/status if not waiting
                if updates.get('status') != 'Waiting':
                    updates['error_message'] = None # Clear previous errors if step succeeded
                    # Get next step ID (LinkToRecord needs ID extraction)
                    next_step_ref = step_definition.get('next_step_id')
                    next_step_id = None
                    if isinstance(next_step_ref, str):
                        next_step_id = next_step_ref
                    elif isinstance(next_step_ref, dict):
                        next_step_id = next_step_ref.get('id')

                    if next_step_id:
                        updates['current_step_id'] = next_step_id
                        updates['status'] = 'Running' # Continue to next step
                    else:
                        logger.info(f"[{self.agent_name}] Task {task_id}: Reached final step.")
                        updates['status'] = 'Completed'
                        if task_id in self.tracked_task_ids: self.tracked_task_ids.remove(task_id) # Stop tracking completed task
            # If step failed and no error jump, state was already updated above

            # Persist all updates
            await self._update_task_state(task_id, updates)

        except Exception as e:
            logger.error(f"[{self.agent_name}] Unhandled error processing task {task_id}: {e}", exc_info=True)
            # Attempt to mark the task as Error in NocoDB
            try:
                await self._update_task_state(task_id, {'status': 'Error', 'error_message': f'Runtime error: {str(e)}'})
            except Exception as db_e:
                 logger.error(f"[{self.agent_name}] Failed to update task {task_id} status to Error in NocoDB: {db_e}")
            if task_id in self.tracked_task_ids: self.tracked_task_ids.remove(task_id)


    async def _execute_step(self, task_state: Dict[str, Any], step_definition: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Executes a single step based on its action type.
        Returns a dictionary containing results like 'tool_output', 'environment_updates', 'log_message', 'wait_until'.
        """
        action = step_definition.get('action')
        # Safely parse current environment from JSON string
        current_env_str = task_state.get('current_environment', '{}')
        try:
            # Assume it's stored as JSON string, parse it
            current_env = json.loads(current_env_str) if isinstance(current_env_str, str) else (current_env_str or {})
            if not isinstance(current_env, dict): # Ensure it's a dict after potential parsing
                 logger.warning(f"[{self.agent_name}] Task {task_state.get('task_id')}: Parsed current_environment is not a dict. Resetting to empty dict. Content: {current_env_str}")
                 current_env = {}
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"[{self.agent_name}] Task {task_state.get('task_id')}: Failed to parse current_environment JSON. Resetting to empty dict. Content: {current_env_str}")
            current_env = {}

        # Safely parse last result from JSON string
        last_result_str = task_state.get('last_result')
        last_result = None
        if isinstance(last_result_str, str):
            try:
                last_result = json.loads(last_result_str)
            except json.JSONDecodeError:
                logger.warning(f"[{self.agent_name}] Task {task_state.get('task_id')}: last_result is not valid JSON. Treating as None. Content: {last_result_str}")
                last_result = None # Or maybe keep the raw string? Depends on tool needs.
        elif last_result_str is not None:
             last_result = last_result_str # Keep if not string (e.g., already parsed by NocoDB?)


        step_id = step_definition.get('step_id')

        result_package = {} # Collect results here

        if action == 'call_tool':
            tool_name = step_definition.get('tool_name')
            if not tool_name: raise ValueError(f"Step {step_id}: Missing 'tool_name' for call_tool action")

            # Resolve parameters
            resolved_params = {}
            # Safely parse tool_params from JSON string
            tool_param_defs_str = step_definition.get('tool_params', '{}')
            try:
                tool_param_defs = json.loads(tool_param_defs_str) if isinstance(tool_param_defs_str, str) else (tool_param_defs_str or {})
            except (json.JSONDecodeError, TypeError):
                 raise ValueError(f"Step {step_id}: Invalid JSON in tool_params: {tool_param_defs_str}")

            if isinstance(tool_param_defs, dict):
                for name, definition in tool_param_defs.items():
                    if not isinstance(definition, dict):
                         raise ValueError(f"Step {step_id}: Invalid parameter definition format for '{name}'")

                    if 'value' in definition:
                        resolved_params[name] = definition['value']
                    elif definition.get('source') == 'environment':
                        key = definition.get('key')
                        if not key: raise ValueError(f"Step {step_id}: Missing 'key' for environment source in param '{name}'")
                        resolved_params[name] = current_env.get(key) # Returns None if key missing
                    elif definition.get('source') == 'prior_step_result':
                        key = definition.get('key')
                        if not key: raise ValueError(f"Step {step_id}: Missing 'key' for prior_step_result source in param '{name}'")
                        if isinstance(last_result, dict):
                            resolved_params[name] = last_result.get(key)
                        else:
                             logger.warning(f"Step {step_id}: Cannot read key '{key}' from prior_step_result as it's not a dictionary: {last_result}")
                             resolved_params[name] = None
                    else:
                         raise ValueError(f"Step {step_id}: Invalid source definition for param '{name}'")
            else:
                 logger.warning(f"Step {step_id}: 'tool_params' could not be parsed as a dictionary.")


            logger.debug(f"[{self.agent_name}] Task {task_state.get('task_id')}: Calling tool '{tool_name}' with params: {resolved_params}")

            # --- Execute Tool ---
            tool_to_execute = self.tools_map.get(tool_name)

            if not tool_to_execute:
                 raise ValueError(f"Step {step_id}: Tool '{tool_name}' not found in agent's available tools.")

            if not isinstance(tool_to_execute, FunctionTool):
                 raise NotImplementedError(f"Step {step_id}: Programmatic execution for non-FunctionTool type '{type(tool_to_execute).__name__}' not supported.")

            # Serialize resolved params to JSON string for on_invoke_tool
            try:
                 params_json_string = json.dumps(resolved_params)
            except TypeError as e:
                 raise ValueError(f"Step {step_id}: Failed to serialize parameters for tool '{tool_name}': {e}") from e

            # Call the tool's invoke method, passing context and JSON string args
            tool_result = await tool_to_execute.on_invoke_tool(self.context_wrapper, params_json_string)

            logger.debug(f"[{self.agent_name}] Task {task_state.get('task_id')}: Tool '{tool_name}' result: {tool_result}")
            result_package['tool_output'] = tool_result # Store raw output (should be string or str-able)

            # Apply result mapping to environment
            environment_updates = {}
            # Safely parse result_mapping from JSON string
            result_mappings_str = step_definition.get('result_mapping', '[]')
            try:
                result_mappings = json.loads(result_mappings_str) if isinstance(result_mappings_str, str) else (result_mappings_str or [])
            except (json.JSONDecodeError, TypeError):
                 raise ValueError(f"Step {step_id}: Invalid JSON in result_mapping: {result_mappings_str}")

            # Ensure tool_result is dict for mapping; handle string results if needed
            tool_result_dict = None
            if isinstance(tool_result, str):
                try:
                    tool_result_dict = json.loads(tool_result)
                except json.JSONDecodeError:
                    logger.warning(f"Step {step_id}: Tool result is a string but not valid JSON, cannot apply mapping: {tool_result}")
            elif isinstance(tool_result, dict):
                tool_result_dict = tool_result

            if isinstance(result_mappings, list) and isinstance(tool_result_dict, dict):
                 for mapping in result_mappings:
                     if not isinstance(mapping, dict): continue # Skip invalid mapping entries
                     source_key = mapping.get('source_key')
                     target_key = mapping.get('target_key')
                     if source_key and target_key:
                         if source_key in tool_result_dict:
                             environment_updates[target_key] = tool_result_dict[source_key]
                         elif mapping.get('required', False):
                              raise ValueError(f"Step {step_id}: Required result key '{source_key}' not found in tool output for mapping.")
            result_package['environment_updates'] = environment_updates

        elif action == 'wait':
            duration = step_definition.get('duration_seconds')
            if not isinstance(duration, (int, float)) or duration < 0:
                raise ValueError(f"Step {step_id}: Invalid or missing 'duration_seconds' for wait action")
            wait_until_dt = datetime.now(timezone.utc) + timedelta(seconds=duration)
            result_package['wait_until'] = wait_until_dt.isoformat() # Store ISO string

        elif action == 'update_environment':
             # Safely parse environment_updates from JSON string
            updates_def_str = step_definition.get('environment_updates', '{}')
            try:
                updates_def = json.loads(updates_def_str) if isinstance(updates_def_str, str) else (updates_def_str or {})
            except (json.JSONDecodeError, TypeError):
                 raise ValueError(f"Step {step_id}: Invalid JSON in environment_updates: {updates_def_str}")

            environment_updates = {}
            if isinstance(updates_def, dict):
                for target_key, definition in updates_def.items():
                     if isinstance(definition, dict):
                         if 'value' in definition:
                             environment_updates[target_key] = definition['value']
                         elif definition.get('source') == 'environment':
                             source_key = definition.get('key')
                             if not source_key: raise ValueError(f"Step {step_id}: Missing 'key' for environment source in update '{target_key}'")
                             environment_updates[target_key] = current_env.get(source_key)
                         # Add more sources if needed
                         else:
                              raise ValueError(f"Step {step_id}: Invalid source definition for environment update '{target_key}'")
                     elif definition is None: # Allow setting to null
                          environment_updates[target_key] = None
                     else: # Treat as static value if not a dict or None
                          environment_updates[target_key] = definition
            else:
                 logger.warning(f"Step {step_id}: 'environment_updates' could not be parsed as a dictionary.")

            result_package['environment_updates'] = environment_updates

        elif action == 'log_message':
            template = step_definition.get('message_template', '')
            message = template
            # Simple substitution: replace {{environment.key}} or {{env.key}}
            import re
            # Ensure current_env is a dict before iterating
            if isinstance(current_env, dict):
                for key, value in current_env.items():
                    # Handle both {{environment.key}} and {{env.key}}
                    placeholder1 = f"{{{{environment.{key}}}}}"
                    placeholder2 = f"{{{{env.{key}}}}}"
                    # Ensure value is string for replacement
                    message = message.replace(placeholder1, str(value)).replace(placeholder2, str(value))
            result_package['log_message'] = message

        else:
            raise ValueError(f"Step {step_id}: Unsupported action type: {action}")

        return result_package

    # --- NocoDB Helper Methods (Now use the generic tool execution) ---

    async def _call_nocodb_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Any]:
        """Helper to call a NocoDB tool by executing the corresponding FunctionTool."""
        # This method now acts as a wrapper around _execute_step's logic for call_tool
        # It finds the tool in the map and calls its on_invoke_tool

        tool_to_execute = self.tools_map.get(tool_name)
        if not tool_to_execute:
            raise ValueError(f"NocoDB tool '{tool_name}' not found in agent's available tools.")

        if not isinstance(tool_to_execute, FunctionTool):
            raise NotImplementedError(f"NocoDB tool '{tool_name}' is not a FunctionTool.")

        try:
            # NocoDB tool arguments might need specific formatting (e.g., nested 'data' or 'params')
            # The create_records tool expects 'data', retrieve/update expect 'record'/'record_id' etc.
            # We pass the whole arguments dict and let the tool's on_invoke_tool handle it.
            params_json_string = json.dumps(arguments)
        except TypeError as e:
            raise ValueError(f"Failed to serialize arguments for NocoDB tool '{tool_name}': {e}") from e

        try:
            logger.debug(f"Calling NocoDB tool '{tool_name}' via its FunctionTool object: {params_json_string}")
            # Pass the stored context_wrapper
            result = await tool_to_execute.on_invoke_tool(self.context_wrapper, params_json_string)
            logger.debug(f"NocoDB tool '{tool_name}' call successful. Result type: {type(result)}")
            # Attempt to parse JSON result if applicable, otherwise return raw string
            # NocoDB MCP tool might return JSON string or already parsed dict/list
            if isinstance(result, str):
                try:
                    # Handle potential empty string results from NocoDB tool
                    return json.loads(result) if result else None
                except json.JSONDecodeError:
                    logger.warning(f"NocoDB tool '{tool_name}' result was not valid JSON: {result}")
                    return result # Return raw string if not JSON
            return result # Return as is if not string (e.g., already a dict/list)
        except Exception as e:
            logger.error(f"Failed to call NocoDB tool '{tool_name}' via FunctionTool: {e}", exc_info=True)
            # Depending on the NocoDB tool, the result might indicate failure.
            # Should we return None or re-raise? Re-raising might be better for step failure.
            raise # Re-raise the exception to be caught by _process_task

    async def _fetch_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Fetches a single task record from AgentTasks."""
        # NocoDB retrieve_record likely expects record_id, not task_id if they differ
        # Assuming task_id IS the primary key NocoDB uses for retrieval via API for now
        # The nocodb tool schema expects 'row_id' for retrieve_record
        response = await self._call_nocodb_tool('retrieve_record', {
            'table_name': NOCODB_AGENT_TASKS_TABLE,
            'row_id': task_id # Use 'row_id' as per nocodb tool schema
        })
        # Check if the response indicates success and contains the record data
        if isinstance(response, dict):
             # Use the actual primary key 'id' or the unique 'task_id' depending on API behavior
             if 'task_id' in response or 'id' in response: # Check if it looks like a valid task record
                  # Parse JSON fields back into objects
                  for field_name in ['current_environment', 'last_result']:
                       if field_name in response and isinstance(response[field_name], str):
                            try:
                                response[field_name] = json.loads(response[field_name])
                            except json.JSONDecodeError:
                                 logger.warning(f"Failed to parse JSON for field '{field_name}' in task {task_id}. Content: {response[field_name]}")
                                 response[field_name] = None # Or keep raw string?
                  return response
             else:
                  logger.warning(f"NocoDB retrieve_record for task {task_id} returned dict without task_id/id: {response}")
                  return None
        else:
             logger.warning(f"NocoDB retrieve_record for task {task_id} did not return a dictionary: {response}")
             return None


    async def _update_task_state(self, task_id: str, updates: Dict[str, Any]):
        """Updates specific fields of a task record in AgentTasks."""
        if not updates: # Don't call if there's nothing to update
             return
        # Ensure last_updated is always set
        updates['last_updated'] = datetime.now(timezone.utc).isoformat()

        # Convert complex types (like dicts for environment) back to JSON strings if needed by NocoDB API
        record_data = {}
        for key, value in updates.items():
             if isinstance(value, dict):
                  record_data[key] = json.dumps(value)
             elif value is not None: # Avoid sending nulls unless explicitly set? Check tool behavior.
                  record_data[key] = value
             # Handle potential non-serializable types in last_result
             elif key == 'last_result':
                  try:
                      record_data[key] = json.dumps(value)
                  except TypeError:
                      record_data[key] = str(value)


        logger.debug(f"[{self.agent_name}] Updating task {task_id} with: {record_data}")
        try:
            # NocoDB update_record likely expects record_id (PK) and the fields to update in 'data'
            await self._call_nocodb_tool('update_records', {
                'table_name': NOCODB_AGENT_TASKS_TABLE,
                'row_id': task_id, # Use 'row_id' as per nocodb tool schema
                'data': record_data # Use 'data' as per nocodb tool schema
            })
            # Add check for success based on NocoDB tool response?
        except Exception as e:
             logger.error(f"[{self.agent_name}] Failed NocoDB update for task {task_id}: {e}", exc_info=True)
             # Should this error stop the runtime or just log? Log for now.


    async def _fetch_sop_step(self, step_id: str) -> Optional[Dict[str, Any]]:
        """Fetches a single step definition from SOP_Steps."""
         # Assuming step_id IS the primary key NocoDB uses for retrieval via API
         # The nocodb tool schema expects 'row_id' for retrieve_record
        response = await self._call_nocodb_tool('retrieve_record', {
            'table_name': NOCODB_SOP_STEPS_TABLE,
            'row_id': step_id # Use 'row_id' as per nocodb tool schema
        })
        if isinstance(response, dict):
             # Check if it looks like a valid step record
             if 'step_id' in response or 'id' in response:
                  # Parse JSON fields back into objects for easier use
                  for field_name in ['tool_params', 'result_mapping', 'environment_updates']:
                       if field_name in response and isinstance(response[field_name], str):
                            try:
                                response[field_name] = json.loads(response[field_name])
                            except json.JSONDecodeError:
                                 logger.warning(f"Failed to parse JSON for field '{field_name}' in step {step_id}. Content: {response[field_name]}")
                                 response[field_name] = None # Or keep raw string? Set to None for safety.
                  return response
             else:
                  logger.warning(f"NocoDB retrieve_record for step {step_id} returned dict without step_id/id: {response}")
                  return None
        else:
             logger.warning(f"NocoDB retrieve_record for step {step_id} did not return a dictionary: {response}")
             return None
