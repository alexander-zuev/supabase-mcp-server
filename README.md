# Supabase MCP Server

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://github.com/user-attachments/assets/4a363bcd-7c15-47fa-a72a-d159916517f7" />
    <source media="(prefers-color-scheme: light)" srcset="https://github.com/user-attachments/assets/d255388e-cb1b-42ea-a7b2-0928f031e0df" />
    <img alt="Supabase" src="https://github.com/user-attachments/assets/d255388e-cb1b-42ea-a7b2-0928f031e0df" height="40" />
  </picture>
  &nbsp;&nbsp;
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://github.com/user-attachments/assets/38db1bcd-50df-4a49-a106-1b5afd924cb2" />
    <source media="(prefers-color-scheme: light)" srcset="https://github.com/user-attachments/assets/82603097-07c9-42bb-9cbc-fb8f03560926" />
    <img alt="MCP" src="https://github.com/user-attachments/assets/82603097-07c9-42bb-9cbc-fb8f03560926" height="40" />
  </picture>
</p>

<p align="center">
  <strong>Let Cursor & Windsurf interact with Supabase</strong>
</p>

Implementation of Supabase MCP server that enables Cursor and Windsurf to interact directly with Supabase PostgreSQL database. It provides a set of database management tools that work seamlessly with these IDEs through the MCP protocol.

## Key features
- 💻 Works with both Windsurf and Cursor IDEs
- ✅ Supports both local Supabase projects and production Supabase instances
- 🔨 Built-in database exploration tools with schema insights
- 🔐 Secure read-only database access
- 🔍 SQL query validation

## Prerequisites
- Python 3.12+
- PostgreSQL 16+
- uv package manager

### Mac-specific Setup
1. **PostgreSQL Installation (Required for psycopg2)**
   ```bash
   brew install postgresql@16
   ```
   > ⚠️ **Important**: PostgreSQL must be installed BEFORE installing project dependencies, as psycopg2 requires PostgreSQL development libraries during compilation.

2. **uv Package Manager**
   ```bash
   pip install uv
   ```

### Windows Setup
1. **PostgreSQL Installation**
   - Download and install PostgreSQL 16+ from https://www.postgresql.org/download/windows/
   - Ensure "PostgreSQL Server" and "Command Line Tools" are selected during installation

2. **uv Package Manager**
   ```bash
   pip install uv
   ```

## Installation

1. Clone the repository and setup environment
```bash
# Clone the repository
git clone https://github.com/alexander-zuev/supabase-mcp-server.git
cd supabase-mcp-server

# Create and activate virtual environment
uv venv

# Mac/Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate
```

2. Install dependencies from the lock file
```bash
uv sync
```
> 📝 If you get psycopg2 compilation errors, make sure you've installed PostgreSQL first!

## Usage

### With local Supabase project

You don't need to create .env file. Connection to local Supabase project is configured by default:
- Host: `127.0.0.1:54322`
- Password: `postgres`

### With production Supabase project
You **need** to create .env file in the root of the project with these variables:
```bash
SUPABASE_PROJECT_REF="your-project-ref"  # e.g., "abcdefghijklm"
SUPABASE_DB_PASSWORD="your-db-password"
```

### Troubleshooting

Before connecting to IDEs, verify server functionality using the MCP Inspector:
```bash
mcp dev main.py
```
This connects to MCP Inspector which allows you to debug and test the server without a client.

### Cursor Setup
Go to `Cursor Settings` -> `Features` -> `MCP Servers` and add:

```
name: supabase
protocol: command
command: uv --directory /path/to/cloned/supabase-mcp-server run main.py
```
Replace `/path/to/cloned/supabase-mcp-server` with your actual repository path.

Example:
```
command: uv --directory /Users/az/cursor/supabase-mcp-server run main.py
```

After adding this configuration, Agent mode will have access to all database tools.

### Windsurf
Windsurf relies on a 'Claude Desktop' like configuration to connect to MCP server. This means you need to edit `mcp_config.json` file to connect to MCP server:

```json
{
  "mcpServers": {
    "supabase": {
      "command": "/Users/az/.local/bin/uv",
      "args": [
        "--directory",
        "/Users/username/cursor/supabase-mcp-server",  // Your repository path
        "run",
        "main.py"
      ]
    }
  }
}
```
After saving and refreshing, Cascade will have access to all database tools.

## Troubleshooting

Start the development server
```bash
mcp dev main.py
```

## Future improvements
- 🐍 Support methods and objects available in native Python SDK
- 🔍 Improve SQL syntax validation
- 📦 Simplify packaging (no installation and dependencies should be necessary)
- Support for creating edge functions, managing secrets (similar to Loveble integration)
