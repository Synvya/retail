# Synvya Retail Backend

Backend API for Synvya Retail Commerce platform, providing integration with Square and other payment providers.

## Features

- Square OAuth integration
- Merchant profile management
- Synvya SDK integration for portfolio publishing
- PostgreSQL database for data storage

## Development

### Prerequisites

- Python 3.12+
- PostgreSQL

### Setup

1. Clone the repository:
   ```
   git clone https://github.com/synvya/retail-backend.git
   cd retail-backend
   ```

2. Install dependencies:
   ```
   pip install -e ".[dev]"
   ```

3. Set up environment variables in `.env` file

4. Run migrations:
   ```
   alembic upgrade head
   ```

5. Start the development server:
   ```
   uvicorn src.retail.core.main:app --reload
   ```

## License

MIT
