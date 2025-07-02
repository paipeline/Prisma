# Prisma (Unstable and in development)
### Automate the automation.
<img src="prisma logo.png" alt="Prisma Logo"/>

## Why Prisma?

Prisma takes automation to the next level by not just executing predefined workflows like n8n, coze, and make.ai, but by actually creating the tools needed for automation.

## How It Works

1. **One Query, Complete Automation**: Simply describe what you want to automate in natural language
3. **Tool Creation**: Dynamically generates and configures necessary tools for your workflow, no need to create them manually like in n8n.
4. **API Keys**: Ask for API keys and other credentials if needed, Prisma will handle the rest.
5. **Ready to Run**: Your automation is immediately ready to use - no manual setup required

For example:
```text
"Create a workflow that monitors my Gmail for invoices, extracts the amounts, and updates a Google Sheet"
```
Prisma will be executed automatically:
- Create email monitoring tools
- Set up invoice parsing capabilities
- Configure Google Sheets integration
- Build and deploy the complete workflow
- Save workflow as a template for future use

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

There are several ways to run Prisma in interactive mode:

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
python -m src.core.prisma
```

