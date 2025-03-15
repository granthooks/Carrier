# Discord Agent for Carrier

This module enables AI agents built with the Carrier framework to autonomously interact in Discord channels. It runs as a background process, listening for mentions in Discord channels and processing messages through the Carrier agent runtime.

## Features

- Autonomously responds to mentions in Discord channels
- Leverages the existing Carrier agent framework for message processing
- Maintains conversation history for context awareness
- Supports running multiple agent characters (currently configured for Tifa)
- Loads Discord credentials from environment variables

## Requirements

- Python 3.9+
- discord.py 2.3.2
- python-dotenv
- Carrier agent framework

## Setup

1. Ensure you have the required dependencies installed:
   ```bash
   pip install -r requirements.txt
   ```

2. Make sure your `.env` file contains the required Discord credentials:
   ```
   DISCORD_APPLICATION_ID=your_application_id
   DISCORD_API_TOKEN=your_bot_token
   ```

3. Create or modify character files in the `characters/` directory (e.g., `characters/tifa.json`)

## Usage

To run the Discord agent in the background:

```bash
python discord_agent.py
```

The agent will start up, connect to Discord, and listen for messages that mention the bot. When mentioned, it will process the message using the appropriate agent and respond in the same channel.

## How It Works

### Initialization

1. The script loads Discord credentials from the `.env` file
2. It initializes the agent(s) from character files (currently Tifa)
3. It sets up the Discord client with appropriate permissions
4. The client connects to Discord and begins listening for events

### Message Processing

1. When a message is received, the bot checks if it's mentioned
2. If mentioned, it extracts the message content and determines which agent to use
3. The message is processed through the Carrier agent runtime using the appropriate agent
4. The agent's response is sent back to the Discord channel

### Conversation Memory

The bot maintains conversation history for each agent, storing:
- User messages
- Agent responses
- Message metadata (timestamps, user IDs, etc.)

This allows the agent to maintain context across interactions.

## Extending

### Adding More Agents

To add more agents, modify the `main()` function to initialize additional agents from character files:

```python
# Initialize another agent
another_agent, another_memory = await initialize_agent("characters/another.json")
agents_mapping[another_agent.name] = (another_agent, another_memory)
```

### Adding Commands

The script uses discord.py's command framework, allowing you to add custom commands:

```python
@client.command()
async def status(ctx):
    """Report the bot's status"""
    await ctx.send("I'm online and ready to assist!")
```

## Troubleshooting

- If the bot fails to connect, check that your Discord token is correct
- Ensure the bot has the necessary permissions in your Discord server
- Check the logs for error messages to diagnose issues
