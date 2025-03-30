# Active Context: Carrier

## Current Focus
* Testing and refining the newly implemented MCP (Model Context Protocol) server integration.
* Enhancing error handling and logging for MCP server management.
* Implementing and testing integration with additional MCP servers (beyond filesystem).
* Implementing a robust memory system for Carrier agents (ongoing).
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

## Next Steps
* **MCP Integration Refinement:**
    * Thoroughly test integration with various MCP servers defined in `config/mcp_servers.json` (Brave, GitHub, Supabase, etc.).
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
* **MCP Considerations (Post-Initial Implementation):**
    * Monitoring the stability and resource usage of centrally managed MCP servers.
    * Refining error handling for scenarios where specific servers fail to start or respond.
    * Ensuring security when passing environment variables (like API keys) to server subprocesses.
    * Verifying compatibility as MCP servers are updated.

## Notes
The project has successfully integrated the initial MCP server functionality using a centralized configuration (`config/mcp_servers.json`) and management approach within `run_agents.py`. Agents can now be configured to access tools from specified MCP servers, and the system handles starting/stopping these servers efficiently. A new `list_available_tools` tool allows agents to report their capabilities. The memory system implementation remains ongoing.

The implementation follows the 7-step runtime loop outlined in the project brief, with memory storage and retrieval integrated at appropriate points in the processing pipeline. The memory system uses Supabase with PostgreSQL and vector extensions for efficient semantic search, allowing agents to retrieve relevant memories based on content similarity.

The current implementation provides a strong foundation for leveraging external tools via MCP. The next steps involve testing this integration thoroughly with various servers, refining error handling, and continuing the development of the memory system alongside the expanded tool capabilities.
