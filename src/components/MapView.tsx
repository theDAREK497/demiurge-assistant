import React, { useState, useEffect, useRef } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { api } from '../api';
import { ArrowLeft, Plus, MapPin, Edit2, Save, X, Trash2, Book, Image as ImageIcon } from 'lucide-react';

const PREDEFINED_IMAGES = [
  { name: 'Город', url: `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 225" width="400" height="225"><rect width="400" height="225" fill="%231e293b"/><rect x="50" y="100" width="40" height="125" fill="%23334155"/><rect x="100" y="50" width="60" height="175" fill="%23475569"/><rect x="170" y="80" width="50" height="145" fill="%23334155"/><rect x="230" y="120" width="40" height="105" fill="%23475569"/><rect x="280" y="60" width="70" height="165" fill="%23334155"/><rect x="110" y="70" width="10" height="10" fill="%23fbbf24"/><rect x="130" y="70" width="10" height="10" fill="%23fbbf24"/><rect x="110" y="100" width="10" height="10" fill="%23fbbf24"/><rect x="290" y="80" width="10" height="10" fill="%23fbbf24"/><rect x="320" y="120" width="10" height="10" fill="%23fbbf24"/></svg>` },
  { name: 'Деревня', url: `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 225" width="400" height="225"><rect width="400" height="225" fill="%2384cc16"/><path d="M 0 150 Q 200 100 400 150 L 400 225 L 0 225 Z" fill="%2365a30d"/><rect x="100" y="120" width="40" height="30" fill="%23fef3c7"/><polygon points="90,120 120,90 150,120" fill="%23ef4444"/><rect x="250" y="140" width="50" height="40" fill="%23fef3c7"/><polygon points="240,140 275,110 310,140" fill="%23ef4444"/></svg>` },
  { name: 'Лес', url: `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 225" width="400" height="225"><rect width="400" height="225" fill="%23166534"/><rect x="80" y="150" width="10" height="40" fill="%2378350f"/><polygon points="40,150 85,70 130,150" fill="%2315803d"/><polygon points="50,110 85,40 120,110" fill="%2316a34a"/><rect x="200" y="130" width="15" height="50" fill="%2378350f"/><polygon points="150,130 207,40 265,130" fill="%2315803d"/><polygon points="165,90 207,20 250,90" fill="%2316a34a"/><rect x="320" y="160" width="10" height="40" fill="%2378350f"/><polygon points="280,160 325,80 370,160" fill="%2315803d"/></svg>` },
  { name: 'Горы', url: `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 225" width="400" height="225"><rect width="400" height="225" fill="%2338bdf8"/><polygon points="0,225 100,50 200,225" fill="%2364748b"/><polygon points="100,50 150,137 200,225" fill="%23475569"/><polygon points="150,225 280,30 400,225" fill="%2394a3b8"/><polygon points="280,30 340,127 400,225" fill="%2364748b"/><polygon points="100,50 70,102 100,110 130,102" fill="%23f8fafc"/><polygon points="280,30 240,95 280,110 320,95" fill="%23f8fafc"/></svg>` },
  { name: 'Мост', url: `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 225" width="400" height="225"><rect width="400" height="225" fill="%23bae6fd"/><rect x="0" y="150" width="400" height="75" fill="%230284c7"/><rect x="0" y="100" width="400" height="20" fill="%23475569"/><rect x="80" y="120" width="40" height="105" fill="%23334155"/><rect x="280" y="120" width="40" height="105" fill="%23334155"/><path d="M 120 120 Q 200 50 280 120" fill="none" stroke="%2364748b" stroke-width="5"/><path d="M 0 120 Q 40 50 80 120" fill="none" stroke="%2364748b" stroke-width="5"/><path d="M 280 120 Q 340 50 400 120" fill="none" stroke="%2364748b" stroke-width="5"/></svg>` },
  { name: 'Замок', url: `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 225" width="400" height="225"><rect width="400" height="225" fill="%231e1b4b"/><rect x="100" y="100" width="200" height="125" fill="%23475569"/><rect x="80" y="60" width="40" height="165" fill="%23334155"/><rect x="280" y="60" width="40" height="165" fill="%23334155"/><polygon points="70,60 100,20 130,60" fill="%23b91c1c"/><polygon points="270,60 300,20 330,60" fill="%23b91c1c"/><path d="M 170 225 L 170 170 A 30 30 0 0 1 230 170 L 230 225 Z" fill="%231c1917"/><rect x="120" y="80" width="20" height="20" fill="%23475569"/><rect x="160" y="80" width="20" height="20" fill="%23475569"/><rect x="200" y="80" width="20" height="20" fill="%23475569"/><rect x="240" y="80" width="20" height="20" fill="%23475569"/></svg>` },
  { name: 'Пустыня', url: `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 225" width="400" height="225"><rect width="400" height="225" fill="%23fcd34d"/><circle cx="300" cy="80" r="40" fill="%23f59e0b"/><path d="M 0 225 Q 100 150 200 225 Z" fill="%23f59e0b"/><path d="M 150 225 Q 250 120 400 225 Z" fill="%23d97706"/><path d="M -50 225 Q 50 180 150 225 Z" fill="%23b45309"/></svg>` },
  { name: 'Море', url: `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 225" width="400" height="225"><rect width="400" height="225" fill="%230ea5e9"/><path d="M 0 150 Q 50 130 100 150 T 200 150 T 300 150 T 400 150 L 400 225 L 0 225 Z" fill="%230284c7"/><path d="M 0 180 Q 50 160 100 180 T 200 180 T 300 180 T 400 180 L 400 225 L 0 225 Z" fill="%230369a1"/><circle cx="100" cy="80" r="30" fill="%23fef08a"/></svg>` },
];

export const MapView = () => {
  const { t } = useLanguage();
  const [currentLevel, setCurrentLevel] = useState<'universe' | 'galaxy' | 'system' | 'planet'>('universe');
  const [currentNode, setCurrentNode] = useState<any>(null);
  const [nodeHistory, setNodeHistory] = useState<any[]>([]);
  const [nodes, setNodes] = useState<any[]>([]);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  
  const [isEditing, setIsEditing] = useState(false);
  const [placementMode, setPlacementMode] = useState(false);
  const [editForm, setEditForm] = useState<any>({});
  
  const [draggingNodeId, setDraggingNodeId] = useState<string | null>(null);
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const [selectedBiome, setSelectedBiome] = useState<string>('random');
  const [gridWidthState, setGridWidthState] = useState(15);
  const [gridHeightState, setGridHeightState] = useState(10);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [regenerateConfirm, setRegenerateConfirm] = useState(false);
  const [factions, setFactions] = useState<any[]>([]);
  
  const svgRef = useRef<SVGSVGElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const url = await api.uploadImage(file);
      setEditForm({...editForm, data: {...(editForm.data || {}), image: url}});
    } catch (err) {
      console.error('Failed to upload image', err);
      alert('Upload failed');
    }
  };

  useEffect(() => {
    loadNodes();
    loadFactions();
    setTransform({ x: 0, y: 0, scale: 1 });
    if (currentNode && currentLevel === 'planet') {
      setGridWidthState(currentNode.data?.gridWidth || 15);
      setGridHeightState(currentNode.data?.gridHeight || 10);
    }
  }, [currentLevel, currentNode?.id]);

  const loadFactions = async () => {
    try {
      const entities = await api.getEntities();
      const factionEntities = entities.filter((e: any) => e.type === 'faction');
      setFactions(factionEntities);
    } catch (e) {
      console.error('Failed to load factions', e);
    }
  };

  const loadNodes = async () => {
    if (currentLevel === 'universe') {
      const data = await api.getMapNodes(undefined, 'galaxy');
      if (data.length === 0) {
        const newGalaxy = { type: 'galaxy', name: 'Млечный Путь', x: 400, y: 300, data: { color: '#fbbf24', size: 15 } };
        const res = await api.saveMapNode(newGalaxy);
        if (res.id) {
          await api.saveEntity({
            id: res.id,
            type: 'location',
            name: newGalaxy.name,
            description: 'A galaxy on the map.',
            tags: 'galaxy'
          });
        }
        const newData = await api.getMapNodes(undefined, 'galaxy');
        setNodes(newData);
      } else {
        setNodes(data);
      }
    } else if (currentNode) {
      const typeToFetch = currentLevel === 'galaxy' ? 'system' : currentLevel === 'system' ? 'planet' : 'hex';
      const data = await api.getMapNodes(currentNode.id, typeToFetch);
      setNodes(data);
    }
  };

  const handleNodeClick = (node: any) => {
    if (draggingNodeId) return;
    setSelectedNode(node);
    if (isEditing) {
      setEditForm({ ...node });
    }
  };

  const handleNodeDoubleClick = (node: any) => {
    if (isEditing) return;
    if (node.type === 'galaxy') {
      setNodeHistory([...nodeHistory, currentNode]);
      setCurrentLevel('galaxy');
      setCurrentNode(node);
    } else if (node.type === 'system') {
      setNodeHistory([...nodeHistory, currentNode]);
      setCurrentLevel('system');
      setCurrentNode(node);
    } else if (node.type === 'planet') {
      setNodeHistory([...nodeHistory, currentNode]);
      setCurrentLevel('planet');
      setCurrentNode(node);
    }
    setSelectedNode(null);
  };

  const handleBack = () => {
    const prevNode = nodeHistory[nodeHistory.length - 1];
    setNodeHistory(nodeHistory.slice(0, -1));
    
    if (currentLevel === 'planet') {
      setCurrentLevel('system');
      setCurrentNode(prevNode);
    } else if (currentLevel === 'system') {
      setCurrentLevel('galaxy');
      setCurrentNode(prevNode);
    } else if (currentLevel === 'galaxy') {
      setCurrentLevel('universe');
      setCurrentNode(prevNode);
    }
    setSelectedNode(null);
    setIsEditing(false);
    setPlacementMode(false);
  };

  const handleGeneratePlanet = async (biomeType: string = 'random') => {
    if (!currentNode || currentLevel !== 'planet') return;
    
    if (nodes.length > 0) {
      if (!regenerateConfirm) {
        setRegenerateConfirm(true);
        setTimeout(() => setRegenerateConfirm(false), 3000);
        return;
      }
      setRegenerateConfirm(false);
      await Promise.all(nodes.map(node => api.deleteMapNode(node.id)));
    }

    const hexRadius = 30;
    const hexWidth = Math.sqrt(3) * hexRadius;
    const hexHeight = 2 * hexRadius;
    
    const gridWidth = gridWidthState;
    const gridHeight = gridHeightState;
    
    // Update planet node with new grid dimensions
    const updatedNode = {
      ...currentNode,
      data: {
        ...currentNode.data,
        gridWidth,
        gridHeight
      }
    };
    await api.saveMapNode(updatedNode);
    setCurrentNode(updatedNode);
    
    const newNodes = [];
    for (let r = 0; r < gridHeight; r++) {
      for (let q = 0; q < gridWidth; q++) {
        const xOffset = (r % 2 === 1) ? (hexWidth / 2) : 0;
        const x = (q * hexWidth) + xOffset + 100;
        const y = (r * hexHeight * 0.75) + 100;
        
        let randomBiome = biomeType;
        if (biomeType === 'random') {
          const biomes = ['forest', 'desert', 'water', 'mountain', 'plains', 'winter', 'stone'];
          randomBiome = biomes[Math.floor(Math.random() * biomes.length)];
        }
        
        newNodes.push({
          parent_id: currentNode.id,
          type: 'hex',
          name: `Hex ${q},${r}`,
          x,
          y,
          data: { biome: randomBiome, q, r }
        });
      }
    }
    
    await api.saveMapNodesBulk(newNodes);
    
    // Fetch fresh nodes
    const data = await api.getMapNodes(currentNode.id, 'hex');
    setNodes(data);
  };

  const handleSvgClick = async (e: React.MouseEvent) => {
    if (!isEditing || !placementMode || !svgRef.current) return;
    
    const svg = svgRef.current;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const svgP = pt.matrixTransform(svg.getScreenCTM()?.inverse());

    const type = currentLevel === 'universe' ? 'galaxy' : currentLevel === 'galaxy' ? 'system' : currentLevel === 'system' ? 'planet' : 'hex';
    
    if (type === 'hex') {
      // Don't allow free placement of hexes, they are generated via grid
      setPlacementMode(false);
      return;
    }

    const newNode = {
      parent_id: currentNode?.id,
      type,
      name: `${t.map_new} ${type}`,
      x: (svgP.x - transform.x) / transform.scale,
      y: (svgP.y - transform.y) / transform.scale,
      data: { 
        biome: t.map_unknown, 
        color: currentLevel === 'universe' ? '#fbbf24' : '#3b82f6', 
        size: currentLevel === 'universe' ? 15 : 25 
      }
    };
    const res = await api.saveMapNode(newNode);
    
    // Create corresponding wiki entity
    if (res.id) {
      await api.saveEntity({
        id: res.id, // Use the same ID to link them
        type: 'location',
        name: newNode.name,
        description: `A ${type} on the map.`,
        tags: type
      });
    }

    setPlacementMode(false);
    loadNodes();
  };

  const handleSaveEdit = async () => {
    if (!selectedNode) return;
    await api.saveMapNode(editForm);
    
    // Update corresponding wiki entity name
    try {
      const entities = await api.getEntities();
      const existingEntity = entities.find((e: any) => e.id === editForm.id);
      if (existingEntity) {
        await api.saveEntity({
          ...existingEntity,
          name: editForm.name
        });
      }
    } catch (e) {
      console.error("Failed to update wiki entity", e);
    }
    
    setNodes(nodes.map(n => n.id === editForm.id ? { ...editForm } : n));
    setSelectedNode({ ...editForm });
  };

  const handleDeleteNode = async () => {
    if (!selectedNode) return;
    if (deleteConfirmId === selectedNode.id) {
      await api.deleteMapNode(selectedNode.id);
      setSelectedNode(null);
      setDeleteConfirmId(null);
      loadNodes();
    } else {
      setDeleteConfirmId(selectedNode.id);
      setTimeout(() => setDeleteConfirmId(null), 3000);
    }
  };

  const handleMouseDown = (e: React.MouseEvent, node?: any) => {
    if (node && isEditing && !placementMode) {
      e.stopPropagation();
      setSelectedNode(node);
      setEditForm({ ...node });
      if (node.type !== 'hex') {
        setDraggingNodeId(node.id);
      }
    } else if (!placementMode) {
      setIsPanning(true);
      setPanStart({ x: e.clientX - transform.x, y: e.clientY - transform.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isPanning) {
      setTransform(prev => ({
        ...prev,
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y
      }));
      return;
    }

    if (!isEditing || !draggingNodeId || !svgRef.current) return;
    
    const svg = svgRef.current;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const svgP = pt.matrixTransform(svg.getScreenCTM()?.inverse());
    
    setNodes(nodes.map(n => {
      if (n.id === draggingNodeId) {
        const updated = { 
          ...n, 
          x: (svgP.x - transform.x) / transform.scale, 
          y: (svgP.y - transform.y) / transform.scale 
        };
        setEditForm(updated);
        return updated;
      }
      return n;
    }));
  };

  const handleMouseUp = async () => {
    if (isPanning) {
      setIsPanning(false);
    }
    
    if (!isEditing || !draggingNodeId) return;
    
    const nodeToSave = nodes.find(n => n.id === draggingNodeId);
    if (nodeToSave) {
      await api.saveMapNode(nodeToSave);
    }
    setDraggingNodeId(null);
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const scaleAmount = -e.deltaY * 0.001;
    const newScale = Math.min(Math.max(0.1, transform.scale * (1 + scaleAmount)), 5);
    
    // Zoom towards mouse cursor
    if (svgRef.current) {
      const rect = svgRef.current.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      
      const ratio = 1 - newScale / transform.scale;
      
      setTransform(prev => ({
        x: prev.x + (mouseX - prev.x) * ratio,
        y: prev.y + (mouseY - prev.y) * ratio,
        scale: newScale
      }));
    }
  };

  const renderHexGrid = () => {
    const hexRadius = 30;
    
    return (
      <svg 
        ref={svgRef}
        width="100%" 
        height="100%" 
        viewBox="0 0 800 600" 
        className={`bg-stone-950 ${placementMode ? 'cursor-crosshair' : ''}`}
        onClick={handleSvgClick}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
      >
        <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.scale})`}>
          <defs>
            {nodes.map(node => node.data?.image && (
              <clipPath id={`hex-clip-${node.id}`} key={`clip-${node.id}`}>
                <polygon points={Array.from({length: 6}).map((_, i) => {
                  const angle_rad = Math.PI / 180 * (60 * i - 30);
                  return `${hexRadius * Math.cos(angle_rad)},${hexRadius * Math.sin(angle_rad)}`;
                }).join(' ')} />
              </clipPath>
            ))}
          </defs>

          {nodes.map(node => {
            const cx = node.x;
            const cy = node.y;
            const points = [];
            const innerPoints = [];
            const innerRadius = hexRadius - 3.5;
            for (let i = 0; i < 6; i++) {
              const angle_deg = 60 * i - 30;
              const angle_rad = Math.PI / 180 * angle_deg;
              points.push(`${cx + hexRadius * Math.cos(angle_rad)},${cy + hexRadius * Math.sin(angle_rad)}`);
              innerPoints.push(`${cx + innerRadius * Math.cos(angle_rad)},${cy + innerRadius * Math.sin(angle_rad)}`);
            }
            const biomeColors: Record<string, string> = {
              forest: '#065f46',
              desert: '#b45309',
              water: '#1d4ed8',
              mountain: '#44403c',
              plains: '#65a30d',
              winter: '#e0f2fe',
              stone: '#78716c',
              unknown: '#292524'
            };
            const biome = node.data?.biome || 'unknown';
            const fill = node.data?.color || biomeColors[biome];
            const isSelected = selectedNode?.id === node.id;
            const faction = factions.find(f => f.id === node.data?.faction);
            const factionColor = faction ? (faction.data?.color || '#f43f5e') : null;

            return (
              <g 
                key={node.id}
                onClick={(e) => { e.stopPropagation(); handleNodeClick(node); }}
                onMouseDown={(e) => handleMouseDown(e, node)}
                className={`transition-opacity ${isEditing && !placementMode ? 'cursor-move hover:opacity-90' : 'cursor-pointer hover:opacity-80'}`}
              >
                <polygon 
                  points={points.join(' ')}
                  fill={fill}
                  stroke={isSelected ? '#10b981' : '#1c1917'}
                  strokeWidth={isSelected ? "4" : "2"}
                />
                {factionColor && (
                  <polygon 
                    points={innerPoints.join(' ')}
                    fill="none"
                    stroke={factionColor}
                    strokeWidth="3"
                  />
                )}
                {node.data?.image && (
                  <image 
                    href={node.data.image} 
                    x={-hexRadius} 
                    y={-hexRadius} 
                    width={hexRadius * 2} 
                    height={hexRadius * 2} 
                    preserveAspectRatio="xMidYMid slice"
                    clipPath={`url(#hex-clip-${node.id})`}
                    className="pointer-events-none"
                    transform={`translate(${cx}, ${cy})`}
                  />
                )}
              </g>
            );
          })}
        </g>
      </svg>
    );
  };

  const renderSpace = () => {
    return (
      <svg 
        ref={svgRef}
        width="100%" 
        height="100%" 
        viewBox="0 0 800 600" 
        className={`bg-stone-950 ${placementMode ? 'cursor-crosshair' : ''}`}
        onClick={handleSvgClick}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
      >
        <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.scale})`}>
          <defs>
            {nodes.map(node => node.data?.image && (
              <clipPath id={`clip-${node.id}`} key={`clip-${node.id}`}>
                <circle r={node.data?.size || (currentLevel === 'universe' ? 15 : 25)} />
              </clipPath>
            ))}
          </defs>

          {/* Stars background */}
          {Array.from({ length: 100 }).map((_, i) => (
            <circle key={i} cx={Math.random() * 800} cy={Math.random() * 600} r={Math.random() * 1.5} fill="#fff" opacity={Math.random()} />
          ))}
          
          {nodes.map(node => {
            const size = node.data?.size || (currentLevel === 'universe' ? 15 : 25);
            const color = node.data?.color || (currentLevel === 'universe' ? '#fbbf24' : '#3b82f6');
            const isSelected = selectedNode?.id === node.id;

            return (
              <g 
                key={node.id} 
                transform={`translate(${node.x}, ${node.y})`}
                onClick={(e) => { e.stopPropagation(); handleNodeClick(node); }}
                onDoubleClick={(e) => { e.stopPropagation(); handleNodeDoubleClick(node); }}
                onMouseDown={(e) => handleMouseDown(e, node)}
                className={isEditing && !placementMode ? 'cursor-move' : 'cursor-pointer'}
              >
                {isSelected && (
                  <circle r={size + 4} fill="none" stroke="#10b981" strokeWidth="2" className="animate-pulse" />
                )}
                
                {node.data?.image ? (
                  <image 
                    href={node.data.image} 
                    x={-size} 
                    y={-size} 
                    width={size * 2} 
                    height={size * 2} 
                    preserveAspectRatio="xMidYMid slice"
                    clipPath={`url(#clip-${node.id})`}
                  />
                ) : (
                  <circle 
                    r={size} 
                    fill={color} 
                    className="hover:opacity-80 transition-opacity"
                  />
                )}
                <text y={size + 15} textAnchor="middle" fill="#fff" fontSize="12" className="pointer-events-none drop-shadow-md">
                  {node.name}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
    );
  };

  return (
    <div className="flex flex-col md:flex-row h-full">
      {/* Map Area */}
      <div className="flex-1 relative flex flex-col h-[50vh] md:h-full">
        <div className="absolute top-4 left-4 z-10 flex flex-wrap gap-2">
          {currentLevel !== 'universe' && (
            <button onClick={handleBack} className="bg-stone-800 hover:bg-stone-700 text-white p-2 rounded-xl flex items-center">
              <ArrowLeft size={20} className="md:mr-2" /> <span className="hidden md:inline">{t.map_back}</span>
            </button>
          )}
          {currentLevel === 'planet' && (
            <div className="flex items-center gap-2 bg-stone-800 p-1 rounded-xl">
              <div className="flex items-center bg-stone-900 rounded-lg px-2">
                <input 
                  type="number" 
                  value={gridWidthState} 
                  onChange={(e) => setGridWidthState(Number(e.target.value))}
                  className="bg-transparent text-white border-none w-12 text-center outline-none py-2"
                  title="Grid Width"
                  min="1"
                  max="50"
                />
                <span className="text-stone-500 text-sm">x</span>
                <input 
                  type="number" 
                  value={gridHeightState} 
                  onChange={(e) => setGridHeightState(Number(e.target.value))}
                  className="bg-transparent text-white border-none w-12 text-center outline-none py-2"
                  title="Grid Height"
                  min="1"
                  max="50"
                />
              </div>
              <select 
                value={selectedBiome} 
                onChange={(e) => setSelectedBiome(e.target.value)}
                className="bg-stone-900 text-white border-none rounded-lg px-3 py-2 outline-none"
              >
                <option value="random">{t.map_biome_random}</option>
                <option value="water">{t.map_biome_water}</option>
                <option value="plains">{t.map_biome_plains}</option>
                <option value="forest">{t.map_biome_forest}</option>
                <option value="desert">{t.map_biome_desert}</option>
                <option value="winter">{t.map_biome_winter}</option>
                <option value="stone">{t.map_biome_stone}</option>
              </select>
              <button onClick={() => handleGeneratePlanet(selectedBiome)} className="bg-emerald-600 hover:bg-emerald-500 text-white p-2 rounded-lg flex items-center">
                <Plus size={20} className="md:mr-2" /> <span className="hidden md:inline">{nodes.length === 0 ? t.map_generate_grid : (regenerateConfirm ? 'Are you sure?' : t.map_regenerate_grid)}</span>
              </button>
            </div>
          )}
          {currentLevel !== 'planet' && isEditing && (
            <button 
              onClick={() => setPlacementMode(!placementMode)} 
              className={`${placementMode ? 'bg-emerald-500' : 'bg-emerald-600 hover:bg-emerald-500'} text-white p-2 rounded-xl flex items-center transition-colors`}
            >
              <Plus size={20} className="md:mr-2" /> <span className="hidden md:inline">{placementMode ? t.map_click_to_place : `${t.map_add} ${currentLevel === 'universe' ? 'Galaxy' : currentLevel === 'galaxy' ? 'System' : 'Planet'}`}</span>
            </button>
          )}
          <button 
            onClick={() => {
              setIsEditing(!isEditing);
              setPlacementMode(false);
              if (!isEditing && selectedNode) setEditForm({ ...selectedNode });
            }} 
            className={`${isEditing ? 'bg-emerald-600 hover:bg-emerald-500' : 'bg-stone-800 hover:bg-stone-700'} text-white p-2 rounded-xl flex items-center transition-colors`}
          >
            <Edit2 size={20} className="md:mr-2" /> <span className="hidden md:inline">{isEditing ? t.map_done_editing : t.map_edit_map}</span>
          </button>
        </div>
        
        <div className="flex-1 overflow-hidden bg-stone-950">
          {currentLevel === 'planet' ? renderHexGrid() : renderSpace()}
        </div>
      </div>

      {/* Sidebar Info */}
      <div className="w-full md:w-80 bg-stone-900 border-t md:border-t-0 md:border-l border-stone-800 p-6 flex flex-col h-[50vh] md:h-full overflow-y-auto">
        <h3 className="text-xl font-bold text-stone-100 mb-4">
          {currentLevel === 'universe' ? t.map_universe_map : `${currentNode?.name} ${t.map_map}`}
        </h3>
        
        {selectedNode ? (
          <div className="space-y-4">
            {isEditing ? (
              <div className="space-y-4">
                <input 
                  type="text" 
                  value={editForm.name || ''} 
                  onChange={e => setEditForm({...editForm, name: e.target.value})}
                  className="bg-stone-950 border border-stone-800 rounded-lg px-3 py-2 text-emerald-400 font-bold w-full"
                  placeholder={t.map_name}
                />
                <textarea 
                  value={editForm.description || ''}
                  onChange={e => setEditForm({...editForm, description: e.target.value})}
                  className="w-full bg-stone-950 border border-stone-800 rounded-lg px-3 py-2 text-sm text-stone-300 h-24 resize-none"
                  placeholder={t.map_description}
                />

                {/* Advanced Properties */}
                <div className="bg-stone-950 p-4 rounded-xl border border-stone-800 space-y-3">
                  <h5 className="text-xs font-bold text-stone-500 uppercase">{t.map_appearance}</h5>
                  
                  <div className="flex items-center justify-between">
                    <label className="text-sm text-stone-400">{t.map_color}</label>
                    <input 
                      type="color" 
                      value={editForm.data?.color || '#ffffff'} 
                      onChange={e => setEditForm({...editForm, data: {...(editForm.data || {}), color: e.target.value}})}
                      className="bg-transparent border-none w-8 h-8 cursor-pointer"
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <label className="text-sm text-stone-400">{t.map_image_url}</label>
                    <div className="flex items-center gap-2">
                      <input 
                        type="text" 
                        value={editForm.data?.image || ''} 
                        onChange={e => setEditForm({...editForm, data: {...(editForm.data || {}), image: e.target.value}})}
                        className="flex-1 bg-stone-900 border border-stone-800 rounded-lg px-3 py-1 text-sm text-stone-300"
                        placeholder="https://..."
                      />
                      <input 
                        type="file" 
                        accept="image/*" 
                        className="hidden" 
                        ref={fileInputRef}
                        onChange={handleImageUpload}
                      />
                      <button 
                        onClick={() => fileInputRef.current?.click()}
                        className="bg-stone-800 hover:bg-stone-700 text-stone-300 p-1.5 rounded-lg flex items-center transition-colors shrink-0"
                        title="Upload Image"
                      >
                        <ImageIcon size={16} />
                      </button>
                    </div>
                    <div className="grid grid-cols-4 gap-2 mt-2">
                      {PREDEFINED_IMAGES.map((img, i) => (
                        <button
                          key={i}
                          onClick={() => setEditForm({...editForm, data: {...(editForm.data || {}), image: img.url}})}
                          className={`relative aspect-video rounded-md overflow-hidden border-2 transition-colors ${editForm.data?.image === img.url ? 'border-emerald-500' : 'border-transparent hover:border-stone-600'}`}
                          title={img.name}
                        >
                          <img src={img.url} alt={img.name} className="w-full h-full object-cover" referrerPolicy="no-referrer" />
                        </button>
                      ))}
                    </div>
                  </div>
                  
                  {currentLevel === 'planet' && selectedNode.type === 'hex' && (
                    <div className="space-y-2">
                      <label className="text-sm text-stone-400">Фракция (Владелец)</label>
                      <select
                        value={editForm.data?.faction || ''}
                        onChange={e => setEditForm({...editForm, data: {...(editForm.data || {}), faction: e.target.value}})}
                        className="w-full bg-stone-900 border border-stone-800 rounded-lg px-3 py-2 text-sm text-stone-300 outline-none"
                      >
                        <option value="">Нет фракции</option>
                        {factions.map(f => (
                          <option key={f.id} value={f.id}>{f.name}</option>
                        ))}
                      </select>
                    </div>
                  )}

                  {currentLevel !== 'planet' && (
                    <div className="flex items-center justify-between">
                      <label className="text-sm text-stone-400">{t.map_size}</label>
                      <input 
                        type="number" 
                        value={editForm.data?.size || 20} 
                        onChange={e => setEditForm({...editForm, data: {...(editForm.data || {}), size: parseInt(e.target.value) || 20}})}
                        className="w-20 bg-stone-900 border border-stone-800 rounded-lg px-3 py-1 text-sm text-stone-300 text-right"
                      />
                    </div>
                  )}
                </div>

                <div className="flex space-x-2">
                  <button 
                    onClick={handleDeleteNode}
                    className="bg-red-900/30 hover:bg-red-900/50 text-red-400 p-2 rounded-xl transition-colors flex justify-center items-center"
                    title={t.map_delete_node}
                  >
                    <Trash2 size={20} />
                    {deleteConfirmId === selectedNode.id && <span className="ml-2 text-xs font-bold text-red-300">?</span>}
                  </button>
                  <button 
                    onClick={handleSaveEdit}
                    className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white py-2 rounded-xl transition-colors flex justify-center items-center"
                  >
                    <Save size={16} className="mr-2" /> {t.map_save}
                  </button>
                </div>
                <p className="text-xs text-stone-500 text-center mt-2">
                  {t.map_drag_hint}
                </p>
              </div>
            ) : (
              <>
                <div>
                  <h4 className="text-emerald-400 font-bold text-lg">{selectedNode.name}</h4>
                  <span className="text-xs font-mono text-stone-500 uppercase">{selectedNode.type}</span>
                </div>
                
                <p className="text-stone-300 text-sm whitespace-pre-wrap">
                  {selectedNode.description || t.map_no_description}
                </p>
                
                {selectedNode.data && Object.keys(selectedNode.data).length > 0 && (
                  <div className="bg-stone-950 p-4 rounded-xl border border-stone-800">
                    <h5 className="text-xs font-bold text-stone-500 uppercase mb-2">{t.map_properties}</h5>
                    {Object.entries(selectedNode.data).map(([k, v]) => {
                      if (k === 'image' || k === 'color' || k === 'size') return null;
                      if (k === 'faction') {
                        const faction = factions.find(f => f.id === v);
                        return (
                          <div key={k} className="flex justify-between text-sm">
                            <span className="text-stone-400">Фракция:</span>
                            <span className="text-rose-400 font-medium">{faction ? faction.name : 'Неизвестно'}</span>
                          </div>
                        );
                      }
                      return (
                        <div key={k} className="flex justify-between text-sm">
                          <span className="text-stone-400">{k}:</span>
                          <span className="text-stone-200">{String(v)}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
                
                {currentLevel !== 'planet' && selectedNode.type !== 'hex' && (
                  <button 
                    onClick={() => handleNodeDoubleClick(selectedNode)}
                    className="w-full bg-stone-800 hover:bg-stone-700 text-white py-2 rounded-xl transition-colors mt-4"
                  >
                    {t.map_enter} {selectedNode.type === 'galaxy' ? 'Galaxy' : selectedNode.type === 'system' ? 'System' : 'Planet'}
                  </button>
                )}
                
                <button 
                  onClick={async () => {
                    try {
                      const entities = await api.getEntities();
                      const exists = entities.find((e: any) => e.id === selectedNode.id);
                      if (!exists) {
                        await api.saveEntity({
                          id: selectedNode.id,
                          type: 'location',
                          name: selectedNode.name,
                          description: `A ${selectedNode.type} on the map.`,
                          tags: selectedNode.type
                        });
                      }
                      window.dispatchEvent(new CustomEvent('navigate', { detail: { tab: 'wiki', entityId: selectedNode.id } }));
                    } catch (e) {
                      console.error("Failed to open in wiki", e);
                    }
                  }}
                  className="w-full bg-emerald-900/30 hover:bg-emerald-900/50 text-emerald-400 py-2 rounded-xl transition-colors mt-2 flex items-center justify-center"
                >
                  <Book size={16} className="mr-2" /> {t.map_open_wiki}
                </button>
              </>
            )}
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-stone-500">
            <MapPin size={48} className="mb-4 opacity-20" />
            <p className="text-center">{t.map_select_node}</p>
          </div>
        )}
      </div>
    </div>
  );
};
