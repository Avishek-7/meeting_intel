# MeetingIntel

MeetingIntel is an AI-powered meeting transcript analysis platform that generates concise summaries and extracts actionable tasks. The backend is built with FastAPI, SQLAlchemy, PostgreSQL, and supports both **OpenAI** and **Google Genai** LLM providers with synchronous and asynchronous processing via Redis caching and RQ background jobs.

## Recent Updates

### 🎉 New Features

- **Google Genai (Gemini) Support**: Full integration with Google's Gemini models alongside OpenAI
- **LLM Provider Comparison Tool**: Side-by-side comparison utility for testing both providers
- **Integrated Development Server**: Single-command startup with API + worker + monitoring ([`start_dev.sh`](backend/scripts/start_dev.sh))
- **Real-time Worker Monitoring**: Heartbeat system showing queue stats and worker health
- **Enhanced Queue Management**: Utilities for requeuing failed jobs and managing worker conflicts
- **Portable Development Scripts**: Auto-detection of Python/RQ paths for cross-platform development

### 🔧 Recent Improvements

- **Dependency Version Constraints**: Bounded `httpx` and `openai` versions to prevent breaking changes
- **Timezone-aware Datetime**: Replaced deprecated `utcnow()` with `timezone.utc` throughout
- **Robust Error Handling**: Null-safe email normalization and improved exception handling
- **Resource Cleanup**: Proper database engine disposal in scripts with `finally` blocks
- **Environment Variable Consistency**: Standardized to uppercase naming with backward compatibility
- **Optional API Keys**: GOOGLE_API_KEY now optional for deployments using only OpenAI

## Highlights

- **Dual LLM Provider Support**: Choose between OpenAI (GPT) or Google Genai (Gemini) with easy provider switching
- **Meeting analysis**: Summary + action items with validation and fallbacks
- **Async processing**: Background analysis via RQ + Redis with worker monitoring
- **Analytics**: User and global usage statistics and daily breakdowns
- **Development Tools**: Integrated dev server with heartbeat monitoring, provider comparison utilities
- **Observability**: Structured logging with request IDs and correlation IDs
- **Abuse protection**: Rate limiting, token caps, and daily usage caps
- **Security**: JWT-based auth, bcrypt password hashing, and Pydantic validation

## System Flow Diagram

```mermaid
flowchart TD
  A[Client] -->|POST /meetings/analyze| B[FastAPI API]
  A -->|POST /meetings/analyze-async| C[RQ Queue]
  C --> D[Worker: jobs.meeting_analysis]
  B --> E[meeting_service.process_meeting_transcript]
  D --> E
  E --> F[Redis Cache]
  E --> G[LLM Pipeline]
  G --> H[OpenAI / Google Genai]
  E --> I[(PostgreSQL)]
  E --> J[Usage Records]
  B --> K[Response]
  D --> K
```

## Additional Diagrams

### Request Sequence (Sync Analysis)

```mermaid
sequenceDiagram
  participant Client
  participant API as FastAPI
  participant Service as MeetingService
  participant Cache as Redis
  participant LLM as LLM Pipeline
  participant DB as PostgreSQL

  Client->>API: POST /meetings/analyze
  API->>Service: process_meeting_transcript()
  Service->>DB: Check transcript hash
  DB-->>Service: Not found
  Service->>Cache: Get cached result
  Cache-->>Service: Cache miss
  Service->>LLM: Analyze transcript
  LLM-->>Service: Summary + action items
  Service->>DB: Persist meeting + usage
  DB-->>Service: Commit OK
  Service-->>API: Response payload
  API-->>Client: 200 OK
```

### LLM Pipeline Steps

```mermaid
flowchart LR
  P[Preprocess] --> C[Chunk if long]
  C --> S[Summarize]
  S --> A[Extract action items]
  A --> V[Validate summary & items]
  V --> O[Return structured result]
```

### Data Model (ER)

```mermaid
erDiagram
  USERS ||--o{ MEETINGS : owns
  USERS ||--o{ USAGE_RECORDS : creates
  MEETINGS ||--o{ USAGE_RECORDS : tracks

  USERS {
    UUID id PK
    STRING email
    STRING role
    DATETIME created_at
  }

  MEETINGS {
    UUID id PK
    UUID user_id FK
    TEXT transcript_text
    STRING transcript_hash
    TEXT summary_text
    JSONB action_items
    DATETIME created_at
  }

  USAGE_RECORDS {
    UUID id PK
    UUID user_id FK
    UUID meeting_id FK
    STRING model_name
    INT prompt_tokens
    INT completion_tokens
    INT total_tokens
    DECIMAL estimated_cost
    DATETIME created_at
  }
```

## Project Structure

```
meeting-intel/
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── ai_engine/              # AI processing pipeline
│   │   ├── pipeline.py         # Analysis workflow
│   │   ├── llm.py              # OpenAI calls + prompt handling
│   │   ├── preprocess.py       # Cleaning + chunking
│   │   ├── validation.py       # Output validation
│   │   └── prompts/            # Prompt templates
│   ├── api/                    # API routes
│   │   ├── auth.py             # Auth endpoints
│   │   ├── meetings.py         # Analysis + analytics endpoints
│   │   └── debug.py            # Debug endpoints
│   ├── core/                   # Core utilities
│   │   ├── config.py           # Settings
│   │   ├── database.py         # DB sessions
│   │   ├── security.py         # JWT + bcrypt
│   │   ├── queue.py            # RQ + Redis setup
│   │   ├── cache.py            # Redis cache client
│   │   ├── middleware/         # Request logging/context
│   │   └── logging.py          # Structlog + Rich configuration
│   ├── jobs/                   # Background jobs
│   │   └── meeting_analysis.py # RQ worker job
│   ├── models/                 # SQLAlchemy models
│   ├── schemas/                # Pydantic schemas
│   ├── services/               # Business logic
│   ├── scripts/                # Development and utility scripts
│   │   ├── start_dev.sh        # Combined API + worker with monitoring
│   │   ├── compare_llm_responses.py  # LLM provider comparison tool
│   │   ├── requeue_failed_import_jobs.py  # Queue management utility
│   │   └── add_usage_meeting_created_index.py  # Database indexing
│   └── tests/                  # Test suite
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.10+
- PostgreSQL
- OpenAI API key **OR** Google Genai API key (depending on chosen provider)
- Redis (required for async jobs and caching)

## Setup

1) Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Configure environment variables (create `.env` in repo root)

```env
# Required (all environments)
JWT_SECRET_KEY="your-secret-key"
DATABASE_URL="postgresql+asyncpg://user:password@localhost/meeting_intel_db"

# LLM Provider - Configure ONE of these based on your chosen provider:
GOOGLE_API_KEY="your-google-genai-api-key"  # For Google Genai (Gemini)
# OPENAI_API_KEY="your-openai-api-key"      # For OpenAI (GPT)

# Required for production deployment
PII_HASH_PEPPER="your-cryptographically-secure-random-string"  # Generate: openssl rand -hex 32

# Required for async processing and caching
REDIS_URL="redis://localhost:6379/0"
```

3) Initialize the database

```bash
createdb meeting_intel_db
```

4) Run the API

**Option A: Using the integrated development script (recommended)**

```bash
cd backend
bash scripts/start_dev.sh
```

This starts both the API server and RQ worker with heartbeat monitoring. API runs at `http://localhost:8003`.

**Option B: Run API only**

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8003
```

API runs at `http://localhost:8003`.

## Running the RQ Worker (Async Jobs)

Async analysis uses RQ + Redis. Ensure `REDIS_URL` is set in `.env`.

**Option A: Using the integrated development script (recommended)**

The `start_dev.sh` script automatically starts an RQ worker alongside the API:

```bash
cd backend
bash scripts/start_dev.sh
```

Features:
- Automatic worker startup with correct PYTHONPATH
- Heartbeat monitoring showing queue statistics
- Detection of existing workers to prevent conflicts
- Graceful shutdown of both API and worker

Environment variables for the script:
- `HEARTBEAT_SECONDS` (default: `5`) - Monitoring interval
- `KILL_EXISTING_WORKERS` (default: `0`) - Set to `1` to kill any existing workers on startup
- `PYTHON_BIN` - Python interpreter path (auto-detected)
- `RQ_BIN` - RQ command path (auto-detected)

**Option B: Run worker manually**

```bash
cd backend
export PYTHONPATH=/path/to/meeting-intel/backend
rq worker default
```

### Worker Scaling Guidance

- Run multiple workers to increase throughput (one job per worker process).
- Separate queues for heavy vs. light jobs if analysis time varies.
- Example: `rq worker default high` to process multiple queues.
- Use `KILL_EXISTING_WORKERS=1` when running the dev script to ensure clean single-worker environment.

## API Reference

### Authentication
- `POST /auth/login` (OAuth2 form fields `username` and `password`) sets auth cookie and returns token
- `POST /auth/logout` clears auth cookie

### Meetings
- `POST /meetings/analyze` (sync analysis)
- `POST /meetings/analyze-async` (enqueue background analysis)
- `GET /meetings/jobs/{job_id}` (async job status and result)
- `GET /meetings/history` (paginated history)
- `GET /meetings/{meeting_id}` (meeting detail)
- `WS /meetings/transcribe/live` (live chunked audio transcription via OpenAI Whisper)

#### Live Transcription WebSocket

Endpoint: `ws://localhost:8003/meetings/transcribe/live`

Authentication:
- Cookie auth works automatically in browser clients.
- Or pass JWT as query param: `?token=<access_token>`.

Protocol:
- Send binary audio chunks (webm/ogg/mp4 chunks from MediaRecorder are recommended).
- Optional control message to finish: `{"event":"finalize"}`.

Server events:
- `{"event":"ready", "model":"whisper-1", "max_chunk_bytes":...}`
- `{"event":"partial", "chunk_index":N, "text":"...", "full_text":"..."}`
- `{"event":"final", "text":"...", "chunks":N}`
- `{"event":"error", "detail":"..."}`

### Analytics
- `GET /meetings/analytics/user` (user aggregate stats)
- `GET /meetings/analytics/user/daily` (user daily stats)
- `GET /meetings/analytics/global` (admin-only aggregate stats)
- `GET /meetings/analytics/global/daily` (admin-only daily stats)

### Debug
- `GET /debug/request-info`

### Health
- `GET /health`

## Example Requests

### Login

```bash
curl -X POST "http://localhost:8003/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=avishek&password=secret123"
```

### Analyze a Meeting (Sync)

```bash
curl -X POST "http://localhost:8003/meetings/analyze" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"title":"Team Standup","transcript":"Meeting transcript text here..."}'
```

### Analyze a Meeting (Async)

```bash
curl -X POST "http://localhost:8003/meetings/analyze-async" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"title":"Team Standup","transcript":"Meeting transcript text here..."}'
```

### Check Job Status

```bash
curl -X GET "http://localhost:8003/meetings/jobs/<job_id>" \
  -H "Authorization: Bearer <token>"
```

## Data Model

### users
- `id` (UUID, PK)
- `email` (unique, nullable)
- `role` (`admin` or `user`)
- `created_at`

### meetings
- `id` (UUID, PK)
- `user_id` (FK -> users.id)
- `transcript_text`
- `transcript_hash` (unique)
- `summary_text`
- `action_items` (JSONB)
- `created_at`

### usage_records
- `id` (UUID, PK)
- `user_id` (FK -> users.id)
- `meeting_id` (FK -> meetings.id)
- `model_name`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `estimated_cost`
- `created_at`

## AI Pipeline Details

### LLM Provider Configuration

MeetingIntel supports two LLM providers that can be easily switched:

**Current Default**: Google Genai (Gemini)

**Supported Providers**:
- **Google Genai**: Uses Gemini models (gemini-2.5-pro, gemini-2.5-flash)
- **OpenAI**: Uses GPT models (gpt-4o-mini, gpt-3.5-turbo, gpt-4)

**Switching Providers**:

1. Update your `.env` file with the appropriate API key:
   ```env
   # For Google Genai
   GOOGLE_API_KEY="your-google-api-key"
   
   # For OpenAI
   # OPENAI_API_KEY="your-openai-api-key"
   ```

2. Update the import in [`backend/ai_engine/pipeline.py`](backend/ai_engine/pipeline.py#L3):
   ```python
   # For Google Genai (current default)
   from ai_engine.google_llm import generate_response, summarize_text, extract_action_items
   
   # For OpenAI
   # from ai_engine.llm import generate_response, summarize_text, extract_action_items
   ```

3. Restart the application

Both providers implement the same interface, ensuring seamless switching without code changes beyond the import statement.

### Pipeline Steps

1) **Preprocessing**: normalize whitespace in transcripts
2) **Chunking**: split long transcripts into word-based chunks
3) **Summarization**: prompt-driven summarization with JSON fallback parsing
4) **Action items**: structured extraction with validation and priority normalization
5) **Validation**: summary and action item schema checks with fallback logic

## Caching

- Results are cached in Redis by transcript hash.
- Cache TTL defaults to 10 minutes and can be tuned via `MEETING_CACHE_TTL_SECONDS`.
- Cache is invalidated after a successful database write.
- If Redis is unavailable, processing continues without cache.

## Analytics

- Per-user and global stats aggregate usage cost and tokens by model.
- Daily stats provide time-series cost, token usage, and meeting counts.

## Observability

- **Request logging** with correlation IDs and request IDs for end-to-end request tracing
- **Structured logs** using structlog with Rich output for development environments
- **Sensitive data redaction**: Query parameters and PII are automatically redacted in logs
- **Background job monitoring**: Real-time heartbeat monitoring when using `start_dev.sh`:
  - Queue statistics (queued, executing, finished, failed counts)
  - Worker status and process IDs
  - Existing worker detection to prevent conflicts
- **Token and cost tracking**: Usage metadata captured for each LLM call
- **Health check endpoint** at `/health` for monitoring and load balancer probes

## Graphify Workflow Note

If graphify extraction includes semantic nodes/edges without `source_file`, run the normalizer before build/report steps:

```bash
python scripts/normalize_graphify_extraction.py
```

This patch is idempotent and updates `graphify-out/.graphify_extract.json` in place so graphify build/report/viz commands run without schema warnings.

## Configuration and Environment Variables

These are read from `.env` at the repo root by default.

Required (all environments):
- `JWT_SECRET_KEY`
- `DATABASE_URL`

**Note**: Either `OPENAI_API_KEY` or `GOOGLE_API_KEY` must be configured depending on which LLM provider is used in the pipeline.

Required (production only):
- `PII_HASH_PEPPER` — Application startup will fail if `ENVIRONMENT=production` and this is not set

Auth and JWT:
- `JWT_ALGORITHM` (default: `HS256`)
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default: `1440`)
- `AUTH_COOKIE_NAME` (default: `access_token`)
- `AUTH_COOKIE_SECURE` (default: `True`)
- `AUTH_COOKIE_SAMESITE` (default: `lax`)
- `AUTH_COOKIE_DOMAIN` (default: `None`)
- `AUTH_COOKIE_PATH` (default: `/`)

App:
- `APP_NAME` (default: `MeetingIntel`)
- `ENVIRONMENT` (default: `development`)

OpenAI:
- `OPENAI_API_KEY` (optional if using Google Genai)
- `OPENAI_MODEL` (default: `gpt-4o-mini`)
- `OPENAI_FALLBACK_MODEL` (default: `gpt-3.5-turbo`)
- `OPENAI_TEMPERATURE` (default: `0.3`)
- `OPENAI_REQUEST_TIMEOUT` (default: `30`)
- `OPENAI_MAX_TOKENS_PER_REQUEST` (default: `2000`)
- `MAX_TRANSCRIPT_TOKENS` (default: `12000`)
- `OPENAI_MAX_RETRIES` (default: `3`)
- `OPENAI_RETRY_BASE_WAIT` (default: `2`)

Google Genai:
- `GOOGLE_API_KEY` (optional if using OpenAI)
- `GOOGLE_MODEL` (default: `gemini-2.5-pro`)
- `GOOGLE_FALLBACK_MODEL` (default: `gemini-2.5-flash`)
- `GOOGLE_API_TIMEOUT_SECONDS` (default: `30`)
- `GOOGLE_TEMPERATURE` (default: `0.3`)
- `GOOGLE_MAX_TOKENS_PER_REQUEST` (default: `2000`)
- `GOOGLE_MAX_RETRIES` (default: `3`)
- `GOOGLE_RETRY_BASE_WAIT` (default: `2`)

Cache:
- `MEETING_CACHE_TTL_SECONDS` (default: `600`)

Rate limiting:
- `RATE_LIMIT_WINDOW_SECONDS` (default: `60`)
- `RATE_LIMIT_MAX_REQUESTS` (default: `60`)
- `RATE_LIMIT_MAX_REQUESTS_ANON` (default: `30`)

Redis and queueing:
- `REDIS_URL` (default: `None`)
- `REDIS_SOCKET_TIMEOUT` (default: `5`)
- `REDIS_SOCKET_CONNECT_TIMEOUT` (default: `5`)

Celery (unused in current code paths):
- `CELERY_BROKER_URL` (default: `None`)
- `CELERY_RESULT_BACKEND` (default: `None`)

**Note**: Environment variable names are case-insensitive; both `REDIS_URL` and `redis_url` will work, but uppercase is recommended for consistency.

Privacy:
- `PII_HASH_PEPPER` (default: empty string for development; **MANDATORY in production**)
  - **Production behavior**: Application will fail to start if `ENVIRONMENT=production` and `PII_HASH_PEPPER` is not set or empty
  - **Security requirement**: Must be a cryptographically secure random string (32+ characters recommended)
  - **Purpose**: Prevents enumeration attacks on hashed PII (user IDs, meeting IDs)
  - **Generation example**: `openssl rand -hex 32` or `python -c "import secrets; print(secrets.token_hex(32))"`

Daily caps:
- `DAILY_TOKEN_CAP` (default: `None`)
- `DAILY_COST_CAP_USD` (default: `None`)

## Development

### Run in Development Mode

**Option A: Integrated development server (recommended)**

```bash
cd backend
bash scripts/start_dev.sh
```

This provides:
- Auto-reload API server on port 8003
- Background RQ worker with correct PYTHONPATH
- Real-time heartbeat monitoring (queue stats, worker status)
- Automatic cleanup on exit

**Option B: API only**

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8003
```

### Development Tools

#### LLM Provider Comparison

Compare responses from OpenAI and Google Genai side-by-side:

```bash
cd backend
export PYTHONPATH=/path/to/meeting-intel/backend
python scripts/compare_llm_responses.py --task summary --prompt "Meeting about project timeline..."
```

Options:
- `--task`: `summary`, `action_items`, or `generic`
- `--prompt`: Text prompt to send to both providers
- `--pretty`: Pretty-print JSON output

Example output shows timing, token usage, and responses from both providers for direct comparison.

#### Queue Management

Requeue failed jobs matching specific error patterns:

```bash
cd backend
export PYTHONPATH=/path/to/meeting-intel/backend
python scripts/requeue_failed_import_jobs.py --error-substring "ImportError" --apply
```

Omit `--apply` for dry-run mode. Useful for recovering from deployment issues or dependency errors.

#### Database Indexing

Add optimized index for usage record queries:

```bash
cd backend
export PYTHONPATH=/path/to/meeting-intel/backend
python scripts/add_usage_meeting_created_index.py
```

### API Docs

Swagger UI is available at `http://localhost:8003/docs`.

### Tests

```bash
pytest
```

## Security Notes

- JWT is issued on login and stored in an HTTP-only cookie by default.
- Authenticated routes rely on the current user from JWT payload.
- Passwords are hashed with bcrypt.

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]
