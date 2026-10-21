import catalog from "../../../data/curated-data.json" with { type: "json" };

const AI_GATEWAY_URL = "https://ai-gateway.vercel.sh/v1/chat/completions";
const DEFAULT_AI_MODEL = "openai/gpt-4.1-mini";

const AI_RESPONSE_SCHEMA = {
  type: "object",
  properties: {
    opening: { type: "string" },
    plans: {
      type: "array",
      items: {
        type: "object",
        properties: {
          idea_id: { type: "string" },
          plan: { type: "string" },
          icebreaker: { type: "string" },
        },
        required: ["idea_id", "plan", "icebreaker"],
        additionalProperties: false,
      },
    },
    closing: { type: "string" },
  },
  required: ["opening", "plans", "closing"],
  additionalProperties: false,
};

const { ideas: IDEAS, areaLabels: AREA_LABELS, moodLabels: MOOD_LABELS, styleLabels: STYLE_LABELS, validChoices: VALID_CHOICES } =
  catalog;

export class AIConfigurationError extends Error {
  constructor(message) {
    super(message);
    this.name = "AIConfigurationError";
  }
}

export class AIGatewayError extends Error {
  constructor(message) {
    super(message);
    this.name = "AIGatewayError";
  }
}

export function validateAnswers(answers) {
  if (!answers || typeof answers !== "object" || Array.isArray(answers)) {
    return "Jawaban harus berupa objek.";
  }

  for (const [field, choices] of Object.entries(VALID_CHOICES)) {
    if (!choices.includes(answers[field])) {
      return `Pilihan untuk ${field} tidak valid.`;
    }
  }

  return null;
}

export function rankIdeas(answers) {
  const budgetLimit = { hemat: 100_000, sedang: 300_000, royal: null }[answers.budget];
  const ranked = IDEAS.map((idea, position) => {
    let score = 0;
    if (answers.area === "any" || idea.area === answers.area) {
      score += 4;
    }
    if (idea.vibes.includes(answers.mood)) {
      score += 4;
    }
    if (idea.styles.includes(answers.style)) {
      score += 2;
    }
    if (budgetLimit === null || idea.high <= budgetLimit) {
      score += 2;
    } else if (idea.low <= budgetLimit) {
      score += 1;
    }
    return { score, position, idea };
  });

  ranked.sort((left, right) => right.score - left.score || left.position - right.position);

  return ranked.slice(0, 10).map(({ score, idea }) => {
    const { vibes, styles, indoor, low, high, map_query: mapQuery, ...recommendation } = idea;
    return {
      ...recommendation,
      map_url: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(mapQuery)}`,
      match_label: score >= 10 ? "PAS BANGET" : score >= 7 ? "MASUK LIST" : "IDE CADANGAN",
    };
  });
}

export function buildSummary(answers) {
  const area = AREA_LABELS[answers.area];
  const mood = MOOD_LABELS[answers.mood];
  const style = STYLE_LABELS[answers.style];

  if (answers.area === "any") {
    return `Kalian pengin ${mood} dengan vibe ${style}. Ini 10 ide dari berbagai sudut Jakarta, diurutkan dari yang paling nyambung.`;
  }

  return `Kalian pengin ${mood} di ${area} dengan vibe ${style}. Ini 10 ide terdekat yang paling nyambung dengan jawabanmu.`;
}

function gatewayMessage(status) {
  if (status === 401) {
    return "AI Gateway menolak kredensial. Periksa API key atau token Vercel.";
  }
  if (status === 402) {
    return "Kredit atau budget AI Gateway tidak mencukupi.";
  }
  if (status === 403) {
    return "Akses AI Gateway ditolak. Periksa verifikasi akun dan akses tim.";
  }
  if (status === 429) {
    return "AI Gateway sedang membatasi permintaan. Coba lagi sebentar.";
  }
  return "Permintaan ke AI Gateway gagal. Coba lagi nanti.";
}

function validateEnrichment(enrichment, candidates) {
  if (!enrichment || typeof enrichment !== "object") {
    throw new AIGatewayError("Respons AI tidak sesuai format yang diminta.");
  }

  const { opening, closing, plans } = enrichment;
  const candidateIds = new Set(candidates.map((idea) => idea.id));

  if (
    typeof opening !== "string" ||
    !opening.trim() ||
    opening.length > 400 ||
    typeof closing !== "string" ||
    !closing.trim() ||
    closing.length > 300 ||
    !Array.isArray(plans) ||
    plans.length !== candidates.length
  ) {
    throw new AIGatewayError("Respons AI tidak lengkap. Coba kirim ulang.");
  }

  const planIds = new Set();
  for (const plan of plans) {
    const { idea_id: ideaId, plan: planText, icebreaker } = plan ?? {};
    if (
      typeof plan !== "object" ||
      typeof ideaId !== "string" ||
      !candidateIds.has(ideaId) ||
      planIds.has(ideaId) ||
      typeof planText !== "string" ||
      !planText.trim() ||
      planText.length > 400 ||
      typeof icebreaker !== "string" ||
      !icebreaker.trim() ||
      icebreaker.length > 200
    ) {
      throw new AIGatewayError("Respons AI tidak sesuai format yang diminta.");
    }
    planIds.add(ideaId);
  }

  return {
    opening: opening.trim(),
    plans,
    closing: closing.trim(),
  };
}

export async function generateAiEnrichment(answers, recommendations) {
  const apiKey = process.env.AI_GATEWAY_API_KEY || process.env.VERCEL_OIDC_TOKEN;
  if (!apiKey) {
    throw new AIConfigurationError(
      "AI belum dikonfigurasi. Atur AI_GATEWAY_API_KEY, lalu deploy ulang.",
    );
  }

  const model = process.env.AI_GATEWAY_MODEL || DEFAULT_AI_MODEL;
  const candidates = recommendations.slice(0, 3);
  const promptData = {
    preferences: {
      area: AREA_LABELS[answers.area],
      budget: answers.budget,
      activity: MOOD_LABELS[answers.mood],
      date_style: STYLE_LABELS[answers.style],
    },
    curated_ideas: candidates.map((idea) => ({
      id: idea.id,
      title: idea.title,
      area: idea.area_label,
      duration: idea.duration,
      budget_estimate: idea.budget_label,
      description: idea.description,
    })),
  };

  const payload = {
    model,
    messages: [
      {
        role: "system",
        content:
          "Kamu date planner Jakarta yang ceria, hangat, dan praktis. " +
          "Tulis dalam bahasa Indonesia santai. Buat opening singkat, satu mini-plan " +
          "dan satu icebreaker untuk setiap ide, lalu closing singkat. " +
          "Hanya gunakan tiga ide yang diberikan dan kembalikan setiap idea_id persis " +
          "satu kali. Jangan menambahkan tempat, harga, jam buka, atau fakta baru. " +
          "Budget dan durasi adalah perkiraan dari sumber; jangan mengubahnya. " +
          "Mini-plan berupa urutan aktivitas sederhana yang bisa dilakukan di tempat " +
          "tersebut, maksimal 2 kalimat. Hindari klaim bahwa kamu mencari data live.",
      },
      {
        role: "user",
        content: JSON.stringify(promptData),
      },
    ],
    response_format: {
      type: "json_schema",
      json_schema: {
        name: "jakarta_date_plan",
        strict: true,
        schema: AI_RESPONSE_SCHEMA,
      },
    },
    temperature: 0.8,
    max_tokens: 700,
  };

  let response;
  try {
    response = await fetch(AI_GATEWAY_URL, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(30_000),
    });
  } catch {
    throw new AIGatewayError("AI Gateway tidak bisa dijangkau sekarang. Coba lagi nanti.");
  }

  if (!response.ok) {
    throw new AIGatewayError(gatewayMessage(response.status));
  }

  let gatewayResponse;
  try {
    gatewayResponse = await response.json();
  } catch {
    throw new AIGatewayError("Respons AI Gateway tidak valid.");
  }

  let enrichment;
  try {
    enrichment = JSON.parse(gatewayResponse.choices[0].message.content);
  } catch {
    throw new AIGatewayError("Respons AI tidak sesuai format yang diminta.");
  }

  return validateEnrichment(enrichment, candidates);
}

export const jsonHeaders = {
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
};
