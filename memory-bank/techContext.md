# Technical Context: Carrier

## Technologies Used

### Core Languages
- **Python 3.9+**: Primary implementation language
- **SQL**: For database queries
- **YAML/JSON**: For configuration files

### Frameworks and Libraries
- **FastAPI**: Web framework for API endpoints
- **Pydantic**: Data validation and settings management
- **SQLAlchemy**: ORM for database interactions
- **asyncio**: Asynchronous I/O operations
- **uvicorn**: ASGI server for running the FastAPI application
- **aiohttp**: Async HTTP client for external API calls
- **discord.py**: Discord bot client library
- **ftplib**: FTP client for file uploads
- **numpy/scipy**: For vector operations (embeddings)
- **pytest**: Testing framework
- **python-dotenv**: Environment variable management

### External Services
- **OpenAI API**: Primary LLM provider
- **Anthropic API**: Alternative LLM provider
- **Discord API**: For Discord bot integration
- **Instagram Graph API**: For Instagram media posting
- **FTP Server**: For media file uploads before Instagram posting
- **PostgreSQL**: Primary database with vector extension
- **Redis**: For caching and pub/sub functionality

## Development Setup

### Environment Setup
1. **Python Environment**: 
   ```bash
   # Using Anaconda virtual environment named "carrier" with Python 3.9
   conda activate carrier
   pip install -r requirements.txt
   ```

2. **Database Setup**:
   ```bash
   # Install PostgreSQL with vector extension
   # Create database carrier
   python -m scripts.init_db
   ```

3. **Configuration**:
   ```bash
   # Copy example config
   cp config.example.yaml config.yaml
   # Create .env file for API keys
   cp .env.example .env
   # Edit with API keys and database connection
   ```

4. **Client API Setup**:
   ```bash
   # Discord API setup
   # Create a Discord application at https://discord.com/developers/applications
   # Add the bot token to .env as DISCORD_API_TOKEN
   
   # Instagram API setup
   # Create a Facebook app at https://developers.facebook.com/
   # Set up Instagram Graph API access
   # Add credentials to .env as INSTAGRAM_ACCOUNT_ID and INSTAGRAM_ACCESS_TOKEN
   
   # FTP Server setup
   # Configure FTP server credentials in .env as FTP_SERVER, FTP_USERNAME, FTP_PASSWORD
   # Add HTTP_SERVER to .env for the public URL of the FTP server
   ```

### Development Tools
- **VSCode** with Python extensions
- **Black** for code formatting
- **isort** for import sorting
- **mypy** for type checking
- **flake8** for linting
- **pre-commit** hooks for automated checks

### Local Development
```bash
# Run development server
uvicorn src.main:app --reload

# Run tests
pytest

# Format code
black src/ tests/
```

## Technical Constraints

1. **Python Ecosystem Limitations**
   - Python's async/await model differs from Node.js and requires careful implementation
   - Package management and dependency resolution through pip/PyPI

2. **LLM API Constraints**
   - Rate limits on LLM API calls
   - Token limits for context windows
   - Latency variability from third-party services

3. **Discord API Constraints**
   - Rate limits on message sending
   - Connection management for WebSocket
   - Event handling for message events

4. **Instagram API Constraints**
   - Daily publishing limits (currently 25 posts per day)
   - Media container creation and publishing workflow
   - Media file size and format restrictions
   - Two-step posting process (create container, then publish)

5. **FTP Constraints**
   - Synchronous file upload operations
   - Error handling for network issues
   - Security considerations for credentials

6. **Database Performance**
   - Vector search performance for large memory stores
   - Connection handling for async database operations

7. **Deployment Considerations**
   - Environment variables for sensitive configurations
   - Docker container memory limitations
   - Async worker processes management
   - Long-running client connections

## Dependencies

### Core Dependencies
```
fastapi>=0.95.0
pydantic>=2.0.0
sqlalchemy>=2.0.0
asyncpg>=0.27.0
aiohttp>=3.8.4
uvicorn>=0.21.1
openai>=1.0.0
anthropic>=0.3.0
discord.py>=2.3.0
python-dotenv>=1.0.0
numpy>=1.22.0
pyyaml>=6.0
```

### Development Dependencies
```
pytest>=7.3.1
black>=23.3.0
isort>=5.12.0
mypy>=1.2.0
flake8>=6.0.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
pre-commit>=3.3.1
```

### Optional Dependencies
```
langchain>=0.0.200  # For additional LLM utilities
pgvector>=0.1.0     # PostgreSQL vector extension client
redis>=4.5.4        # For caching and pub/sub
moviepy>=1.0.3      # For video processing (Instagram)
```

## Build Process

### Development Build
```bash
# Install in development mode
pip install -e .
```

### Production Build
```bash
# Create wheel package
python -m build
```

### Packaging
```bash
# Package the application
python -m build --wheel
```

## Deployment Strategy

### Docker Deployment
1. **Build Container**:
   ```bash
   docker build -t carrier:latest .
   ```

2. **Run Container**:
   ```bash
   docker run -p 8000:8000 \
     -e DATABASE_URL=postgresql://user:pass@host/db \
     -e OPENAI_API_KEY=sk-... \
     -e DISCORD_API_TOKEN=... \
     -e INSTAGRAM_ACCOUNT_ID=... \
     -e INSTAGRAM_ACCESS_TOKEN=... \
     -e FTP_SERVER=... \
     -e FTP_USERNAME=... \
     -e FTP_PASSWORD=... \
     -e HTTP_SERVER=... \
     carrier:latest
   ```

### Cloud Deployment Options
- **AWS Elastic Beanstalk**: For simple deployment
- **Kubernetes**: For more complex, scalable deployments
- **AWS Lambda/GCP Cloud Functions**: For serverless agent functions

### Configuration Management
- Environment variables for sensitive data
- YAML configuration files for application settings
- Separation of configuration from code

## Testing Approach

### Testing Levels
1. **Unit Tests**: 
   - Test individual components (message processing, state management)
   - Mock external dependencies and LLM providers

2. **Integration Tests**:
   - Test component interactions
   - Database operations with test database
   - Tool integrations with mock services

3. **Functional Tests**:
   - End-to-end flow testing
   - API endpoint functionality
   - Agent behavior testing with fixed LLM responses

4. **Performance Tests**:
   - Memory usage optimization
   - Response time benchmarking
   - Concurrent request handling

### LLM Testing Strategy
- Deterministic LLM responses for testing
- Evaluation metrics for response quality
- Regression test suite for agent behaviors

## Integration Points

### External API Integrations
- **LLM Provider APIs**: OpenAI, Anthropic, etc.
- **Discord API**: For bot integration and message handling
- **Instagram Graph API**: For media posting and status checking
- **Vector Database**: For efficient semantic search
- **External Tool APIs**: Services agents can use

### Client Integrations
- **Discord Client**: Integration with Discord servers and channels
  - Message event handling
  - Mention detection
  - Response sending
  - User interaction

- **Instagram Client**: Integration with Instagram for media posting
  - Media file upload via FTP
  - Container creation and publishing
  - Status checking
  - Publishing limit management

- **REST API**: Primary integration point for clients
- **WebSocket API**: For real-time communication
- **Webhook Support**: For asynchronous notifications

### Authentication Integration
- **OAuth 2.0**: For client authentication
- **API Key**: For service-to-service authentication
- **JWT**: For user session management
- **Bot Token**: For Discord API authentication
- **Access Token**: For Instagram Graph API authentication

## Notes
The Carrier project is designed as a Python reimplementation of the ElizaOS runtime loop, with adaptations to leverage Python's strengths in asyncio, data validation (Pydantic), and web services (FastAPI). The architecture maintains the core concepts of ElizaOS while providing a more Pythonic experience for developers.

Key differences from ElizaOS include the use of Python's async/await pattern, Pydantic models for data validation, and FastAPI for HTTP endpoints. The memory system utilizes PostgreSQL with vector extensions for efficient semantic search, which is critical for the context-aware agent functionality.

The multi-client architecture allows for integration with different platforms, with Discord providing conversational interactions and Instagram enabling media posting capabilities. Each client implementation follows a similar pattern with client-specific adaptations for the unique requirements of each platform. The Discord client uses discord.py for event-based message handling, while the Instagram client uses the Instagram Graph API with a two-step posting process (container creation followed by publishing).

The FTP integration for Instagram media posting demonstrates how the framework can handle different types of content beyond text, providing a foundation for future expansions to additional media types and platforms.
