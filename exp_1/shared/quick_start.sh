#!/bin/bash

# ============================================================
# Quick Start Script - Live Stream Coupon Grabbing System
# ============================================================

set -e  # Exit immediately if a command exits with a non-zero status

echo "╔════════════════════════════════════════════════════════╗"
echo "║   Live Stream Coupon System - Quick Start Script      ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# ============================================================
# 1. Check Dependencies
# ============================================================
echo "📋 Step 1: Checking dependencies..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed. Please install Python3 first"
    exit 1
fi

echo "✅ Dependency check passed"
echo ""

# ============================================================
# 2. Install Python Dependencies
# ============================================================
echo "📦 Step 2: Installing Python dependencies..."

if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt --quiet
    echo "✅ Python dependencies installed"
else
    echo "⚠️  requirements.txt not found, skipping"
fi
echo ""

# ============================================================
# 3. Start Docker Services
# ============================================================
echo "🐳 Step 3: Starting Docker services..."

docker-compose down 2>/dev/null || true
docker-compose up -d

echo "⏳ Waiting for services to start (30 seconds)..."
sleep 30

echo "✅ Docker services started"
echo ""

# ============================================================
# 4. Check Service Status
# ============================================================
echo "🔍 Step 4: Checking service status..."

docker-compose ps

echo ""
echo "✅ All services are running"
echo ""

# ============================================================
# 5. Initialize Database
# ============================================================
echo "🗄️  Step 5: Initializing database..."

echo "Importing schema..."
docker exec -i coupon_mysql_main mysql -uroot -ppassword coupon_system < database_schema.sql

echo "✅ Database schema imported"
echo ""

# ============================================================
# 6. Generate Test Data (Optional)
# ============================================================
echo "📊 Step 6: Generate test data..."
echo "⚠️  Note: Generating 100K users may take a few minutes"
read -p "Do you want to generate test data? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 data_seeder.py
    echo "✅ Test data generation complete"
else
    echo "⏭️  Skipping data generation"
fi
echo ""

# ============================================================
# 7. Display Access Information
# ============================================================
echo "╔════════════════════════════════════════════════════════╗"
echo "║                  🎉 Setup Complete!                    ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "📍 Service Access URLs:"
echo ""
echo "  MySQL Main:       localhost:3306"
echo "  MySQL Shard 0-3:  localhost:3307-3310"
echo "  Redis:            localhost:6379"
echo "  RabbitMQ:         localhost:5672"
echo "  RabbitMQ Admin:   http://localhost:15672 (admin/admin123)"
echo "  phpMyAdmin:       http://localhost:8080"
echo "  RedisInsight:     http://localhost:8081"
echo ""
echo "🚀 Next Steps:"
echo ""
echo "  1. Start your backend service (FastAPI, Spring Boot, etc.)"
echo "  2. Run Locust load test:"
echo "     locust -f locustfile_advanced.py --host=http://localhost:8000"
echo ""
echo "  3. Access Locust WebUI:"
echo "     http://localhost:8089"
echo ""
echo "📖 For more information, see README.md"
echo ""
echo "═══════════════════════════════════════════════════════"
echo "💡 Stop services: docker-compose down"
echo "💡 View logs: docker-compose logs -f [service_name]"
echo "═══════════════════════════════════════════════════════"
