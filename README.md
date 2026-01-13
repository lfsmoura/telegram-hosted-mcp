# Telegram MCP Server for Claude Teams

A hosted, multi-tenant Telegram MCP server that enables Claude Teams users to connect their Telegram accounts with a simple OAuth flow.

## Features

- **OAuth 2.0 + PKCE** authentication for Claude Teams
- **Web-based Telegram auth** - no terminal needed
- **Multi-tenant** - each user gets isolated sessions
- **Encrypted session storage** - AES-256 encryption at rest
- **Audit logging** - metadata only, never message content
- **Railway-ready** deployment

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL database
- Telegram API credentials from [my.telegram.org](https://my.telegram.org/apps)

### Local Development

1. Clone and install dependencies:

```bash
git clone <repo-url>
cd telegram-hosted-mcp
pip install -e ".[dev]"
```

2. Copy and configure environment:

```bash
cp .env.example .env
# Edit .env with your credentials
```

3. Run database migrations:

```bash
alembic upgrade head
```

4. Start the server:

```bash
uvicorn app.main:app --reload
```

5. Test the OAuth metadata endpoint:

```bash
curl http://localhost:8000/.well-known/oauth-authorization-server
```

### Railway Deployment

1. Create a new Railway project
2. Add a PostgreSQL database
3. Set environment variables:
   - `DATABASE_URL` (auto-set by Railway)
   - `TELEGRAM_API_ID`
   - `TELEGRAM_API_HASH`
   - `ENCRYPTION_KEY`
   - `JWT_SECRET`
   - `BASE_URL` (your Railway URL)

4. Deploy:

```bash
railway up
```

## Claude Teams Integration

### Admin Setup

1. Deploy the service to Railway
2. In Claude Teams Admin Settings → Connectors
3. Add Custom Connector:
   - **Name:** Telegram
   - **MCP Server URL:** `https://your-app.railway.app/mcp`
   - Register a client at `/oauth/register` to get credentials

### User Setup

1. Go to Settings → Connectors in Claude
2. Click "Connect" on Telegram
3. Enter your phone number
4. Enter the SMS code from Telegram
5. (If 2FA enabled) Enter your 2FA password
6. Done! Telegram tools are now available

## Available Tools

### Messages (P0)
- `list_chats` - List all Telegram chats
- `get_chat` - Get chat details
- `get_messages` - Get messages from a chat
- `send_message` - Send a message
- `search_messages` - Search messages

### Contacts (P1)
- `list_contacts` - List all contacts
- `search_contacts` - Search contacts

### Groups (P1)
- `get_participants` - Get group/channel participants

## Security

- Sessions encrypted with Fernet (AES-128-CBC + HMAC)
- Phone numbers stored as SHA-256 hashes only
- JWT tokens expire after 1 hour
- Audit logs contain metadata only (never message content)
- One Telegram account per Claude user

## Project Structure

```
app/
├── main.py              # FastAPI entrypoint
├── config.py            # Environment configuration
├── database.py          # SQLAlchemy setup
├── auth/
│   ├── oauth.py         # OAuth 2.0 endpoints
│   ├── tokens.py        # JWT management
│   └── telegram_auth.py # Phone/SMS auth flow
├── mcp/
│   ├── server.py        # MCP server
│   └── tools/           # Tool implementations
├── telegram/
│   ├── client_pool.py   # Multi-tenant clients
│   └── session_store.py # Encrypted sessions
├── models/              # Database models
└── templates/           # Auth UI templates
```

## License

MIT
