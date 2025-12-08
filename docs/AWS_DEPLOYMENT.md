# AWS Deployment Guide

This guide covers deploying the Terminal application to AWS for production use.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                   AWS Cloud                                      │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                              VPC (10.0.0.0/16)                             │  │
│  │  ┌─────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                     Public Subnets (10.0.1.0/24, 10.0.2.0/24)       │  │  │
│  │  │  ┌─────────────────────────────────────────────────────────────┐   │  │  │
│  │  │  │                  Application Load Balancer                   │   │  │  │
│  │  │  │              (HTTPS + WebSocket, Sticky Sessions)            │   │  │  │
│  │  │  └─────────────────────────────────────────────────────────────┘   │  │  │
│  │  └─────────────────────────────────────────────────────────────────────┘  │  │
│  │                                    │                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                   Private Subnets (10.0.3.0/24, 10.0.4.0/24)        │  │  │
│  │  │  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐   │  │  │
│  │  │  │  ECS Cluster     │  │  EC2 Auto Scaling│  │  ElastiCache    │   │  │  │
│  │  │  │  (API Service)   │  │  (TN3270 Gateway)│  │  (Valkey)       │   │  │  │
│  │  │  │  - Fargate OK    │  │  - EC2 Required  │  │  - Redis Mode   │   │  │  │
│  │  │  └──────────────────┘  └──────────────────┘  └─────────────────┘   │  │  │
│  │  └─────────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────────┐   │
│  │    DynamoDB      │  │  S3 + CloudFront │  │  Route 53                    │   │
│  │   (On-Demand)    │  │  (Static Assets) │  │  (DNS)                       │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       │ Direct Connect / VPN
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              On-Premises / Mainframe                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                           IBM z/OS Mainframe                             │    │
│  │                           (TN3270 Host)                                  │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Why Not Fargate for TN3270 Gateway?

AWS Fargate is a serverless container platform that abstracts server management. However, the **TN3270 Gateway cannot run on Fargate** due to:

1. **Long-running TCP connections**: TN3270 sessions maintain persistent TCP connections to mainframes that can last hours or days. Fargate has task timeout limits.

2. **Network requirements**: TN3270 connections to mainframes often require:
   - Direct Connect or VPN access to on-premises networks
   - Specific IP addresses for firewall whitelisting
   - Custom network configurations

3. **Session affinity**: Each gateway instance manages multiple TN3270 sessions in-memory. Sessions cannot be easily migrated between containers.

4. **Resource patterns**: TN3270 sessions have unpredictable I/O patterns that don't fit Fargate's scaling model well.

**Solution**: Run the TN3270 Gateway on **EC2 instances** with Auto Scaling Groups.

## Component Deployment Strategy

| Component | Deployment Target | Scaling | Notes |
|-----------|------------------|---------|-------|
| Web Frontend | S3 + CloudFront | CDN scales automatically | Static assets |
| API Server | ECS Fargate or EC2 | Horizontal (task count) | Stateless, Fargate OK |
| TN3270 Gateway | EC2 Auto Scaling | Horizontal (instance count) | **Must be EC2** |
| Message Broker | ElastiCache (Redis) | Vertical + Read Replicas | Managed service |
| Database | DynamoDB | On-Demand | Managed, auto-scales |

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI configured
- Docker installed locally
- Domain name (for HTTPS)
- Direct Connect or VPN to mainframe network (if on-premises)

## Step 1: Network Setup (VPC)

### Create VPC with Public and Private Subnets

```bash
# Create VPC
aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=terminal-vpc}]'

# Note the VPC ID from output
export VPC_ID=vpc-xxxxxxxxx
```

### Create Subnets

```bash
# Public Subnets (for ALB)
aws ec2 create-subnet \
  --vpc-id $VPC_ID \
  --cidr-block 10.0.1.0/24 \
  --availability-zone us-east-1a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=terminal-public-1a}]'

aws ec2 create-subnet \
  --vpc-id $VPC_ID \
  --cidr-block 10.0.2.0/24 \
  --availability-zone us-east-1b \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=terminal-public-1b}]'

# Private Subnets (for API, Gateway, ElastiCache)
aws ec2 create-subnet \
  --vpc-id $VPC_ID \
  --cidr-block 10.0.3.0/24 \
  --availability-zone us-east-1a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=terminal-private-1a}]'

aws ec2 create-subnet \
  --vpc-id $VPC_ID \
  --cidr-block 10.0.4.0/24 \
  --availability-zone us-east-1b \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=terminal-private-1b}]'
```

### Internet Gateway and NAT Gateway

```bash
# Internet Gateway (for public subnets)
aws ec2 create-internet-gateway \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=terminal-igw}]'

aws ec2 attach-internet-gateway \
  --internet-gateway-id igw-xxxxxxxxx \
  --vpc-id $VPC_ID

# NAT Gateway (for private subnets to access internet)
# First, allocate an Elastic IP
aws ec2 allocate-address --domain vpc

# Then create NAT Gateway in public subnet
aws ec2 create-nat-gateway \
  --subnet-id subnet-public-1a \
  --allocation-id eipalloc-xxxxxxxxx
```

## Step 2: ElastiCache (Valkey/Redis)

```bash
# Create subnet group
aws elasticache create-cache-subnet-group \
  --cache-subnet-group-name terminal-cache-subnet \
  --cache-subnet-group-description "Terminal app cache subnets" \
  --subnet-ids subnet-private-1a subnet-private-1b

# Create Redis cluster (Valkey compatible)
aws elasticache create-cache-cluster \
  --cache-cluster-id terminal-cache \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --engine-version 7.0 \
  --num-cache-nodes 1 \
  --cache-subnet-group-name terminal-cache-subnet \
  --security-group-ids sg-xxxxxxxxx
```

For production, consider:

- `cache.r6g.large` or larger for production workloads
- Multi-AZ with automatic failover
- Redis cluster mode for horizontal scaling

## Step 3: DynamoDB Tables

```bash
# Users Table
aws dynamodb create-table \
  --table-name Users \
  --attribute-definitions \
    AttributeName=id,AttributeType=S \
    AttributeName=email,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --global-secondary-indexes \
    '[{"IndexName":"email-index","KeySchema":[{"AttributeName":"email","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"}}]' \
  --billing-mode PAY_PER_REQUEST

# Sessions Table
aws dynamodb create-table \
  --table-name Sessions \
  --attribute-definitions \
    AttributeName=id,AttributeType=S \
    AttributeName=userId,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --global-secondary-indexes \
    '[{"IndexName":"userId-index","KeySchema":[{"AttributeName":"userId","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"}}]' \
  --billing-mode PAY_PER_REQUEST

# Executions Table
aws dynamodb create-table \
  --table-name Executions \
  --attribute-definitions \
    AttributeName=execution_id,AttributeType=S \
    AttributeName=user_id,AttributeType=S \
    AttributeName=date,AttributeType=S \
  --key-schema AttributeName=execution_id,KeyType=HASH \
  --global-secondary-indexes \
    '[{"IndexName":"user-date-index","KeySchema":[{"AttributeName":"user_id","KeyType":"HASH"},{"AttributeName":"date","KeyType":"RANGE"}],"Projection":{"ProjectionType":"ALL"}}]' \
  --billing-mode PAY_PER_REQUEST

# Policies Table
aws dynamodb create-table \
  --table-name Policies \
  --attribute-definitions \
    AttributeName=execution_id,AttributeType=S \
    AttributeName=policy_number,AttributeType=S \
  --key-schema \
    AttributeName=execution_id,KeyType=HASH \
    AttributeName=policy_number,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST
```

## Step 4: ECR Repositories

```bash
# Create repositories for Docker images
aws ecr create-repository --repository-name terminal/api
aws ecr create-repository --repository-name terminal/gateway
```

## Step 5: Build and Push Docker Images

### API Server Dockerfile

Create `apps/api/Dockerfile`:

```dockerfile
FROM node:24-alpine AS builder

WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY packages/shared ./packages/shared
COPY apps/api ./apps/api

RUN npm install -g pnpm
RUN pnpm install --frozen-lockfile
RUN pnpm --filter @terminal/api build

FROM node:24-alpine AS runner

WORKDIR /app
COPY --from=builder /app/apps/api/dist ./dist
COPY --from=builder /app/apps/api/package.json ./
COPY --from=builder /app/node_modules ./node_modules

ENV NODE_ENV=production
EXPOSE 3001

CMD ["node", "dist/index.js"]
```

### Gateway Dockerfile

Create `gateway/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen

# Copy application
COPY src ./src

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "python", "-m", "src.app"]
```

### Build and Push

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build and push API
docker build -t terminal/api -f apps/api/Dockerfile .
docker tag terminal/api:latest $AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/terminal/api:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/terminal/api:latest

# Build and push Gateway
docker build -t terminal/gateway -f gateway/Dockerfile ./gateway
docker tag terminal/gateway:latest $AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/terminal/gateway:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/terminal/gateway:latest
```

## Step 6: ECS Cluster for API Server

The API server is stateless and can run on Fargate:

### Task Definition

```json
{
  "family": "terminal-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/terminal-api-task-role",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/terminal/api:latest",
      "portMappings": [
        {
          "containerPort": 3001,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "NODE_ENV", "value": "production"},
        {"name": "PORT", "value": "3001"},
        {"name": "VALKEY_HOST", "value": "terminal-cache.xxxxx.cache.amazonaws.com"},
        {"name": "VALKEY_PORT", "value": "6379"},
        {"name": "DYNAMODB_REGION", "value": "us-east-1"},
        {"name": "JWT_SECRET", "value": "FROM_SECRETS_MANAGER"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/terminal-api",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "api"
        }
      }
    }
  ]
}
```

### Create Service

```bash
aws ecs create-service \
  --cluster terminal-cluster \
  --service-name terminal-api \
  --task-definition terminal-api:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-private-1a,subnet-private-1b],securityGroups=[sg-api],assignPublicIp=DISABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=api,containerPort=3001"
```

## Step 7: EC2 Auto Scaling for TN3270 Gateway

The Gateway **must run on EC2** due to long-running TN3270 connections.

### Launch Template

```bash
aws ec2 create-launch-template \
  --launch-template-name terminal-gateway-template \
  --version-description "TN3270 Gateway v1" \
  --launch-template-data '{
    "ImageId": "ami-xxxxxxxxx",
    "InstanceType": "t3.medium",
    "IamInstanceProfile": {
      "Arn": "arn:aws:iam::ACCOUNT:instance-profile/terminal-gateway-role"
    },
    "NetworkInterfaces": [{
      "DeviceIndex": 0,
      "AssociatePublicIpAddress": false,
      "Groups": ["sg-gateway"],
      "SubnetId": "subnet-private-1a"
    }],
    "UserData": "BASE64_ENCODED_STARTUP_SCRIPT",
    "TagSpecifications": [{
      "ResourceType": "instance",
      "Tags": [{"Key": "Name", "Value": "terminal-gateway"}]
    }]
  }'
```

### User Data Script

```bash
#!/bin/bash
yum update -y
yum install -y docker
systemctl start docker
systemctl enable docker

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT.dkr.ecr.us-east-1.amazonaws.com

# Pull and run gateway
docker pull ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/terminal/gateway:latest
docker run -d \
  --name gateway \
  --restart always \
  -e VALKEY_HOST=terminal-cache.xxxxx.cache.amazonaws.com \
  -e VALKEY_PORT=6379 \
  -e DYNAMODB_REGION=us-east-1 \
  -e TN3270_HOST=mainframe.internal \
  -e TN3270_PORT=3270 \
  -e MAX_SESSIONS=10 \
  ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/terminal/gateway:latest
```

### Auto Scaling Group

```bash
aws autoscaling create-auto-scaling-group \
  --auto-scaling-group-name terminal-gateway-asg \
  --launch-template LaunchTemplateName=terminal-gateway-template,Version='$Latest' \
  --min-size 1 \
  --max-size 10 \
  --desired-capacity 2 \
  --vpc-zone-identifier "subnet-private-1a,subnet-private-1b" \
  --health-check-type EC2 \
  --health-check-grace-period 300 \
  --tags Key=Name,Value=terminal-gateway,PropagateAtLaunch=true
```

### Scaling Policy

```bash
# Scale based on active sessions (custom metric)
aws autoscaling put-scaling-policy \
  --auto-scaling-group-name terminal-gateway-asg \
  --policy-name scale-on-sessions \
  --policy-type TargetTrackingScaling \
  --target-tracking-configuration '{
    "CustomizedMetricSpecification": {
      "MetricName": "ActiveSessions",
      "Namespace": "Terminal/Gateway",
      "Statistic": "Average",
      "Unit": "Count"
    },
    "TargetValue": 8.0
  }'
```

## Step 8: Application Load Balancer

```bash
# Create ALB
aws elbv2 create-load-balancer \
  --name terminal-alb \
  --subnets subnet-public-1a subnet-public-1b \
  --security-groups sg-alb \
  --scheme internet-facing \
  --type application

# Create target group for API
aws elbv2 create-target-group \
  --name terminal-api-tg \
  --protocol HTTP \
  --port 3001 \
  --vpc-id $VPC_ID \
  --target-type ip \
  --health-check-path /health \
  --health-check-interval-seconds 30

# Create listener
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:... \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=arn:aws:acm:... \
  --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:...

# Enable sticky sessions for WebSocket
aws elbv2 modify-target-group-attributes \
  --target-group-arn arn:aws:elasticloadbalancing:... \
  --attributes Key=stickiness.enabled,Value=true Key=stickiness.type,Value=lb_cookie Key=stickiness.lb_cookie.duration_seconds,Value=86400
```

## Step 9: Static Assets (S3 + CloudFront)

```bash
# Create S3 bucket
aws s3 mb s3://terminal-web-assets

# Build frontend
cd apps/web
pnpm build

# Upload to S3
aws s3 sync dist/ s3://terminal-web-assets/ --delete

# Create CloudFront distribution
aws cloudfront create-distribution \
  --origin-domain-name terminal-web-assets.s3.amazonaws.com \
  --default-root-object index.html
```

## Step 10: Security Groups

### ALB Security Group

```bash
aws ec2 create-security-group \
  --group-name terminal-alb-sg \
  --description "Terminal ALB" \
  --vpc-id $VPC_ID

# Allow HTTPS from anywhere
aws ec2 authorize-security-group-ingress \
  --group-id sg-alb \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0
```

### API Security Group

```bash
aws ec2 create-security-group \
  --group-name terminal-api-sg \
  --description "Terminal API" \
  --vpc-id $VPC_ID

# Allow from ALB only
aws ec2 authorize-security-group-ingress \
  --group-id sg-api \
  --protocol tcp \
  --port 3001 \
  --source-group sg-alb
```

### Gateway Security Group

```bash
aws ec2 create-security-group \
  --group-name terminal-gateway-sg \
  --description "Terminal Gateway" \
  --vpc-id $VPC_ID

# Allow from ElastiCache (Valkey pub/sub)
# No inbound rules needed - gateway subscribes to Valkey

# Allow outbound to mainframe (TN3270)
aws ec2 authorize-security-group-egress \
  --group-id sg-gateway \
  --protocol tcp \
  --port 3270 \
  --cidr 10.100.0.0/16  # Mainframe network
```

### ElastiCache Security Group

```bash
aws ec2 create-security-group \
  --group-name terminal-cache-sg \
  --description "Terminal ElastiCache" \
  --vpc-id $VPC_ID

# Allow from API and Gateway
aws ec2 authorize-security-group-ingress \
  --group-id sg-cache \
  --protocol tcp \
  --port 6379 \
  --source-group sg-api

aws ec2 authorize-security-group-ingress \
  --group-id sg-cache \
  --protocol tcp \
  --port 6379 \
  --source-group sg-gateway
```

## Step 11: IAM Roles

### API Task Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:ACCOUNT:table/Users",
        "arn:aws:dynamodb:us-east-1:ACCOUNT:table/Users/index/*",
        "arn:aws:dynamodb:us-east-1:ACCOUNT:table/Sessions",
        "arn:aws:dynamodb:us-east-1:ACCOUNT:table/Sessions/index/*",
        "arn:aws:dynamodb:us-east-1:ACCOUNT:table/Executions",
        "arn:aws:dynamodb:us-east-1:ACCOUNT:table/Executions/index/*",
        "arn:aws:dynamodb:us-east-1:ACCOUNT:table/Policies"
      ]
    }
  ]
}
```

### Gateway Instance Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:ACCOUNT:table/Executions",
        "arn:aws:dynamodb:us-east-1:ACCOUNT:table/Policies"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*"
    }
  ]
}
```

## Step 12: Monitoring and Logging

### CloudWatch Alarms

```bash
# API high latency
aws cloudwatch put-metric-alarm \
  --alarm-name terminal-api-latency \
  --metric-name TargetResponseTime \
  --namespace AWS/ApplicationELB \
  --statistic Average \
  --period 60 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 3

# Gateway unhealthy instances
aws cloudwatch put-metric-alarm \
  --alarm-name terminal-gateway-unhealthy \
  --metric-name UnHealthyHostCount \
  --namespace AWS/AutoScaling \
  --statistic Average \
  --period 60 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 2
```

### Custom Metrics from Gateway

The gateway should publish custom metrics:

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

def publish_session_count(count: int):
    cloudwatch.put_metric_data(
        Namespace='Terminal/Gateway',
        MetricData=[{
            'MetricName': 'ActiveSessions',
            'Value': count,
            'Unit': 'Count'
        }]
    )
```

## Scaling Considerations

### Horizontal Scaling

| Component | Scaling Trigger | Target |
|-----------|-----------------|--------|
| API (Fargate) | CPU > 70% | Add tasks |
| Gateway (EC2) | Sessions > 8 per instance | Add instances |
| ElastiCache | Memory > 80% | Upgrade node type |

### Capacity Planning

| Sessions | API Tasks | Gateway Instances | ElastiCache |
|----------|-----------|-------------------|-------------|
| 1-50 | 2 | 2 | cache.t3.micro |
| 50-200 | 4 | 4-6 | cache.t3.small |
| 200-500 | 6-8 | 10-15 | cache.r6g.large |
| 500+ | Auto-scale | Auto-scale | Cluster mode |

### Gateway Session Limits

Each gateway instance should handle a limited number of sessions:

- **t3.medium**: ~10 concurrent sessions
- **t3.large**: ~20 concurrent sessions
- **c6i.xlarge**: ~50 concurrent sessions

Configure `MAX_SESSIONS` environment variable accordingly.

## Disaster Recovery

### Multi-AZ Deployment

- ALB spans multiple AZs
- ECS tasks distributed across AZs
- EC2 Auto Scaling Group spans multiple AZs
- ElastiCache Multi-AZ for automatic failover

### Backup Strategy

- DynamoDB: Point-in-time recovery enabled
- No persistent data in Gateway (sessions are ephemeral)
- Infrastructure as Code (CloudFormation/Terraform)

## Cost Optimization

### Reserved Capacity

For predictable workloads:

- EC2 Reserved Instances for gateway
- ElastiCache Reserved Nodes
- DynamoDB Reserved Capacity

### Spot Instances

Gateway can use Spot Instances with proper handling:

- Graceful shutdown on Spot interruption
- Session migration (future enhancement)

## Checklist

- [ ] VPC with public/private subnets
- [ ] Internet Gateway and NAT Gateway
- [ ] ElastiCache (Redis/Valkey) cluster
- [ ] DynamoDB tables created
- [ ] ECR repositories created
- [ ] Docker images built and pushed
- [ ] ECS cluster and API service
- [ ] EC2 Launch Template for Gateway
- [ ] Auto Scaling Group for Gateway
- [ ] Application Load Balancer
- [ ] SSL certificate in ACM
- [ ] S3 bucket and CloudFront for static assets
- [ ] Security groups configured
- [ ] IAM roles created
- [ ] CloudWatch alarms set up
- [ ] Direct Connect / VPN to mainframe (if required)



