const form = document.querySelector("#date-form");
const results = document.querySelector("#results");
const resultsGrid = document.querySelector("#recommendation-grid");
const resultsIntro = document.querySelector("#results-intro");
const resultsStatus = document.querySelector("#results-status");
const aiOpening = document.querySelector("#ai-opening");
const aiOpeningText = document.querySelector("#ai-opening-text");
const aiClosing = document.querySelector("#ai-closing");
const submitButton = form.querySelector('button[type="submit"]');
const submitLabel = submitButton.querySelector("span");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setLoading(true);
  resultsStatus.textContent = "";

  try {
    const response = await fetch("/api/recommendations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.fromEntries(new FormData(form))),
    });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || "Jawabannya belum bisa diproses. Coba lagi, ya.");
    }

    renderRecommendations(payload);
    results.hidden = false;
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    results.hidden = false;
    resultsGrid.replaceChildren();
    resultsIntro.textContent = "";
    aiOpening.hidden = true;
    aiOpeningText.textContent = "";
    aiClosing.hidden = true;
    aiClosing.textContent = "";
    resultsStatus.textContent =
      error instanceof TypeError
        ? "Backend belum jalan. Lokal: `python3 app.py` + `yarn dev`, atau `netlify dev`."
        : error.message;
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  } finally {
    setLoading(false);
  }
});

document.querySelector("#edit-answers").addEventListener("click", () => {
  form.scrollIntoView({ behavior: "smooth", block: "start" });
  form.querySelector("select").focus({ preventScroll: true });
});

function setLoading(isLoading) {
  submitButton.disabled = isLoading;
  submitLabel.textContent = isLoading ? "NYUSUN DATE PLAN..." : "CARI IDE DATE";
}

function renderRecommendations(payload) {
  resultsStatus.textContent = "";
  resultsIntro.textContent = payload.summary;
  const enrichment = payload.ai_enrichment;
  const plansById = new Map(enrichment.plans.map((plan) => [plan.idea_id, plan]));
  aiOpeningText.textContent = enrichment.opening;
  aiOpening.hidden = false;
  aiClosing.textContent = enrichment.closing;
  aiClosing.hidden = false;
  resultsGrid.replaceChildren(
    ...payload.recommendations.map((idea, index) =>
      createRecommendationCard(idea, index, plansById.get(idea.id)),
    ),
  );
}

function createRecommendationCard(idea, index, aiPlan) {
  const card = document.createElement("article");
  card.className = "idea-card";

  const top = document.createElement("div");
  top.className = "idea-card-top";

  const number = document.createElement("span");
  number.className = "idea-number";
  number.textContent = String(index + 1).padStart(2, "0");

  const match = document.createElement("span");
  match.className = "match-label";
  match.textContent = idea.match_label;
  top.append(number, match);

  const icon = document.createElement("span");
  icon.className = "idea-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = idea.icon;

  const title = document.createElement("h3");
  title.textContent = idea.title;

  const location = document.createElement("p");
  location.className = "idea-location";
  location.textContent = `${idea.area_label} · ${idea.duration}`;

  const description = document.createElement("p");
  description.className = "idea-description";
  description.textContent = idea.description;

  const why = document.createElement("p");
  why.className = "idea-why";
  why.textContent = idea.why;

  const aiPlanElement = createAiPlan(aiPlan);
  const footer = document.createElement("div");
  footer.className = "idea-card-footer";

  const budget = document.createElement("span");
  budget.className = "budget-label";
  budget.textContent = idea.budget_label;

  const links = document.createElement("div");
  links.className = "idea-links";
  links.append(createLink("PETA ↗", idea.map_url));
  if (idea.official_url) {
    links.append(createLink("INFO ↗", idea.official_url));
  }
  footer.append(budget, links);

  card.append(top, icon, title, location, description, why);
  if (aiPlanElement) {
    card.append(aiPlanElement);
  }
  card.append(footer);
  return card;
}

function createAiPlan(aiPlan) {
  if (!aiPlan) {
    return null;
  }
  const section = document.createElement("section");
  section.className = "ai-plan";

  const label = document.createElement("span");
  label.className = "ai-plan-label";
  label.textContent = "✦ AI DATE PLAN";

  const plan = document.createElement("p");
  plan.className = "ai-plan-text";
  plan.textContent = aiPlan.plan;

  const icebreaker = document.createElement("p");
  icebreaker.className = "ai-icebreaker";
  icebreaker.textContent = `PEMANCING OBROLAN  ↗  “${aiPlan.icebreaker}”`;

  section.append(label, plan, icebreaker);
  return section;
}

function createLink(label, href) {
  const link = document.createElement("a");
  link.className = "source-link";
  link.href = href;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = label;
  return link;
}
