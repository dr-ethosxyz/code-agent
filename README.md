# Code Agent - AI PR Reviewer

Agentic PR reviewer that uses LangGraph to intelligently review code changes.

## Local Setup

### 1. Create a GitHub App

Go to https://github.com/settings/apps/new and create an app with:

**Permissions:**
- Repository > Contents: Read
- Repository > Pull requests: Read & Write
- Repository > Issues: Read & Write

**Webhook:**
- URL: Your ngrok/cloudflare tunnel URL + `/api/webhook/github`
- Secret: Generate a random string
- Events: Pull request, Pull request review

After creating, generate a private key (downloads a `.pem` file).

### 2. Install the App

Install your GitHub App on the repos you want to review.

### 3. Set Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:
```
# Required
GITHUB_APP_ID=123456
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET=your-webhook-secret

# LLM (pick one)
ANTHROPIC_API_KEY=sk-ant-...
# or
OPENROUTER_API_KEY=sk-or-...

# Optional: Slack notifications
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_ID=C...
```

### 4. Run Locally

```bash
# Install dependencies
uv sync --dev

# Start server
uv run uvicorn src.main:app --reload --port 8080

# Expose with ngrok (in another terminal)
ngrok http 8080
```

Update your GitHub App webhook URL to the ngrok URL.

### 5. Test It

Open a PR on a repo where the app is installed. The agent will automatically review it.

Or trigger manually via Slack (if configured):
```
review dr-ethosxyz/backend#123
```

## Endpoints

- `GET /health` - Health check
- `POST /github/webhook` - GitHub webhook receiver
- `POST /slack/events` - Slack events receiver

## Architecture

```
src/
├── main.py              # FastAPI app
├── config.py            # Environment settings
├── core/                # Shared utilities
│   ├── llm.py           # LLM client
│   └── logging.py       # Logging
└── services/
    ├── github/          # GitHub webhook handling
    ├── slack/           # Slack integration
    └── reviewer/        # LangGraph review agent
        ├── graph.py     # Agent workflow
        ├── tools.py     # GitHub tools for agent
        └── state.py     # Agent state
```

## Deployment

Deployed to Cloud Run automatically on push to `main`.

Service URL: https://pr-reviewer-188136330225.us-central1.run.app
