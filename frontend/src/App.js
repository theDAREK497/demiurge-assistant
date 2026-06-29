import React, { useEffect, useMemo, useState } from "react";
import { api } from "./api.js";

const tabs = [
  ["wiki", "Вики"],
  ["graph", "Граф"],
  ["timeline", "Таймлайн"],
  ["chat", "Чат"],
  ["settings", "Настройки"],
];

export function App() {
  const [activeTab, setActiveTab] = useState("wiki");
  const [worlds, setWorlds] = useState([]);
  const [selectedWorldId, setSelectedWorldId] = useState(null);
  const [entities, setEntities] = useState([]);
  const [relationships, setRelationships] = useState([]);
  const [status, setStatus] = useState("Загрузка...");
  const selectedWorld = worlds.find((world) => world.id === selectedWorldId) || null;

  useEffect(() => {
    loadWorlds().catch((error) => setStatus(error.message));
  }, []);

  useEffect(() => {
    if (!selectedWorldId) return;
    loadWorldData(selectedWorldId).catch((error) => setStatus(error.message));
  }, [selectedWorldId]);

  async function loadWorlds() {
    const nextWorlds = await api("/worlds");
    setWorlds(nextWorlds);
    setSelectedWorldId((current) => current || nextWorlds[0]?.id || null);
    setStatus("Backend online");
  }

  async function loadWorldData(worldId) {
    const [nextEntities, nextRelationships] = await Promise.all([
      api(`/worlds/${worldId}/entities?role=master`),
      api(`/worlds/${worldId}/relationships?role=master`),
    ]);
    setEntities(nextEntities);
    setRelationships(nextRelationships);
  }

  const events = useMemo(() => entities.filter((entity) => entity.type === "event"), [entities]);

  return React.createElement(
    "div",
    { className: "app-shell" },
    React.createElement(
      "aside",
      { className: "sidebar" },
      React.createElement("h1", null, "Worldbuilder"),
      React.createElement("p", { className: "muted" }, "React/Vite shell"),
      React.createElement("span", { className: "status" }, status),
      React.createElement(
        "div",
        { className: "world-list" },
        worlds.map((world) =>
          React.createElement(
            "button",
            {
              className: world.id === selectedWorldId ? "world active" : "world",
              key: world.id,
              onClick: () => setSelectedWorldId(world.id),
              type: "button",
            },
            React.createElement("strong", null, world.name),
            React.createElement("span", null, world.description || "Без описания"),
          ),
        ),
      ),
    ),
    React.createElement(
      "main",
      { className: "main" },
      React.createElement(
        "header",
        { className: "topbar" },
        React.createElement("div", null, React.createElement("p", { className: "eyebrow" }, "Выбранный мир"), React.createElement("h2", null, selectedWorld?.name || "Нет мира")),
        React.createElement(
          "nav",
          { className: "tabs" },
          tabs.map(([id, label]) =>
            React.createElement(
              "button",
              { className: activeTab === id ? "tab active" : "tab", key: id, onClick: () => setActiveTab(id), type: "button" },
              label,
            ),
          ),
        ),
      ),
      React.createElement(TabContent, { activeTab, entities, events, relationships }),
    ),
  );
}

function TabContent({ activeTab, entities, events, relationships }) {
  if (activeTab === "graph") {
    return React.createElement("section", { className: "panel" }, React.createElement("h3", null, "Граф связей"), React.createElement("p", null, `${entities.length} сущностей, ${relationships.length} связей. Интерактивный граф переносится из vanilla UI следующим этапом.`));
  }
  if (activeTab === "timeline") {
    return React.createElement(
      "section",
      { className: "panel stack" },
      React.createElement("h3", null, "Таймлайн"),
      events.length ? events.map((event) => React.createElement("article", { className: "card", key: event.id }, React.createElement("strong", null, event.name), React.createElement("p", null, event.summary || event.description || "Без описания"))) : React.createElement("p", { className: "muted" }, "Событий пока нет."),
    );
  }
  if (activeTab === "chat") {
    return React.createElement("section", { className: "panel" }, React.createElement("h3", null, "Чат"), React.createElement("p", null, "Чат и write-back pipeline уже работают в текущем /app/. Этот shell подготовлен для переноса UI на React."));
  }
  if (activeTab === "settings") {
    return React.createElement("section", { className: "panel" }, React.createElement("h3", null, "Настройки"), React.createElement("p", null, "React/Vite dev server проксирует /api и /assets на FastAPI."));
  }
  return React.createElement(
    "section",
    { className: "cards" },
    entities.length ? entities.map((entity) => React.createElement(EntityCard, { entity, key: entity.id })) : React.createElement("p", { className: "muted" }, "Сущностей пока нет."),
  );
}

function EntityCard({ entity }) {
  return React.createElement(
    "article",
    { className: "card" },
    entity.attributes?.image_url ? React.createElement("img", { alt: "", src: entity.attributes.image_url }) : null,
    React.createElement("strong", null, entity.name),
    React.createElement("span", { className: "muted" }, entity.type),
    React.createElement("p", null, entity.summary || entity.description || "Без описания"),
  );
}
