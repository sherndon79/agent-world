#!/bin/bash
# Start persistent MCP servers with Docker Compose

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting Persistent MCP Servers"
echo "=================================="

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "   Copy .env.example to .env and configure your credentials"
    exit 1
fi

# Build and start services
echo "🏗️ Building MCP server containers..."
docker-compose build

echo "🚀 Starting MCP server services..."
docker-compose up -d

echo ""
echo "✅ MCP servers started successfully!"
echo ""
echo "📋 View running containers:"
echo "   docker-compose ps"
echo ""
echo "📺 View logs:"
echo "   docker-compose logs -f"
echo ""
echo "🛑 Stop servers:"
echo "   docker-compose down"