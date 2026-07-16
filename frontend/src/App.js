import React, { useEffect, useMemo, useState } from "react";
import { api } from "./api.js";

const tabs = [
  ["wiki", "Вики"],
  ["graph", "Граф"],
  ["timeline", "Хронология"],
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
    const controller = new AbortController();
    loadWorlds(controller.signal).catch((error) => {
      if (error.name !== "AbortError") setStatus(error.message);
    });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!selectedWorldId) return undefined;
    const controller = new AbortController();
    loadWorldData(selectedWorldId, controller.signal).catch((error) => {
      if (error.name !== "AbortError") setStatus(error.message);
    });
    return () => controller.abort();
  }, [selectedWorldId]);

  async function loadWorlds(signal) {
    const nextWorlds = await api("/worlds", { signal });
    setWorlds(nextWorlds);
    setSelectedWorldId((current) => current || nextWorlds[0]?.id || null);
    setStatus("Сервер доступен");
  }

  async function loadWorldData(worldId, signal) {
    const [nextEntities, nextRelationships] = await Promise.all([
      api(`/worlds/${worldId}/entities?role=master`, { signal }),
      api(`/worlds/${worldId}/relationships?role=master`, { signal }),
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
        React.createElement(
          "div",
          null,
          React.createElement("p", { className: "eyebrow" }, "Выбранный мир"),
          React.createElement("h2", null, selectedWorld?.name || "Нет мира"),
        ),
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
    return React.createElement(
      "section",
      { className: "panel" },
      React.createElement("h3", null, "Граф связей"),
      React.createElement("p", null, `${entities.length} сущностей, ${relationships.length} связей.`),
    );
  }
  if (activeTab === "timeline") {
    return React.createElement(
      "section",
      { className: "panel stack" },
      React.createElement("h3", null, "Хронология"),
      events.length
        ? events.map((event) =>
            React.createElement(
              "article",
              { className: "card", key: event.id },
              React.createElement("strong", null, event.name),
              React.createElement("p", null, event.summary || event.description || "Без описания"),
            ),
          )
        : React.createElement("p", { className: "muted" }, "Событий пока нет."),
    );
  }
  if (activeTab === "chat") {
    return React.createElement("section", { className: "panel" }, React.createElement("h3", null, "Чат"));
  }
  if (activeTab === "settings") {
    return React.createElement("section", { className: "panel" }, React.createElement("h3", null, "Настройки"));
  }
  return React.createElement(
    "section",
    { className: "cards" },
    entities.length
      ? entities.map((entity) => React.createElement(EntityCard, { entity, key: entity.id }))
      : React.createElement("p", { className: "muted" }, "Сущностей пока нет."),
  );
}

function EntityCard({ entity }) {
  const imageUrl = safeImageUrl(entity.attributes?.image_url);
  return React.createElement(
    "article",
    { className: "card" },
    imageUrl ? React.createElement("img", { alt: "", src: imageUrl }) : null,
    React.createElement("strong", null, entity.name),
    React.createElement("span", { className: "muted" }, entity.type),
    React.createElement("p", null, entity.summary || entity.description || "Без описания"),
  );
}

function safeImageUrl(value) {
  try {
    const parsed = new URL(String(value || ""), window.location.origin);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : "";
  } catch {
    return "";
  }
}
