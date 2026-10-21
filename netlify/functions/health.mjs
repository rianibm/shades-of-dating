import { jsonHeaders } from "./lib/planner.js";

export default async () =>
  new Response(JSON.stringify({ status: "ok" }), {
    status: 200,
    headers: jsonHeaders,
  });
