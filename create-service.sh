#!/bin/bash
#
# Quick Setup Script for Creating New AOL Service
# Usage: ./create-service.sh my-new-service [service-type]
# Service types: Agent, Tool, Plugin, Service (default: Service)
#
# This script scaffolds a new AOL service with:
# - Manifest-based configuration
# - Lifecycle hooks
# - Event bus integration
# - Tool/Integration support
# - Health monitoring

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
mkdir -p "$TARGET_DIR/integration"

# Copy template files
echo "📋 Copying template files..."
cp -r "$SCRIPT_DIR/service/"* "$TARGET_DIR/service/"
cp -r "$SCRIPT_DIR/utils/"* "$TARGET_DIR/utils/"
cp -r "$SCRIPT_DIR/sidecar/"* "$TARGET_DIR/sidecar/"
cp -r "$SCRIPT_DIR/proto/"* "$TARGET_DIR/proto/"
cp -r "$SCRIPT_DIR/integration/"* "$TARGET_DIR/integration/"
cp "$SCRIPT_DIR/requirements.txt" "$TARGET_DIR/"
cp "$SCRIPT_DIR/Dockerfile" "$TARGET_DIR/"

# Copy manifest and config files
cp "$SCRIPT_DIR/manifest.yaml" "$TARGET_DIR/manifest.yaml"
cp "$SCRIPT_DIR/config.yaml" "$TARGET_DIR/config.yaml"

# Ask about data storage and configure accordingly
read -p "Does this service need data storage? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    DATA_ENABLED="true"
    echo "✅ Data storage will be enabled in manifest and config"
else
    DATA_ENABLED="false"
    echo "✅ Using basic configuration (data storage disabled)"
fi

# Ask about integrations
read -p "Does this service need external integrations (LLM, APIs)? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    INTEGRATIONS_ENABLED="true"
    echo "✅ Integrations will be enabled"
else
    INTEGRATIONS_ENABLED="false"
fi

# Ask about pub-sub
read -p "Does this service need pub-sub messaging? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    PUBSUB_ENABLED="true"
    echo "✅ Pub-sub messaging will be enabled"
else
    PUBSUB_ENABLED="false"
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
        SERVICE_ROLE="agent"
        ;;
    Tool|tool|TOOL)
        SERVICE_KIND="AOLTool"
        SERVICE_ROLE="tool"
        ;;
    Plugin|plugin|PLUGIN)
        SERVICE_KIND="AOLPlugin"
        SERVICE_ROLE="plugin"
        ;;
    *)
        SERVICE_KIND="AOLService"
        SERVICE_ROLE="service"
        ;;
esac

# Update manifest.yaml
sed -i.bak "s/kind: \"AOLService\"/kind: \"$SERVICE_KIND\"/g" "$TARGET_DIR/manifest.yaml"
sed -i.bak "s/name: \"aol-service\"/name: \"$SERVICE_NAME\"/g" "$TARGET_DIR/manifest.yaml"
sed -i.bak "s/name: \"example-service\"/name: \"$SERVICE_NAME\"/g" "$TARGET_DIR/manifest.yaml"
sed -i.bak "s/role: \"service\"/role: \"$SERVICE_ROLE\"/g" "$TARGET_DIR/manifest.yaml"
sed -i.bak "s/50050/$GRPC_PORT/g" "$TARGET_DIR/manifest.yaml"
sed -i.bak "s/50200/$HEALTH_PORT/g" "$TARGET_DIR/manifest.yaml"
sed -i.bak "s/8080/$METRICS_PORT/g" "$TARGET_DIR/manifest.yaml"
sed -i.bak "s/50060/$GRPC_PORT/g" "$TARGET_DIR/manifest.yaml"
sed -i.bak "s/50210/$HEALTH_PORT/g" "$TARGET_DIR/manifest.yaml"
sed -i.bak "s/8090/$METRICS_PORT/g" "$TARGET_DIR/manifest.yaml"

# Update config.yaml (if it has service name references)
sed -i.bak "s/aol-service/$SERVICE_NAME/g" "$TARGET_DIR/config.yaml" 2>/dev/null || true
sed -i.bak "s/name: \"aol-service\"/name: \"$SERVICE_NAME\"/g" "$TARGET_DIR/config.yaml" 2>/dev/null || true
sed -i.bak "s/kind: \"AOLService\"/kind: \"$SERVICE_KIND\"/g" "$TARGET_DIR/config.yaml" 2>/dev/null || true

# Update data requirements in manifest and config
if [ "$DATA_ENABLED" = "true" ]; then
    # Enable data requirements in manifest
    sed -i.bak "s/enabled: false  # Set to true to enable/enabled: true  # Data storage enabled/g" "$TARGET_DIR/manifest.yaml" 2>/dev/null || true
    sed -i.bak "s/enabled: false$/enabled: true/g" "$TARGET_DIR/manifest.yaml" 2>/dev/null || true
    # Uncomment knowledge-db dependency in manifest
    sed -i.bak "s/# - service: \"knowledge-db\"/- service: \"knowledge-db\"/g" "$TARGET_DIR/manifest.yaml" 2>/dev/null || true
    sed -i.bak "s/#   optional: false/  optional: false/g" "$TARGET_DIR/manifest.yaml" 2>/dev/null || true
    
    # Enable data client in config
    sed -i.bak "s/enabled: false  # Set to true to enable/enabled: true  # Data storage enabled/g" "$TARGET_DIR/config.yaml" 2>/dev/null || true
    sed -i.bak "s/enabled: false$/enabled: true/g" "$TARGET_DIR/config.yaml" 2>/dev/null || true
fi

# Update integrations in config
if [ "$INTEGRATIONS_ENABLED" = "true" ]; then
    sed -i.bak "s/enabled: false$/enabled: true/g" "$TARGET_DIR/config.yaml" 2>/dev/null || true
fi

# Update pubsub in config  
if [ "$PUBSUB_ENABLED" = "true" ]; then
    sed -i.bak "s/pubsub:/pubsub:\n  enabled: true/g" "$TARGET_DIR/config.yaml" 2>/dev/null || true
fi

# Clean up backup files
rm -f "$TARGET_DIR"/*.bak 2>/dev/null || true
rm -f "$TARGET_DIR/service/"*.bak 2>/dev/null || true
rm -f "$TARGET_DIR/utils/"*.bak 2>/dev/null || true

# Validate the manifest
echo ""
echo "🔍 Validating generated manifest..."
python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from utils.validators import validate_manifest, print_validation_result
result = validate_manifest('$TARGET_DIR/manifest.yaml')
print_validation_result(result)
if not result.valid:
    sys.exit(1)
" 2>/dev/null || echo "⚠️  Manifest validation skipped (validators not available)"

echo ""
echo "✅ Service created successfully!"
echo ""
echo "📁 Service location: $TARGET_DIR"
echo ""
echo "Service Configuration:"
echo "   Name: $SERVICE_NAME"
echo "   Kind: $SERVICE_KIND"
echo "   gRPC Port: $GRPC_PORT"
echo "   Health Port: $HEALTH_PORT"
echo "   Metrics Port: $METRICS_PORT"
echo "   Data Storage: $DATA_ENABLED"
echo "   Integrations: $INTEGRATIONS_ENABLED"
echo "   Pub-Sub: $PUBSUB_ENABLED"
echo ""
echo "Next steps:"
echo "1. Edit $TARGET_DIR/service/main.py and implement your logic:"
echo ""
case "$SERVICE_TYPE" in
    Agent|agent|AGENT)
        echo "   For Agents - Override the Process() method with your reasoning logic:"
        echo "   async def Process(self, request):"
        echo "       # Implement agent reasoning here"
        echo "       # Use self.data_client for persistence"
        echo "       # Use self.event_bus for pub-sub"
        echo "       # Use self.tool_registry for integrations"
        ;;
    Tool|tool|TOOL)
        echo "   For Tools - Override the Process() method with your execution logic:"
        echo "   async def Process(self, request):"
        echo "       # Implement tool execution here"
        echo "       # Return structured results"
        ;;
    Plugin|plugin|PLUGIN)
        echo "   For Plugins - Override the Process() method with your handler:"
        echo "   async def Process(self, request):"
        echo "       # Implement plugin behavior here"
        ;;
    *)
        echo "   For Services - Override the Process() method:"
        echo "   async def Process(self, request):"
        echo "       # Implement service logic here"
        ;;
esac
echo ""
echo "2. Configure dependencies in $TARGET_DIR/manifest.yaml"
echo ""
echo "3. Add service to docker-compose.yml:"
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
echo "    environment:"
echo "      - CONSUL_HTTP_ADDR=consul-server:8500"
echo "      - AOL_CORE_ENDPOINT=http://aol-core:8080"
echo "    networks:"
echo "      - heart-pulse-network"
echo "    depends_on:"
echo "      - consul-server"
echo "      - aol-core"
echo ""
echo "4. Build and run:"
echo "   cd app"
echo "   docker-compose build $SERVICE_NAME"
echo "   docker-compose up -d $SERVICE_NAME"
echo ""
echo "5. Verify:"
echo "   curl http://localhost:$HEALTH_PORT/health"
echo "   curl http://localhost:$HEALTH_PORT/ready"
echo "   curl http://localhost:$METRICS_PORT/metrics"
echo ""
echo "📖 Key files to customize:"
echo "   - manifest.yaml: Service declaration and dependencies"
echo "   - config.yaml: Runtime configuration"
echo "   - service/main.py: Service implementation"
echo "   - integration/: External tool adapters (if needed)"
echo ""
