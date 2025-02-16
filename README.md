# Supabase MCP Server

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/supabase/supabase-dark.svg" />
    <source media="(prefers-color-scheme: light)" srcset="assets/supabase/supabase-light.svg" />
    <img alt="Supabase" src="assets/supabase/supabase-light.svg" height="40" />
  </picture>
  &nbsp;&nbsp;
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/mcp/mcp-dark.svg" />
    <source media="(prefers-color-scheme: light)" srcset="assets/mcp/mcp-light.svg" />
    <img alt="MCP" src="assets/mcp/mcp-light.svg" height="40" />
  </picture>
</p>

<p align="center">
  <strong>Let Cursor & Windsurf interact with Supabase</strong>
</p>

Implementaton of Supabase MCP server that enables Cursor and Windsurf to interact directly with Supabase PostgreSQL database. It provides a set of database management tools that work seamlessly with these IDEs through the MCP protocol.

## Key features
- 💻 Works with both Windsurf and Cursor IDEs
- ✅ Compatible with local development and production Supabase projects
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
   > ⚠️ **Important**: PostgreSQL must be installed BEFORE installing project dependencies. The `psycopg2` package requires PostgreSQL development libraries during compilation.

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

### Installing via Smithery

To install Supabase MCP Server for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@alexander-zuev/supabase-mcp-server):

```bash
npx -y @smithery/cli install @alexander-zuev/supabase-mcp-server --client claude
```

### Manual Installation
1. Clone and setup environment
```bash
git clone https://github.com/alexander-zuev/supabase-mcp-server.git
cd supabase-mcp-server

# Create and activate virtual environment
uv venv

# Mac/Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate
```

2. Install dependencies
```bash
uv sync
```
> 📝 If you get psycopg2 compilation errors, make sure you've installed PostgreSQL first!

## Usage

### Local Development
MCP server connects to your local Supabase project by default:
- Host: `127.0.0.1:54322` 
- Password: `postgres`

### Production Setup
For staging or production Supabase projects, set these environment variables (setup differs for Cursor and Windsurf):
```bash
SUPABASE_PROJECT_REF="your-project-ref"  # e.g., "abcdefghijklm"
SUPABASE_DB_PASSWORD="your-db-password"
```

### Cursor Setup
Add an MCP server with this configuration:
```
name: supabase
protocol: stdio
command: uv --directory /path/to/cloned/supabase-mcp-server run main.py
```

Example with actual path:
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
      ],
      "env": {
        "SUPABASE_PROJECT_REF": "127.0.0.1:54322",  // Local development default
        "SUPABASE_DB_PASSWORD": "postgres"  // Local development default
      }
    }
  }
}
```
After saving and refreshing, Cascade will have access to all database tools.

## Development

1. Start the development server
```bash
mcp dev main.py
```

2. Start your local Supabase instance
```bash
supabase start
```


## Future improvements
- 🐍 Support methods and objects available in native Python SDK 
- 🔍 Improve SQL syntax validation






