# Universal AI Memory

A personal memory system designed for AI agents. Deploy your own persistent memory that **any AI tool can access** — breaking the silos between ChatGPT, Claude, Gemini, and custom agents.

## Why Universal AI Memory?

### The Problem
Today, every AI tool maintains its own isolated memory:
- ChatGPT remembers your conversations... but Claude doesn't know about them
- Claude Code knows your codebase... but Cursor doesn't share that context
- Your custom agents start from zero every time

**Your knowledge is fragmented across dozens of AI silos.**

### The Solution
Universal AI Memory is a **single source of truth** that all your AI tools can read from and write to:

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Claude    │  │   ChatGPT   │  │   Gemini    │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────────────┼────────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │  Universal AI   │
              │     Memory      │
              │   (Your Data)   │
              └─────────────────┘
```

**Benefits:**
- 🔗 **Cross-AI Context**: Tell Claude about a project, ChatGPT already knows
- 🧠 **Persistent Memory**: Your AI relationships survive across sessions and tools
- 🏠 **Self-Hosted**: Your data stays on YOUR infrastructure
- 🔓 **Vendor Independent**: Switch AI providers without losing memory
- 🤖 **Agent-Ready**: AI agents can create their own tables and schemas
- 📁 **File Support**: Store documents, images, and files alongside structured data

## Features

- **REST API**: Universal access from any AI tool or script
- **MCP Compatible**: Native integration with Claude Desktop and MCP-enabled tools
- **Dynamic Schema**: AI agents can create new tables on-the-fly
- **File Storage**: Upload and manage files via S3-compatible storage (Tigris)
- **Full-Text Search**: Search across all your data
- **Web Dashboard**: Visual interface at your deployment URL
- **SQLite + Fly.io**: Simple, cheap, and infinitely scalable

---

## Implementation Guide

### Step 1: Fork & Clone

```bash
git clone https://github.com/YOUR-USERNAME/universal-ai-memory.git
cd universal-ai-memory/server
```

### Step 2: Install Fly.io CLI

```bash
# macOS
brew install flyctl

# Windows
powershell -Command "irm https://fly.io/install.ps1 | iex"

# Linux
curl -L https://fly.io/install.sh | sh
```

### Step 3: Create Fly.io Account & Login

```bash
flyctl auth signup  # or 'flyctl auth login' if you have an account
```

### Step 4: Launch Your App

```bash
# Copy the example config
cp fly.toml.example fly.toml

# Edit fly.toml - change 'your-app-name' to something unique
# e.g., 'johndoe-memory' or 'my-ai-brain'

# Launch (this creates the app on Fly.io)
flyctl launch --copy-config --name your-app-name --region yyz --yes
```

### Step 5: Create Persistent Storage

```bash
# Create a volume for SQLite database (1GB is plenty)
flyctl volumes create memory_data --size 1 --region yyz --yes

# Optional: Create file storage bucket
flyctl storage create --name your-files-bucket --public --yes
```

### Step 6: Deploy

```bash
flyctl deploy
```

Your memory is now live at `https://your-app-name.fly.dev`!

### Step 7: Initialize Your Identity

```bash
curl -X POST https://your-app-name.fly.dev/seed \
  -H "Content-Type: application/json" \
  -d '{
    "identity": [
      {"key": "name", "value": "Your Name", "category": "basic"},
      {"key": "email", "value": "you@example.com", "category": "contact"},
      {"key": "bio", "value": "A short bio about yourself", "category": "basic"}
    ]
  }'
```

### Step 8: Connect Your AI Tools

#### Claude Desktop (MCP)
Add to `~/.claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "my-memory": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-proxy", "https://your-app-name.fly.dev"]
    }
  }
}
```

#### ChatGPT (Custom GPT)
Create a Custom GPT with these instructions:
```
You have access to the user's personal memory at https://your-app-name.fly.dev

Before responding, check relevant memory:
- GET /identity - User's basic info
- GET /people - User's contacts
- GET /search?q=topic - Search for relevant context

When learning something new about the user, save it:
- POST /tables/{table}/records - Store new information
```

#### Any AI Tool
Just make HTTP requests to your API:
```python
import requests

# Read
response = requests.get("https://your-app-name.fly.dev/identity")
user_info = response.json()

# Write
requests.post("https://your-app-name.fly.dev/people", json={
    "name": "John Doe",
    "relationship": "colleague",
    "notes": "Met at conference"
})
```

---

## API Reference

### Core Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web dashboard |
| `/health` | GET | Health check |
| `/identity` | GET | Get identity info |
| `/search?q=term` | GET | Full-text search |

### People CRM
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/people` | GET | List all people |
| `/people` | POST | Add a person |
| `/people/{id}` | GET | Get person details |
| `/people/{id}` | PUT | Update person |

### Projects
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/projects` | GET | List projects |
| `/projects` | POST | Create project |

### Dynamic Tables (for AI agents)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tables` | GET | List all tables |
| `/tables` | POST | Create new table |
| `/tables/{name}` | GET | Get table records |
| `/tables/{name}` | POST | Insert record |
| `/tables/{name}/{id}` | PUT | Update record |
| `/tables/{name}/{id}` | DELETE | Delete record |

### Raw SQL (for AI agents)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/execute` | POST | Execute any SQL |

### File Storage
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/files` | GET | List files |
| `/files` | POST | Upload file |
| `/files/{id}` | GET | Get file info |
| `/files/{id}/download` | GET | Get download URL |
| `/files/{id}` | DELETE | Delete file |

---

## Default Database Schema

The system comes with these tables pre-configured:

| Table | Purpose |
|-------|---------|
| `identity` | Key-value store for personal info |
| `people` | Contact/relationship management |
| `projects` | Project tracking |
| `interactions` | Meeting/conversation logs |
| `notes` | General notes |
| `skills` | Skills inventory |
| `education` | Education history |
| `work_experience` | Work history |
| `files` | File metadata |

**AI agents can create additional tables dynamically** via `POST /tables`:

```json
{
  "table_name": "business_ideas",
  "columns": {
    "title": "TEXT",
    "description": "TEXT",
    "potential_revenue": "INTEGER",
    "status": "TEXT"
  }
}
```

---

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Claude Code    │     │  ChatGPT        │     │  Custom Agent   │
│  (MCP Client)   │     │  (REST Client)  │     │  (REST Client)  │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                                 ▼
                   ┌───────────────────────┐
                   │   FastAPI Server      │
                   │   (Fly.io Machine)    │
                   └───────────┬───────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
    ┌─────────────────┐               ┌─────────────────┐
    │   SQLite DB     │               │  Tigris (S3)    │
    │   (Fly Volume)  │               │  File Storage   │
    └─────────────────┘               └─────────────────┘
```

### Why This Stack?

- **SQLite**: Simple, zero-config, handles millions of records
- **Fly.io**: Deploys globally, scales to zero when idle ($0 when not in use)
- **Tigris**: S3-compatible file storage, integrated with Fly
- **FastAPI**: Fast, modern Python API with auto-generated docs

---

## Local Development

```bash
cd server
pip install -r requirements.txt

# Initialize local database
DB_PATH=./memory.db python init_db.py

# Run server
DB_PATH=./memory.db uvicorn main:app --reload
```

Visit `http://localhost:8000` for the dashboard.

---

## Cost

With Fly.io's generous free tier and scale-to-zero:
- **$0/month** for light personal use
- **~$2-5/month** for moderate use
- Storage: $0.15/GB/month

---

## Security Considerations

This is designed for **personal use**. The API is open by default. For production:

1. Add authentication (API keys, JWT, etc.)
2. Use Fly.io private networking
3. Enable HTTPS only (already default on Fly)

---

## Roadmap

- [ ] Authentication layer
- [ ] Encryption at rest
- [ ] Webhook support for real-time sync
- [ ] Vector embeddings for semantic search
- [ ] Mobile app

---

## License

MIT

## Author

Created by [Rohit Challa](https://rohitchalla.com)

---

**Stop fragmenting your AI knowledge. Unify it.**
