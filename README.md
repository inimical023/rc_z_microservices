# RingCentral-Zoho Microservices Integration

A modern, microservices-based integration between RingCentral and Zoho CRM that processes call logs, creates leads, and attaches recordings.

## Architecture

This project implements a microservices architecture with event-driven communication:

![Architecture Diagram](docs/architecture.png)

### Services

1. **Call Service**: Handles RingCentral API interactions (call logs, recordings)
   - Retrieves call logs from RingCentral
   - Fetches call recordings
   - Publishes call events to the message broker

2. **Lead Service**: Manages Zoho CRM API interactions (leads, notes, attachments)
   - Creates and updates leads in Zoho CRM
   - Adds notes to leads
   - Attaches recordings to leads
   - Publishes lead events to the message broker

3. **Orchestrator Service**: Coordinates the workflow between Call Service and Lead Service
   - Subscribes to events from both services
   - Implements business logic for call processing
   - Handles the workflow for accepted and missed calls
   - Publishes lead processed events

4. **Notification Service**: Handles email notifications
   - Subscribes to lead processed events
   - Sends email notifications based on configurable templates

5. **Admin Service**: Provides a web-based admin interface
   - Configures credentials and settings
   - Manages extensions and lead owners
   - Triggers call processing
   - Monitors service health

### Event-Driven Communication

Services communicate asynchronously through a message broker (Kafka, RabbitMQ, or in-memory for development). Events include:

- `call_logged`: Emitted when a call log is retrieved from RingCentral
- `lead_created`: Emitted when a new lead is created in Zoho CRM
- `lead_updated`: Emitted when an existing lead is updated
- `recording_attached`: Emitted when a recording is attached to a lead
- `lead_processed`: Emitted when lead processing is complete

## Technology Stack

- **Language:** Python 3.9+
- **Web Framework:** FastAPI
- **API Client:** HTTPX
- **Data Validation:** Pydantic
- **Message Broker:** Kafka/RabbitMQ (configurable)
- **Containerization:** Docker
- **Orchestration:** Kubernetes

## Installation

### Prerequisites

- Python 3.9 or higher
- pip (Python package manager)
- Docker (optional, for containerized deployment)
- Kubernetes (optional, for orchestrated deployment)

### Single-Click Setup

For a quick and easy setup, use our single-click setup scripts:

#### On Linux/macOS:
```bash
# Clone the repository
git clone https://github.com/example/rc_zoho_microservices.git
cd rc_zoho_microservices

# Make the setup script executable
chmod +x setup.sh

# Run the setup script
./setup.sh
```

#### On Windows:
```bash
# Clone the repository
git clone https://github.com/example/rc_zoho_microservices.git
cd rc_zoho_microservices

# Run the setup script
setup.bat
```

The setup script will:
1. Check for required dependencies (Docker and Docker Compose)
2. Create necessary directories
3. Generate a default configuration file
4. Optionally start all services using Docker Compose

### Manual Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/example/rc_zoho_microservices.git
   cd rc_zoho_microservices
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the package in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

4. Create a default configuration file:
   ```bash
   python -m rc_zoho_microservices.shared.config
   ```

5. Update the configuration file with your credentials:
   ```bash
   # Edit config.json with your RingCentral and Zoho credentials
   ```

### Docker Deployment

1. Build the Docker images:
   ```bash
   docker-compose build
   ```

2. Start the services:
   ```bash
   docker-compose up -d
   ```

## Configuration

The application is configured through a `config.json` file or environment variables. The configuration includes:

- RingCentral API credentials
- Zoho CRM API credentials
- Message broker settings
- Service configurations (host, port, log level, etc.)

Example configuration:

```json
{
  "ringcentral": {
    "jwt_token": "your_jwt_token",
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "account_id": "~"
  },
  "zoho": {
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "refresh_token": "your_refresh_token"
  },
  "message_broker": {
    "type": "memory"
  },
  "services": {
    "call_service": {
      "host": "0.0.0.0",
      "port": 8001,
      "log_level": "INFO",
      "debug": false
    },
    "lead_service": {
      "host": "0.0.0.0",
      "port": 8002,
      "log_level": "INFO",
      "debug": false
    },
    "orchestrator_service": {
      "host": "0.0.0.0",
      "port": 8003,
      "log_level": "INFO",
      "debug": false
    },
    "admin_service": {
      "host": "0.0.0.0",
      "port": 8000,
      "log_level": "INFO",
      "debug": false
    },
    "notification_service": {
      "host": "0.0.0.0",
      "port": 8004,
      "log_level": "INFO",
      "debug": false
    }
  }
}
```

## Usage

### Starting the Services

Each service can be started individually:

```bash
# Start the Call Service
python -m rc_zoho_microservices.call_service.service

# Start the Lead Service
python -m rc_zoho_microservices.lead_service.service

# Start the Orchestrator Service
python -m rc_zoho_microservices.orchestrator_service.service

# Start the Notification Service
python -m rc_zoho_microservices.notification_service.service

# Start the Admin Service
python -m rc_zoho_microservices.admin_service.service
```

Or using Docker Compose:

```bash
docker-compose up -d
```

### Accessing the Admin Interface

Once the services are running, you can access the Admin Interface at:

```
http://localhost:8000
```

The Admin Interface allows you to:

1. Configure RingCentral and Zoho CRM credentials
2. Manage extensions to monitor
3. Configure lead owners
4. Process call logs
5. Monitor service health

## API Documentation

Each service provides a Swagger UI for API documentation:

- Call Service: `http://localhost:8001/docs`
- Lead Service: `http://localhost:8002/docs`
- Orchestrator Service: `http://localhost:8003/docs`
- Notification Service: `http://localhost:8004/docs`
- Admin Service: `http://localhost:8000/docs`

## Development

### Project Structure

```
rc_zoho_microservices/
├── shared/                 # Shared utilities and models
│   ├── utils.py            # Utility functions
│   ├── models.py           # Data models
│   ├── message_broker.py   # Message broker abstraction
│   └── config.py           # Configuration handling
├── call_service/           # RingCentral API interactions
│   ├── ringcentral_client.py  # RingCentral API client
│   └── service.py          # Call Service implementation
├── lead_service/           # Zoho CRM API interactions
│   ├── zoho_client.py      # Zoho CRM API client
│   └── service.py          # Lead Service implementation
├── orchestrator_service/   # Workflow orchestration
│   └── service.py          # Orchestrator Service implementation
├── notification_service/   # Email notifications
│   └── service.py          # Notification Service implementation
├── admin_service/          # Admin interface
│   └── service.py          # Admin Service implementation
├── deployment/             # Deployment configurations
│   ├── docker/             # Docker configurations
│   └── kubernetes/         # Kubernetes configurations
└── docs/                   # Documentation
```

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black .
isort .
```

### Type Checking

```bash
mypy .
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.