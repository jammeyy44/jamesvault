# GameAPI

A centralized REST API for interacting with multiple third-party game providers across five categories. Features an admin dashboard for managing accounts and API keys, with high concurrency and scalability using Flask, Flask-RESTx, Flask-SQLAlchemy, and Redis caching.

## Overview

This project provides a unified interface to interact with various game provider APIs, organized into five categories. It includes comprehensive admin functionality, logging, and caching mechanisms for optimal performance.

## Features

- 🎮 **Multi-Provider Support**: Unified API for 5 categories of game providers
- 🔐 **Admin Dashboard**: Web interface for managing accounts, tokens, and logs
- ⚡ **High Performance**: Redis caching for improved response times
- 📊 **Comprehensive Logging**: Track all API requests and responses
- 🔑 **Token Management**: Secure API key management system
- 📝 **Swagger Documentation**: Interactive API documentation
- 🧪 **Test Coverage**: Comprehensive test suite

## Game Provider Categories

### Category 1
Gameroom, Cash Machine, Mr All In One, Cash Frenzy, Mafia, King of Pop

### Category 2
Game Vault, Vegas Sweeps, Juwa

### Category 3
Orion Stars, Panda Master, Milkyway, Fire Kirin

### Category 4
River Sweeps

### Category 5
Vblink, Egame, Ultra Panda

## Tech Stack

- **Backend**: Flask, Flask-RESTx, Flask-SQLAlchemy
- **Database**: PostgreSQL
- **Caching**: Redis
- **Documentation**: Swagger/OpenAPI
- **Testing**: pytest (see TESTING.md)

## Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Redis 6+
- pip

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/petergt44/GameAPI.git
cd GameAPI
```

### 2. Create a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

Create a `.env` file in the root directory:

```env
SECRET_KEY=your_secret_key_here
DATABASE_URL=postgresql://username:password@127.0.0.1:5432/gameapis
CAPTCHA_API_KEY=your_2captcha_api_key
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

**Note**: The `config.py` file will use these environment variables if set, otherwise it will use default values for local development.

### 5. Set Up the Database

Initialize and migrate the database:

```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### 6. Seed Initial Data

Populate the database with initial provider and admin data:

```bash
# Seed providers
python seed_providers.py

# Seed admin accounts
python seed_admins.py
```

### 7. Start Redis

Install and start Redis:

**Ubuntu/Debian:**
```bash
sudo apt-get install redis-server
redis-server
```

**macOS:**
```bash
brew install redis
brew services start redis
```

**Windows:**
Download and install from [Redis for Windows](https://github.com/microsoftarchive/redis/releases)

### 8. Run the Application

```bash
python run.py
```

The application will be available at `http://localhost:5000` (or the port specified in `run.py`).

## API Documentation

### Swagger UI

Access interactive API documentation at:
- **Swagger UI**: `http://localhost:5000/swagger/`
- **ReDoc**: `http://localhost:5000/redoc/`

### Admin API

**Base URL**: `/admin/api/`

**Endpoints**:
- `POST /admin/api/login` - Admin authentication
- `GET /admin/api/accounts` - List all accounts
- `POST /admin/api/accounts` - Create new account
- `GET /admin/api/tokens` - List API tokens
- `POST /admin/api/tokens` - Generate new token
- `GET /admin/api/logs` - View API logs

### Game Provider API

**Base URL**: `/categoryX/` (where X is 1–5)

**Common Endpoints** (available for all categories):
- `POST /categoryX/login` - User login
- `POST /categoryX/add_user` - Add new user
- `POST /categoryX/recharge` - Recharge user balance
- `POST /categoryX/redeem` - Redeem user balance
- `POST /categoryX/reset_password` - Reset user password
- `GET /categoryX/balance` - Get user balance
- `GET /categoryX/agent_balance` - Get agent balance

## Project Structure

```
GameAPI/
├── app/
│   ├── routes/
│   │   ├── admin/          # Admin API routes
│   │   └── api/            # Game provider API routes
│   ├── services/           # Business logic for each category
│   ├── templates/          # Admin dashboard templates
│   └── utils/              # Utility functions
├── migrations/             # Database migrations
├── tests/                  # Test suite
├── config.py               # Configuration settings
├── run.py                  # Application entry point
├── seed_providers.py       # Seed provider data
├── seed_admins.py          # Seed admin accounts
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## Usage Examples

### Using the Admin Dashboard

1. Navigate to `http://localhost:5000/admin/`
2. Login with admin credentials (created via `seed_admins.py`)
3. Manage accounts, tokens, and view logs through the web interface

### Using the API

**Example: User Login (Category 1)**
```bash
curl -X POST http://localhost:5000/category1/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "password123"
  }'
```

**Example: Get User Balance**
```bash
curl -X GET http://localhost:5000/category1/balance?username=testuser
```

## Testing

See [TESTING.md](TESTING.md) for comprehensive testing documentation.

Run tests:
```bash
pytest tests/
```

## Configuration

The application configuration is managed in `config.py`. Key settings:

- **Database**: PostgreSQL connection string
- **Redis**: Caching configuration
- **Providers**: URLs for each game provider category
- **Security**: Secret keys and API keys

For production, ensure all sensitive values are set via environment variables.

## Development

### Running in Development Mode

```bash
export FLASK_ENV=development
export FLASK_DEBUG=1
python run.py
```

### Database Migrations

Create a new migration:
```bash
flask db migrate -m "Description of changes"
```

Apply migrations:
```bash
flask db upgrade
```

## Deployment

For production deployment:

1. Set all environment variables securely
2. Use a production WSGI server (e.g., Gunicorn)
3. Configure proper database connection pooling
4. Set up Redis persistence
5. Enable HTTPS/SSL
6. Configure proper logging
7. Set up monitoring and alerting

**Example with Gunicorn:**
```bash
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License.

## Author

**Peter Gakungu**
- GitHub: [@petergt44](https://github.com/petergt44)

## Support

For questions or issues, please open an issue on GitHub.

---

🚀 **Happy gaming!** 🎮
