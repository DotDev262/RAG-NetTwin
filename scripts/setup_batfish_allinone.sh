#!/bin/bash
# Setup Batfish Allinone with Podman (Rootless)

echo "🚀 Setting up Batfish Allinone..."

# Stop and remove old containers
echo "🧹 Cleaning up old containers..."
podman stop batfish 2>/dev/null
podman rm batfish 2>/dev/null

# Pull the image
echo "📥 Pulling batfish/allinone image..."
podman pull docker.io/batfish/allinone:latest

# Run the container
echo "🏃 Starting Batfish container..."
podman run -d \
  --name batfish \
  -v batfish-data:/data \
  -p 8888:8888 \
  -p 9996:9996 \
  docker.io/batfish/allinone:latest

echo "⏳ Waiting for Batfish to initialize (60 seconds)..."
sleep 60

echo "🧪 Testing connection..."
if curl -s http://localhost:8888 > /dev/null 2>&1; then
    echo "✅ Batfish Allinone is running!"
    echo ""
    echo "📊 Status:"
    podman ps | grep batfish
    echo ""
    echo "🌐 Access URLs:"
    echo "  - API: http://localhost:8888"
    echo "  - Alternative: http://127.0.0.1:8888"
    echo ""
    echo "⚙️  Update your .env file:"
    echo "  BATFISH_HOST=localhost"
    echo "  BATFISH_PORT=8888"
else
    echo "⏳ Still starting up..."
    echo "📋 Current status:"
    podman ps | grep batfish
    echo ""
    echo "📜 Recent logs:"
    podman logs batfish --tail 20
    echo ""
    echo "💡 Wait another 30-60 seconds and test:"
    echo "  curl http://localhost:8888"
fi
