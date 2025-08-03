# Document Management System

A comprehensive Flask-based document management system with advanced features including search, versioning, and security controls.

## Features

- **Advanced Search & Filtering**: Full-text search with filters by date, file type, size, and status
- **Document Versioning**: Track document changes with version history and comments
- **Enhanced Security**: Role-based permissions and document-specific access controls
- **Image Group Support**: Handle multiple images with navigation and bulk download
- **Activity Logging**: Track user actions and document access

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python run.py
   ```

## Usage

- Access the application at `http://localhost:5000`
- Login with provided credentials:
  - Admin: `admin` / `1111`
  - Admin: `mqwrya` / `mqwryapass`
  - Employee: `employee` / `2222`
  - Omar: `omar` / `omarpass`
  - Pola: `pola` / `polapass`

## Project Structure

```
test/
├── app/                          # Main application package
│   ├── models/                  # Database models and DMS logic
│   ├── routes/                  # Flask route blueprints
│   ├── utils/                   # Utility functions and helpers
│   └── config.py               # Configuration settings
├── templates/                   # HTML templates (organized)
├── static/                     # Static files (CSS, JS, images)
├── storage/                    # Document storage
├── database/                   # Database files
├── tests/                      # Test files
└── run.py                      # Application entry point
```

## License

This project is for educational and demonstration purposes. 