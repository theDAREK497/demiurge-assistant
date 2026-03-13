import express from 'express';
import { db } from '../db/index.js';
import crypto from 'crypto';
import multer from 'multer';
import path from 'path';

const router = express.Router();

const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    cb(null, path.join(process.cwd(), 'public', 'uploads'))
  },
  filename: function (req, file, cb) {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9)
    cb(null, uniqueSuffix + path.extname(file.originalname))
  }
});

const upload = multer({ storage: storage });

router.post('/upload', upload.single('image'), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: 'No file uploaded' });
  }
  const url = `/uploads/${req.file.filename}`;
  res.json({ url });
});

router.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

// Settings
router.get('/settings/:key', (req, res) => {
  const stmt = db.prepare('SELECT value FROM settings WHERE key = ?');
  const row = stmt.get(req.params.key) as any;
  res.json({ value: row ? row.value : null });
});

router.post('/settings', (req, res) => {
  const { key, value } = req.body;
  const stmt = db.prepare('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)');
  stmt.run(key, value);
  res.json({ success: true });
});

// Universes
router.get('/universes', (req, res) => {
  const stmt = db.prepare('SELECT * FROM universes ORDER BY created_at DESC');
  res.json(stmt.all());
});

router.post('/universes', (req, res) => {
  const { id, name, description } = req.body;
  const stmt = db.prepare('INSERT OR REPLACE INTO universes (id, name, description) VALUES (?, ?, ?)');
  const newId = id || crypto.randomUUID();
  stmt.run(newId, name, description || '');
  res.json({ success: true, id: newId });
});

router.delete('/universes/:id', (req, res) => {
  const { id } = req.params;
  
  db.transaction(() => {
    db.prepare('DELETE FROM universes WHERE id = ?').run(id);
    db.prepare('DELETE FROM entities WHERE universe_id = ?').run(id);
    db.prepare('DELETE FROM events WHERE universe_id = ?').run(id);
    db.prepare('DELETE FROM map_nodes WHERE universe_id = ?').run(id);
    db.prepare('DELETE FROM random_tables WHERE universe_id = ?').run(id);
  })();

  res.json({ success: true });
});

router.post('/universes/seed', (req, res) => {
  const universeId = crypto.randomUUID();
  
  db.transaction(() => {
    // Create universe
    db.prepare('INSERT INTO universes (id, name, description) VALUES (?, ?, ?)').run(
      universeId, 
      'Млечный Путь (Sci-Fi)', 
      'Демонстрационная вселенная для демонстрации космических масштабов: от галактики до поверхности планет.'
    );

    // Entities
    const insertEntity = db.prepare('INSERT INTO entities (id, universe_id, type, name, description, tags, data) VALUES (?, ?, ?, ?, ?, ?, ?)');
    insertEntity.run(crypto.randomUUID(), universeId, 'location', 'Земля', 'Колыбель человечества, третья планета от Солнца.', 'planet, core, human', null);
    insertEntity.run(crypto.randomUUID(), universeId, 'location', 'Марс', 'Красная планета, первая колония человечества.', 'planet, colony', null);
    insertEntity.run(crypto.randomUUID(), universeId, 'location', 'Альфа Центавра', 'Ближайшая к Солнцу звездная система.', 'system, frontier', null);
    insertEntity.run(crypto.randomUUID(), universeId, 'npc', 'Джон Шепард', 'Легендарный капитан космического флота.', 'human, commander, hero', null);
    insertEntity.run(crypto.randomUUID(), universeId, 'npc', 'Эллен Рипли', 'Офицер безопасности, специалист по выживанию.', 'human, survivor', null);
    
    const uneId = crypto.randomUUID();
    const tfId = crypto.randomUUID();
    insertEntity.run(uneId, universeId, 'faction', 'Объединенные Нации Земли', 'Глобальное правительство человечества.', 'government, earth, order', JSON.stringify({ color: '#3b82f6' }));
    insertEntity.run(tfId, universeId, 'faction', 'Торговая Федерация', 'Межзвездный конгломерат корпораций.', 'corporate, wealth, neutral', JSON.stringify({ color: '#f59e0b' }));

    // Events
    const insertEvent = db.prepare('INSERT INTO events (id, universe_id, title, description, event_date, order_index) VALUES (?, ?, ?, ?, ?, ?)');
    insertEvent.run(crypto.randomUUID(), universeId, 'Первый контакт', 'Человечество впервые встретило внеземную цивилизацию.', '2157 CE', 2157);
    insertEvent.run(crypto.randomUUID(), universeId, 'Основание Федерации', 'Подписание договора о создании Торговой Федерации.', '2160 CE', 2160);

    // Map Nodes
    const insertMapNode = db.prepare('INSERT INTO map_nodes (id, universe_id, parent_id, type, name, description, x, y, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)');
    const galaxyId = crypto.randomUUID();
    insertMapNode.run(galaxyId, universeId, null, 'galaxy', 'Млечный Путь', 'Наша родная галактика.', 400, 300, JSON.stringify({ color: '#fbbf24', size: 15 }));
    
    const systemId = crypto.randomUUID();
    insertMapNode.run(systemId, universeId, galaxyId, 'system', 'Солнечная система', 'Дом человечества.', 400, 300, JSON.stringify({ color: '#3b82f6', size: 25 }));
    
    const earthId = crypto.randomUUID();
    insertMapNode.run(earthId, universeId, systemId, 'planet', 'Земля', 'Голубая планета.', 300, 300, JSON.stringify({ color: '#10b981', size: 20, gridWidth: 15, gridHeight: 10 }));
    insertMapNode.run(crypto.randomUUID(), universeId, systemId, 'planet', 'Марс', 'Красная планета.', 500, 300, JSON.stringify({ color: '#ef4444', size: 18, gridWidth: 15, gridHeight: 10 }));

    // Generate Hexes for Earth
    const hexRadius = 30;
    const hexWidth = Math.sqrt(3) * hexRadius;
    const hexHeight = 2 * hexRadius;
    
    const earthMap = [
      "SSSWWWWWSSSSSWW", // 0: Arctic
      "SSWWWWWWSSSPPWW", // 1: NA / Europe/Asia
      "WWFFPWWWWPPFFFW", // 2: NA / Europe/Asia
      "WFFPPMWWPPPPFFW", // 3: NA / Europe/Asia
      "WWPDDMWWWDPPPWW", // 4: Central Am / North Africa / Mid East
      "WWWFMWWWWDDDPWW", // 5: South Am / Africa
      "WWWFFWWWWWDPWWW", // 6: South Am / Africa
      "WWWWWWWWWWWWPWW", // 7: Ocean / Australia
      "WWWWWWWWWWWWWWW", // 8: Ocean
      "SSSSSSSSSSSSSSS"  // 9: Antarctica
    ];
    
    const charToBiome: Record<string, string> = {
      'W': 'water',
      'F': 'forest',
      'P': 'plains',
      'M': 'mountain',
      'D': 'desert',
      'S': 'winter'
    };
    
    for (let r = 0; r < 10; r++) {
      for (let q = 0; q < 15; q++) {
        const xOffset = (r % 2 === 1) ? (hexWidth / 2) : 0;
        const x = (q * hexWidth) + xOffset + 100;
        const y = (r * hexHeight * 0.75) + 100;
        
        const char = earthMap[r][q];
        const biome = charToBiome[char] || 'water';
        
        let factionId = null;
        let name = `Hex ${q},${r}`;
        
        // Assign UNE to NA (q:2-5, r:2-4) and Europe (q:9-11, r:1-3)
        if (biome !== 'water' && biome !== 'winter') {
            if ((q >= 2 && q <= 5 && r >= 2 && r <= 4) || (q >= 9 && q <= 11 && r >= 1 && r <= 3)) {
                factionId = uneId;
                name = "Территория ОНЗ";
            }
            // Assign TF to Africa/Asia (q:9-13, r:4-6)
            else if (q >= 9 && q <= 13 && r >= 4 && r <= 6) {
                factionId = tfId;
                name = "Зона Торговой Федерации";
            }
        }
        
        insertMapNode.run(
          crypto.randomUUID(),
          universeId,
          earthId,
          'hex',
          name,
          '',
          x,
          y,
          JSON.stringify({ biome: biome, q, r, faction: factionId })
        );
      }
    }

    // Random Tables
    const insertRandomTable = db.prepare('INSERT INTO random_tables (id, universe_id, name, description, type, rollType, entries, conditions) VALUES (?, ?, ?, ?, ?, ?, ?, ?)');
    insertRandomTable.run(
      crypto.randomUUID(),
      universeId,
      'Случайная находка на орбите',
      'Что можно найти сканируя орбиту неизвестной планеты.',
      'general',
      'weight',
      JSON.stringify([
        { weight: 2, result: 'Космический мусор (обломки старых спутников)' },
        { weight: 1, result: 'Заброшенный спасательный модуль' },
        { weight: 1, result: 'Астероид с редкими минералами' },
        { weight: 1, result: 'Древний инопланетный зонд' },
        { weight: 3, result: 'Ничего интересного, только пыль' }
      ]),
      JSON.stringify([])
    );

    insertRandomTable.run(
      crypto.randomUUID(),
      universeId,
      'Случайная встреча на поверхности',
      'Кто или что может встретиться при исследовании планеты.',
      'encounter',
      'dice',
      JSON.stringify([
        { result: 'Группа агрессивных местных хищников' },
        { result: 'Патруль Торговой Федерации' },
        { result: 'Мирные исследователи или ученые' },
        { result: 'Поврежденный дрон-разведчик' },
        { result: 'Засада космических пиратов' },
        { result: 'Странная аномалия, искажающая гравитацию' }
      ]),
      JSON.stringify([{ type: 'location', value: 'Земля' }])
    );
  })();

  res.json({ success: true, id: universeId });
});

// Entities
router.get('/entities', (req, res) => {
  const { universe_id } = req.query;
  const stmt = db.prepare('SELECT * FROM entities WHERE universe_id = ? ORDER BY updated_at DESC');
  res.json(stmt.all(universe_id));
});

router.post('/entities', (req, res) => {
  const { id, universe_id, type, name, description, tags, image, data } = req.body;
  const newId = id || crypto.randomUUID();
  const stmt = db.prepare('INSERT OR REPLACE INTO entities (id, universe_id, type, name, description, tags, image, data, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)');
  stmt.run(newId, universe_id, type, name, description, tags, image || null, data ? JSON.stringify(data) : null);
  res.json({ success: true, id: newId });
});

router.delete('/entities/:id', (req, res) => {
  const stmt = db.prepare('DELETE FROM entities WHERE id = ?');
  stmt.run(req.params.id);
  res.json({ success: true });
});

// Timeline Events
router.get('/events', (req, res) => {
  const { universe_id } = req.query;
  const stmt = db.prepare('SELECT * FROM events WHERE universe_id = ? ORDER BY order_index ASC, event_date ASC');
  res.json(stmt.all(universe_id));
});

router.post('/events', (req, res) => {
  const { id, universe_id, title, description, event_date, order_index } = req.body;
  const stmt = db.prepare('INSERT OR REPLACE INTO events (id, universe_id, title, description, event_date, order_index) VALUES (?, ?, ?, ?, ?, ?)');
  stmt.run(id || crypto.randomUUID(), universe_id, title, description, event_date, order_index || 0);
  res.json({ success: true });
});

router.delete('/events/:id', (req, res) => {
  const stmt = db.prepare('DELETE FROM events WHERE id = ?');
  stmt.run(req.params.id);
  res.json({ success: true });
});

// Map Nodes
router.get('/map-nodes', (req, res) => {
  const { universe_id, parent_id, type } = req.query;
  let query = 'SELECT * FROM map_nodes WHERE universe_id = ?';
  const params: any[] = [universe_id];
  
  if (parent_id) {
    query += ' AND parent_id = ?';
    params.push(parent_id);
  } else if (type === 'galaxy') {
    query += ' AND type = ?';
    params.push('galaxy');
  }
  
  const stmt = db.prepare(query);
  const nodes = stmt.all(...params).map((n: any) => ({
    ...n,
    data: n.data ? JSON.parse(n.data) : {}
  }));
  res.json(nodes);
});

router.post('/map-nodes', (req, res) => {
  const { id, universe_id, parent_id, type, name, description, x, y, data } = req.body;
  const newId = id || crypto.randomUUID();
  const stmt = db.prepare('INSERT OR REPLACE INTO map_nodes (id, universe_id, parent_id, type, name, description, x, y, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)');
  stmt.run(newId, universe_id, parent_id || null, type, name, description || '', x || 0, y || 0, JSON.stringify(data || {}));
  res.json({ success: true, id: newId });
});

router.post('/map-nodes/bulk', (req, res) => {
  const { nodes, universe_id } = req.body;
  
  db.transaction(() => {
    const stmt = db.prepare('INSERT OR REPLACE INTO map_nodes (id, universe_id, parent_id, type, name, description, x, y, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)');
    for (const node of nodes) {
      const newId = node.id || crypto.randomUUID();
      stmt.run(newId, universe_id, node.parent_id || null, node.type, node.name, node.description || '', node.x || 0, node.y || 0, JSON.stringify(node.data || {}));
    }
  })();
  
  res.json({ success: true });
});

router.delete('/map-nodes/:id', (req, res) => {
  const deleteRecursive = (id: string) => {
    const children = db.prepare('SELECT id FROM map_nodes WHERE parent_id = ?').all(id) as {id: string}[];
    for (const child of children) {
      deleteRecursive(child.id);
    }
    db.prepare('DELETE FROM map_nodes WHERE id = ?').run(id);
  };
  
  deleteRecursive(req.params.id);
  res.json({ success: true });
});

// Random Tables
router.get('/random-tables', (req, res) => {
  const { universe_id } = req.query;
  const stmt = db.prepare('SELECT * FROM random_tables WHERE universe_id = ? ORDER BY created_at DESC');
  const tables = stmt.all(universe_id).map((t: any) => ({
    ...t,
    entries: t.entries ? JSON.parse(t.entries) : [],
    conditions: t.conditions ? JSON.parse(t.conditions) : []
  }));
  res.json(tables);
});

router.post('/random-tables', (req, res) => {
  const { id, universe_id, name, description, type, rollType, entries, conditions } = req.body;
  const stmt = db.prepare('INSERT OR REPLACE INTO random_tables (id, universe_id, name, description, type, rollType, entries, conditions) VALUES (?, ?, ?, ?, ?, ?, ?, ?)');
  stmt.run(
    id || crypto.randomUUID(), 
    universe_id, 
    name, 
    description || '', 
    type || 'general', 
    rollType || 'weight',
    JSON.stringify(entries || []), 
    JSON.stringify(conditions || [])
  );
  res.json({ success: true });
});

router.delete('/random-tables/:id', (req, res) => {
  const stmt = db.prepare('DELETE FROM random_tables WHERE id = ?');
  stmt.run(req.params.id);
  res.json({ success: true });
});

// Chat / LLM Proxy
router.post('/chat', async (req, res) => {
  try {
    const { messages, universe_id } = req.body;
    
    const endpointStmt = db.prepare("SELECT value FROM settings WHERE key = 'llm_endpoint'");
    const endpointRow = endpointStmt.get() as any;
    const endpoint = endpointRow?.value || 'http://localhost:1234/v1';

    const modelStmt = db.prepare("SELECT value FROM settings WHERE key = 'llm_model'");
    const modelRow = modelStmt.get() as any;
    const model = modelRow?.value || 'local-model';

    // Fetch current universe context
    let contextStr = '';
    if (universe_id) {
      const entities = db.prepare('SELECT id, type, name, description, tags FROM entities WHERE universe_id = ?').all(universe_id);
      const events = db.prepare('SELECT id, title, description, event_date FROM events WHERE universe_id = ? ORDER BY order_index ASC').all(universe_id);
      const mapNodes = db.prepare('SELECT id, parent_id, type, name, description FROM map_nodes WHERE universe_id = ?').all(universe_id);
      
      contextStr = `\n\nCURRENT UNIVERSE CONTEXT:\n`;
      if (entities.length > 0) {
        contextStr += `Entities:\n${JSON.stringify(entities, null, 2)}\n`;
      }
      if (events.length > 0) {
        contextStr += `Events:\n${JSON.stringify(events, null, 2)}\n`;
      }
      if (mapNodes.length > 0) {
        contextStr += `Map Nodes (Galaxies, Systems, Planets):\n${JSON.stringify(mapNodes, null, 2)}\n`;
      }
    }

    // We instruct the LLM to output JSON if it extracts entities
    const systemPrompt = `You are a worldbuilding assistant. You help the user flesh out their world.
You have access to the current state of the user's universe. Use this context to answer questions and generate consistent ideas.
${contextStr}

If the user provides information about NEW characters, locations, items, factions, events, or map nodes (galaxies, systems, planets), you should extract this information and return it in a JSON block at the end of your response.
For any NEW item, generate a random UUID for its "id" field. If it's a map node that belongs to another node, use the parent's id in the "parent_id" field.
Format the JSON block exactly like this:
\`\`\`json
{
  "entities": [
    { "id": "a1b2c3d4-...", "type": "npc", "name": "John Doe", "description": "A brave warrior", "tags": "human, warrior" }
  ],
  "events": [
    { "id": "e5f6g7h8-...", "title": "The Great War", "description": "A war that lasted 100 years", "event_date": "Year 1000", "order_index": 1000 }
  ],
  "map_nodes": [
    { "id": "i9j0k1l2-...", "parent_id": "parent_id_or_null", "type": "planet", "name": "Earth", "description": "A blue planet", "x": 400, "y": 300, "data": { "color": "#3b82f6", "size": 25 } }
  ]
}
\`\`\`
Valid entity types are: npc, enemy, item, location, country, faction, settlement, pc, event.
Valid map_node types are: galaxy, system, planet.
If there are no new entities, events, or map nodes to extract, just respond normally without the JSON block.`;

    const fullMessages = [
      { role: 'system', content: systemPrompt },
      ...messages
    ];

    const response = await fetch(`${endpoint}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: model,
        messages: fullMessages,
        temperature: 0.7
      })
    });

    if (!response.ok) {
      throw new Error(`LLM Error: ${response.statusText}`);
    }

    const data = await response.json();
    const reply = data.choices[0].message.content;
    let displayReply = reply;

    // Parse JSON block if exists
    const jsonMatch = reply.match(/\`\`\`json\n([\s\S]*?)\n\`\`\`/);
    if (jsonMatch) {
      try {
        const extracted = JSON.parse(jsonMatch[1]);
        if (extracted.entities && Array.isArray(extracted.entities)) {
          const stmt = db.prepare('INSERT OR REPLACE INTO entities (id, universe_id, type, name, description, tags, updated_at) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)');
          const insertMany = db.transaction((entities) => {
            for (const ent of entities) {
              stmt.run(ent.id || crypto.randomUUID(), universe_id, ent.type, ent.name, ent.description, ent.tags || '');
            }
          });
          insertMany(extracted.entities);
        }
        
        if (extracted.events && Array.isArray(extracted.events)) {
          const stmt = db.prepare('INSERT OR REPLACE INTO events (id, universe_id, title, description, event_date, order_index) VALUES (?, ?, ?, ?, ?, ?)');
          const insertMany = db.transaction((events) => {
            for (const ev of events) {
              stmt.run(ev.id || crypto.randomUUID(), universe_id, ev.title, ev.description, ev.event_date || '', ev.order_index || 0);
            }
          });
          insertMany(extracted.events);
        }

        if (extracted.map_nodes && Array.isArray(extracted.map_nodes)) {
          const stmt = db.prepare('INSERT OR REPLACE INTO map_nodes (id, universe_id, parent_id, type, name, description, x, y, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)');
          const insertMany = db.transaction((nodes) => {
            for (const node of nodes) {
              stmt.run(node.id || crypto.randomUUID(), universe_id, node.parent_id || null, node.type, node.name, node.description || '', node.x || 0, node.y || 0, JSON.stringify(node.data || {}));
            }
          });
          insertMany(extracted.map_nodes);
        }
        
        // Remove the JSON block from the reply shown to the user
        displayReply = reply.replace(/\`\`\`json\n([\s\S]*?)\n\`\`\`/, '').trim();
      } catch (e) {
        console.error("Failed to parse extracted entities", e);
      }
    }

    res.json({ reply: displayReply });
  } catch (error: any) {
    console.error(error);
    res.status(500).json({ error: error.message });
  }
});

export default router;
