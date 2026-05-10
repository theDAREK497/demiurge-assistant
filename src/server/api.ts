import express from 'express';
import { db } from '../db/index.js';
import crypto from 'crypto';
import multer from 'multer';
import path from 'path';
import fs from 'fs';
import { GoogleGenAI } from '@google/genai';

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
    const insertEntity = db.prepare('INSERT INTO entities (id, universe_id, type, name, description, tags, data, is_secret) VALUES (?, ?, ?, ?, ?, ?, ?, ?)');
    insertEntity.run(crypto.randomUUID(), universeId, 'location', 'Земля', 'Колыбель человечества, третья планета от Солнца.', 'planet, core, human', null, 0);
    insertEntity.run(crypto.randomUUID(), universeId, 'location', 'Марс', 'Красная планета, первая колония человечества.', 'planet, colony', null, 0);
    insertEntity.run(crypto.randomUUID(), universeId, 'location', 'Альфа Центавра', 'Ближайшая к [[Солнечная система]] звездная система. Торговый пост.', 'system, frontier', null, 0);
    insertEntity.run(crypto.randomUUID(), universeId, 'npc', 'Джон Шепард', 'Легендарный капитан космического флота. Владеет уникальным оружием: [[Бластер Шепарда]]. Часто бывает на планете [[Земля]].', 'human, commander, hero', null, 0);
    insertEntity.run(crypto.randomUUID(), universeId, 'npc', 'Эллен Рипли', 'Офицер безопасности, специалист по выживанию. Сталкивалась со множеством монстров.', 'human, survivor', null, 0);
    insertEntity.run(crypto.randomUUID(), universeId, 'npc', 'Теневой Брокер', 'Тайный торговец информацией. Игроки пока не должны знать о его существовании.', 'informant, secret', null, 1);
    
    const uneId = crypto.randomUUID();
    const tfId = crypto.randomUUID();
    insertEntity.run(uneId, universeId, 'faction', 'Объединенные Нации Земли', 'Глобальное правительство человечества.', 'government, earth, order', JSON.stringify({ color: '#3b82f6' }), 0);
    insertEntity.run(tfId, universeId, 'faction', 'Торговая Федерация', 'Межзвездный конгломерат корпораций.', 'corporate, wealth, neutral', JSON.stringify({ color: '#f59e0b' }), 0);

    // Events
    const insertEvent = db.prepare('INSERT INTO events (id, universe_id, title, description, event_date, order_index) VALUES (?, ?, ?, ?, ?, ?)');
    insertEvent.run(crypto.randomUUID(), universeId, 'Первый контакт', 'Человечество впервые встретило внеземную цивилизацию.', '2157 CE', 2157);
    insertEvent.run(crypto.randomUUID(), universeId, 'Основание Федерации', 'Подписание договора о создании Торговой Федерации.', '2160 CE', 2160);

    // Map Nodes
    const insertMapNode = db.prepare('INSERT INTO map_nodes (id, universe_id, parent_id, type, name, description, x, y, data, is_secret) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
    const galaxyId = crypto.randomUUID();
    insertMapNode.run(galaxyId, universeId, null, 'galaxy', 'Млечный Путь', 'Наша родная галактика.', 400, 300, JSON.stringify({ color: '#fbbf24', size: 15 }), 0);
    
    const systemId = crypto.randomUUID();
    insertMapNode.run(systemId, universeId, galaxyId, 'system', 'Солнечная система', 'Дом человечества.', 400, 300, JSON.stringify({ color: '#3b82f6', size: 25 }), 0);
    insertEntity.run(systemId, universeId, 'location', 'Солнечная система', 'Родная система человечества. Здесь находится [[Земля]] и [[Марс]]. Под контролем фракции [[Объединенные Нации Земли]].', 'system, core', JSON.stringify({ mapNodeId: systemId }), 0);
    
    const earthId = crypto.randomUUID();
    insertMapNode.run(earthId, universeId, systemId, 'planet', 'Земля', 'Голубая планета.', 300, 300, JSON.stringify({ color: '#10b981', size: 20, gridWidth: 15, gridHeight: 10 }), 0);
    insertMapNode.run(crypto.randomUUID(), universeId, systemId, 'planet', 'Марс', 'Красная планета.', 500, 300, JSON.stringify({ color: '#ef4444', size: 18, gridWidth: 15, gridHeight: 10 }), 0);
    
    const secretSystemId = crypto.randomUUID();
    insertMapNode.run(secretSystemId, universeId, galaxyId, 'system', 'Система Омега', 'Скрытая система пиратов.', 600, 450, JSON.stringify({ color: '#6366f1', size: 15 }), 1);

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
          JSON.stringify({ biome: biome, q, r, faction: factionId }),
          0
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

    // Journal Logs
    const insertJournal = db.prepare('INSERT INTO journal_logs (id, universe_id, title, content, session_date, is_secret) VALUES (?, ?, ?, ?, ?, ?)');
    insertJournal.run(
      crypto.randomUUID(), 
      universeId, 
      'День 1: Прибытие', 
      'Мы прибыли на орбиту [[Марс]]. Сканирование показывает странные аномалии. Капитан 1d20+5 на проверку сканеров: сигналы исходят от локации [[Секретная База]]. Экипаж готовится к высадке, ожидаем встретить сопротивление фракции [[Торговая Федерация]].',
      '2157-10-25',
      0
    );
    insertJournal.run(
      crypto.randomUUID(), 
      universeId, 
      'День 2: Исследование руин', 
      'Высадка прошла успешно. Встретили местного жителя по имени [[Джон Шепард]], он передал нам данные.',
      '2157-10-26',
      0
    );
    insertJournal.run(
      crypto.randomUUID(), 
      universeId, 
      'Заметки Мастера: День 2', 
      'Игроки не знают, но Шепард работает на [[Теневой Брокер]]. Следующая встреча будет засадой.',
      '2157-10-26',
      1
    );
    
    // Quests
    const insertQuest = db.prepare('INSERT INTO quests (id, universe_id, title, description, status, order_index, is_secret) VALUES (?, ?, ?, ?, ?, ?, ?)');
    insertQuest.run(crypto.randomUUID(), universeId, 'Исследовать аномалию', 'Проверить странный сигнал с поверхности [[Марс]].', 'todo', 0, 0);
    insertQuest.run(crypto.randomUUID(), universeId, 'Найти припасы', 'Собрать ресурсы для починки корабля перед отлетом на [[Земля]].', 'in_progress', 0, 0);
    insertQuest.run(crypto.randomUUID(), universeId, 'Договориться с Федерацией', 'Встретиться с представителем фракции [[Торговая Федерация]].', 'done', 0, 0);
    insertQuest.run(crypto.randomUUID(), universeId, 'Секретная цель: Саботаж', 'Если игроки предадут ОНЗ, они получат награду от [[Теневой Брокер]].', 'todo', 1, 1);

    // Boards
    const insertBoard = db.prepare('INSERT INTO boards (id, universe_id, name, data) VALUES (?, ?, ?, ?)');
    const boardData = {
      nodes: [
        { id: '1', type: 'default', position: { x: 100, y: 100 }, data: { label: 'Джон Шепард' }, style: { background: '#fef08a', color: '#000', border: '1px solid #ca8a04', borderRadius: '8px', padding: '10px', width: 150 } },
        { id: '2', type: 'default', position: { x: 300, y: 100 }, data: { label: 'Торговая Федерация' }, style: { background: '#fef08a', color: '#000', border: '1px solid #ca8a04', borderRadius: '8px', padding: '10px', width: 150 } },
        { id: '3', type: 'default', position: { x: 200, y: 250 }, data: { label: 'Секретная База' }, style: { background: '#fca5a5', color: '#000', border: '1px solid #dc2626', borderRadius: '8px', padding: '10px', width: 150 } }
      ],
      edges: [
        { id: 'e1-2', source: '1', target: '2', animated: true, style: { stroke: '#ef4444' } },
        { id: 'e1-3', source: '1', target: '3' },
        { id: 'e2-3', source: '2', target: '3' }
      ]
    };
    insertBoard.run(crypto.randomUUID(), universeId, 'Связи на Марсе', JSON.stringify(boardData));

    // Custom Map Image with Pins
    const customMapId = crypto.randomUUID();
    insertMapNode.run(customMapId, universeId, systemId, 'planet', 'Секретная База', 'Заброшенная станция ОНЗ', 700, 300, JSON.stringify({ 
      color: '#a855f7', 
      size: 15,
      image: 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 225" width="400" height="225"><rect width="400" height="225" fill="%231e1b4b"/><rect x="100" y="100" width="200" height="125" fill="%23475569"/><rect x="80" y="60" width="40" height="165" fill="%23334155"/><rect x="280" y="60" width="40" height="165" fill="%23334155"/><polygon points="70,60 100,20 130,60" fill="%23b91c1c"/><polygon points="270,60 300,20 330,60" fill="%23b91c1c"/><path d="M 170 225 L 170 170 A 30 30 0 0 1 230 170 L 230 225 Z" fill="%231c1917"/><rect x="120" y="80" width="20" height="20" fill="%23475569"/><rect x="160" y="80" width="20" height="20" fill="%23475569"/><rect x="200" y="80" width="20" height="20" fill="%23475569"/><rect x="240" y="80" width="20" height="20" fill="%23475569"/></svg>'
    }), 0);

    insertEntity.run(customMapId, universeId, 'location', 'Секретная База', 'Заброшенная станция наблюдения, обнаруженная недалеко от Марса.', 'station, secret', null, 0);

    const pinId = crypto.randomUUID();
    insertMapNode.run(pinId, universeId, customMapId, 'pin', 'Главный Вход', 'Центральные ворота', 50, 60, JSON.stringify({
      color: '#ef4444', 
      size: 20
    }), 0);
    insertEntity.run(pinId, universeId, 'location', 'Главный Вход', 'Центральные бронированные ворота Секретной Базы.', 'door', JSON.stringify({ locationId: pinId }), 0);
    
    // An item associated with John Shepard to check the Wiki better
    insertEntity.run(crypto.randomUUID(), universeId, 'item', 'Бластер Шепарда', 'Короткоствольный энергетический бластер N7.', 'weapon, rare', JSON.stringify({ "damage": "2d6+2" }), 0);

  })();

  res.json({ success: true, id: universeId });
});

// Backlinks
router.get('/backlinks', (req, res) => {
  const { universe_id, name } = req.query;
  if (!universe_id || !name) {
    return res.status(400).json({ error: 'universe_id and name are required' });
  }

  const searchPattern = `%[[${name}]]%`;
  
  // Find in entities (description or data)
  const entities = db.prepare('SELECT id, type, name FROM entities WHERE universe_id = ? AND (description LIKE ? OR data LIKE ?)').all(universe_id, searchPattern, searchPattern);
  
  // Find in quests (description)
  const quests = db.prepare('SELECT id, title as name FROM quests WHERE universe_id = ? AND description LIKE ?').all(universe_id, searchPattern);
  
  // Find in journals (content)
  const journals = db.prepare('SELECT id, title as name, session_date FROM journal_logs WHERE universe_id = ? AND content LIKE ?').all(universe_id, searchPattern);
  
  res.json({ entities, quests, journals });
});

// Entities
router.get('/entities', (req, res) => {
  const { universe_id } = req.query;
  const stmt = db.prepare('SELECT * FROM entities WHERE universe_id = ? ORDER BY updated_at DESC');
  res.json(stmt.all(universe_id));
});

router.post('/entities', (req, res) => {
  const { id, universe_id, type, name, description, tags, image, data, is_secret } = req.body;
  const newId = id || crypto.randomUUID();
  const stmt = db.prepare('INSERT OR REPLACE INTO entities (id, universe_id, type, name, description, tags, image, data, is_secret, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)');
  stmt.run(newId, universe_id, type, name, description, tags, image || null, data ? JSON.stringify(data) : null, is_secret ? 1 : 0);
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

// Journal Logs
router.get('/journal-logs', (req, res) => {
  const { universe_id } = req.query;
  const stmt = db.prepare('SELECT * FROM journal_logs WHERE universe_id = ? ORDER BY created_at DESC');
  res.json(stmt.all(universe_id));
});

router.post('/journal-logs', (req, res) => {
  const { id, universe_id, title, content, session_date, is_secret } = req.body;
  const newId = id || crypto.randomUUID();
  const stmt = db.prepare('INSERT OR REPLACE INTO journal_logs (id, universe_id, title, content, session_date, is_secret) VALUES (?, ?, ?, ?, ?, ?)');
  stmt.run(newId, universe_id, title, content, session_date || new Date().toISOString(), is_secret ? 1 : 0);
  res.json({ success: true, id: newId });
});

router.delete('/journal-logs/:id', (req, res) => {
  const stmt = db.prepare('DELETE FROM journal_logs WHERE id = ?');
  stmt.run(req.params.id);
  res.json({ success: true });
});

// Quests
router.get('/quests', (req, res) => {
  const { universe_id } = req.query;
  const stmt = db.prepare('SELECT * FROM quests WHERE universe_id = ? ORDER BY order_index ASC, updated_at DESC');
  res.json(stmt.all(universe_id));
});

router.post('/quests', (req, res) => {
  const { id, universe_id, title, description, status, order_index, is_secret } = req.body;
  const newId = id || crypto.randomUUID();
  const stmt = db.prepare('INSERT OR REPLACE INTO quests (id, universe_id, title, description, status, order_index, is_secret, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)');
  stmt.run(newId, universe_id, title, description || '', status || 'todo', order_index || 0, is_secret ? 1 : 0);
  res.json({ success: true, id: newId });
});

router.delete('/quests/:id', (req, res) => {
  const stmt = db.prepare('DELETE FROM quests WHERE id = ?');
  stmt.run(req.params.id);
  res.json({ success: true });
});

// Boards
router.get('/boards', (req, res) => {
  const { universe_id } = req.query;
  const stmt = db.prepare('SELECT * FROM boards WHERE universe_id = ? ORDER BY updated_at DESC');
  res.json(stmt.all(universe_id));
});

router.post('/boards', (req, res) => {
  const { id, universe_id, name, data } = req.body;
  const newId = id || crypto.randomUUID();
  const stmt = db.prepare('INSERT OR REPLACE INTO boards (id, universe_id, name, data, updated_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)');
  stmt.run(newId, universe_id, name, data ? JSON.stringify(data) : '{}');
  res.json({ success: true, id: newId });
});

router.delete('/boards/:id', (req, res) => {
  const stmt = db.prepare('DELETE FROM boards WHERE id = ?');
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
  } else {
    query += ' AND parent_id IS NULL';
  }
  
  if (type) {
    query += ' AND type = ?';
    params.push(type);
  }
  
  const stmt = db.prepare(query);
  const nodes = stmt.all(...params).map((n: any) => ({
    ...n,
    data: n.data ? JSON.parse(n.data) : {}
  }));
  res.json(nodes);
});

router.get('/map-nodes/:id', (req, res) => {
  const stmt = db.prepare('SELECT * FROM map_nodes WHERE id = ?');
  const node: any = stmt.get(req.params.id);
  if (node) {
    node.data = node.data ? JSON.parse(node.data) : {};
    res.json(node);
  } else {
    res.status(404).json({ error: 'Not found' });
  }
});

router.post('/map-nodes', (req, res) => {
  const { id, universe_id, parent_id, type, name, description, x, y, data, is_secret } = req.body;
  const newId = id || crypto.randomUUID();
  const stmt = db.prepare('INSERT OR REPLACE INTO map_nodes (id, universe_id, parent_id, type, name, description, x, y, data, is_secret) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
  stmt.run(newId, universe_id, parent_id || null, type, name, description || '', x || 0, y || 0, JSON.stringify(data || {}), is_secret ? 1 : 0);
  res.json({ success: true, id: newId });
});

router.post('/map-nodes/bulk', (req, res) => {
  const { nodes, universe_id } = req.body;
  
  db.transaction(() => {
    const stmt = db.prepare('INSERT OR REPLACE INTO map_nodes (id, universe_id, parent_id, type, name, description, x, y, data, is_secret) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
    for (const node of nodes) {
      const newId = node.id || crypto.randomUUID();
      stmt.run(newId, universe_id, node.parent_id || null, node.type, node.name, node.description || '', node.x || 0, node.y || 0, JSON.stringify(node.data || {}), node.is_secret ? 1 : 0);
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
    
    const providerStmt = db.prepare("SELECT value FROM settings WHERE key = 'llm_provider'");
    const provider = providerStmt.get()?.value || 'openai';

    const endpointStmt = db.prepare("SELECT value FROM settings WHERE key = 'llm_endpoint'");
    const endpoint = endpointStmt.get()?.value || 'http://localhost:1234/v1';

    const modelStmt = db.prepare("SELECT value FROM settings WHERE key = 'llm_model'");
    const model = modelStmt.get()?.value || 'local-model';

    const apiKeyStmt = db.prepare("SELECT value FROM settings WHERE key = 'llm_api_key'");
    const apiKey = apiKeyStmt.get()?.value || '';

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

    let reply = '';

    if (provider === 'gemini' || (!endpoint && process.env.GEMINI_API_KEY)) {
      const ai = new GoogleGenAI({ apiKey: apiKey || process.env.GEMINI_API_KEY || '' });
      
      const geminiMessages = messages.map((m: any) => ({
        role: m.role === 'assistant' ? 'model' : 'user',
        parts: [{ text: m.content }]
      }));

      const response = await ai.models.generateContent({
        model: model && model !== 'local-model' ? model : 'gemini-2.5-flash',
        contents: geminiMessages,
        config: {
          systemInstruction: systemPrompt,
          temperature: 0.7,
        }
      });
      reply = response.text;
    } else {
      // OpenAI-Compatible (LM Studio, ChatGPT, DeepSeek, Qwen)
      const fullMessages = [
        { role: 'system', content: systemPrompt },
        ...messages
      ];

      const headers: any = { 'Content-Type': 'application/json' };
      if (apiKey) {
        headers['Authorization'] = `Bearer ${apiKey}`;
      }

      const response = await fetch(`${endpoint}/chat/completions`, {
        method: 'POST',
        headers,
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
      reply = data.choices[0].message.content;
    }

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
          const stmt = db.prepare('INSERT OR REPLACE INTO map_nodes (id, universe_id, parent_id, type, name, description, x, y, data, is_secret) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
          const insertMany = db.transaction((nodes) => {
            for (const node of nodes) {
              stmt.run(node.id || crypto.randomUUID(), universe_id, node.parent_id || null, node.type, node.name, node.description || '', node.x || 0, node.y || 0, JSON.stringify(node.data || {}), 0);
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

router.post('/analyze-journal', async (req, res) => {
  const { text, universe_id } = req.body;
  
  try {
    const providerStmt = db.prepare("SELECT value FROM settings WHERE key = 'llm_provider'");
    const provider = providerStmt.get()?.value || 'openai';

    const endpointStmt = db.prepare("SELECT value FROM settings WHERE key = 'llm_endpoint'");
    const endpoint = endpointStmt.get()?.value || 'http://localhost:1234/v1';

    const modelStmt = db.prepare("SELECT value FROM settings WHERE key = 'llm_model'");
    const model = modelStmt.get()?.value || 'local-model';

    const apiKeyStmt = db.prepare("SELECT value FROM settings WHERE key = 'llm_api_key'");
    const apiKey = apiKeyStmt.get()?.value || '';

    const systemPrompt = `You are a helpful assistant for a tabletop RPG game master.
Analyze the following session log and extract:
1. New entities (NPCs, locations, items, factions) mentioned.
2. Key events that happened, suitable for a timeline.

Return the result ONLY as a valid JSON object with the following structure:
{
  "entities": [
    { "name": "Entity Name", "type": "npc|location|item|faction", "description": "Short description of the entity based on the log." }
  ],
  "events": [
    { "title": "Event Title", "description": "What happened", "date": "Date or time if mentioned, else leave empty" }
  ]
}
Do not include any markdown formatting like \`\`\`json, just the raw JSON string.`;

    let content = '';

    if (provider === 'gemini' || (!endpoint && process.env.GEMINI_API_KEY)) {
      const ai = new GoogleGenAI({ apiKey: apiKey || process.env.GEMINI_API_KEY || '' });
      const response = await ai.models.generateContent({
        model: model && model !== 'local-model' ? model : 'gemini-2.5-flash',
        contents: text,
        config: {
          systemInstruction: systemPrompt,
          temperature: 0.3,
        }
      });
      content = response.text.trim();
    } else {
      const headers: any = { 'Content-Type': 'application/json' };
      if (apiKey) {
        headers['Authorization'] = `Bearer ${apiKey}`;
      }

      const response = await fetch(`${endpoint}/chat/completions`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          model: model,
          messages: [
            { role: 'system', content: systemPrompt },
            { role: 'user', content: text }
          ],
          temperature: 0.3
        })
      });

      if (!response.ok) {
        throw new Error(`LLM Error: ${response.statusText}`);
      }

      const data = await response.json();
      content = data.choices[0].message.content.trim();
    }
    
    // Try to parse the JSON. Sometimes LLMs still wrap in ```json
    const cleanedContent = content.replace(/^```json\s*/, '').replace(/\s*```$/, '');
    const parsed = JSON.parse(cleanedContent);
    
    res.json(parsed);
  } catch (error: any) {
    console.error(error);
    res.status(500).json({ error: error.message });
  }
});

// Export/Import
router.get('/export', (req, res) => {
  try {
    const data = {
      settings: db.prepare('SELECT * FROM settings').all(),
      universes: db.prepare('SELECT * FROM universes').all(),
      entities: db.prepare('SELECT * FROM entities').all(),
      events: db.prepare('SELECT * FROM events').all(),
      map_nodes: db.prepare('SELECT * FROM map_nodes').all(),
      random_tables: db.prepare('SELECT * FROM random_tables').all(),
      journal_logs: db.prepare('SELECT * FROM journal_logs').all(),
      quests: db.prepare('SELECT * FROM quests').all(),
      boards: db.prepare('SELECT * FROM boards').all(),
    };
    res.json(data);
  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
});

router.post('/generate-image', async (req, res) => {
  const { prompt } = req.body;
  
  try {
    const providerStmt = db.prepare("SELECT value FROM settings WHERE key = 'image_provider'");
    const provider = providerStmt.get()?.value || 'sd';

    const endpointStmt = db.prepare("SELECT value FROM settings WHERE key = 'image_endpoint'");
    const endpoint = endpointStmt.get()?.value || 'http://127.0.0.1:7860';

    const apiKeyStmt = db.prepare("SELECT value FROM settings WHERE key = 'image_api_key'");
    const apiKey = apiKeyStmt.get()?.value || '';

    let base64Image = '';

    if (provider === 'sd') {
      const response = await fetch(`${endpoint}/sdapi/v1/txt2img`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: prompt + ", masterpiece, best quality, highres, highly detailed",
          negative_prompt: "worst quality, low quality, bad anatomy, bad hands, missing fingers, blurry",
          steps: 20,
          width: 512,
          height: 512
        })
      });
      if (!response.ok) throw new Error(`SD API Error: ${response.statusText}`);
      const data = await response.json();
      base64Image = data.images[0];
    } else if (provider === 'openai') {
      const response = await fetch(`${endpoint}/v1/images/generations`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`
        },
        body: JSON.stringify({
          prompt: prompt,
          n: 1,
          size: "512x512",
          response_format: "b64_json"
        })
      });
      if (!response.ok) throw new Error(`OpenAI API Error: ${response.statusText}`);
      const data = await response.json();
      base64Image = data.data[0].b64_json;
    } else {
      throw new Error('Unknown image provider');
    }

    // Save base64 to file
    const fileName = `gen_${Date.now()}.png`;
    const filePath = path.join(process.cwd(), 'public', 'uploads', fileName);
    fs.writeFileSync(filePath, Buffer.from(base64Image, 'base64'));

    res.json({ url: `/uploads/${fileName}` });
  } catch (error: any) {
    console.error(error);
    res.status(500).json({ error: error.message });
  }
});

router.post('/import', upload.single('file'), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: 'No file uploaded' });
  }
  
  try {
    const fileContent = fs.readFileSync(req.file.path, 'utf-8');
    const data = JSON.parse(fileContent);
    
    db.transaction(() => {
      // Clear existing data
      db.prepare('DELETE FROM settings').run();
      db.prepare('DELETE FROM universes').run();
      db.prepare('DELETE FROM entities').run();
      db.prepare('DELETE FROM events').run();
      db.prepare('DELETE FROM map_nodes').run();
      db.prepare('DELETE FROM random_tables').run();
      db.prepare('DELETE FROM journal_logs').run();
      db.prepare('DELETE FROM quests').run();
      db.prepare('DELETE FROM boards').run();
      
      // Insert settings
      if (data.settings) {
        const stmt = db.prepare('INSERT INTO settings (key, value) VALUES (?, ?)');
        for (const row of data.settings) stmt.run(row.key, row.value);
      }
      
      // Insert universes
      if (data.universes) {
        const stmt = db.prepare('INSERT INTO universes (id, name, description, created_at) VALUES (?, ?, ?, ?)');
        for (const row of data.universes) stmt.run(row.id, row.name, row.description, row.created_at);
      }
      
      // Insert entities
      if (data.entities) {
        const stmt = db.prepare('INSERT INTO entities (id, universe_id, type, name, description, tags, data, is_secret, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
        for (const row of data.entities) stmt.run(row.id, row.universe_id, row.type, row.name, row.description, row.tags, row.data, row.is_secret || 0, row.created_at, row.updated_at);
      }
      
      // Insert events
      if (data.events) {
        const stmt = db.prepare('INSERT INTO events (id, universe_id, title, description, event_date, order_index, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)');
        for (const row of data.events) stmt.run(row.id, row.universe_id, row.title, row.description, row.event_date, row.order_index, row.created_at);
      }
      
      // Insert map_nodes
      if (data.map_nodes) {
        const stmt = db.prepare('INSERT INTO map_nodes (id, universe_id, parent_id, type, name, description, x, y, data, is_secret, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
        for (const row of data.map_nodes) stmt.run(row.id, row.universe_id, row.parent_id, row.type, row.name, row.description, row.x, row.y, row.data, row.is_secret || 0, row.created_at);
      }
      
      // Insert random_tables
      if (data.random_tables) {
        const stmt = db.prepare('INSERT INTO random_tables (id, universe_id, name, description, type, rollType, entries, conditions, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)');
        for (const row of data.random_tables) stmt.run(row.id, row.universe_id, row.name, row.description, row.type, row.rollType, row.entries, row.conditions, row.created_at);
      }

      // Insert journal_logs
      if (data.journal_logs) {
        const stmt = db.prepare('INSERT INTO journal_logs (id, universe_id, title, content, session_date, is_secret, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)');
        for (const row of data.journal_logs) stmt.run(row.id, row.universe_id, row.title, row.content, row.session_date, row.is_secret || 0, row.created_at);
      }

      // Insert quests
      if (data.quests) {
        const stmt = db.prepare('INSERT INTO quests (id, universe_id, title, description, status, order_index, is_secret, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)');
        for (const row of data.quests) stmt.run(row.id, row.universe_id, row.title, row.description, row.status, row.order_index, row.is_secret || 0, row.created_at, row.updated_at);
      }

      // Insert boards
      if (data.boards) {
        const stmt = db.prepare('INSERT INTO boards (id, universe_id, name, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)');
        for (const row of data.boards) stmt.run(row.id, row.universe_id, row.name, row.data, row.created_at, row.updated_at);
      }
    })();
    
    // Clean up uploaded file
    fs.unlinkSync(req.file.path);
    
    res.json({ success: true });
  } catch (error: any) {
    console.error('Import error:', error);
    res.status(500).json({ error: error.message });
  }
});

export default router;
