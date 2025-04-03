#!/bin/bash
# Single-click setup script for RingCentral-Zoho Microservices

# Print colored output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting RingCentral-Zoho Microservices Setup${NC}"
echo "========================================================"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    echo "Visit https://docs.docker.com/get-docker/ for installation instructions."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Docker Compose is not installed. Please install Docker Compose first.${NC}"
    echo "Visit https://docs.docker.com/compose/install/ for installation instructions."
    exit 1
fi

# Create necessary directories
echo -e "${YELLOW}Creating necessary directories...${NC}"
mkdir -p data logs templates static/css static/js

# Check if config.json exists, if not create it
if [ ! -f "config.json" ]; then
    echo -e "${YELLOW}Creating default configuration file...${NC}"
    python -c "from rc_zoho_microservices.shared.config import create_default_config; create_default_config('config.json')"
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create default configuration file.${NC}"
        echo "Creating a basic config.json manually..."
        
        cat > config.json << EOF
{
  "ringcentral": {
    "jwt_token": "",
    "client_id": "",
    "client_secret": "",
    "account_id": "~",
    "base_url": "https://platform.ringcentral.com"
  },
  "zoho": {
    "client_id": "",
    "client_secret": "",
    "refresh_token": "",
    "base_url": "https://www.zohoapis.com/crm/v7"
  },
  "message_broker": {
    "type": "rabbitmq",
    "host": "rabbitmq",
    "port": 5672,
    "username": "guest",
    "password": "guest"
  },
  "services": {
    "call_service": {
      "name": "call_service",
      "host": "0.0.0.0",
      "port": 8001,
      "log_level": "INFO",
      "debug": false
    },
    "lead_service": {
      "name": "lead_service",
      "host": "0.0.0.0",
      "port": 8002,
      "log_level": "INFO",
      "debug": false
    },
    "orchestrator_service": {
      "name": "orchestrator_service",
      "host": "0.0.0.0",
      "port": 8003,
      "log_level": "INFO",
      "debug": false
    },
    "admin_service": {
      "name": "admin_service",
      "host": "0.0.0.0",
      "port": 8000,
      "log_level": "INFO",
      "debug": false
    },
    "notification_service": {
      "name": "notification_service",
      "host": "0.0.0.0",
      "port": 8004,
      "log_level": "INFO",
      "debug": false
    }
  }
}
EOF
    fi
    
    echo -e "${GREEN}Default configuration file created.${NC}"
    echo -e "${YELLOW}Please update config.json with your RingCentral and Zoho credentials before starting the services.${NC}"
else
    echo -e "${GREEN}Configuration file already exists.${NC}"
fi

# Ask if user wants to start services now
read -p "Do you want to start the services now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Starting services with Docker Compose...${NC}"
    docker-compose up -d
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Services started successfully!${NC}"
        echo "Admin interface is available at: http://localhost:8000"
        echo "API documentation is available at: http://localhost:8000/docs"
        echo
        echo "Service endpoints:"
        echo "- Call Service: http://localhost:8001"
        echo "- Lead Service: http://localhost:8002"
        echo "- Orchestrator Service: http://localhost:8003"
        echo "- Notification Service: http://localhost:8004"
        echo "- RabbitMQ Management: http://localhost:15672 (guest/guest)"
    else
        echo -e "${RED}Failed to start services.${NC}"
        echo "Please check the error messages above."
    fi
else
    echo -e "${YELLOW}You can start the services later with:${NC} docker-compose up -d"
fi

echo
echo -e "${GREEN}Setup completed!${NC}"