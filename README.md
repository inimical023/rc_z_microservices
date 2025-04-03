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

Services communicate asynchronously through a message broker (RabbitMQ). Events include:

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
- **Message Broker:** RabbitMQ
- **Containerization:** Docker
- **Orchestration:** Kubernetes

## Installation

### Prerequisites

- Python 3.9 or higher
- pip (Python package manager)
- Docker and Docker Compose (for containerized deployment)
- Kubernetes (optional, for orchestrated deployment)

### Configuration

1. Create a configuration file:
   ```bash
   cp config.example.json config.json
   ```

2. Update the configuration file with your credentials:
   - RingCentral JWT token, client ID, and client secret
   - Zoho client ID, client secret, and refresh token
   - Message broker connection details
   - Service-specific configuration

**IMPORTANT**: The configuration file contains sensitive information and should not be committed to version control.

### Docker Deployment

1. Create and configure your `config.json` file
   ```bash
   cp config.example.json config.json
   # Edit config.json with your credentials
   ```

2. Build the Docker images:
   ```bash
   docker-compose build
   ```

3. Start the services:
   ```bash
   docker-compose up -d
   ```

### Local Development Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install the package in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

3. Create and configure your `config.json` file:
   ```bash
   cp config.example.json config.json
   # Edit config.json with your credentials
   ```

4. Start each service individually:
   ```bash
   python call_service/service.py
   python lead_service/service.py
   python orchestrator_service/service.py
   python notification_service/service.py
   python admin_service/service.py
   ```

## Environment Variable Configuration

The application can also be configured using environment variables. This is particularly useful for containerized deployments. The following environment variables are supported:

- `RINGCENTRAL_JWT_TOKEN` - RingCentral JWT token
- `RINGCENTRAL_CLIENT_ID` - RingCentral client ID
- `RINGCENTRAL_CLIENT_SECRET` - RingCentral client secret
- `ZOHO_CLIENT_ID` - Zoho CRM client ID
- `ZOHO_CLIENT_SECRET` - Zoho CRM client secret
- `ZOHO_REFRESH_TOKEN` - Zoho CRM refresh token
- `RABBITMQ_HOST` - RabbitMQ host
- `RABBITMQ_PORT` - RabbitMQ port
- `RABBITMQ_USERNAME` - RabbitMQ username
- `RABBITMQ_PASSWORD` - RabbitMQ password

Environment variables take precedence over values in the config.json file.

## Usage

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

## Troubleshooting

### Common Issues

1. **Config file not found**: 
   - Make sure you've created `config.json` in the project root
   - Try specifying the full path to the config file
   - Check if Docker volumes are mounting correctly

2. **API Authentication Errors**:
   - Verify your RingCentral and Zoho credentials
   - Check that API tokens haven't expired
   - Ensure the correct API version is being used (Zoho v7)

3. **Service Communication Issues**:
   - Check if RabbitMQ is running correctly
   - Verify service endpoints are accessible
   - Check network settings in Docker Compose

### Health Checks

Each service provides a health check endpoint at `/health`. Use this to verify service status:

```bash
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
curl http://localhost:8000/health
```

## License

This project is licensed under the MIT License - see the LICENSE file for details. 