# Evo AI - Deployment Guide

This document provides detailed instructions for deploying the Evo AI platform in different environments.

## Prerequisites

- Docker and Docker Compose
- PostgreSQL database
- Redis instance
- SendGrid account for email services
- Domain name (for production deployments)
- SSL certificate (for production deployments)

## Environment Configuration

The Evo AI platform uses environment variables for configuration. Create a `.env` file based on the example below:

```
# Database Configuration
POSTGRES_CONNECTION_STRING=postgresql://username:password@postgres:5432/evo_ai
POSTGRES_USER=username
POSTGRES_PASSWORD=password
POSTGRES_DB=evo_ai

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# JWT Configuration
JWT_SECRET_KEY=your-secret-key-at-least-32-characters
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Email Configuration
SENDGRID_API_KEY=your-sendgrid-api-key
EMAIL_FROM=noreply@your-domain.com
EMAIL_FROM_NAME=Evo AI Platform

# Application Configuration
APP_URL=https://your-domain.com
ENVIRONMENT=production  # development, testing, or production
DEBUG=false
```

## Development Deployment

### Using Docker Compose

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/evo-ai.git
   cd evo-ai
   ```

2. Create a `.env` file:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. Start the development environment:
   ```bash
   make docker-up
   ```

4. Apply database migrations:
   ```bash
   make docker-migrate
   ```

5. Access the API at `http://localhost:8000`

### Local Development (without Docker)

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/evo-ai.git
   cd evo-ai
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or
   .venv\Scripts\activate  # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. Apply database migrations:
   ```bash
   make alembic-upgrade
   ```

6. Start the development server:
   ```bash
   make run
   ```

7. Access the API at `http://localhost:8000`

## Production Deployment

### Docker Swarm

1. Initialize Docker Swarm (if not already done):
   ```bash
   docker swarm init
   ```

2. Create a `.env` file for production:
   ```bash
   cp .env.example .env.prod
   # Edit .env.prod with your production configuration
   ```

3. Deploy the stack:
   ```bash
   docker stack deploy -c docker-compose.prod.yml evo-ai
   ```

4. Verify the deployment:
   ```bash
   docker stack ps evo-ai
   ```

### Kubernetes

1. Create Kubernetes configuration files:

   **postgres-deployment.yaml**:
   ```yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: postgres
   spec:
     replicas: 1
     selector:
       matchLabels:
         app: postgres
     template:
       metadata:
         labels:
           app: postgres
       spec:
         containers:
         - name: postgres
           image: postgres:13
           ports:
           - containerPort: 5432
           env:
           - name: POSTGRES_USER
             valueFrom:
               secretKeyRef:
                 name: evo-ai-secrets
                 key: POSTGRES_USER
           - name: POSTGRES_PASSWORD
             valueFrom:
               secretKeyRef:
                 name: evo-ai-secrets
                 key: POSTGRES_PASSWORD
           - name: POSTGRES_DB
             valueFrom:
               secretKeyRef:
                 name: evo-ai-secrets
                 key: POSTGRES_DB
           volumeMounts:
           - name: postgres-data
             mountPath: /var/lib/postgresql/data
         volumes:
         - name: postgres-data
           persistentVolumeClaim:
             claimName: postgres-pvc
   ```

   **redis-deployment.yaml**:
   ```yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: redis
   spec:
     replicas: 1
     selector:
       matchLabels:
         app: redis
     template:
       metadata:
         labels:
           app: redis
       spec:
         containers:
         - name: redis
           image: redis:6
           ports:
           - containerPort: 6379
           volumeMounts:
           - name: redis-data
             mountPath: /data
         volumes:
         - name: redis-data
           persistentVolumeClaim:
             claimName: redis-pvc
   ```

   **api-deployment.yaml**:
   ```yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: evo-ai-api
   spec:
     replicas: 3
     selector:
       matchLabels:
         app: evo-ai-api
     template:
       metadata:
         labels:
           app: evo-ai-api
       spec:
         containers:
         - name: evo-ai-api
           image: your-registry/evo-ai-api:latest
           ports:
           - containerPort: 8000
           envFrom:
           - secretRef:
               name: evo-ai-secrets
           - configMapRef:
               name: evo-ai-config
           readinessProbe:
             httpGet:
               path: /api/v1/health
               port: 8000
             initialDelaySeconds: 5
             periodSeconds: 10
           livenessProbe:
             httpGet:
               path: /api/v1/health
               port: 8000
             initialDelaySeconds: 15
             periodSeconds: 20
   ```

2. Create Kubernetes secrets:
   ```bash
   kubectl create secret generic evo-ai-secrets \
     --from-literal=POSTGRES_USER=username \
     --from-literal=POSTGRES_PASSWORD=password \
     --from-literal=POSTGRES_DB=evo_ai \
     --from-literal=JWT_SECRET_KEY=your-secret-key \
     --from-literal=SENDGRID_API_KEY=your-sendgrid-api-key
   ```

3. Create ConfigMap:
   ```bash
   kubectl create configmap evo-ai-config \
     --from-literal=POSTGRES_CONNECTION_STRING=postgresql://username:password@postgres:5432/evo_ai \
     --from-literal=REDIS_HOST=redis \
     --from-literal=REDIS_PORT=6379 \
     --from-literal=JWT_ALGORITHM=HS256 \
     --from-literal=JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30 \
     --from-literal=EMAIL_FROM=noreply@your-domain.com \
     --from-literal=EMAIL_FROM_NAME="Evo AI Platform" \
     --from-literal=APP_URL=https://your-domain.com \
     --from-literal=ENVIRONMENT=production \
     --from-literal=DEBUG=false
   ```

4. Apply the configurations:
   ```bash
   kubectl apply -f postgres-deployment.yaml
   kubectl apply -f redis-deployment.yaml
   kubectl apply -f api-deployment.yaml
   ```

5. Create services:
   ```bash
   kubectl expose deployment postgres --port=5432 --type=ClusterIP
   kubectl expose deployment redis --port=6379 --type=ClusterIP
   kubectl expose deployment evo-ai-api --port=80 --target-port=8000 --type=LoadBalancer
   ```

## Scaling Considerations

### Database Scaling

For production environments with high load, consider:

1. **PostgreSQL Replication**:
   - Set up a master-slave replication
   - Use read replicas for read-heavy operations
   - Consider using a managed PostgreSQL service (AWS RDS, Azure Database, etc.)

2. **Redis Cluster**:
   - Implement Redis Sentinel for high availability
   - Use Redis Cluster for horizontal scaling
   - Consider using a managed Redis service (AWS ElastiCache, Azure Cache, etc.)

### API Scaling

1. **Horizontal Scaling**:
   - Increase the number of API containers/pods
   - Use a load balancer to distribute traffic

2. **Vertical Scaling**:
   - Increase resources (CPU, memory) for API containers

3. **Caching Strategy**:
   - Implement response caching for frequent requests
   - Use Redis for distributed caching

## Monitoring and Logging

### Monitoring

1. **Prometheus and Grafana**:
   - Set up Prometheus for metrics collection
   - Configure Grafana dashboards for visualization
   - Monitor API response times, error rates, and system resources

2. **Health Checks**:
   - Use the `/api/v1/health` endpoint to check system health
   - Set up alerts for when services are down

### Logging

1. **Centralized Logging**:
   - Configure ELK Stack (Elasticsearch, Logstash, Kibana)
   - Or use a managed logging service (AWS CloudWatch, Datadog, etc.)

2. **Log Levels**:
   - In production, set log level to INFO or WARNING
   - In development, set log level to DEBUG for more details

## Backup and Recovery

1. **Database Backups**:
   - Schedule regular PostgreSQL backups
   - Store backups in a secure location (e.g., AWS S3, Azure Blob Storage)
   - Test restoration procedures regularly

2. **Application State**:
   - Store configuration in version control
   - Document environment setup and dependencies

## SSL Configuration

For production deployments, SSL is required:

1. **Using Nginx**:
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       return 301 https://$host$request_uri;
   }

   server {
       listen 443 ssl;
       server_name your-domain.com;

       ssl_certificate /path/to/certificate.crt;
       ssl_certificate_key /path/to/private.key;

       ssl_protocols TLSv1.2 TLSv1.3;
       ssl_ciphers HIGH:!aNULL:!MD5;

       location / {
           proxy_pass http://evo-ai-api:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

2. **Using Let's Encrypt and Certbot**:
   ```bash
   certbot --nginx -d your-domain.com
   ```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**:
   - Check PostgreSQL connection string
   - Verify network connectivity between API and database
   - Check database credentials

2. **Redis Connection Issues**:
   - Verify Redis host and port
   - Check network connectivity to Redis
   - Ensure Redis service is running

3. **Email Sending Failures**:
   - Verify SendGrid API key
   - Check email templates
   - Test email sending with SendGrid debugging tools

### Debugging

1. **Container Logs**:
   ```bash
   # Docker
   docker logs <container_id>

   # Kubernetes
   kubectl logs <pod_name>
   ```

2. **API Logs**:
   - Check `/logs` directory
   - Set DEBUG=true in development to get more detailed logs

3. **Database Connection Testing**:
   ```bash
   psql postgresql://username:password@postgres:5432/evo_ai
   ```

4. **Health Check**:
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

## Security Considerations

1. **API Security**:
   - Keep JWT_SECRET_KEY secure and random
   - Rotate JWT secrets periodically
   - Set appropriate token expiration times

2. **Network Security**:
   - Use internal networks for database and Redis
   - Expose only the API through a load balancer
   - Implement a Web Application Firewall (WAF)

3. **Data Protection**:
   - Encrypt sensitive data in database
   - Implement proper access controls
   - Regularly audit system access

## Continuous Integration/Deployment

### GitHub Actions Example

```yaml
name: Deploy Evo AI

on:
  push:
    branches: [ main ]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest
    
    - name: Run tests
      run: |
        pytest
    
    - name: Build Docker image
      run: |
        docker build -t your-registry/evo-ai-api:latest .
    
    - name: Push to registry
      run: |
        echo "${{ secrets.DOCKER_PASSWORD }}" | docker login -u "${{ secrets.DOCKER_USERNAME }}" --password-stdin
        docker push your-registry/evo-ai-api:latest
    
    - name: Deploy to production
      run: |
        # Deployment commands depending on your environment
        # For example, if using Kubernetes:
        kubectl set image deployment/evo-ai-api evo-ai-api=your-registry/evo-ai-api:latest
```

## Conclusion

This deployment guide covers the basics of deploying the Evo AI platform in different environments. For specific needs or custom deployments, additional configuration may be required. Always follow security best practices and ensure proper monitoring and backup procedures are in place. 