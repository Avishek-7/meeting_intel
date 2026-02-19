# MeetingIntel

MeetingIntel is an AI-powered meeting transcript analysis platform that generates concise summaries and extracts actionable tasks. The backend is built with FastAPI, SQLAlchemy, PostgreSQL, and OpenAI, and supports both synchronous and asynchronous processing with optional Redis caching and RQ background jobs.

## Highlights

- **Meeting analysis**: Summary + action items with validation and fallbacks
- **Async processing**: Background analysis via RQ + Redis
- **Analytics**: User and global usage statistics and daily breakdowns
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
  G --> H[OpenAI]
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
│   └── tests/                  # Test suite
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.10+
- PostgreSQL
- OpenAI API key
- Redis (optional, for caching and async jobs)

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
DATABASE_URL="postgresql+psycopg2://user:password@localhost/meeting_intel_db"
OPENAI_API_KEY="your-openai-api-key"

# Required for production deployment
PII_HASH_PEPPER="your-cryptographically-secure-random-string"  # Generate: openssl rand -hex 32

# Optional (recommended for async processing and caching)
redis_url="redis://localhost:6379/0"
```

3) Initialize the database

```bash
createdb meeting_intel_db
```

4) Run the API

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API runs at `http://localhost:8000`.

## Running the RQ Worker (Async Jobs)

Async analysis uses RQ + Redis. Ensure `redis_url` is set in `.env`, then run a worker:

```bash
rq worker default
```

### Worker Scaling Guidance

- Run multiple workers to increase throughput (one job per worker process).
- Separate queues for heavy vs. light jobs if analysis time varies.
- Example: `rq worker default high` to process multiple queues.

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
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=avishek&password=secret123"
```

### Analyze a Meeting (Sync)

```bash
curl -X POST "http://localhost:8000/meetings/analyze" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"title":"Team Standup","transcript":"Meeting transcript text here..."}'
```

### Analyze a Meeting (Async)

```bash
curl -X POST "http://localhost:8000/meetings/analyze-async" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"title":"Team Standup","transcript":"Meeting transcript text here..."}'
```

### Check Job Status

```bash
curl -X GET "http://localhost:8000/meetings/jobs/<job_id>" \
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

- Request logging with correlation IDs and request IDs.
- Structured logs using structlog with Rich output.
- Sensitive query parameters are redacted in logs.

## Configuration and Environment Variables

These are read from `.env` at the repo root by default.

Required (all environments):
- `JWT_SECRET_KEY`
- `DATABASE_URL`
- `OPENAI_API_KEY`

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
- `app_name` (default: `MeetingIntel`)
- `ENVIRONMENT` (default: `development`)

OpenAI:
- `OPENAI_MODEL` (default: `gpt-4o-mini`)
- `OPENAI_FALLBACK_MODEL` (default: `gpt-3.5-turbo`)
- `OPENAI_TEMPERATURE` (default: `0.3`)
- `OPENAI_REQUEST_TIMEOUT` (default: `30`)
- `OPENAI_MAX_TOKENS_PER_REQUEST` (default: `2000`)
- `MAX_TRANSCRIPT_TOKENS` (default: `12000`)
- `OPENAI_MAX_RETRIES` (default: `3`)
- `OPENAI_RETRY_BASE_WAIT` (default: `2`)

Cache:
- `MEETING_CACHE_TTL_SECONDS` (default: `600`)

Rate limiting:
- `RATE_LIMIT_WINDOW_SECONDS` (default: `60`)
- `RATE_LIMIT_MAX_REQUESTS` (default: `60`)
- `RATE_LIMIT_MAX_REQUESTS_ANON` (default: `30`)

Redis and queueing:
- `redis_url` (default: `None`)
- `redis_socket_timeout` (default: `5`)
- `redis_socket_connect_timeout` (default: `5`)

Celery (unused in current code paths):
- `celery_broker_url` (default: `None`)
- `celery_result_backend` (default: `None`)

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

```bash
cd backend
uvicorn main:app --reload
```

### API Docs

Swagger UI is available at `http://localhost:8000/docs`.

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
