# Project Brief: Carrier

## Overview
Carrier is a Python-based framework for creating autonomous AI Agents that can perform tasks and accomplish goals independently. The project focuses on developing a runtime loop system inspired by the ElizaOS architecture, but implemented in Python rather than Node.js.

## Project Scope
Carrier aims to provide a robust framework for AI Agents with the following capabilities:
- Individual agent personalities and characteristics
- Tool integration for performing various tasks
- Memory systems for context retention
- Runtime loop for processing and responding to messages
- Client integrations for receiving input from different sources

## Core Requirements
1. Agent Runtime Loop Implementation
   - Adapt the ElizaOS runtime loop to Python
   - Maintain core functionality while leveraging Python's strengths
   - Support async processing for efficient operation

2. Agent Personalization
   - Each agent has individual personalities and tools available
   - Configurable characteristics and behaviors

3. Tool Integration
   - Agents can access and use tools to accomplish tasks
   - Extensible tool system for adding new capabilities

4. Memory Management
   - Storage of interactions for future context
   - Retrieval of relevant memories during processing

## The Carrier Runtime Loop

### High-Level Overview

The Carrier runtime loop follows this pattern:

1. **Initialization**: Set up the agent with its personality, actions, providers, and services
2. **Message Reception**: Receive messages from various clients
3. **Message Processing**: Process messages through a decision pipeline
4. **Response Generation**: Generate appropriate responses using LLMs
5. **Action Execution**: Execute any actions determined necessary
6. **Evaluation**: Apply evaluators to assess response quality
7. **Memory Storage**: Store interactions for future context

### Detailed Step-by-Step Explanation

#### 1. Agent Initialization (`AgentRuntime` Class)

The runtime loop begins with initialization in the `AgentRuntime` constructor:

```python
class AgentRuntime:
    def __init__(self, 
                 conversation_length: Optional[int] = None,
                 agent_id: Optional[str] = None,
                 character: Optional[Character] = None,
                 token: str,
                 # ...other parameters
                ):
        # Initialize agent components
```

During initialization:
- Character configuration is loaded
- Database connections are established
- Memory managers are initialized
- Plugins, actions, and services are registered

#### 2. Message Reception

The main entry point for messages is typically through client interfaces. For example, a FastAPI implementation might look like:

```python
@app.post("/{agent_id}/message")
async def receive_message(
    agent_id: str,
    request: Request,
    file: Optional[UploadFile] = None
):
    form_data = await request.form()
    room_id = form_data.get("roomId", f"default-room-{agent_id}")
    user_id = form_data.get("userId", "user")
    # Process message...
```

Regardless of the source, all messages are standardized to a common `Memory` format before entering the processing pipeline.

#### 3. Message Processing Pipeline

The main processing occurs through these steps:

##### a. Connection Establishment
First, the runtime ensures the necessary database entities exist:

```python
await runtime.ensure_connection(
    user_id,
    room_id,
    request.form_data.get("userName"),
    request.form_data.get("name"),
    "direct"
)
```

This creates user, room, and participant records if they don't exist.

##### b. Message Storage
The incoming message is stored in the database:

```python
await runtime.message_manager.add_embedding_to_memory(memory)
await runtime.message_manager.create_memory(memory)
```

##### c. State Composition
The runtime then composes the full agent state from various sources:

```python
state = await runtime.compose_state(user_message, {
    "agent_name": runtime.character.name,
})
```

This includes:
- Recent conversation history
- Actor information
- Knowledge retrieval
- Goals and progress
- Context from providers

##### d. Context Assembly
The state is transformed into a prompt context:

```python
context = compose_context(
    state=state,
    template=message_handler_template
)
```

#### 4. Response Generation

The assembled context is sent to the LLM for response generation:

```python
response = await generate_message_response(
    runtime=runtime,
    context=context,
    model_class=ModelClass.LARGE
)
```

This uses the appropriate provider (OpenAI, Anthropic, etc.) based on the agent's configuration.

#### 5. Action Execution

If the LLM's response includes an action, it's processed:

```python
async def process_callback(new_messages):
    nonlocal message
    message = new_messages
    return [memory]

await runtime.process_actions(
    memory,
    [response_message],
    state,
    process_callback
)
```

Each registered action has:
- A validation function to determine if it applies
- A handler function that performs the actual operation
- Examples that help the LLM understand when to use it

#### 6. Evaluation

After generating a response and executing actions, evaluators assess the quality:

```python
await runtime.evaluate(memory, state)
```

Evaluators can trigger additional actions if necessary, such as revising responses or adding follow-up information.

#### 7. Memory Management

Finally, the response is stored in memory for future context:

```python
response_message = {
    "id": f"{message_id}-{runtime.agent_id}",
    **user_message,
    "user_id": runtime.agent_id,
    "content": response,
    "embedding": get_embedding_zero_vector(),
    "created_at": datetime.now().timestamp(),
}

await runtime.message_manager.create_memory(response_message)
```

## Key Python Implementation Components

### 1. Async Processing

The Carrier runtime leverages Python's asyncio for asynchronous operations:

```python
import asyncio

async def process_message(message, runtime):
    # Async processing
    await runtime.ensure_connection(user_id, room_id)
    state = await runtime.compose_state(message)
    # ...
```

### 2. State Management

Use Pydantic models to represent state:

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class State(BaseModel):
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    bio: str
    lore: str
    # ...other fields
```

### 3. Plugin Architecture

Implement a plugin system using Python's dynamic imports:

```python
import importlib

def load_plugin(plugin_name: str) -> Plugin:
    module = importlib.import_module(f"plugins.{plugin_name}")
    return module.plugin
```

### 4. Database Abstraction

Create an abstract base class for database operations:

```python
from abc import ABC, abstractmethod

class DatabaseAdapter(ABC):
    @abstractmethod
    async def get_memories(self, **params) -> List[Memory]:
        pass
    
    @abstractmethod
    async def create_memory(self, memory: Memory) -> None:
        pass
    
    # Other abstract methods
```

### 5. LLM Integration

Use a provider pattern for different LLM backends:

```python
class OpenAIProvider(LLMProvider):
    async def generate_text(self, context: str, **params) -> str:
        # Implementation using OpenAI API
        
class AnthropicProvider(LLMProvider):
    async def generate_text(self, context: str, **params) -> str:
        # Implementation using Anthropic API
```

## Technology Stack

- **FastAPI**: Web framework for API endpoints
- **Pydantic**: Data validation and settings management
- **SQLAlchemy**: ORM for database interactions
- **Asyncio**: Asynchronous I/O
- **LangChain/Custom Wrappers**: LLM integrations

## Timeline
* Project Start: March 13, 2025
* Current Phase: Runtime Loop Implementation
* Next Milestone: Agent Personality Development

## Stakeholders
* Development Team
* AI Agent Users
* Tool Developers
* Client Interface Developers
