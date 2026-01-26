# MeetingIntel

AI-powered meeting transcript analysis platform that automatically generates summaries and extracts action items from meeting transcripts using LangGraph and OpenAI.

## Features

- **Smart Meeting Analysis**: Automatically processes meeting transcripts to generate concise summaries
- **Action Item Extraction**: Identifies and extracts action items with tasks, owners, and due dates
- **Intelligent Chunking**: Handles long transcripts by intelligently chunking text for optimal processing
- **RESTful API**: FastAPI-based backend with authentication and validation
- **Database Integration**: PostgreSQL database for storing meetings and user data
- **Authentication**: JWT-based authentication with secure password handling

## Tech Stack

### Backend
- **FastAPI** - Modern web framework for building APIs
- **LangChain & LangGraph** - LLM orchestration and workflow management
- **OpenAI GPT** - Natural language processing and generation
- **PostgreSQL** - Relational database
- **SQLAlchemy** - ORM and database toolkit
- **Pydantic** - Data validation and settings management
- **Python-JOSE** - JWT token handling
- **Loguru** - Logging
- **Uvicorn** - ASGI server

## Project Structure

```
meeting-intel/
├── backend/
│   ├── main.py                 # FastAPI application entry point
│   ├── ai_engine/              # AI processing pipeline
│   │   ├── pipeline.py         # Main analysis workflow
│   │   ├── llm.py              # LLM interaction logic
│   │   ├── preprocess.py       # Text cleaning and chunking
│   │   ├── validation.py       # Output validation
│   │   └── prompts/            # LLM prompt templates
│   ├── api/                    # API route handlers
│   │   ├── auth.py             # Authentication endpoints
│   │   ├── meetings.py         # Meeting processing endpoints
│   │   └── debug.py            # Debug endpoints
│   ├── core/                   # Core functionality
│   │   ├── config.py           # Configuration management
│   │   ├── database.py         # Database connection
│   │   ├── security.py         # Security utilities
│   │   ├── middleware.py       # Request logging
│   │   └── dependencies.py     # FastAPI dependencies
│   ├── schemas/                # Pydantic models
│   │   ├── meeting.py          # Meeting request/response schemas
│   │   └── auth.py             # Authentication schemas
│   └── services/               # Business logic layer
│       └── meeting_service.py  # Meeting processing service
├── .env                        # Environment variables
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Setup

### Prerequisites

- Python 3.10 or higher
- PostgreSQL database
- OpenAI API key

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd meeting-intel
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   
   Update the `.env` file with your credentials:
   ```env
   JWT_SECRET_KEY="your-secret-key"
   DATABASE_URL="postgresql+psycopg2://user:password@localhost/database"
   OPENAI_API_KEY="your-openai-api-key"
   ```

5. **Set up the database**
   ```bash
   # Create the PostgreSQL database
   createdb meeting_intel_db
   
   # Run migrations (if using Alembic)
   alembic upgrade head
   ```

6. **Run the application**
   ```bash
   cd backend
   python main.py
   # Or use uvicorn directly:
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

The API will be available at `http://localhost:8000`

## API Endpoints

### Authentication
- `POST /auth/login` - User login with email and password
- `GET /authorize` - Authorization placeholder

### Meetings
- `POST /meetings/process` - Process a meeting transcript
  - **Request Body:**
    ```json
    {
      "title": "Team Standup",
      "transcript": "Meeting transcript text here..."
    }
    ```
  - **Response:**
    ```json
    {
      "summary": "Meeting summary...",
      "action_items": [
        {
          "task": "Task description",
          "owner": "Person name",
          "due_date": "2026-01-30"
        }
      ]
    }
    ```

### Health Check
- `GET /health` - API health check

### Debug
- `POST /debug/request-info` - Get request information (for debugging)

## Usage Example

```python
import requests

# Login
login_response = requests.post(
    "http://localhost:8000/auth/login",
    json={"email": "user@example.com", "password": "password"}
)
token = login_response.json()["access_token"]

# Process meeting transcript
response = requests.post(
    "http://localhost:8000/meetings/process",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "title": "Q1 Planning Meeting",
        "transcript": "Your meeting transcript here..."
    }
)

result = response.json()
print("Summary:", result["summary"])
print("Action Items:", result["action_items"])
```

## AI Pipeline

The AI engine uses a multi-stage pipeline:

1. **Preprocessing**: Cleans and normalizes the transcript text
2. **Chunking**: Splits long transcripts into manageable chunks (max 3000 chars)
3. **Summarization**: Uses LangChain + OpenAI to generate concise summaries
4. **Action Item Extraction**: Identifies tasks, owners, and deadlines
5. **Validation**: Ensures output quality and format consistency

## Development

### Running in Development Mode
```bash
cd backend
uvicorn main:app --reload
```

### API Documentation
Visit `http://localhost:8000/docs` for interactive API documentation (Swagger UI)

## Security Features

- JWT-based authentication
- Password hashing with bcrypt
- Request validation using Pydantic
- Environment-based configuration
- SQL injection protection via SQLAlchemy ORM

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]
