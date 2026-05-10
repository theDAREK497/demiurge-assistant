import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { useLanguage } from '../i18n/LanguageContext';

interface GraphViewProps {
  entities: any[];
  onNodeClick: (entity: any) => void;
}

export const GraphView: React.FC<GraphViewProps> = ({ entities, onNodeClick }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { t } = useLanguage();

  useEffect(() => {
    if (!svgRef.current || !containerRef.current || entities.length === 0) return;

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;

    // Clear previous graph
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    const g = svg.append('g');

    // Zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom);

    // Prepare data
    const nodes = entities.map(e => ({ ...e, radius: 20 }));
    const links: any[] = [];

    entities.forEach(sourceEntity => {
      if (!sourceEntity.description) return;
      const matches = sourceEntity.description.match(/\[\[(.*?)\]\]/g);
      if (matches) {
        matches.forEach((m: string) => {
          const targetName = m.slice(2, -2).trim().toLowerCase();
          const targetEntity = entities.find(e => e.name.toLowerCase() === targetName);
          if (targetEntity && targetEntity.id !== sourceEntity.id) {
            // Avoid duplicate links
            const existingLink = links.find(l => 
              (l.source === sourceEntity.id && l.target === targetEntity.id) ||
              (l.source === targetEntity.id && l.target === sourceEntity.id)
            );
            if (!existingLink) {
              links.push({ source: sourceEntity.id, target: targetEntity.id });
            }
          }
        });
      }
    });

    const colorScale = d3.scaleOrdinal(d3.schemeCategory10);
    const getColor = (type: string) => {
      const colors: Record<string, string> = {
        npc: '#3b82f6', // blue
        enemy: '#ef4444', // red
        item: '#f59e0b', // amber
        location: '#10b981', // emerald
        country: '#8b5cf6', // violet
        faction: '#f97316', // orange
        settlement: '#06b6d4', // cyan
        pc: '#ec4899', // pink
      };
      return colors[type] || '#6b7280';
    };

    const simulation = d3.forceSimulation(nodes as any)
      .force('link', d3.forceLink(links).id((d: any) => d.id).distance(150))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide().radius(40));

    // Draw links
    const link = g.append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', '#4b5563')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', 2);

    // Draw nodes
    const node = g.append('g')
      .selectAll('g')
      .data(nodes)
      .join('g')
      .call(d3.drag<any, any>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended)
      )
      .on('click', (event, d) => {
        onNodeClick(d);
      })
      .style('cursor', 'pointer');

    node.append('circle')
      .attr('r', 20)
      .attr('fill', (d: any) => d.data?.color || getColor(d.type))
      .attr('stroke', '#1f2937')
      .attr('stroke-width', 3)
      .attr('class', 'transition-colors hover:stroke-emerald-500');

    node.append('text')
      .text((d: any) => d.name)
      .attr('x', 25)
      .attr('y', 5)
      .attr('fill', '#d1d5db')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('text-shadow', '0px 2px 4px rgba(0,0,0,0.8)');

    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      node
        .attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    function dragstarted(event: any) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }

    function dragged(event: any) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }

    function dragended(event: any) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }

    // Initial zoom to fit
    svg.call(zoom.transform as any, d3.zoomIdentity.translate(width/2, height/2).scale(0.8).translate(-width/2, -height/2));

    return () => {
      simulation.stop();
    };
  }, [entities, onNodeClick]);

  return (
    <div ref={containerRef} className="w-full h-[calc(100vh-200px)] min-h-[500px] bg-stone-950 rounded-2xl border border-stone-800 overflow-hidden relative">
      <svg ref={svgRef} className="w-full h-full" />
      <div className="absolute bottom-4 left-4 bg-stone-900/90 p-3 rounded-lg border border-stone-800 text-xs text-stone-400 pointer-events-none shadow-lg">
        <p>{t.wiki_graph_help || "Scroll to zoom, drag to pan. Click nodes to open."}</p>
      </div>
    </div>
  );
};
