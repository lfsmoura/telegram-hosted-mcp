# Telegram MCP Server for Claude

A hosted, multi-tenant Telegram MCP (Model Context Protocol) server that enables Claude to interact with Telegram on behalf of users. Built with FastAPI, Telethon, and OAuth 2.0 authentication.

## Features

- **73 Telegram Tools** - Complete Telegram automation including chats, messages, contacts, groups, channels, and more
- **Multi-tenant Architecture** - Single deployment serves multiple users with isolated Telegram sessions
- **OAuth 2.0 + PKCE** - Secure authentication flow compatible with Claude Teams
- **Web-based Telegram Auth** - Users connect their Telegram accounts via phone/SMS verification (no CLI required)
- **Encrypted Session Storage** - Telegram sessions stored with AES-256 encryption
- **Railway-ready** - One-click deployment to Railway with PostgreSQL

---

## Available Tools (73 total)

<details>
<summary><strong>Chat & Group Management (21 tools)</strong></summary>

| Tool | Description |
|------|-------------|
| `get_chats` | Get paginated list of Telegram chats |
| `list_chats` | List chats with optional filtering by type |
| `get_chat` | Get detailed information about a specific chat |
| `create_group` | Create a new group chat |
| `invite_to_group` | Invite users to a group or channel |
| `create_channel` | Create a new channel or supergroup |
| `edit_chat_title` | Edit chat/channel title |
| `leave_chat` | Leave a group or channel |
| `get_participants` | Get participants of a group or channel |
| `get_admins` | Get administrators of a group or channel |
| `get_banned_users` | Get banned users of a group or channel |
| `promote_admin` | Promote a user to admin |
| `demote_admin` | Demote an admin |
| `ban_user` | Ban a user from a group or channel |
| `unban_user` | Unban a user from a group or channel |
| `get_invite_link` | Get the invite link for a group or channel |
| `export_chat_invite` | Export a new invite link |
| `import_chat_invite` | Join a chat using an invite hash |
| `join_chat_by_link` | Join a chat using a full invite link |
| `subscribe_public_channel` | Subscribe to a public channel |
| `get_recent_actions` | Get recent admin actions in a group or channel |

</details>

<details>
<summary><strong>Messaging (24 tools)</strong></summary>

| Tool | Description |
|------|-------------|
| `get_messages` | Get paginated messages from a chat |
| `list_messages` | List messages with search and date filtering |
| `send_message` | Send a message to a Telegram chat |
| `reply_to_message` | Reply to a specific message |
| `edit_message` | Edit a message |
| `delete_message` | Delete a message |
| `forward_message` | Forward a message to another chat |
| `pin_message` | Pin a message in a chat |
| `unpin_message` | Unpin a message in a chat |
| `mark_as_read` | Mark all messages in a chat as read |
| `get_message_context` | Get messages around a specific message |
| `get_history` | Get chat history |
| `get_pinned_messages` | Get all pinned messages in a chat |
| `search_messages` | Search for messages in a chat or globally |
| `get_last_interaction` | Get the last interaction with a contact |
| `create_poll` | Create a poll in a chat |
| `list_inline_buttons` | List inline keyboard buttons on a message |
| `press_inline_button` | Press an inline keyboard button |
| `send_reaction` | Add a reaction to a message |
| `remove_reaction` | Remove reaction from a message |
| `get_message_reactions` | Get all reactions on a message |
| `get_media_info` | Get media information from a message |

</details>

<details>
<summary><strong>Contact Management (12 tools)</strong></summary>

| Tool | Description |
|------|-------------|
| `list_contacts` | List all contacts |
| `search_contacts` | Search for contacts by name or username |
| `add_contact` | Add a new contact |
| `delete_contact` | Delete a contact |
| `block_user` | Block a user |
| `unblock_user` | Unblock a user |
| `import_contacts` | Import multiple contacts |
| `export_contacts` | Export all contacts |
| `get_blocked_users` | Get list of blocked users |
| `get_contact_ids` | Get list of all contact IDs |
| `get_direct_chat_by_contact` | Find direct chat with a contact |
| `get_contact_chats` | Get all chats involving a specific contact |

</details>

<details>
<summary><strong>User & Profile (5 tools)</strong></summary>

| Tool | Description |
|------|-------------|
| `get_me` | Get current user's account information |
| `update_profile` | Update current user's profile |
| `delete_profile_photo` | Delete current profile photo |
| `get_user_photos` | Get a user's profile photos |
| `get_user_status` | Get a user's online status |

</details>

<details>
<summary><strong>Search & Discovery (4 tools)</strong></summary>

| Tool | Description |
|------|-------------|
| `search_public_chats` | Search for public chats/channels |
| `resolve_username` | Resolve a username to get user/channel ID |
| `get_sticker_sets` | Get user's saved sticker sets |
| `get_bot_info` | Get information about a bot |

</details>

<details>
<summary><strong>Privacy & Settings (6 tools)</strong></summary>

| Tool | Description |
|------|-------------|
| `get_privacy_settings` | Get current privacy settings |
| `set_privacy_settings` | Set privacy settings for a specific key |
| `mute_chat` | Mute notifications for a chat |
| `unmute_chat` | Unmute notifications for a chat |
| `archive_chat` | Archive a chat |
| `unarchive_chat` | Unarchive a chat |

</details>

<details>
<summary><strong>Drafts (3 tools)</strong></summary>

| Tool | Description |
|------|-------------|
| `save_draft` | Save a draft message for a chat |
| `get_drafts` | Get all draft messages |
| `clear_draft` | Clear draft message for a specific chat |

</details>

---

## Deployment

### Prerequisites

1. **Telegram API Credentials** - Get from [my.telegram.org](https://my.telegram.org):
   - Go to "API development tools"
   - Create a new application
   - Note the `api_id` and `api_hash`

2. **Railway Account** - Sign up at [railway.app](https://railway.app)

### Deploy to Railway

```bash
# Clone the repository
git clone https://github.com/your-org/telegram-hosted-mcp.git
cd telegram-hosted-mcp

# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Create a new project
railway init

# Add PostgreSQL
railway add --plugin postgresql

# Set environment variables
railway variables set TELEGRAM_API_ID=your_api_id
railway variables set TELEGRAM_API_HASH=your_api_hash
railway variables set JWT_SECRET=$(openssl rand -hex 32)
railway variables set ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
railway variables set BASE_URL=https://your-app.up.railway.app
railway variables set ALLOWED_REDIRECT_URIS=https://claude.ai/oauth/callback

# Deploy
railway up
```

### Environment Variables

| Variable | Description | How to Generate |
|----------|-------------|-----------------|
| `DATABASE_URL` | PostgreSQL connection string | Auto-set by Railway (ensure it has `+asyncpg`) |
| `TELEGRAM_API_ID` | Telegram API ID | Get from [my.telegram.org](https://my.telegram.org) |
| `TELEGRAM_API_HASH` | Telegram API hash | Get from [my.telegram.org](https://my.telegram.org) |
| `JWT_SECRET` | Secret key for JWT tokens | `openssl rand -hex 32` |
| `ENCRYPTION_KEY` | Fernet key for session encryption | See below |
| `BASE_URL` | Public URL of your server | Your Railway URL |
| `ALLOWED_REDIRECT_URIS` | OAuth redirect URIs (comma-separated) | `https://claude.ai/oauth/callback` |

**Generate Encryption Key:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Important:** If Railway sets `DATABASE_URL` as `postgresql://...`, update it to `postgresql+asyncpg://...`

---

## Claude Teams Setup

### Step 1: Register OAuth Client

After deploying, register an OAuth client for Claude Teams:

```bash
curl -X POST https://your-app.up.railway.app/oauth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Claude Teams",
    "redirect_uris": ["https://claude.ai/oauth/callback"]
  }'
```

**Response:**
```json
{
  "client_id": "abc123...",
  "client_secret": "secret456...",
  "client_name": "Claude Teams",
  "redirect_uris": ["https://claude.ai/oauth/callback"]
}
```

Save the `client_id` and `client_secret`.

### Step 2: Add MCP Server in Claude Teams Admin

1. Go to your **Claude Teams admin dashboard**
2. Navigate to **Integrations** → **MCP Servers**
3. Click **Add MCP Server**
4. Fill in the configuration:

| Field | Value |
|-------|-------|
| **Name** | Telegram |
| **Server URL** | `https://your-app.up.railway.app/mcp` |
| **Authentication** | OAuth 2.0 |
| **Authorization URL** | `https://your-app.up.railway.app/oauth/authorize` |
| **Token URL** | `https://your-app.up.railway.app/oauth/token` |
| **Client ID** | *(from Step 1)* |
| **Client Secret** | *(from Step 1)* |
| **Scopes** | `telegram:read telegram:write` |

5. Click **Save**

### Step 3: User Connects Telegram

When a team member first uses Telegram tools:

1. Claude prompts them to authorize the Telegram connection
2. They click "Connect" and are redirected to your OAuth server
3. After OAuth, they see a web form to enter their **Telegram phone number** (international format, e.g., +1234567890)
4. Telegram sends an **SMS code** to their phone
5. They enter the code on the web form
6. If they have 2FA enabled, they enter their 2FA password
7. Success! They're redirected back to Claude with Telegram connected

**The user only needs to do this once.** Their session persists across conversations.

---

## Claude Desktop / Individual Setup

For individual Claude users (not on a Team), use Claude Desktop with MCP support.

### Step 1: Register OAuth Client

```bash
curl -X POST https://your-app.up.railway.app/oauth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Claude Desktop",
    "redirect_uris": ["http://localhost:3000/callback"]
  }'
```

### Step 2: Configure Claude Desktop

Add to your Claude Desktop config file:

**macOS:** `~/.config/claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "telegram": {
      "url": "https://your-app.up.railway.app/mcp",
      "transport": "http",
      "auth": {
        "type": "oauth2",
        "authorizationUrl": "https://your-app.up.railway.app/oauth/authorize",
        "tokenUrl": "https://your-app.up.railway.app/oauth/token",
        "clientId": "YOUR_CLIENT_ID",
        "clientSecret": "YOUR_CLIENT_SECRET",
        "scopes": ["telegram:read", "telegram:write"]
      }
    }
  }
}
```

### Step 3: Connect Your Telegram

1. Restart Claude Desktop
2. Start a new conversation
3. Ask Claude: *"List my Telegram chats"*
4. Claude will prompt you to authorize - click the link
5. Complete the Telegram phone verification in your browser
6. Return to Claude - you're connected!

---

## Usage Examples

Once connected, ask Claude things like:

### Reading Messages
```
"Show me my recent Telegram chats"
"Get the last 20 messages from the 'Family' group"
"Search my Telegram for messages about 'meeting notes'"
"What did John send me yesterday?"
```

### Sending Messages
```
"Send a message to @username saying 'Hello, how are you?'"
"Reply to the last message in 'Work Team' with 'Sounds good!'"
"Forward that message to the 'Archive' chat"
```

### Group Management
```
"Create a new group called 'Project Alpha' and add @user1 and @user2"
"Show me the admins in the 'Company' channel"
"Promote @newadmin to admin in 'My Group'"
"Remove the person who keeps spamming from the group"
```

### Interactive Features
```
"Create a poll in the family chat: 'What should we have for dinner?' with options Pizza, Sushi, Tacos"
"React with 👍 to John's last message"
"Press the 'Confirm' button on that bot message"
```

### Organization
```
"Archive all chats I haven't messaged in over a month"
"Mute the 'Announcements' channel"
"Show me my blocked users"
```

---

## API Reference

### OAuth Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/oauth-authorization-server` | GET | OAuth server metadata (RFC 8414) |
| `/.well-known/oauth-protected-resource` | GET | Protected resource metadata (RFC 9728) |
| `/oauth/register` | POST | Register new OAuth client |
| `/oauth/authorize` | GET | Start OAuth authorization |
| `/oauth/token` | POST | Exchange code for tokens |

### Telegram Auth Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/telegram/start` | POST | Start phone verification |
| `/auth/telegram/verify` | POST | Submit SMS code |
| `/auth/telegram/2fa` | POST | Submit 2FA password |

### MCP Endpoint

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/mcp` | POST | MCP JSON-RPC endpoint |

### Health Check

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Server health status |

---

## Troubleshooting

### "Error connecting to MCP server"

1. **Check server health:**
   ```bash
   curl https://your-app.up.railway.app/health
   ```

2. **Verify OAuth metadata:**
   ```bash
   curl https://your-app.up.railway.app/.well-known/oauth-authorization-server
   ```

3. **Check environment variables:**
   - `BASE_URL` must match your actual deployed URL exactly
   - `ALLOWED_REDIRECT_URIS` must include the Claude callback URL

### "Telegram session not found"

The user needs to complete Telegram authentication:
1. Trigger the OAuth flow again by asking Claude to use a Telegram tool
2. Complete phone/SMS verification

### "Invalid Fernet key"

The encryption key must be a valid Fernet key. Generate one:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### "Database connection failed"

Ensure `DATABASE_URL` includes the async driver:
```
postgresql+asyncpg://user:pass@host:port/db
```

If Railway set it as `postgresql://...`, update the variable.

### "Phone number invalid"

Phone numbers must be in international format with country code:
- Correct: `+14155551234`
- Wrong: `415-555-1234`

### Railway deployment fails

Check logs:
```bash
railway logs --build   # Build logs
railway logs           # Runtime logs
```

---

## Security

| Feature | Implementation |
|---------|----------------|
| **Session Encryption** | AES-256 via Fernet (encrypts Telegram session strings) |
| **Phone Privacy** | Phone numbers used only during auth, never stored in plaintext |
| **OAuth Security** | OAuth 2.0 + PKCE prevents authorization code interception |
| **Token Security** | JWT tokens with configurable expiration |
| **Session Isolation** | Each user has their own Telegram client instance |
| **Audit Logging** | Metadata only - never logs message content |

---

## Local Development

### Setup

```bash
# Clone repository
git clone https://github.com/your-org/telegram-hosted-mcp.git
cd telegram-hosted-mcp

# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Create .env file
cat > .env << EOF
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/telegram_mcp
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
JWT_SECRET=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
BASE_URL=http://localhost:8000
ALLOWED_REDIRECT_URIS=http://localhost:3000/callback
EOF

# Start PostgreSQL (using Docker)
docker run -d --name postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:15

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

### Testing

```bash
# Test OAuth metadata
curl http://localhost:8000/.well-known/oauth-authorization-server

# Register a test client
curl -X POST http://localhost:8000/oauth/register \
  -H "Content-Type: application/json" \
  -d '{"client_name": "Test", "redirect_uris": ["http://localhost:3000/callback"]}'
```

---

## Project Structure

```
telegram-hosted-mcp/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Environment configuration (pydantic-settings)
│   ├── database.py          # SQLAlchemy async engine setup
│   ├── models.py            # Database models (users, clients, sessions)
│   ├── auth/
│   │   ├── oauth.py         # OAuth 2.0 endpoints (authorize, token, register)
│   │   ├── tokens.py        # JWT token creation and verification
│   │   └── telegram.py      # Telegram phone/SMS/2FA auth flow
│   ├── mcp/
│   │   ├── server.py        # MCP server (73 tool definitions + routing)
│   │   ├── middleware.py    # Bearer token validation, audit logging
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── chats.py     # 21 chat/group management tools
│   │       ├── messages.py  # 24 messaging tools
│   │       ├── contacts.py  # 12 contact management tools
│   │       ├── users.py     # 9 user/profile/discovery tools
│   │       ├── privacy.py   # 6 privacy/settings tools
│   │       └── drafts.py    # 3 draft tools
│   ├── telegram/
│   │   ├── client_pool.py   # Multi-tenant Telethon client pool with LRU
│   │   └── session_store.py # Fernet-encrypted session storage
│   └── templates/           # HTML templates for auth flow
│       ├── phone.html       # Phone number entry
│       ├── code.html        # SMS code entry
│       ├── 2fa.html         # 2FA password entry
│       └── success.html     # Success page
├── alembic/                  # Database migrations
├── Dockerfile               # Container configuration
├── pyproject.toml           # Python dependencies
├── railway.toml             # Railway deployment config
└── README.md
```

---

## Credits

- Inspired by [chigwell/telegram-mcp](https://github.com/chigwell/telegram-mcp)
- Built with [Telethon](https://github.com/LonamiWebs/Telethon)
- MCP Protocol by [Anthropic](https://modelcontextprotocol.io)

## License

MIT License
