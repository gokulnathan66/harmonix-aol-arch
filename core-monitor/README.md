# AOL Core Monitor

Real-time monitoring dashboard for AOL Core service mesh.

## Features

- **Graph View**: Obsidian-style force-directed graph visualization of service communication
- **List View**: Sortable table of all registered services
- **Timeline View**: Chronological event stream
- **Metrics View**: Charts and statistics
- **Service Detail**: Deep dive into individual service information
- **Real-time Updates**: WebSocket with polling fallback

## Development

### Prerequisites

- Node.js 18+
- npm or yarn

### Setup

```bash
cd aol-core/aol-core-monitor
npm install
```

### Run Development Server

```bash
npm run dev
```

The dashboard will be available at http://localhost:5173

### Build for Production

```bash
npm run build
```

The built files will be in the `dist` directory.

## Configuration

The frontend connects to the AOL Core API running on port 50201 by default. This can be configured via environment variables:

- `VITE_WS_URL`: WebSocket URL (default: `ws://localhost:50201/ws`)
- `VITE_API_URL`: API base URL (default: `http://localhost:50201`)

## Architecture

- **React 18** with TypeScript
- **Vite** for build tooling
- **Zustand** for state management
- **D3.js** for graph visualization
- **Recharts** for metrics charts
- **TailwindCSS** for styling
- **React Router** for navigation

