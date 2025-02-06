# Grade-A Express Backend

Backend API for Grade-A Express, a logistics and Buy4Me service platform built with Django and Django REST Framework.

## Features

- 🔐 JWT Authentication
- 👤 User Management (Walk-In, Buy4Me, Admin, Super Admin)
- 📦 Buy4Me Service Management
- 🚚 Shipment Tracking
- 💳 Payment Processing
- 📊 API Documentation with Swagger/ReDoc

## Tech Stack

- Python 3.10+
- Django 5.0+
- Django REST Framework
- SQLite (Development) / PostgreSQL (Production)
- JWT Authentication
- Swagger/ReDoc Documentation

## Project Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/grade-a-express.git
cd grade-a-express
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install -r requirements/development.txt
```

4. Create .env file:
```bash
cp .env.example .env
# Update the values in .env file
```

5. Run migrations:
```bash
python manage.py migrate
```

6. Create superuser:
```bash
python manage.py createsuperuser
```

7. Run development server:
```bash
python manage.py runserver
```

## API Documentation

Access the API documentation at:
- Swagger UI: http://127.0.0.1:8000/api/docs/
- ReDoc: http://127.0.0.1:8000/api/redoc/

## Authentication

The API uses JWT authentication. To get tokens:

```bash
# Get tokens
curl -X POST http://127.0.0.1:8000/api/token/ \
    -H "Content-Type: application/json" \
    -d '{"username":"your_username","password":"your_password"}'

# Use token
curl http://127.0.0.1:8000/api/accounts/users/ \
    -H "Authorization: Bearer your_access_token"
```

## Project Structure

```
grade-a-express/
├── core/                  # Project configuration
├── accounts/             # User management
├── buy4me/              # Buy4Me service
├── shipments/           # Shipment management
├── vendors/             # Vendor management
├── reports/             # Reporting and analytics
├── requirements/        # Project dependencies
└── manage.py           # Django management script
```

## Development

1. Install development dependencies:
```bash
pip install -r requirements/development.txt
```

2. Run tests:
```bash
python manage.py test
```

3. Check code style:
```bash
black .
flake8
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
