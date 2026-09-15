import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

globalThis.window = { location: { hash: "" } };
globalThis.sessionStorage = { getItem: () => null };
const source = await readFile(new URL("../src/worldbuilder_core/static/js/api.js", import.meta.url), "utf8");
const { api, apiRaw } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);

for (const request of [api, apiRaw]) {
  test(`${request.name} preserves successful creation and actionable errors`, async () => {
    globalThis.fetch = async () => new Response(JSON.stringify({ id: "created" }), { status: 201 });
    assert.deepEqual(await request("/entities", { method: "POST" }), { id: "created" });
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Name already exists" }), { status: 409 });
    await assert.rejects(request("/entities"), /Name already exists/);
    globalThis.fetch = async () => new Response(JSON.stringify({
      detail: [{ loc: ["body", "type"], msg: "Entity type must be a string" }],
    }), { status: 422 });
    await assert.rejects(request("/entities"), /type: Entity type must be a string/);
    globalThis.fetch = async () => new Response("Internal Server Error", { status: 500 });
    await assert.rejects(request("/entities"), /Internal Server Error/);
  });
}
