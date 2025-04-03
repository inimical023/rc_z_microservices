@echo off
REM Single-click setup script for RingCentral-Zoho Microservices (Windows version)

echo Starting RingCentral-Zoho Microservices Setup
echo ========================================================

REM Check if Docker is installed
docker --version > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Docker is not installed. Please install Docker Desktop for Windows first.
    echo Visit https://docs.docker.com/desktop/windows/install/ for installation instructions.
    pause
    exit /b 1
)

REM Check if Docker Compose is installed (included with Docker Desktop for Windows)
docker-compose --version > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Docker Compose is not installed. It should be included with Docker Desktop for Windows.
    echo Please ensure Docker Desktop is properly installed.
    pause
    exit /b 1
)

REM Create necessary directories
echo Creating necessary directories...
mkdir data 2>nul
mkdir logs 2>nul
mkdir templates 2>nul
mkdir static\css 2>nul
mkdir static\js 2>nul

REM Check if config.json exists, if not create it
if not exist config.json (
    echo Creating default configuration file...
    
    REM Try to create config using Python module
    python -c "from rc_zoho_microservices.shared.config import create_default_config; create_default_config('config.json')" 2>nul
    
    if %ERRORLEVEL% NEQ 0 (
        echo Failed to create default configuration file.
        echo Creating a basic config.json manually...
        
        echo {> config.json
        echo   "ringcentral": {>> config.json
        echo     "jwt_token": "",>> config.json
        echo     "client_id": "",>> config.json
        echo     "client_secret": "",>> config.json
        echo     "account_id": "~",>> config.json
        echo     "base_url": "https://platform.ringcentral.com">> config.json
        echo   },>> config.json
        echo   "zoho": {>> config.json
        echo     "client_id": "",>> config.json
        echo     "client_secret": "",>> config.json
        echo     "refresh_token": "",>> config.json
        echo     "base_url": "https://www.zohoapis.com/crm/v7">> config.json
        echo   },>> config.json
        echo   "message_broker": {>> config.json
        echo     "type": "rabbitmq",>> config.json
        echo     "host": "rabbitmq",>> config.json
        echo     "port": 5672,>> config.json
        echo     "username": "guest",>> config.json
        echo     "password": "guest">> config.json
        echo   },>> config.json
        echo   "services": {>> config.json
        echo     "call_service": {>> config.json
        echo       "name": "call_service",>> config.json
        echo       "host": "0.0.0.0",>> config.json
        echo       "port": 8001,>> config.json
        echo       "log_level": "INFO",>> config.json
        echo       "debug": false>> config.json
        echo     },>> config.json
        echo     "lead_service": {>> config.json
        echo       "name": "lead_service",>> config.json
        echo       "host": "0.0.0.0",>> config.json
        echo       "port": 8002,>> config.json
        echo       "log_level": "INFO",>> config.json
        echo       "debug": false>> config.json
        echo     },>> config.json
        echo     "orchestrator_service": {>> config.json
        echo       "name": "orchestrator_service",>> config.json
        echo       "host": "0.0.0.0",>> config.json
        echo       "port": 8003,>> config.json
        echo       "log_level": "INFO",>> config.json
        echo       "debug": false>> config.json
        echo     },>> config.json
        echo     "admin_service": {>> config.json
        echo       "name": "admin_service",>> config.json
        echo       "host": "0.0.0.0",>> config.json
        echo       "port": 8000,>> config.json
        echo       "log_level": "INFO",>> config.json
        echo       "debug": false>> config.json
        echo     },>> config.json
        echo     "notification_service": {>> config.json
        echo       "name": "notification_service",>> config.json
        echo       "host": "0.0.0.0",>> config.json
        echo       "port": 8004,>> config.json
        echo       "log_level": "INFO",>> config.json
        echo       "debug": false>> config.json
        echo     }>> config.json
        echo   }>> config.json
        echo }>> config.json
    )
    
    echo Default configuration file created.
    echo Please update config.json with your RingCentral and Zoho credentials before starting the services.
) else (
    echo Configuration file already exists.
)

REM Ask if user wants to start services now
set /p START_SERVICES="Do you want to start the services now? (y/n) "
if /i "%START_SERVICES%"=="y" (
    echo Starting services with Docker Compose...
    docker-compose up -d
    
    if %ERRORLEVEL% EQU 0 (
        echo Services started successfully!
        echo Admin interface is available at: http://localhost:8000
        echo API documentation is available at: http://localhost:8000/docs
        echo.
        echo Service endpoints:
        echo - Call Service: http://localhost:8001
        echo - Lead Service: http://localhost:8002
        echo - Orchestrator Service: http://localhost:8003
        echo - Notification Service: http://localhost:8004
        echo - RabbitMQ Management: http://localhost:15672 (guest/guest)
    ) else (
        echo Failed to start services.
        echo Please check the error messages above.
    )
) else (
    echo You can start the services later with: docker-compose up -d
)

echo.
echo Setup completed!
pause