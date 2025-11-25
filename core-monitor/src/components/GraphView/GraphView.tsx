import { useEffect, useRef, useState } from 'react';
import { useServiceStore } from '../../store/serviceStore';
import { buildGraphData, createForceSimulation, getStatusColor, getTypeColor } from '../../utils/graphUtils';
import * as d3 from 'd3';
import { useNavigate } from 'react-router-dom';
import { ZoomIn, ZoomOut, RotateCcw, Download } from 'lucide-react';

export default function GraphView() {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const simulationRef = useRef<d3.Simulation<any, any> | null>(null);
  const [dimensions, setDimensions] = useState({ width: 1200, height: 800 });
  const navigate = useNavigate();
  
  const { services, routes, filter } = useServiceStore();

  // Filter services based on filter criteria
  const filteredServices = services.filter(service => {
    if (!service || !service.service_id) return false;
    
    if (filter.status && service.status !== filter.status) return false;
    if (filter.type) {
      const serviceType = service?.manifest?.metadata?.labels?.['aol.service.type'] 
        || service?.manifest?.kind 
        || 'unknown';
      if (serviceType !== filter.type) return false;
    }
    if (filter.search) {
      const searchLower = filter.search.toLowerCase();
      if (!service.name?.toLowerCase().includes(searchLower)) return false;
    }
    return true;
  });

  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const { nodes, links } = buildGraphData(filteredServices, routes);

    if (nodes.length === 0) {
      svg.append('text')
        .attr('x', dimensions.width / 2)
        .attr('y', dimensions.height / 2)
        .attr('text-anchor', 'middle')
        .attr('fill', '#94a3b8')
        .text('No services to display');
      return;
    }

    // Create zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        container.attr('transform', event.transform.toString());
      });

    svg.call(zoom);

    const container = svg.append('g');

    // Create force simulation
    const simulation = createForceSimulation(nodes, links, dimensions.width, dimensions.height);
    simulationRef.current = simulation;

    // Create links
    const link = container.append('g')
      .selectAll('line')
      .data(links)
      .enter()
      .append('line')
      .attr('stroke', (d) => d.success_rate > 0.8 ? '#10b981' : d.success_rate > 0.5 ? '#f59e0b' : '#ef4444')
      .attr('stroke-width', (d) => Math.max(1, Math.min(5, d.count / 10)))
      .attr('stroke-opacity', 0.6)
      .attr('marker-end', 'url(#arrowhead)');

    // Create arrow marker
    svg.append('defs').append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 25)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#94a3b8');

    // Create nodes
    const node = container.append('g')
      .selectAll('g')
      .data(nodes)
      .enter()
      .append('g')
      .attr('class', 'node')
      .call(d3.drag<SVGGElement, any>()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        })
      )
      .on('click', (event, d) => {
        navigate(`/service/${d.id}`);
      })
      .style('cursor', 'pointer');

    // Add circles for nodes
    node.append('circle')
      .attr('r', 20)
      .attr('fill', (d) => getStatusColor(d.status))
      .attr('stroke', (d) => getTypeColor(d.type))
      .attr('stroke-width', 3);

    // Add labels
    node.append('text')
      .text((d) => d.name)
      .attr('dx', 25)
      .attr('dy', 5)
      .attr('fill', '#e2e8f0')
      .attr('font-size', '12px')
      .attr('font-weight', '500');

    // Update positions on simulation tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => (d.source as any).x)
        .attr('y1', (d: any) => (d.source as any).y)
        .attr('x2', (d: any) => (d.target as any).x)
        .attr('y2', (d: any) => (d.target as any).y);

      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    // Handle window resize
    const handleResize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({ width: rect.width, height: rect.height - 100 });
      }
    };

    window.addEventListener('resize', handleResize);
    handleResize();

    return () => {
      window.removeEventListener('resize', handleResize);
      simulation.stop();
    };
  }, [filteredServices, routes, dimensions, navigate]);

  const handleZoomIn = () => {
    if (svgRef.current) {
      const svg = d3.select(svgRef.current);
      svg.transition().call(d3.zoom<SVGSVGElement, unknown>().scaleBy as any, 1.5);
    }
  };

  const handleZoomOut = () => {
    if (svgRef.current) {
      const svg = d3.select(svgRef.current);
      svg.transition().call(d3.zoom<SVGSVGElement, unknown>().scaleBy as any, 1 / 1.5);
    }
  };

  const handleReset = () => {
    if (svgRef.current) {
      const svg = d3.select(svgRef.current);
      svg.transition().call(d3.zoom<SVGSVGElement, unknown>().transform as any, d3.zoomIdentity);
    }
    if (simulationRef.current) {
      simulationRef.current.alpha(1).restart();
    }
  };

  const handleExport = () => {
    if (svgRef.current) {
      const svgData = new XMLSerializer().serializeToString(svgRef.current);
      const blob = new Blob([svgData], { type: 'image/svg+xml' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'aol-core-graph.svg';
      link.click();
      URL.revokeObjectURL(url);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Service Graph</h2>
          <p className="text-sm text-slate-400">
            {filteredServices.length} services, {routes.length} connections
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleZoomIn}
            className="p-2 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
            title="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={handleZoomOut}
            className="p-2 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
            title="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={handleReset}
            className="p-2 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
            title="Reset View"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
          <button
            onClick={handleExport}
            className="p-2 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
            title="Export SVG"
          >
            <Download className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div
        ref={containerRef}
        className="border border-slate-700 rounded-lg bg-slate-800 overflow-hidden"
        style={{ height: 'calc(100vh - 250px)' }}
      >
        <svg
          ref={svgRef}
          width={dimensions.width}
          height={dimensions.height}
          className="w-full h-full"
        />
      </div>

      <div className="flex gap-6 text-sm text-slate-400">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-status-healthy border-2 border-blue-400" />
          <span>Healthy</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-status-unhealthy border-2 border-blue-400" />
          <span>Unhealthy</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-status-starting border-2 border-blue-400" />
          <span>Starting</span>
        </div>
      </div>
    </div>
  );
}

