'use client';

import React, { useEffect, useRef, useMemo } from 'react';
import * as d3 from 'd3';
import { GraphNode, GraphEdge } from '../../lib/types';
import { NEXORA_TOKENS } from '../../lib/design-tokens';

interface TaskGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  className?: string;
}

interface D3Node extends d3.SimulationNodeDatum, GraphNode {}

interface D3Edge extends d3.SimulationLinkDatum<D3Node> {
  source: string | D3Node;
  target: string | D3Node;
  type: GraphEdge['type'];
}

export const TaskGraph: React.FC<TaskGraphProps> = ({ nodes, edges, className = "" }) => {
  const svgRef = useRef<SVGSVGElement>(null);

  // Memoize D3 data
  const d3Data = useMemo(() => {
    const d3Nodes: D3Node[] = nodes.map(n => ({ ...n }));
    const d3Edges: D3Edge[] = edges.map(e => ({ ...e }));
    return { nodes: d3Nodes, edges: d3Edges };
  }, [nodes, edges]);

  useEffect(() => {
    if (!svgRef.current || d3Data.nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    svg.selectAll('*').remove();

    const simulation = d3.forceSimulation<D3Node>(d3Data.nodes)
      .force('link', d3.forceLink<D3Node, D3Edge>(d3Data.edges).id(d => d.id).distance(120))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('x', d3.forceX(width / 2).strength(0.1))
      .force('y', d3.forceY(height / 2).strength(0.1));

    // Markers for directed edges
    svg.append('defs').append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '-0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('xoverflow', 'visible')
      .append('svg:path')
      .attr('d', 'M 0,-5 L 10 ,0 L 0,5')
      .attr('fill', 'rgba(255,255,255,0.2)')
      .style('stroke', 'none');

    // Edges
    const link = svg.append('g')
      .selectAll('line')
      .data(d3Data.edges)
      .join('line')
      .attr('stroke', d => {
        if (d.type === 'contradicts') return `${NEXORA_TOKENS.colors.red}66`; // 40% opacity
        if (d.type === 'supports') return `${NEXORA_TOKENS.colors.green}66`; // 40% opacity
        return 'rgba(255, 255, 255, 0.1)';
      })
      .attr('stroke-width', 1)
      .attr('stroke-dasharray', d => d.type === 'contradicts' ? '4 2' : 'none')
      .attr('marker-end', 'url(#arrowhead)');

    // Nodes
    const node = svg.append('g')
      .selectAll<SVGGElement, D3Node>('g')
      .data(d3Data.nodes)
      .join('g')
      .call(d3.drag<SVGGElement, D3Node>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended));

    // Node Visuals
    node.append('rect')
      .attr('width', 12)
      .attr('height', 12)
      .attr('x', -6)
      .attr('y', -6)
      .attr('fill', d => {
        if (d.type === 'contradiction') return NEXORA_TOKENS.colors.red;
        if (d.type === 'source') return NEXORA_TOKENS.colors.blue;
        if (d.type === 'claim') return NEXORA_TOKENS.colors.green;
        return NEXORA_TOKENS.colors.indigo;
      })
      .attr('opacity', d => 0.4 + (d.confidence * 0.6))
      .attr('stroke', 'rgba(255,255,255,0.2)')
      .attr('stroke-width', 1);

    // Label
    node.append('text')
      .attr('dx', 10)
      .attr('dy', 4)
      .attr('fill', 'rgba(255, 255, 255, 0.8)')
      .style('font-family', NEXORA_TOKENS.typography.mono)
      .style('font-size', '10px')
      .style('text-transform', 'uppercase')
      .style('pointer-events', 'none')
      .text(d => d.label.length > 20 ? d.label.substring(0, 17) + '...' : d.label);

    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as D3Node).x ?? 0)
        .attr('y1', d => (d.source as D3Node).y ?? 0)
        .attr('x2', d => (d.target as D3Node).x ?? 0)
        .attr('y2', d => (d.target as D3Node).y ?? 0);

      node.attr('transform', d => `translate(${d.x}, ${d.y})`);
    });

    function dragstarted(event: d3.D3DragEvent<SVGGElement, D3Node, D3Node>) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }

    function dragged(event: d3.D3DragEvent<SVGGElement, D3Node, D3Node>) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }

    function dragended(event: d3.D3DragEvent<SVGGElement, D3Node, D3Node>) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }

    return () => {
      simulation.stop();
    };
  }, [d3Data]);

  return (
    <div className={`relative w-full h-full bg-nexora-surface-1 border border-nexora-border-subtle terminal-surface corner-accent ${className}`}>
      {/* HUD HUD HUD */}
      <div className="absolute top-3 left-3 flex items-center gap-2">
        <div className="w-1.5 h-1.5 status-dot active" />
        <span className="text-[10px] font-bold tracking-widest text-nexora-text-secondary uppercase">
          KNOWLEDGE_GRAPH_VIS
        </span>
      </div>
      
      <svg ref={svgRef} className="w-full h-full transition-opacity duration-300" />
      
      {/* Legend */}
      <div className="absolute bottom-3 left-3 flex flex-wrap gap-x-4 gap-y-1 text-[8px] tracking-[0.1em] uppercase text-nexora-text-muted">
        <div className="flex items-center gap-1">
          <div className="w-1.5 h-1.5" style={{ background: NEXORA_TOKENS.colors.green }} /> CLAIM
        </div>
        <div className="flex items-center gap-1">
          <div className="w-1.5 h-1.5" style={{ background: NEXORA_TOKENS.colors.blue }} /> SOURCE
        </div>
        <div className="flex items-center gap-1">
          <div className="w-1.5 h-1.5" style={{ background: NEXORA_TOKENS.colors.red }} /> CONTRADICTION
        </div>
        <div className="flex items-center gap-1">
          <div className="w-1.5 h-1.5" style={{ background: NEXORA_TOKENS.colors.indigo }} /> CONCEPT
        </div>
      </div>
    </div>
  );
};
