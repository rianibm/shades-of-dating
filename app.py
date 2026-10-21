from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen


HOST = "127.0.0.1"
PORT = 8000
AI_GATEWAY_URL = "https://ai-gateway.vercel.sh/v1/chat/completions"
DEFAULT_AI_MODEL = "openai/gpt-4.1-mini"
AI_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "opening": {"type": "string"},
        "plans": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "idea_id": {"type": "string"},
                    "plan": {"type": "string"},
                    "icebreaker": {"type": "string"},
                },
                "required": ["idea_id", "plan", "icebreaker"],
                "additionalProperties": False,
            },
        },
        "closing": {"type": "string"},
    },
    "required": ["opening", "plans", "closing"],
    "additionalProperties": False,
}
VALID_CHOICES = {
    "area": {"any", "central", "south", "west", "north", "east"},
    "budget": {"hemat", "sedang", "royal"},
    "mood": {"ngobrol", "kuliner", "seni", "alam", "main"},
    "style": {"first", "regular", "adventure"},
}


class AIConfigurationError(Exception):
    pass


class AIGatewayError(Exception):
    pass


def generate_ai_enrichment(
    answers: dict[str, str], recommendations: list[dict[str, object]]
) -> dict[str, object]:
    """Ask AI Gateway to personalize plans using only curated venue data."""
    api_key = os.environ.get("AI_GATEWAY_API_KEY") or os.environ.get("VERCEL_OIDC_TOKEN")
    if not api_key:
        raise AIConfigurationError(
            "AI belum dikonfigurasi. Atur AI_GATEWAY_API_KEY, lalu mulai ulang backend."
        )

    model = os.environ.get("AI_GATEWAY_MODEL", DEFAULT_AI_MODEL)
    candidates = recommendations[:3]
    prompt_data = {
        "preferences": {
            "area": AREA_LABELS[answers["area"]],
            "budget": answers["budget"],
            "activity": MOOD_LABELS[answers["mood"]],
            "date_style": STYLE_LABELS[answers["style"]],
        },
        "curated_ideas": [
            {
                "id": idea["id"],
                "title": idea["title"],
                "area": idea["area_label"],
                "duration": idea["duration"],
                "budget_estimate": idea["budget_label"],
                "description": idea["description"],
            }
            for idea in candidates
        ],
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Kamu date planner Jakarta yang ceria, hangat, dan praktis. "
                    "Tulis dalam bahasa Indonesia santai. Buat opening singkat, satu mini-plan "
                    "dan satu icebreaker untuk setiap ide, lalu closing singkat. "
                    "Hanya gunakan tiga ide yang diberikan dan kembalikan setiap idea_id persis "
                    "satu kali. Jangan menambahkan tempat, harga, jam buka, atau fakta baru. "
                    "Budget dan durasi adalah perkiraan dari sumber; jangan mengubahnya. "
                    "Mini-plan berupa urutan aktivitas sederhana yang bisa dilakukan di tempat "
                    "tersebut, maksimal 2 kalimat. Hindari klaim bahwa kamu mencari data live."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(prompt_data, ensure_ascii=False),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "jakarta_date_plan",
                "strict": True,
                "schema": AI_RESPONSE_SCHEMA,
            },
        },
        "temperature": 0.8,
        "max_tokens": 700,
    }
    request = Request(
        AI_GATEWAY_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            gateway_response = json.loads(response.read(65_536))
    except HTTPError as error:
        if error.code == 401:
            message = "AI Gateway menolak kredensial. Periksa API key atau token Vercel."
        elif error.code == 402:
            message = "Kredit atau budget AI Gateway tidak mencukupi."
        elif error.code == 403:
            message = "Akses AI Gateway ditolak. Periksa verifikasi akun dan akses tim."
        elif error.code == 429:
            message = "AI Gateway sedang membatasi permintaan. Coba lagi sebentar."
        else:
            message = "Permintaan ke AI Gateway gagal. Coba lagi nanti."
        raise AIGatewayError(message) from error
    except (URLError, TimeoutError):
        raise AIGatewayError(
            "AI Gateway tidak bisa dijangkau sekarang. Coba lagi nanti."
        ) from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise AIGatewayError("Respons AI Gateway tidak valid.") from None

    try:
        content = gateway_response["choices"][0]["message"]["content"]
        enrichment = json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        raise AIGatewayError("Respons AI tidak sesuai format yang diminta.") from None

    if not isinstance(enrichment, dict):
        raise AIGatewayError("Respons AI tidak sesuai format yang diminta.")
    opening = enrichment.get("opening")
    closing = enrichment.get("closing")
    plans = enrichment.get("plans")
    candidate_ids = {idea["id"] for idea in candidates}
    if (
        not isinstance(opening, str)
        or not opening.strip()
        or len(opening) > 400
        or not isinstance(closing, str)
        or not closing.strip()
        or len(closing) > 300
        or not isinstance(plans, list)
        or len(plans) != len(candidates)
    ):
        raise AIGatewayError("Respons AI tidak lengkap. Coba kirim ulang.")

    plan_ids: set[str] = set()
    for plan in plans:
        if not isinstance(plan, dict):
            raise AIGatewayError("Respons AI tidak sesuai format yang diminta.")
        idea_id = plan.get("idea_id")
        plan_text = plan.get("plan")
        icebreaker = plan.get("icebreaker")
        if (
            not isinstance(idea_id, str)
            or idea_id not in candidate_ids
            or idea_id in plan_ids
            or not isinstance(plan_text, str)
            or not plan_text.strip()
            or len(plan_text) > 400
            or not isinstance(icebreaker, str)
            or not icebreaker.strip()
            or len(icebreaker) > 200
        ):
            raise AIGatewayError("Respons AI tidak sesuai format yang diminta.")
        plan_ids.add(idea_id)

    return {
        "opening": opening.strip(),
        "plans": plans,
        "closing": closing.strip(),
    }


IDEAS = [
    {
        "id": "blok-m",
        "title": "Food crawl Blok M + M Bloc",
        "area": "south",
        "area_label": "Jakarta Selatan",
        "icon": "🥐",
        "vibes": {"kuliner", "ngobrol", "main"},
        "styles": {"first", "regular"},
        "indoor": True,
        "low": 45_000,
        "high": 180_000,
        "budget_label": "Rp45–180rb / orang",
        "duration": "2–3 jam",
        "description": "Pilih dua tempat makan, lanjut jalan-jalan dan window shopping. Bikin challenge: masing-masing pilih satu snack buat dicoba bareng.",
        "why": "Banyak opsi buat ngobrol santai, dan gampang pindah tempat kalau suasananya kurang cocok.",
        "official_url": "",
        "map_query": "M Bloc Space Blok M Jakarta",
    },
    {
        "id": "kota-tua",
        "title": "Jalan sore di Kota Tua",
        "area": "west",
        "area_label": "Jakarta Barat",
        "icon": "🚲",
        "vibes": {"alam", "seni", "ngobrol"},
        "styles": {"first", "regular", "adventure"},
        "indoor": False,
        "low": 15_000,
        "high": 100_000,
        "budget_label": "Rp15–100rb / orang",
        "duration": "1–3 jam",
        "description": "Keliling kawasan bersejarah, cari jajanan, dan foto-foto dengan tema turis lokal. Bonus: pilih bangunan favorit masing-masing.",
        "why": "Aktivitas ringan bantu obrolan first date mengalir tanpa harus saling tatap di meja terus.",
        "official_url": "",
        "map_query": "Kota Tua Jakarta",
    },
    {
        "id": "museum-macan",
        "title": "Lihat pameran di Museum MACAN",
        "area": "west",
        "area_label": "Jakarta Barat",
        "icon": "🖼️",
        "vibes": {"seni", "ngobrol"},
        "styles": {"first", "regular"},
        "indoor": True,
        "low": 100_000,
        "high": 180_000,
        "budget_label": "Sekitar Rp100–180rb / orang",
        "duration": "1,5–2 jam",
        "description": "Keliling pameran seni kontemporer, lalu saling tebak arti karya yang paling bikin penasaran.",
        "why": "Selalu ada topik obrolan baru, bahkan kalau kalian belum hafal nama semua seniman.",
        "official_url": "https://www.museummacan.org/",
        "map_query": "Museum MACAN Jakarta",
    },
    {
        "id": "hutan-kota",
        "title": "Piknik tipis di Hutan Kota GBK",
        "area": "central",
        "area_label": "Jakarta Pusat",
        "icon": "🌳",
        "vibes": {"alam", "ngobrol"},
        "styles": {"first", "regular"},
        "indoor": False,
        "low": 0,
        "high": 80_000,
        "budget_label": "Gratis–Rp80rb / orang",
        "duration": "1–2 jam",
        "description": "Bawa minuman dan camilan sendiri, cari spot duduk, lalu ngobrol sambil lihat kota dari sisi yang lebih adem.",
        "why": "Hemat, santai, dan enak buat ngobrol tanpa harus berebut suara sama musik kafe.",
        "official_url": "https://gbk.id/",
        "map_query": "Hutan Kota GBK Jakarta",
    },
    {
        "id": "ragunan",
        "title": "Jalan santai di Ragunan",
        "area": "south",
        "area_label": "Jakarta Selatan",
        "icon": "🦒",
        "vibes": {"alam", "main"},
        "styles": {"regular", "adventure"},
        "indoor": False,
        "low": 10_000,
        "high": 75_000,
        "budget_label": "Mulai sekitar Rp10rb / orang",
        "duration": "2–4 jam",
        "description": "Pilih beberapa area satwa, jalan santai, dan istirahat buat jajan. Cek jam operasional serta tiket sebelum berangkat.",
        "why": "Ada banyak bahan obrolan dan jalan kaki bareng bikin date terasa aktif tapi nggak kompetitif.",
        "official_url": "https://ragunanzoo.jakarta.go.id/",
        "map_query": "Taman Margasatwa Ragunan Jakarta",
    },
    {
        "id": "ancol",
        "title": "Kejar sunset di Ancol",
        "area": "north",
        "area_label": "Jakarta Utara",
        "icon": "🌅",
        "vibes": {"alam", "ngobrol"},
        "styles": {"regular", "adventure"},
        "indoor": False,
        "low": 35_000,
        "high": 250_000,
        "budget_label": "Mulai sekitar Rp35rb / orang",
        "duration": "2–3 jam",
        "description": "Jalan di tepi pantai menjelang sore, cari camilan, lalu pilih spot buat menikmati langit berubah warna.",
        "why": "Pemandangan jadi ice breaker alami. Cek tiket masuk dan kondisi cuaca sebelum berangkat.",
        "official_url": "https://www.ancol.com/",
        "map_query": "Ancol Beach Jakarta",
    },
    {
        "id": "tmii",
        "title": "Keliling mini di TMII",
        "area": "east",
        "area_label": "Jakarta Timur",
        "icon": "🚠",
        "vibes": {"seni", "alam", "main"},
        "styles": {"regular", "adventure"},
        "indoor": False,
        "low": 35_000,
        "high": 200_000,
        "budget_label": "Mulai sekitar Rp35rb / orang",
        "duration": "3–5 jam",
        "description": "Pilih beberapa anjungan atau museum, naik kendaraan keliling jika tersedia, dan bikin rute mini bareng.",
        "why": "Cocok buat date seharian yang isinya eksplor, bukan cuma duduk dan tanya “mau makan apa?”.",
        "official_url": "https://tamanmini.com/",
        "map_query": "Taman Mini Indonesia Indah",
    },
    {
        "id": "aquarium",
        "title": "Date bawah laut di Jakarta Aquarium",
        "area": "west",
        "area_label": "Jakarta Barat",
        "icon": "🐠",
        "vibes": {"main", "alam"},
        "styles": {"first", "regular"},
        "indoor": True,
        "low": 150_000,
        "high": 300_000,
        "budget_label": "Sekitar Rp150–300rb / orang",
        "duration": "1,5–2,5 jam",
        "description": "Jelajahi akuarium indoor, cari hewan paling unik, lalu istirahat atau makan di area sekitarnya.",
        "why": "Aktivitasnya sudah disediakan, jadi nggak perlu mikir cara mengisi jeda obrolan.",
        "official_url": "https://www.jakartaaquariumsafari.com/",
        "map_query": "Jakarta Aquarium Safari",
    },
    {
        "id": "monas",
        "title": "Monas + jajan di sekitar Medan Merdeka",
        "area": "central",
        "area_label": "Jakarta Pusat",
        "icon": "🏛️",
        "vibes": {"alam", "seni", "ngobrol"},
        "styles": {"first", "regular", "adventure"},
        "indoor": False,
        "low": 15_000,
        "high": 100_000,
        "budget_label": "Rp15–100rb / orang",
        "duration": "1,5–3 jam",
        "description": "Jalan di kawasan Monas dan taman, lalu cari jajanan. Kalau mau masuk area tertentu, cek tiket dan aksesnya dulu.",
        "why": "Ikonik, gampang jadi titik temu, dan rencananya bisa disesuaikan dengan tenaga serta budget.",
        "official_url": "",
        "map_query": "Monumen Nasional Jakarta",
    },
    {
        "id": "tebet-eco-park",
        "title": "Ngobrol sambil muter Tebet Eco Park",
        "area": "south",
        "area_label": "Jakarta Selatan",
        "icon": "🍃",
        "vibes": {"alam", "ngobrol"},
        "styles": {"first", "regular"},
        "indoor": False,
        "low": 0,
        "high": 60_000,
        "budget_label": "Gratis–Rp60rb / orang",
        "duration": "1–2 jam",
        "description": "Jalan santai, cari area duduk yang nyaman, dan lanjut jajan di sekitar taman setelahnya.",
        "why": "Pilihan low-pressure buat ngobrol lebih lama tanpa harus booking atau pesan banyak.",
        "official_url": "",
        "map_query": "Tebet Eco Park Jakarta",
    },
]

AREA_LABELS = {
    "any": "bebas area",
    "central": "Jakarta Pusat",
    "south": "Jakarta Selatan",
    "west": "Jakarta Barat",
    "north": "Jakarta Utara",
    "east": "Jakarta Timur",
}
MOOD_LABELS = {
    "ngobrol": "ngobrol santai",
    "kuliner": "kulineran",
    "seni": "seni dan budaya",
    "alam": "suasana outdoor",
    "main": "aktivitas seru",
}
STYLE_LABELS = {
    "first": "first date yang nggak awkward",
    "regular": "date rutin yang butuh suasana baru",
    "adventure": "petualangan berdua",
}


def rank_ideas(answers: dict[str, str]) -> list[dict[str, object]]:
    """Rank the curated Jakarta date ideas against a validated answer set."""
    budget_limit = {"hemat": 100_000, "sedang": 300_000, "royal": None}[
        answers["budget"]
    ]
    ranked: list[tuple[int, int, dict[str, object]]] = []

    for position, idea in enumerate(IDEAS):
        score = 0
        if answers["area"] == "any" or idea["area"] == answers["area"]:
            score += 4
        if answers["mood"] in idea["vibes"]:
            score += 4
        if answers["style"] in idea["styles"]:
            score += 2
        if budget_limit is None or idea["high"] <= budget_limit:
            score += 2
        elif idea["low"] <= budget_limit:
            score += 1
        ranked.append((score, position, idea))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    recommendations = []
    for score, _, idea in ranked[:10]:
        recommendation = {
            key: value
            for key, value in idea.items()
            if key not in {"vibes", "styles", "indoor", "low", "high", "map_query"}
        }
        recommendation["map_url"] = (
            "https://www.google.com/maps/search/?api=1&query="
            + quote_plus(str(idea["map_query"]))
        )
        recommendation["match_label"] = (
            "PAS BANGET" if score >= 10 else "MASUK LIST" if score >= 7 else "IDE CADANGAN"
        )
        recommendations.append(recommendation)
    return recommendations


class DatePlannerHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/api/health":
            self._send_json(200, {"status": "ok"})
            return
        self._send_json(404, {"error": "Endpoint tidak ditemukan."})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/recommendations":
            self._send_json(404, {"error": "Endpoint tidak ditemukan."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "Ukuran permintaan tidak valid."})
            return
        if content_length <= 0 or content_length > 8_192:
            self._send_json(400, {"error": "Ukuran permintaan tidak valid."})
            return

        try:
            answers = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "Jawaban harus berupa JSON yang valid."})
            return
        if not isinstance(answers, dict):
            self._send_json(400, {"error": "Jawaban harus berupa objek."})
            return

        for field, choices in VALID_CHOICES.items():
            if answers.get(field) not in choices:
                self._send_json(400, {"error": f"Pilihan untuk {field} tidak valid."})
                return

        recommendations = rank_ideas(answers)
        try:
            ai_enrichment = generate_ai_enrichment(answers, recommendations)
        except AIConfigurationError as error:
            self._send_json(503, {"error": str(error), "code": "ai_not_configured"})
            return
        except AIGatewayError as error:
            self._send_json(502, {"error": str(error), "code": "ai_request_failed"})
            return

        area = AREA_LABELS[answers["area"]]
        mood = MOOD_LABELS[answers["mood"]]
        style = STYLE_LABELS[answers["style"]]
        if answers["area"] == "any":
            summary = (
                f"Kalian pengin {mood} dengan vibe {style}. "
                "Ini 10 ide dari berbagai sudut Jakarta, diurutkan dari yang paling nyambung."
            )
        else:
            summary = (
                f"Kalian pengin {mood} di {area} dengan vibe {style}. "
                "Ini 10 ide terdekat yang paling nyambung dengan jawabanmu."
            )
        self._send_json(
            200,
            {
                "summary": summary,
                "recommendations": recommendations,
                "ai_enrichment": ai_enrichment,
                "ai_model": os.environ.get("AI_GATEWAY_MODEL", DEFAULT_AI_MODEL),
            },
        )

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), DatePlannerHandler)
    print(f"Date Plan Jakarta API running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Date Plan Jakarta API.")
    finally:
        server.server_close()
