# Prisma (Unstable and in development)
### Automate the Automation.
<img src="prisma logo.png" alt="Prisma Logo"/>

## Why Prisma?

Prisma takes automation to the next level by creating the tools needed for automation, not just executing predefined workflows like n8n, coze, and make.ai that are limited to the tools they provide.

## How It Works

1. **Complete Automation with a Single Query**: Simply describe what you want to automate in natural language
2. **Tool Creation**: Dynamically generates and configures necessary tools for your workflow, no need to create them manually like in n8n.
3. **API Keys**: Get API keys and other credentials if been asked by Prisma, the rest of the workflow will be handled by Agent.
4. **Ready to Run**: Your automation is immediately ready to use - no manual setup required

For example:
```text
"Create a workflow that monitors my Gmail for invoices, extracts the amounts, and updates a Google Sheet"
```
Prisma will internally create the tools and execute the workflow:
- Create email monitoring tool
- Set up invoice parsing capabilities
- Configure Google Sheets integration
- Build and deploy the complete workflow with the tools
- Save workflow as a template for future use

In the future the workflow and tools will be saved as a template for resuse and sharing.

## Getting Started

### Prerequisites
- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver

### Setup Instructions

1. Clone the repository:
```bash
git clone https://github.com/yourusername/Prisma.git
cd Prisma
```

2. Create a virtual environment and install dependencies using uv:
```bash
uv venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate     # On Windows

# Install project dependencies
uv pip install -e .

# Optional: Install development dependencies
uv pip install -e ".[dev]"
```

### Running Prisma

Prisma operates in two modes:

1. **Interactive Mode** - For development and testing:
   - Real-time feedback and interaction with the agent
   - Step-by-step visibility into tool creation and workflow execution
   - Ideal for debugging and understanding the automation process
   ```python
   prisma = Prisma(interactive_mode=True)
   ```

2. **Autonomous Mode** - For production use:
   - Fully automated execution without user intervention
   - Handles the entire process from tool creation to workflow deployment
   - Best for running established workflows without API keys
   ```python
   prisma = Prisma(interactive_mode=False)  # or just Prisma()
   ```

You can run Prisma using any of these methods:

1. As a Python import:
```python
from src.core.prisma import Prisma

# Initialize Prisma in interactive mode
prisma = Prisma(interactive_mode=True)

# Example: Create a simple automation
response = prisma.run(
    "Create a workflow that sends a daily weather report to my email"
)
print(response)
```

2. Using the Python module syntax:
```bash
python -m src.core.prisma # interactive mode (default, human in the loop)
python -m src.core.prisma -a # autonomous mode
```


