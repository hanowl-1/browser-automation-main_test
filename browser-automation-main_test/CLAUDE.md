# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a browser automation project using Browser Use - an AI-powered browser automation framework that enables automated web interactions through LLM agents.

## Setup Commands

```bash
# Create and activate Python virtual environment (Python 3.11+ required)
uv venv --python 3.11
source .venv/bin/activate  # Mac/Linux
# or
.venv\Scripts\activate     # Windows

# Install Browser Use and dependencies
uv pip install browser-use

# Install Playwright browsers
uv run playwright install
```

## Environment Configuration

Create a `.env` file with necessary API keys:
```
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
# Add other LLM API keys as needed
```

## Project Structure

```
browser-automation/
├── src/
│   ├── agents/         # Agent definitions and tasks
│   ├── models/         # Pydantic models for structured output
│   ├── utils/          # Helper functions
│   └── config/         # Configuration files
├── tests/              # Test files
├── logs/               # Conversation logs and screenshots
├── .env               # API keys and environment variables
└── requirements.txt    # Python dependencies
```

## Agent Configuration Options

### Core Parameters
- `task` (required): Primary instruction for the agent
- `llm` (required): Chat model instance
- `use_vision`: Enable/disable visual processing (default: True)
- `vision_detail_level`: 'low', 'high', or 'auto' (default)
- `controller`: Custom function registry
- `save_conversation_path`: Path for saving conversation history
- `extend_system_message`: Add instructions to default prompt
- `override_system_message`: Replace entire system prompt (not recommended)

### Vision Settings
- Disabling vision reduces costs (~800-1000 tokens per image for GPT-4o)
- Use 'low' detail level for faster, cheaper processing
- Use 'high' for detailed visual analysis

## Browser Configuration

### BrowserSession Parameters
- `headless`: Run without UI (default: True)
- `channel`: Browser type ('chromium', 'chrome', 'edge')
- `executable_path`: Custom browser executable
- `user_data_dir`: Browser profile directory
- `stealth`: Avoid bot detection
- `viewport`: Window size {'width': 964, 'height': 647}
- `user_agent`: Custom browser identification
- `allowed_domains`: Restrict navigation to specific domains
- `proxy`: Network proxy settings
- `permissions`: Grant specific browser permissions
- `deterministic_rendering`: Consistent but slower rendering
- `highlight_elements`: Show interactive element boundaries
- `wait_for_network_idle_page_load_time`: Network wait time

### Security Considerations
- Agents can access logged-in sessions, cookies, saved passwords
- Use isolated browser profiles for different agents
- `disable_security`: ⚠️ EXTREMELY RISKY - avoid unless absolutely necessary
- Use `allowed_domains` to restrict access

## Output Format Configuration

Define structured output using Pydantic models:

```python
from pydantic import BaseModel
from typing import List

class DataItem(BaseModel):
    title: str
    url: str
    description: str

class DataCollection(BaseModel):
    items: List[DataItem]

controller = Controller(output_model=DataCollection)
```

## System Prompt Customization

Extend default prompt (recommended):
```python
extend_system_message = """
Additional instructions for the agent...
"""
```

Override entire prompt (not recommended unless necessary):
```python
override_system_message = """
Complete replacement system prompt...
"""
```

## Core Code Patterns

### Basic Agent
```python
from browser_use.llm import ChatOpenAI
from browser_use import Agent
from dotenv import load_dotenv
import asyncio

load_dotenv()

llm = ChatOpenAI(model="gpt-4o")

async def main():
    agent = Agent(
        task="Your automation task",
        llm=llm,
    )
    result = await agent.run()
    return result

asyncio.run(main())
```

### Advanced Agent with Full Customization
```python
from browser_use import Agent, Controller, BrowserSession
from browser_use.llm import ChatOpenAI
from pydantic import BaseModel
import asyncio

# Define output structure
class SearchResult(BaseModel):
    title: str
    url: str
    summary: str

class SearchResults(BaseModel):
    results: List[SearchResult]

# Configure browser
browser_session = BrowserSession(
    headless=False,
    stealth=True,
    viewport={'width': 1280, 'height': 720},
    user_data_dir='~/.config/browseruse/profiles/research'
)

# Configure controller with output model
controller = Controller(output_model=SearchResults)

# Configure agent
agent = Agent(
    task="Search and extract top 5 AI news articles",
    llm=ChatOpenAI(model="gpt-4o"),
    controller=controller,
    use_vision=True,
    vision_detail_level='auto',
    save_conversation_path="logs/conversation",
    extend_system_message="Focus on recent articles from reputable sources"
)

# Run with browser session
result = await agent.run(browser_session=browser_session)
```

## Best Practices

1. **Browser Management**
   - Use unique `user_data_dir` for multiple browsers
   - Set `headless=False` for debugging
   - Enable `stealth=True` to avoid detection
   - Close browser sessions properly

2. **Performance Optimization**
   - Disable vision when not needed
   - Use 'low' vision detail for simple tasks
   - Implement proper error handling
   - Use structured output for data extraction

3. **Security**
   - Never disable security unless absolutely necessary
   - Use isolated browser profiles
   - Limit domain access when possible
   - Store API keys securely in .env

4. **Development**
   - Test with `headless=False` initially
   - Save conversations for debugging
   - Use structured output for predictable results
   - Implement retry logic for network failures

## Running Tasks

```bash
# Run main script
python main.py

# Run advanced agent
python advanced_agent.py

# Using uv
uv run python main.py
```

## Testing

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest -v tests/

# Run specific test
pytest tests/test_agent.py
```

## Troubleshooting

- Close all Chrome instances before launching
- Ensure Python 3.11+ is installed
- Check browser executable paths
- Verify API keys in .env file
- Use `headless=False` for debugging

## Documentation Reference

- Quickstart: https://docs.browser-use.com/quickstart
- Agent Settings: https://docs.browser-use.com/customize/agent-settings
- Browser Settings: https://docs.browser-use.com/customize/browser-settings
- Output Format: https://docs.browser-use.com/customize/output-format
- System Prompt: https://docs.browser-use.com/customize/system-prompt