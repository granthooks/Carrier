# Active Context: Carrier

## Current Focus
* **Proactive Agent Runtime:** Implementing and refining the `AgentRuntime` for goal-driven agent behavior using NocoDB SOPs. # Renamed
* **NocoDB Integration:** Defining SOPs and AgentTasks, ensuring reliable interaction via the `nocodb` MCP server.
* **Testing Proactive Loop:** Verifying task initialization, step execution (tool calls, waits, env updates), status transitions, and error handling within `AgentRuntime`. # Added context
* **MCP Integration (Ongoing):** Testing integration with various MCP servers.
* **Memory System (Ongoing):** Continuing development of the Supabase-based memory system.
* Developing Supabase integration with PostgreSQL and vector extensions for memory storage (ongoing).
* Creating specialized memory managers for different memory types.
* Integrating memory system with agent runtime through hooks.
* Implementing CLI tools for memory management.
* Testing memory integration with agents.
* Enhancing the Instagram integration with different character files.
* Implementing multi-agent support for concurrent client operation.

## Recent Changes
* March 13, 2025: Created memory bank directory and initialized core documentation files
* March 13, 2025: Defined project scope for creating autonomous AI Agents
* March 13, 2025: Adapted ElizaOS runtime loop architecture to Python implementation
* March 13, 2025: Established technical context including technologies, dependencies, and development setup
* March 13, 2025: Defined system patterns and component relationships
* March 13, 2025: Updated development environment to use Anaconda virtual environment "carrier" with Python 3.9 instead of venv
* March 13, 2025: Planned Discord client integration for agents to autonomously interact in Discord channels
* March 14, 2025: Implemented discord_agent.py script for Discord integration using discord.py
* March 14, 2025: Created tifa_agent.py as a simpler CLI-based agent for testing
* March 14, 2025: Integrated Agent framework with Discord events for message processing
* March 15, 2025: Implemented instagram_client.py for Instagram Graph API integration
* March 16, 2025: Created test_instagram_cli.py for testing Instagram client functionality
* March 16, 2025: Added Instagram hooks for agent runtime integration
* March 17, 2025: Integrated Instagram client with Agent framework for media posting capabilities
* March 17, 2025: Updated run_agent.py to support concurrent Discord and Instagram client operation
* March 18, 2025: Implemented core MemorySystem class for Supabase integration
* March 18, 2025: Created specialized memory managers (MessageManager, DescriptionManager, LoreManager, etc.)
* March 19, 2025: Implemented memory hooks for integrating conversation history with agent context
* March 19, 2025: Created memory CLI tool for managing memories
* March 20, 2025: Implemented integration tests for memory system
* March 20, 2025: Added vector search capabilities for semantic memory retrieval
* March 20, 2025: Implemented RAG knowledge manager for retrieval-augmented generation
* March 27, 2025: Fixed Discord client parameter naming in Runner.run() method (using starting_agent instead of agent)
* March 27, 2025: Improved Discord channel configuration by reading from character files instead of hardcoding
* March 27, 2025: Enhanced run_agents.py to support multiple agents with different client configurations
* March 28, 2025: Created central MCP server configuration (`config/mcp_servers.json`).
* March 28, 2025: Refactored `run_agents.py` for centralized MCP server management using `AsyncExitStack`, loading configs, handling environment variables, and adding logging.
* March 28, 2025: Updated `initialize_agent` to fetch and combine built-in and MCP tools.
* March 28, 2025: Updated `build_system_prompt` to include all available tools.
* March 28, 2025: Added `list_available_tools` tool for agent introspection.
* March 28, 2025: Updated `CarrierAgent` to store combined tool descriptions.
* March 28, 2025: Created `tests/test_mcp_integration.py` with an initial test for the filesystem server.
* **April 10, 2025: Planned Proactive Runtime:** Designed NocoDB schemas (`SOPs`, `SOP_Steps`, `AgentTasks`) for goal-driven execution.
* **April 10, 2025: Implemented `AgentRuntime`:** Created `src/carrier/runtime/agent_runtime.py` (originally `continuous_runtime.py`) with logic for task processing, step execution, status management, and NocoDB interaction via MCP. Added validation for required NocoDB tools. # Renamed class and file
* **April 10, 2025: Integrated `AgentRuntime`:** Modified `run_agents.py` to initialize and manage the `AgentRuntime` task alongside client tasks for agents with defined goals. # Renamed class
* **April 11, 2025: Populated Initial NocoDB Data:** Successfully created initial SOP, Step, and AgentTask records for `TeslaFan` agent's `DailyNewsReport` goal using the `nocodb` MCP tool (after troubleshooting).

## Next Steps
* **`AgentRuntime` Testing & Refinement:** # Renamed section
    * Run `run_agents.py` and monitor logs for `TeslaFan`'s `AgentRuntime`. # Renamed class
    * Verify task initialization (`_initialize_tasks` logic).
    * Verify correct execution of different step actions (`call_tool`, `wait`, `update_environment`, `log_message`).
    * Test parameter resolution (`environment`, `prior_step_result`).
    * Test result mapping and environment updates.
    * Validate status transitions (Running, Waiting, Paused, Completed, Error).
    * Test error handling and jumps to `error_handling_step_id`.
    * Test `control_signal` handling (Pause, Stop).
    * Refine logging within the runtime.
* **Agent Integration:**
    * Ensure `agent.call_tool` and `agent.call_mcp_tool` (or equivalent) work correctly when called from `AgentRuntime`. # Renamed class
    * Test the reactive flow's ability to query task status from `AgentTasks` via NocoDB tools.
* **MCP Integration Refinement (Ongoing):**
    * Thoroughly test integration with various MCP servers defined in `config/mcp_servers.json`.
    * Implement robust error handling for MCP server startup and tool calls within `run_agents.py`.
    * Ensure API keys/tokens are correctly loaded from `.env` and passed to servers.
    * Test the `list_available_tools` functionality.
    * Evaluate and potentially adjust `cache_tools_list` settings per server.
* **Memory System (Ongoing):**
    * Optimize memory retrieval for better performance with large memory stores.
    * Implement caching strategies for frequently accessed memories.
    * Add memory persistence across agent restarts.
    * Enhance vector search with improved embedding models.
    * Implement memory pruning and summarization for long-running conversations.
    * Add relationship tracking between users and agents.
    * Implement sentiment analysis for relationship quality assessment.
    * Create memory visualization tools for debugging and analysis.
    * Integrate memory system with Discord and Instagram clients.
    * Implement memory-aware response generation for more contextual responses.
    * Add memory export/import functionality for backup and migration.
    * Develop memory privacy controls and access management.
    * Implement memory retention policies and automatic cleanup.
    * Create memory analytics for usage patterns and optimization.

## Active Decisions
* Python will be the primary implementation language
* The runtime loop will follow the 7-step process outlined in projectbrief.md
* Async processing will be implemented using Python's asyncio
* Data validation will be handled by Pydantic models
* The API layer will be implemented using FastAPI
* Database storage will use SQLAlchemy with PostgreSQL and vector extensions
* Discord integration uses discord.py library
* Instagram integration uses Instagram Graph API
* FTP server is used for media file uploads before Instagram posting
* Discord and Instagram clients run concurrently as background processes
* Agents respond when mentioned/tagged in Discord channels
* Instagram client provides media posting capabilities
* Discord and Instagram credentials are loaded from the existing .env file
* Agent memory is maintained using the MemorySystem with Supabase backend
* Memory retrieval uses vector embeddings for semantic search
* OpenAI embeddings are used for vector representation of text
* Memory is organized by type (message, description, lore, document, knowledge)
* Memory managers provide specialized interfaces for different memory types
* Memory hooks integrate conversation history with agent context
* Runtime hooks implement the 7-step process for message handling

## Current Considerations
* How to efficiently implement memory retrieval for very large memory stores
* Balancing between memory precision and recall in semantic search
* Optimizing embedding generation to reduce API costs
* Implementing effective caching strategies for frequently accessed memories
* Handling long-term vs. short-term memory differentiation
* Implementing memory summarization for extended conversations
* Managing memory privacy and access controls
* Implementing cross-agent memory sharing where appropriate
* Optimizing database schema for vector search performance
* Handling memory migration and versioning
* Implementing memory backup and recovery procedures
* Balancing memory retention with storage constraints
* Implementing memory analytics for optimization
* Maintaining consistent parameter naming conventions across the OpenAI Agents SDK integration
* Standardizing configuration approaches for different client types
* Multi-agent management for different Discord channels or servers
* Handling long-running Discord and Instagram connections and reconnection strategies
* Managing Discord and Instagram API rate limits in high-traffic environments
* Optimizing media file uploads for Instagram posting
* Handling Instagram API publishing limits and quotas
* Implementing robust error handling for Instagram media posting
* **MCP Considerations (Ongoing):**
    * Monitoring the stability and resource usage of centrally managed MCP servers.
    * Refining error handling for scenarios where specific servers fail to start or respond.
    * Ensuring security when passing environment variables (like API keys) to server subprocesses.
    * Verifying compatibility as MCP servers are updated.
* **Agent Runtime Considerations:** # Renamed section
    * Scalability of checking many tasks frequently.
    * Robustness of NocoDB interactions (retries, error parsing).
    * Complexity of `prior_step_result` handling if non-sequential results are needed.
    * Interaction model between proactive tasks and reactive message handling (prioritization, interruption).
    * Mechanism for creating new tasks in `AgentTasks` (manual, API, triggered by goals).

## Notes
The project has successfully integrated the initial MCP server functionality. A major architectural addition, the `AgentRuntime` (formerly `ContinuousRuntime`), has been implemented to enable proactive, goal-driven agent behavior based on SOPs defined in NocoDB. This runtime runs as a separate asynchronous task for each eligible agent, processing steps defined in the `SOP_Steps` table and managing state in the `AgentTasks` table via the `nocodb` MCP server. Validation ensures the runtime only starts if required NocoDB tools are available. # Renamed class

The existing reactive runtime loop (based on client messages) remains, and the proactive `AgentRuntime` operates alongside it. The reactive loop can query the `AgentTasks` table to provide status updates on proactive work. # Renamed class

The next critical steps involve setting up the NocoDB tables with actual SOP data and thoroughly testing the `AgentRuntime`'s execution logic, state management, and interaction with the agent's tool execution capabilities. The memory system implementation also remains ongoing. # Renamed class
</final_file_content>

IMPORTANT: For any future changes to this file, use the final_file_content shown above as your reference. This content reflects the current state of the file, including any auto-formatting (e.g., if you used single quotes but the formatter converted them to double quotes). Always base your SEARCH/REPLACE operations on this final version to ensure accuracy.

<environment_details>
# VSCode Visible Files
memory-bank/activeContext.md

# VSCode Open Tabs
src/agents/mcp/util.py
run_agents.py
tests/new/test_filesystem.py
src/agents/tool.py
src/carrier/clients/discord_client.py
src/agents/execution/openai_execution.py
tests/new/test_brave_search.py
memory-bank/projectbrief.md
memory-bank/productContext.md
memory-bank/activeContext.md
.env
src/carrier/tools.py
src/carrier/extensions/carrier_agent.py
src/agents/agent.py
tests/new/test_mcp_util.py
tests/new/test_mcp_connection.py

# Current Time
3/31/2025, 2:15:01 AM (America/Los_Angeles, UTC-7:00)

# Current Mode
ACT MODE
</environment_details>
