import React, { useState, useEffect, useRef } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { useUndo } from '../contexts/UndoContext';
import { usePlayerMode } from '../contexts/PlayerModeContext';
import { api } from '../api';
import { ArrowLeft, Plus, MapPin, Edit2, Save, X, Trash2, Book, Image as ImageIcon, Sparkles, EyeOff } from 'lucide-react';
import { MarkdownRenderer } from './MarkdownRenderer';

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

import { SectionHelp } from './SectionHelp';

export const MapView = () => {
  const { t } = useLanguage();
  const { addUndo } = useUndo();
  const { isPlayerMode } = usePlayerMode();
  const [currentLevel, setCurrentLevel] = useState<string>('universe');
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
  const [allEntities, setAllEntities] = useState<any[]>([]);
  const [linkedEntities, setLinkedEntities] = useState<any[]>([]);
  const [isLinking, setIsLinking] = useState(false);
  const [showPins, setShowPins] = useState(true);
  const [isGeneratingLocs, setIsGeneratingLocs] = useState(false);
  
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const imageWrapperRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const fetchVersion = useRef(0);

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
    loadFactionsAndEntities();
    setTransform({ x: 0, y: 0, scale: 1 });
    if (currentNode && currentLevel === 'planet') {
      setGridWidthState(currentNode.data?.gridWidth || 15);
      setGridHeightState(currentNode.data?.gridHeight || 10);
    }
  }, [currentLevel, currentNode?.id]);

  useEffect(() => {
    const processNavigationDetail = async (detail: any) => {
      if (detail?.mapNodeId) {
        try {
          const targetNode = await api.getMapNode(detail.mapNodeId);
          if (targetNode) {
             const parentId = targetNode.parent_id;
             if (parentId) {
               const parentNode = await api.getMapNode(parentId);
               let level = 'universe';
               if (parentNode.type === 'galaxy') level = 'galaxy';
               if (parentNode.type === 'system') level = 'system';
               if (parentNode.type === 'planet') level = 'planet';
               if (parentNode.type === 'pin' || parentNode.type === 'location' || parentNode.type === 'settlement') level = 'customMap';
               
               setCurrentLevel(level);
               setCurrentNode(parentNode);
               setTimeout(() => {
                 setSelectedNode(targetNode);
                 setTransform({ x: -targetNode.x * 3 + 400, y: -targetNode.y * 3 + 300, scale: 3 });
               }, 500);
             } else {
               setCurrentLevel('universe');
               setCurrentNode(null);
               setSelectedNode(targetNode);
             }
          }
        } catch (err) {
          console.error("Failed to load map node for navigation", err);
        }
      }
    };

    if ((window as any).__lastNavigateDetail) {
      processNavigationDetail((window as any).__lastNavigateDetail);
      delete (window as any).__lastNavigateDetail;
    }

    const handleNavigate = (e: CustomEvent) => processNavigationDetail(e.detail);
    window.addEventListener('navigate', handleNavigate as EventListener);
    return () => window.removeEventListener('navigate', handleNavigate as EventListener);
  }, []);

  useEffect(() => {
    if (selectedNode) {
      setLinkedEntities(allEntities.filter(e => e.data?.locationId === selectedNode.id));
    } else {
      setLinkedEntities([]);
    }
  }, [selectedNode, allEntities]);

  const loadFactionsAndEntities = async () => {
    try {
      const entities = await api.getEntities();
      setAllEntities(entities);
      const factionEntities = entities.filter((e: any) => e.type === 'faction');
      setFactions(factionEntities);
    } catch (e) {
      console.error('Failed to load entities', e);
    }
  };

  const loadNodes = async () => {
    const currentVersion = ++fetchVersion.current;
    
    if (currentLevel === 'universe') {
      const data = await api.getMapNodes(undefined, 'galaxy');
      if (currentVersion !== fetchVersion.current) return;
      
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
        if (currentVersion !== fetchVersion.current) return;
        setNodes(newData);
      } else {
        setNodes(data);
      }
    } else if (currentNode) {
      if (currentNode.data?.image || currentLevel === 'customMap') {
        const data = await api.getMapNodes(currentNode.id, 'pin');
        if (currentVersion !== fetchVersion.current) return;
        setNodes(data);
      } else {
        const typeToFetch = currentLevel === 'galaxy' ? 'system' : currentLevel === 'system' ? 'planet' : 'hex';
        let data = await api.getMapNodes(currentNode.id, typeToFetch);
        if (currentVersion !== fetchVersion.current) return;
        // Also fetch pins for any level that isn't a custom image (which only has pins)
        if (currentLevel !== 'planet') {
           const pins = await api.getMapNodes(currentNode.id, 'pin');
           if (currentVersion !== fetchVersion.current) return;
           data = [...data, ...pins];
        } else if (currentLevel === 'planet' && !currentNode.data?.image) {
            // Can a planet have pins on top of hexes? No, hex logic handles content. Let's keep it clean.
        }
        setNodes(data);
      }
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
    
    // We treat pins just like other containers if they have an image or we want to allow going inside them.
    if (node.type === 'pin' || node.type === 'location' || node.type === 'settlement') {
        const linkedEntity = allEntities.find(e => e.data?.locationId === node.id);
        
        // If it has its own map image, we drop into it
        if (node.data?.image) {
            setNodeHistory([...nodeHistory, { node: currentNode, levelMode: currentLevel }]);
            // We use 'customMap' level mode for custom image rendering
            setCurrentLevel('customMap'); 
            setCurrentNode(node);
        } else if (linkedEntity) {
            // If no map but has entity, open wiki
            window.dispatchEvent(new CustomEvent('navigate', { detail: { tab: 'wiki', entityId: linkedEntity.id, search: linkedEntity.name } }));
        }
        return;
    }

    if (node.type === 'galaxy') {
      setNodeHistory([...nodeHistory, { node: currentNode, levelMode: currentLevel }]);
      setCurrentLevel('galaxy');
      setCurrentNode(node);
    } else if (node.type === 'system') {
      setNodeHistory([...nodeHistory, { node: currentNode, levelMode: currentLevel }]);
      setCurrentLevel('system');
      setCurrentNode(node);
    } else if (node.type === 'planet') {
      setNodeHistory([...nodeHistory, { node: currentNode, levelMode: currentLevel }]);
      setCurrentLevel('planet');
      setCurrentNode(node);
    }
    setSelectedNode(null);
  };

  const handleBack = () => {
    const prevNodeEntry = nodeHistory[nodeHistory.length - 1];
    setNodeHistory(nodeHistory.slice(0, -1));
    
    if (prevNodeEntry && prevNodeEntry.levelMode) {
      setCurrentLevel(prevNodeEntry.levelMode);
      setCurrentNode(prevNodeEntry.node);
    } else {
      // Fallback to legacy history
      const prevNode = prevNodeEntry;
      if (currentLevel === 'planet') {
        setCurrentLevel('system');
        setCurrentNode(prevNode);
      } else if (currentLevel === 'system') {
        setCurrentLevel('galaxy');
        setCurrentNode(prevNode);
      } else if (currentLevel === 'galaxy') {
        setCurrentLevel('universe');
        setCurrentNode(prevNode);
      } else {
        setCurrentLevel('universe');
        setCurrentNode(null);
      }
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

  const handleMapClick = async (e: React.MouseEvent, xPercent: number, yPercent: number) => {
    if (!isEditing || !placementMode) return;
    
    const newNode = {
      parent_id: currentNode?.id,
      type: 'pin',
      name: `New Pin`,
      x: xPercent,
      y: yPercent,
      data: { 
        color: '#10b981', 
        size: 20 
      }
    };
    
    const res = await api.saveMapNode(newNode);
    if (res.id) {
      await api.saveEntity({
        id: res.id,
        type: 'location',
        name: newNode.name,
        description: 'A pin on the map.',
        tags: 'pin'
      });
    }
    
    setPlacementMode(false);
    loadNodes();
  };

  const handleGenerateLocations = async (node: any) => {
    setIsGeneratingLocs(true);
    try {
      const prompt = `Сгенерируй 2-3 интересные под-локации или точки интереса (POI) внутри локации "${node.name}" (Тип: ${node.type}).
Опиши их кратко и атмосферно (1 абзац на каждую) на русском языке.
ТЫ ОБЯЗАН вывести JSON блок в конце ответа для добавления их на карту.
JSON блок должен содержать массив 'map_nodes', где для каждого элемента 'parent_id' строго равен "${node.id}", 'type' равен "pin", а внутри 'data' цвет метки (например "#10b981"). А также создай массив 'entities' с типом "location", чтобы привязать к ним лор, используя те же 'id'. Формат:
\`\`\`json
{
  "map_nodes": [...],
  "entities": [...]
}
\`\`\`
Остальной текст ответа - просто красивое литературное описание этих мест для Мастера.`;
      const reply = await api.chat([{ role: 'user', content: prompt }]);
      alert("Генерация завершена!\n\n" + reply);
      loadNodes(); // Refresh to show new pins
    } catch (e: any) {
      console.error(e);
      alert("Ошибка при генерации: " + e.message);
    } finally {
      setIsGeneratingLocs(false);
    }
  };

  const handleSvgClick = async (e: React.MouseEvent) => {
    if (!isEditing || !placementMode || !svgRef.current) return;
    
    const svg = svgRef.current;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const svgP = pt.matrixTransform(svg.getScreenCTM()?.inverse());

    // By default, add typical level node. But if holding Shift or we add a switch, we could add pin.
    // However we'll just add pins on galaxies / systems as type "pin". Let's say if we are placing in universe, galaxy, system
    const type = currentLevel === 'universe' ? 'galaxy' : currentLevel === 'galaxy' ? 'system' : currentLevel === 'system' ? 'planet' : 'hex';
    
    if (type === 'hex' && currentLevel !== 'customMap') {
      // Don't allow free placement of hexes, they are generated via grid
      setPlacementMode(false);
      return;
    }

    const newNode = {
      parent_id: currentNode?.id,
      type: currentNode?.data?.image ? 'pin' : (currentLevel === 'customMap' ? 'pin' : type),
      name: `${t.map_new} ${currentNode?.data?.image ? 'Pin' : type}`,
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
        description: `A ${newNode.type} on the map.`,
        tags: newNode.type
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
      const nodeToDelete = nodes.find(n => n.id === selectedNode.id);
      await api.deleteMapNode(selectedNode.id);
      
      if (nodeToDelete) {
        addUndo(`Удаление метки "${nodeToDelete.name}"`, async () => {
          await api.saveMapNode(nodeToDelete);
          loadNodes();
        });
      }
      
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

    if (!isEditing || !draggingNodeId) return;
    
    // Custom map draggable logic (Percentage-based)
    if (currentNode?.data?.image && imageWrapperRef.current) {
      const rect = imageWrapperRef.current.getBoundingClientRect();
      // rect includes scale since the wrapper has transform scale applied
      // But we just need relative mouse position compared to the unscaled dimensions?
      // Actually boundingClientRect provides dimensions matching the scaled size.
      // So e.clientX - rect.left is exactly how many screen pixels from the left.
      // E.g., if we want percentage, it's just that difference divided by rect.width!
      const newX = ((e.clientX - rect.left) / rect.width) * 100;
      const newY = ((e.clientY - rect.top) / rect.height) * 100;
      
      setNodes(nodes.map(n => {
        if (n.id === draggingNodeId) {
          const updated = { ...n, x: newX, y: newY };
          setEditForm(updated);
          return updated;
        }
        return n;
      }));
      return;
    }

    // Standard SVG draggable logic (Coordinate-based)
    if (!svgRef.current) return;
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
    } else if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
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

  const visibleNodes = nodes.filter(n => !(isPlayerMode && n.is_secret));

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
            {visibleNodes.map(node => node.data?.image && (
              <clipPath id={`hex-clip-${node.id}`} key={`clip-${node.id}`}>
                <polygon points={Array.from({length: 6}).map((_, i) => {
                  const angle_rad = Math.PI / 180 * (60 * i - 30);
                  return `${hexRadius * Math.cos(angle_rad)},${hexRadius * Math.sin(angle_rad)}`;
                }).join(' ')} />
              </clipPath>
            ))}
          </defs>

          {visibleNodes.map(node => {
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
            const hasLinkedEntities = allEntities.some(e => e.data?.locationId === node.id);

            return (
              <g 
                key={node.id}
                onClick={(e) => { e.stopPropagation(); handleNodeClick(node); }}
                onDoubleClick={(e) => { e.stopPropagation(); handleNodeDoubleClick(node); }}
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
                {hasLinkedEntities && (
                  <circle cx={cx} cy={cy} r={4} fill="#10b981" stroke="#1c1917" strokeWidth="1" />
                )}
              </g>
            );
          })}
        </g>
      </svg>
    );
  };

  const renderSpace = () => {
    if (currentNode?.data?.image) {
      return (
        <div 
          ref={containerRef}
          className="w-full h-full relative overflow-hidden bg-stone-950 cursor-grab active:cursor-grabbing text-center whitespace-nowrap"
          onMouseDown={(e) => handleMouseDown(e)}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onWheel={handleWheel}
        >
          <div 
            ref={imageWrapperRef}
            style={{ 
              transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
              transformOrigin: '0 0',
              display: 'inline-block'
            }}
            className="relative align-top"
            onClick={(e) => {
              if (placementMode && imageWrapperRef.current) {
                 e.stopPropagation();
                 const rect = imageWrapperRef.current.getBoundingClientRect();
                 const xPercent = ((e.clientX - rect.left) / rect.width) * 100;
                 const yPercent = ((e.clientY - rect.top) / rect.height) * 100;
                 handleMapClick(e, xPercent, yPercent);
              }
            }}
          >
            <img 
              key={`img-${currentNode.id}`}
              src={currentNode.data.image} 
              alt={currentNode.name} 
              className="max-w-[4000px] max-h-[4000px] pointer-events-none align-top"
              style={{ minWidth: '300px', minHeight: '300px' }}
              draggable={false}
            />
            {showPins && visibleNodes.map(node => (
              <div
                key={node.id}
                style={{
                  position: 'absolute',
                  left: `${node.x}%`,
                  top: `${node.y}%`,
                  transform: `translate(-50%, -100%) scale(${1 / transform.scale})`
                }}
                className={`cursor-pointer absolute group flex flex-col items-center ${selectedNode?.id === node.id ? 'z-20' : 'z-10'}`}
                onClick={(e) => { e.stopPropagation(); handleNodeClick(node); }}
                onDoubleClick={(e) => { e.stopPropagation(); handleNodeDoubleClick(node); }}
                onMouseDown={(e) => handleMouseDown(e as any, node)}
              >
                <div className={`p-1 rounded-full ${selectedNode?.id === node.id ? 'bg-emerald-500 text-stone-900 border-stone-900' : 'bg-stone-900 text-emerald-500 border-emerald-500'} border-2 shadow-lg transition-colors`}>
                  <MapPin size={24} />
                </div>
                <div className="mt-1 px-2 py-1 bg-stone-900/90 text-stone-200 text-xs rounded border border-stone-700 opacity-0 group-hover:opacity-100 transition-opacity whitespace-normal shadow-xl">
                  {node.name}
                </div>
              </div>
            ))}
          </div>
        </div>
      );
    }

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
            {visibleNodes.map(node => node.data?.image && (
              <clipPath id={`clip-${node.id}`} key={`clip-${node.id}`}>
                <circle r={node.data?.size || (currentLevel === 'universe' ? 15 : 25)} />
              </clipPath>
            ))}
          </defs>

          {/* Stars background */}
          {Array.from({ length: 100 }).map((_, i) => (
            <circle key={i} cx={Math.random() * 800} cy={Math.random() * 600} r={Math.random() * 1.5} fill="#fff" opacity={Math.random()} />
          ))}
          
          {visibleNodes.map(node => {
            const size = node.data?.size || (currentLevel === 'universe' ? 15 : 25);
            const color = node.data?.color || (currentLevel === 'universe' ? '#fbbf24' : '#3b82f6');
            const isSelected = selectedNode?.id === node.id;
            const hasLinkedEntities = allEntities.some(e => e.data?.locationId === node.id);

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
                
                {hasLinkedEntities && (
                  <circle cx={size * 0.7} cy={-size * 0.7} r={4} fill="#10b981" stroke="#1c1917" strokeWidth="1" />
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
          {currentLevel === 'planet' && !currentNode?.data?.image && !isPlayerMode && (
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
          {currentLevel !== 'planet' && currentLevel !== 'customMap' && !currentNode?.data?.image && isEditing && (
            <button 
              onClick={() => setPlacementMode(!placementMode)} 
              className={`${placementMode ? 'bg-emerald-500' : 'bg-emerald-600 hover:bg-emerald-500'} text-white p-2 rounded-xl flex items-center transition-colors`}
            >
              <Plus size={20} className="md:mr-2" /> <span className="hidden md:inline">{placementMode ? t.map_click_to_place : `${t.map_add} ${currentLevel === 'universe' ? 'Galaxy' : currentLevel === 'galaxy' ? 'System' : 'Planet'}`}</span>
            </button>
          )}
          {currentNode?.data?.image && (
            <button 
              onClick={() => setShowPins(!showPins)} 
              className={`${showPins ? 'bg-stone-700' : 'bg-stone-800'} hover:bg-stone-600 text-white p-2 rounded-xl flex items-center transition-colors`}
            >
              <MapPin size={20} className="md:mr-2" /> <span className="hidden md:inline">{showPins ? 'Hide Pins' : 'Show Pins'}</span>
            </button>
          )}
          {currentNode?.data?.image && isEditing && (
            <button 
              onClick={() => setPlacementMode(!placementMode)} 
              className={`${placementMode ? 'bg-emerald-500' : 'bg-emerald-600 hover:bg-emerald-500'} text-white p-2 rounded-xl flex items-center transition-colors`}
            >
              <Plus size={20} className="md:mr-2" /> <span className="hidden md:inline">{placementMode ? 'Click to place pin' : 'Add Pin'}</span>
            </button>
          )}
          {!isPlayerMode && (
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
          )}
        </div>
        
        <div className="flex-1 overflow-hidden bg-stone-950">
          {currentLevel === 'planet' && !currentNode?.data?.image ? renderHexGrid() : renderSpace()}
        </div>
      </div>

      {/* Sidebar Info */}
      <div className="w-full md:w-80 bg-stone-900 border-t md:border-t-0 md:border-l border-stone-800 p-6 flex flex-col h-[50vh] md:h-full overflow-y-auto">
        <h3 className="text-xl font-bold text-stone-100 mb-4 flex items-center">
          {currentLevel === 'universe' ? t.map_universe_map : `${currentNode?.name} ${t.map_map}`}
          <SectionHelp content={
            <>
              <h3 className="text-xl font-bold text-emerald-400 mb-4">Справка по Карте</h3>
              <p>Интерактивная карта поддерживает макро-уровень (галактики и системы) и микро-уровень (планеты, локации, собственные карты).</p>
              <ul className="list-disc list-inside space-y-2 mt-2">
                <li><strong>Уровни навигации:</strong> Двойной клик по объекту (или одиночный по пину) приближает вас в этот объект (из Галактики -&gt; в Систему -&gt; на Планету). Для возврата используйте стрелку назад или клик по пустому месту (по умолчанию).</li>
                <li><strong>Секретные локации:</strong> Можно сделать ноду карты "Секретной" в режиме редактирования. Это скроет её в Режиме Игрока.</li>
                <li><strong>Свои картинки:</strong> В режиме редактирования, при выборе планеты или системы, можно вставить URL картинки, чтобы использовать её как карту (Battlemap).</li>
                <li><strong>Создание:</strong> Нажмите на карандаш (✏️), чтобы включить режим редактирования. Появятся кнопки добавления объектов.</li>
              </ul>
            </>
          } />
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

                  <button
                    onClick={() => setEditForm({...editForm, is_secret: !editForm.is_secret})}
                    className={`w-full flex items-center justify-center p-2 rounded-lg transition-colors border ${editForm.is_secret ? 'bg-amber-500/20 text-amber-500 border-amber-500/30' : 'bg-stone-900 text-stone-500 border-stone-800 hover:text-stone-400'}`}
                  >
                    <EyeOff size={18} className="mr-2" />
                    {editForm.is_secret ? 'Секретная метка (только GM)' : 'Доступно игрокам'}
                  </button>
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
                <div className="flex justify-between items-start">
                  <div>
                    <h4 className="text-emerald-400 font-bold text-lg">{selectedNode.name}</h4>
                    <div className="flex gap-2 items-center mt-1">
                      <span className="text-xs font-mono text-stone-500 uppercase">{selectedNode.type}</span>
                      {selectedNode.is_secret && (
                        <span className="flex items-center text-[10px] font-bold bg-amber-500/20 text-amber-500 px-1.5 py-0.5 rounded uppercase">
                          <EyeOff size={10} className="mr-1" />
                          Секретно
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                
                <div className="text-stone-300 text-sm whitespace-pre-wrap">
                  {selectedNode.description ? (
                    <MarkdownRenderer>
                      {selectedNode.description}
                    </MarkdownRenderer>
                  ) : (
                    t.map_no_description
                  )}
                </div>
                
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
                
                {((currentLevel !== 'planet' && currentLevel !== 'customMap' && selectedNode.type !== 'hex') || selectedNode.data?.image) && (
                  <button 
                    onClick={() => handleNodeDoubleClick(selectedNode)}
                    className="w-full bg-stone-800 hover:bg-stone-700 text-white py-2 rounded-xl transition-colors mt-4"
                  >
                    {t.map_enter} {selectedNode.type === 'galaxy' ? 'Galaxy' : selectedNode.type === 'system' ? 'System' : selectedNode.type === 'planet' ? 'Planet' : 'Map'}
                  </button>
                )}

                {!isPlayerMode && (
                  <button 
                    onClick={() => handleGenerateLocations(selectedNode)}
                    disabled={isGeneratingLocs}
                    className="w-full bg-indigo-900/30 hover:bg-indigo-900/50 text-indigo-400 py-2 rounded-xl transition-colors mt-2 flex items-center justify-center disabled:opacity-50"
                    title="ИИ: Сгенерировать дочерние сущности/пины внутри"
                  >
                    <Sparkles size={16} className={`mr-2 ${isGeneratingLocs ? 'animate-pulse' : ''}`} /> 
                    ИИ: Наполнить локацию
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

                {/* Linked Entities Section */}
                <div className="mt-6 border-t border-stone-800 pt-4">
                  <div className="flex justify-between items-center mb-3">
                    <h5 className="text-sm font-bold text-stone-300">Сущности в этой локации</h5>
                    <button 
                      onClick={() => setIsLinking(!isLinking)}
                      className="text-xs bg-stone-800 hover:bg-stone-700 text-stone-300 px-2 py-1 rounded transition-colors"
                    >
                      {isLinking ? 'Отмена' : 'Привязать'}
                    </button>
                  </div>
                  
                  {isLinking && (
                    <div className="mb-4">
                      <select 
                        className="w-full bg-stone-950 border border-stone-800 rounded-lg px-3 py-2 text-sm text-stone-300 outline-none"
                        onChange={async (e) => {
                          const entityId = e.target.value;
                          if (!entityId) return;
                          const entity = allEntities.find(ent => ent.id === entityId);
                          if (entity) {
                            const updatedEntity = {
                              ...entity,
                              data: { ...(entity.data || {}), locationId: selectedNode.id }
                            };
                            await api.saveEntity(updatedEntity);
                            setIsLinking(false);
                            loadFactionsAndEntities();
                          }
                        }}
                        value=""
                      >
                        <option value="" disabled>Выберите сущность...</option>
                        {allEntities.filter(e => e.id !== selectedNode.id && e.data?.locationId !== selectedNode.id).map(e => (
                          <option key={e.id} value={e.id}>{e.name} ({e.type})</option>
                        ))}
                      </select>
                    </div>
                  )}

                  <div className="space-y-2">
                    {linkedEntities.length === 0 ? (
                      <p className="text-xs text-stone-500 italic">Нет привязанных сущностей</p>
                    ) : (
                      linkedEntities.map(entity => (
                        <div key={entity.id} className="flex justify-between items-center bg-stone-950 p-2 rounded-lg border border-stone-800">
                          <div 
                            className="flex items-center gap-2 cursor-pointer hover:text-emerald-400 transition-colors"
                            onClick={() => window.dispatchEvent(new CustomEvent('navigate', { detail: { tab: 'wiki', entityId: entity.id } }))}
                          >
                            {entity.image && <img src={entity.image} alt={entity.name} className="w-6 h-6 rounded-full object-cover" />}
                            <span className="text-sm font-medium text-stone-300">{entity.name}</span>
                          </div>
                          <button 
                            onClick={async () => {
                              const updatedEntity = {
                                ...entity,
                                data: { ...entity.data }
                              };
                              delete updatedEntity.data.locationId;
                              await api.saveEntity(updatedEntity);
                              loadFactionsAndEntities();
                            }}
                            className="text-stone-500 hover:text-red-400 p-1 transition-colors"
                            title="Отвязать"
                          >
                            <X size={14} />
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </div>
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
