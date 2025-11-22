#!/bin/bash
#
# Quick Setup Script for Creating New AOL Service
# Usage: ./create-service.sh my-new-service [service-type]
# Service types: Agent, Tool, Plugin, Service (default: Service)

set -e

# Check if service name provided
if [ -z "$1" ]; then
    echo "Usage: ./create-service.sh <service-name> [service-type]"
    echo "Example: ./create-service.sh text-analyzer Agent"
    echo "Service types: Agent, Tool, Plugin, Service (default: Service)"
    exit 1
fi

SERVICE_NAME=$1
SERVICE_TYPE=${2:-Service}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="../app/$SERVICE_NAME"

echo "🚀 Creating new AOL service: $SERVICE_NAME (type: $SERVICE_TYPE)"
echo ""

# Check if target already exists
if [ -d "$TARGET_DIR" ]; then
    echo "❌ Error: Directory $TARGET_DIR already exists!"
    exit 1
fi

# Create service directory structure
echo "📁 Creating directory structure: $TARGET_DIR"
mkdir -p "$TARGET_DIR/service"
mkdir -p "$TARGET_DIR/utils"
mkdir -p "$TARGET_DIR/sidecar"
mkdir -p "$TARGET_DIR/proto"
mkdir -p "$TARGET_DIR/examples"

# Copy template files
echo "📋 Copying template files..."
cp -r "$SCRIPT_DIR/service/"* "$TARGET_DIR/service/"
cp -r "$SCRIPT_DIR/utils/"* "$TARGET_DIR/utils/"
cp -r "$SCRIPT_DIR/sidecar/"* "$TARGET_DIR/sidecar/"
cp -r "$SCRIPT_DIR/proto/"* "$TARGET_DIR/proto/"
cp "$SCRIPT_DIR/requirements.txt" "$TARGET_DIR/"
cp "$SCRIPT_DIR/Dockerfile" "$TARGET_DIR/"

# Copy manifest (user can choose with-data or basic)
read -p "Does this service need data storage? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    cp "$SCRIPT_DIR/manifest-with-data.yaml" "$TARGET_DIR/manifest.yaml"
    cp "$SCRIPT_DIR/config-with-data.yaml" "$TARGET_DIR/config.yaml"
    echo "✅ Using manifest with data storage"
else
    cp "$SCRIPT_DIR/manifest.yaml" "$TARGET_DIR/manifest.yaml"
    cp "$SCRIPT_DIR/config.yaml" "$TARGET_DIR/config.yaml"
    echo "✅ Using basic manifest"
fi

# Suggest port numbers
echo ""
echo "📝 Suggested port allocation:"
echo "   gRPC Port: 500XX (pick from 50051-50099)"
echo "   Health Port: 502XX (pick from 50200-50299)"
echo "   Metrics Port: 80XX (pick from 8080-8099)"
echo ""

# Customize manifest
read -p "Enter gRPC port (default: 50070): " GRPC_PORT
GRPC_PORT=${GRPC_PORT:-50070}

read -p "Enter health port (default: 50220): " HEALTH_PORT
HEALTH_PORT=${HEALTH_PORT:-50220}

read -p "Enter metrics port (default: 8095): " METRICS_PORT
METRICS_PORT=${METRICS_PORT:-8095}

# Update files
echo "✏️  Customizing configuration..."

# Determine kind based on service type
case "$SERVICE_TYPE" in
    Agent|agent|AGENT)
        SERVICE_KIND="AOLAgent"
        ;;
    Tool|tool|TOOL)
        SERVICE_KIND="AOLTool"
        ;;
    Plugin|plugin|PLUGIN)
        SERVICE_KIND="AOLPlugin"
        ;;
    *)
        SERVICE_KIND="AOLService"
        ;;
esac

# Update manifest.yaml
sed -i.bak "s/kind: \"AOLService\"/kind: \"$SERVICE_KIND\"/g" "$TARGET_DIR/manifest.yaml"
sed -i.bak "s/name: \"aol-service\"/name: \"$SERVICE_NAME\"/g" "$TARGET_DIR/manifest.yaml"
sed -i.bak "s/name: \"example-service\"/name: \"$SERVICE_NAME\"/g" "$TARGET_DIR/manifest.yaml"
sed -i.bak "s/50050/$GRPC_PORT/g" "$TARGET_DIR/manifest.yaml"
sed -i.bak "s/50200/$HEALTH_PORT/g" "$TARGET_DIR/manifest.yaml"
sed -i.bak "s/8080/$METRICS_PORT/g" "$TARGET_DIR/manifest.yaml"
sed -i.bak "s/50060/$GRPC_PORT/g" "$TARGET_DIR/manifest.yaml"
sed -i.bak "s/50210/$HEALTH_PORT/g" "$TARGET_DIR/manifest.yaml"
sed -i.bak "s/8090/$METRICS_PORT/g" "$TARGET_DIR/manifest.yaml"

# Update config.yaml (if it has service name references)
sed -i.bak "s/aol-service/$SERVICE_NAME/g" "$TARGET_DIR/config.yaml" 2>/dev/null || true

# Clean up backup files
rm "$TARGET_DIR"/*.bak

echo ""
echo "✅ Service created successfully!"
echo ""
echo "📁 Service location: $TARGET_DIR"
echo ""
echo "Next steps:"
echo "1. Edit $TARGET_DIR/service/main.py and implement your Process() method"
echo "   - For Agents: Implement Think() logic"
echo "   - For Tools: Implement Execute() logic"
echo "   - For Plugins: Implement Handle() logic"
echo "   - For Services: Implement Process() logic"
echo "2. Add service to docker-compose.yml:"
echo ""
echo "  $SERVICE_NAME:"
echo "    build:"
echo "      context: ."
echo "      dockerfile: ./$SERVICE_NAME/Dockerfile"
echo "    container_name: $SERVICE_NAME"
echo "    hostname: $SERVICE_NAME"
echo "    ports:"
echo "      - \"$GRPC_PORT:$GRPC_PORT\""
echo "      - \"$HEALTH_PORT:$HEALTH_PORT\""
echo "      - \"$METRICS_PORT:$METRICS_PORT\""
echo "    networks:"
echo "      - heart-pulse-network"
echo "    depends_on:"
echo "      - consul-server"
echo "      - aol-core"
echo ""
echo "3. Build and run:"
echo "   cd app"
echo "   docker-compose build $SERVICE_NAME"
echo "   docker-compose up -d $SERVICE_NAME"
echo ""
echo "4. Verify:"
echo "   curl http://localhost:$HEALTH_PORT/health"
echo ""
echo "📖 For detailed documentation, see: g2-aol-template/README.md"
echo ""
