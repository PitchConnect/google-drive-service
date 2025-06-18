# Start the service
docker-compose -f /path/to/docker-compose.yml up -d

# Stop the service
docker-compose -f /path/to/docker-compose.yml down

# Check if service is running
docker-compose -f /path/to/docker-compose.yml ps

# Check service health
docker inspect --format='{{json .State.Health.Status}}' google-drive-service

# Get service logs
docker-compose -f /path/to/docker-compose.yml logs --tail=100 google-drive-service

# Restart service
docker-compose -f /path/to/docker-compose.yml restart google-drive-service
