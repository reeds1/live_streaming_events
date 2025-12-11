terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# VPC Configuration
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "hash-vs-range-vpc"
    Project = "CS6650-Sharding-Comparison"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "hash-vs-range-igw"
  }
}

# Subnets (2 AZs for RDS requirement)
resource "aws_subnet" "public_1" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "public-subnet-1"
  }
}

resource "aws_subnet" "public_2" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "${var.aws_region}b"
  map_public_ip_on_launch = true

  tags = {
    Name = "public-subnet-2"
  }
}

# Route Table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "public-route-table"
  }
}

resource "aws_route_table_association" "public_1" {
  subnet_id      = aws_subnet.public_1.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_2" {
  subnet_id      = aws_subnet.public_2.id
  route_table_id = aws_route_table.public.id
}

# Security Group for RDS
resource "aws_security_group" "rds" {
  name        = "hash-vs-range-rds-sg"
  description = "Security group for RDS MySQL instances"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 3306
    to_port     = 3306
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # For testing only! Restrict in production
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "rds-security-group"
  }
}

# DB Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "hash-vs-range-db-subnet"
  subnet_ids = [aws_subnet.public_1.id, aws_subnet.public_2.id]

  tags = {
    Name = "DB subnet group"
  }
}

# RDS MySQL Instances (4 shards)
resource "aws_db_instance" "shard_0" {
  identifier           = "hash-range-shard-0"
  engine               = "mysql"
  engine_version       = "8.0"
  instance_class       = var.db_instance_class
  allocated_storage    = 20
  storage_type         = "gp3"
  
  db_name  = "coupon_db_0"
  username = var.db_username
  password = var.db_password
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  
  publicly_accessible    = true
  skip_final_snapshot    = true
  
  backup_retention_period = 0
  
  tags = {
    Name = "Shard 0"
    ShardId = "0"
  }
}

resource "aws_db_instance" "shard_1" {
  identifier           = "hash-range-shard-1"
  engine               = "mysql"
  engine_version       = "8.0"
  instance_class       = var.db_instance_class
  allocated_storage    = 20
  storage_type         = "gp3"
  
  db_name  = "coupon_db_1"
  username = var.db_username
  password = var.db_password
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  
  publicly_accessible    = true
  skip_final_snapshot    = true
  
  backup_retention_period = 0
  
  tags = {
    Name = "Shard 1"
    ShardId = "1"
  }
}

resource "aws_db_instance" "shard_2" {
  identifier           = "hash-range-shard-2"
  engine               = "mysql"
  engine_version       = "8.0"
  instance_class       = var.db_instance_class
  allocated_storage    = 20
  storage_type         = "gp3"
  
  db_name  = "coupon_db_2"
  username = var.db_username
  password = var.db_password
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  
  publicly_accessible    = true
  skip_final_snapshot    = true
  
  backup_retention_period = 0
  
  tags = {
    Name = "Shard 2"
    ShardId = "2"
  }
}

resource "aws_db_instance" "shard_3" {
  identifier           = "hash-range-shard-3"
  engine               = "mysql"
  engine_version       = "8.0"
  instance_class       = var.db_instance_class
  allocated_storage    = 20
  storage_type         = "gp3"
  
  db_name  = "coupon_db_3"
  username = var.db_username
  password = var.db_password
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  
  publicly_accessible    = true
  skip_final_snapshot    = true
  
  backup_retention_period = 0
  
  tags = {
    Name = "Shard 3"
    ShardId = "3"
  }
}

