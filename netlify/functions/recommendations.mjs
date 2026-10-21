import {
  AIConfigurationError,
  AIGatewayError,
  buildSummary,
  generateAiEnrichment,
  jsonHeaders,
  rankIdeas,
  validateAnswers,
} from "./lib/planner.js";

export default async (request) => {
  if (request.method !== "POST") {
    return new Response(JSON.stringify({ error: "Endpoint tidak ditemukan." }), {
      status: 404,
      headers: jsonHeaders,
    });
  }

  const rawBody = await request.text();
  if (!rawBody || rawBody.length > 8_192) {
    return new Response(JSON.stringify({ error: "Ukuran permintaan tidak valid." }), {
      status: 400,
      headers: jsonHeaders,
    });
  }

  let answers;
  try {
    answers = JSON.parse(rawBody);
  } catch {
    return new Response(JSON.stringify({ error: "Jawaban harus berupa JSON yang valid." }), {
      status: 400,
      headers: jsonHeaders,
    });
  }

  const validationError = validateAnswers(answers);
  if (validationError) {
    return new Response(JSON.stringify({ error: validationError }), {
      status: 400,
      headers: jsonHeaders,
    });
  }

  const recommendations = rankIdeas(answers);

  try {
    const aiEnrichment = await generateAiEnrichment(answers, recommendations);
    return new Response(
      JSON.stringify({
        summary: buildSummary(answers),
        recommendations,
        ai_enrichment: aiEnrichment,
        ai_model: process.env.AI_GATEWAY_MODEL || "openai/gpt-4.1-mini",
      }),
      { status: 200, headers: jsonHeaders },
    );
  } catch (error) {
    if (error instanceof AIConfigurationError) {
      return new Response(JSON.stringify({ error: error.message, code: "ai_not_configured" }), {
        status: 503,
        headers: jsonHeaders,
      });
    }
    if (error instanceof AIGatewayError) {
      return new Response(JSON.stringify({ error: error.message, code: "ai_request_failed" }), {
        status: 502,
        headers: jsonHeaders,
      });
    }
    throw error;
  }
};
