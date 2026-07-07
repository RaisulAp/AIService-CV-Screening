# RENCANA ADJUST AIService → "Teman Melamar Kerja"

> Dokumen kerja untuk menyelaraskan program **AIService** yang sudah ada (mode HRD / batch ranking) menjadi **AI Service kandidat-facing** yang dipanggil oleh Web Backend (Go) dan ditampilkan Frontend (Next.js).
> Referensi: [`Brain/BLUEPRINT.md`](../Brain/BLUEPRINT.md), [`Brain/BACKEND.md`](../Brain/BACKEND.md), kontrak nyata di `BE/internal/aiclient/`.
> Tanggal: 2026-07-03 · Status BE ✅ done · FE ✅ done (teruji vs mock) · **AIService ✅ Fase A-D selesai & teruji end-to-end dengan BE + OpenAI asli** (lihat §11 checklist). Sisa: Fase E (kalibrasi bobot skor dengan CV nyata lebih banyak, verifikasi FE penuh).

---

## 0. Ringkasan Keputusan (baca ini dulu)

| Hal | Sekarang (AIService) | Yang dibutuhkan | Aksi |
|---|---|---|---|
| **Bentuk** | CLI batch (`main.py`) + Streamlit `dashboard.py` | **HTTP service (FastAPI)** dengan 4 endpoint | **Tambah** layer FastAPI, tidak buang yang lama |
| **Arah use-case** | HRD: **N CV vs 1 lowongan → ranking** | Kandidat: **1 CV vs 1 JD → skor + report + rewrite** | Ubah orientasi output |
| **LLM** | OpenAI `gpt-4` (sudah dipakai di 2 tempat) | BLUEPRINT bilang Ollama lokal | **Pakai OpenAI** (keputusan user) via seam provider — lihat §5 |
| **Output** | `ranking.csv`, plots | JSON persis bentuk `BE/internal/aiclient/mock.go` | Sesuaikan skema |
| **PDF** | pdfminer (teks saja) | + analisis struktur (Momen A) | **Tambah PyMuPDF** |
| **Bahasa output** | Inggris | **Indonesia** (FE & mock berbahasa Indonesia) | Ubah prompt |

**Inti pekerjaan:** membungkus logika yang sudah ada dengan **FastAPI**, mengubah skema output agar **byte-for-byte cocok** dengan kontrak yang sudah diuji FE terhadap `MockClient`, lalu balik `AI_MOCK=false` di `BE/.env` dan verifikasi ulang alur yang sama.

---

## 1. Kontrak yang WAJIB dipatuhi (sumber kebenaran)

FE sudah diuji E2E melawan `MockClient`. Artinya **mock adalah kontrak de-facto**. AI Service harus menghasilkan bentuk JSON yang identik. Empat endpoint yang dipanggil BE (`BE/internal/aiclient/http.go`):

### 1.1 `POST /analyze/jd`
Request: `{ "text": "<raw job description>" }`
Response (`JDResult`, `types.go:12`):
```json
{
  "title": "Backend Engineer",
  "company": "PT Contoh Teknologi",
  "skills": ["Go", "REST API", "PostgreSQL", "Docker", "Kubernetes"],
  "keywords": ["microservice", "CI/CD", "unit testing"],
  "experience": "Minimal 2 tahun pengalaman backend.",
  "education": "S1 Teknik Informatika atau setara."
}
```
> Catatan: `experience` & `education` adalah **string manusiawi** (bukan angka seperti parser lama). Angka untuk scoring dihitung internal, tidak diekspos di sini.

### 1.2 `POST /parse/cv`
Request: `multipart/form-data`, field **`file`** (PDF). Timeout BE 120s.
Response (`CVResult`, `types.go:22`):
```json
{
  "raw_text": "Fresh graduate dengan pengalaman Go, REST API, MySQL...",
  "sections": {
    "profile": "Fresh graduate Informatika, aktif organisasi.",
    "experience": [
      {"id": "b1", "text": "Mengurus database organisasi kampus."},
      {"id": "b2", "text": "Ikut membuat aplikasi web untuk lomba."}
    ],
    "skills": ["Go", "REST API", "MySQL"],
    "education": ["S1 Teknik Informatika"]
  },
  "structure_report": {
    "issues": [
      {"severity": "fatal", "type": "multi_column", "detail": "CV memakai 2 kolom — ATS sering membaca urutannya acak."},
      {"severity": "warning", "type": "photo", "detail": "Terdapat foto — sebagian ATS gagal memprosesnya."}
    ]
  }
}
```
> **KRITIS — bullet IDs:** `sections.experience[].id` (`b1`, `b2`, …) harus **stabil**, karena `/match` mengembalikan `weak_bullets[].id` yang mereferensikan ID ini, dan FE mengirim `appliedRewrites[].bulletId` balik saat rescore. ID harus deterministik terhadap isi CV.
> **`severity` hanya `"fatal"` atau `"warning"`** (FE: `types.ts:25`). `type` bebas string; `detail` string Indonesia.
> **Jika CV tak terbaca** (teks kosong / bukan PDF valid): kembalikan **HTTP 422** → BE memetakan ke `CV_UNREADABLE`. Jangan kembalikan 200 dengan body kosong.

### 1.3 `POST /match`
Request: `{ "jd_json": <JDResult>, "cv_json": <CVResult> }`
Response (`MatchResult`, `types.go:35`):
```json
{
  "score": 62,
  "breakdown": {
    "keyword":         {"score": 55, "reason": "Beberapa keyword inti sudah ada, sebagian penting belum."},
    "semantic":        {"score": 68, "reason": "Pengalaman relevan tapi kurang eksplisit."},
    "skill_coverage":  {"score": 60, "reason": "Docker & Kubernetes belum tampak di CV."},
    "ats_readability": {"score": 45, "reason": "Format 2 kolom menurunkan keterbacaan mesin."}
  },
  "matched": ["Go", "REST API", "PostgreSQL"],
  "missing": ["Docker", "Kubernetes", "CI/CD"],
  "skill_gap": ["Containerization (Docker)", "Orkestrasi (Kubernetes)"],
  "experience_gap": "Belum ada pengalaman kerja formal; tonjolkan proyek & magang.",
  "weak_bullets": [
    {"id": "b1", "text": "Mengurus database organisasi kampus."}
  ]
}
```
> - `score` = **integer 0–100** (bukan float 0–1 seperti `scoring.py` lama).
> - `breakdown` **wajib 4 kunci ini persis**: `keyword`, `semantic`, `skill_coverage`, `ats_readability`, masing-masing `{score:0-100, reason}` (FE: `score-breakdown.tsx:21`).
> - `matched`/`missing`/`skill_gap` = array string. `experience_gap` = **string tunggal** (bukan array — FE `types.ts:73`).
> - `weak_bullets[].id` **harus** cocok dengan `sections.experience[].id`.

### 1.4 `POST /rewrite`
Request: `{ "bullet": "<teks bullet asli>", "jd_context": "<judul | skills: a, b, c>" }`
Response (`RewriteResult`, `types.go:46`):
```json
{
  "suggestion": "Mengelola basis data organisasi kampus (PostgreSQL) untuk 500+ anggota...",
  "reasoning": "Memakai formula XYZ: apa yang dikerjakan, dengan alat apa, dan dampak terukurnya."
}
```
> `jd_context` yang dikirim BE berformat `"<title> | skills: <s1>, <s2>, ..."` (`pipeline.go:287`).

### 1.5 Semantik status HTTP (dipetakan BE → `fail_reason`)
`BE/internal/aiclient/http.go` + `pipeline.go:263`:
- **422** → `CV_UNREADABLE` (khusus `/parse/cv` saat CV tak terbaca).
- **koneksi gagal / service mati** → `AI_SERVICE_DOWN` (BE retry 1x).
- **non-2xx lain / JSON tak bisa di-decode** → `AI_BAD_OUTPUT`.
- **200 + JSON valid sesuai skema** → sukses.
➡️ Implikasi: **selalu** validasi output (mis. via Pydantic `response_model`) sebelum balas 200. Output cacat lebih baik jadi 500 daripada 200-yang-salah, tapi paling baik: validasi & perbaiki di service.

---

## 2. Analisis Gap: apa yang dipakai ulang, diadaptasi, dibuang

| File lama | Fungsi | Nasib | Alasan |
|---|---|---|---|
| `src/text_extraction.py` | PDF/DOCX → teks (pdfminer, docx2txt) | **Pakai ulang** sbg fallback teks | Solid untuk ekstraksi teks datar |
| `src/gpt_vacancy_parser.py` | JD → JSON (OpenAI) | **Adaptasi** jadi `/analyze/jd` | Sudah OpenAI; skema beda (§1.1) |
| `dashboard.py:gpt_deep_analysis` | CV vs JD → analisis (OpenAI) | **Ambil idenya** untuk `/match` & `/rewrite` | Sudah ada pola prompt HR |
| `src/entity_extraction.py` | Regex/spaCy skill+edu+exp | **Sebagian** (heuristik exp/edu untuk skoring deterministik) | Berguna sbg sinyal jujur non-LLM |
| `src/scoring.py` | cosine skill + weighted | **Adaptasi** jadi komponen skor `/match` | Formula perlu ganti ke bobot BLUEPRINT §9 |
| `src/vectorize.py` | skill-vector vs skill_set | **Buang untuk MVP** (bisa balik di fase pgvector) | Semantic diganti pendekatan §7 |
| `src/plot_results.py`, `ranking.csv` | plots + ranking | **Simpan** (mode HRD batch masih valid) | Jangan rusak fitur HRD yang sudah jalan |
| `main.py` (CLI pipeline) | orkestrasi batch | **Simpan** sbg mode HRD | Dipisah dari service kandidat |
| `dashboard.py` | Streamlit HRD | **Simpan** | Alat HRD tetap berguna |

**Prinsip:** kita **menambah** service kandidat, **tanpa membongkar** alat HRD yang sudah siap pakai. Keduanya berbagi util ekstraksi & klien LLM.

---

## 3. Arsitektur Target AIService

```
AIService/
├── app/                      # ← BARU: service kandidat-facing (FastAPI)
│   ├── main.py               # FastAPI app + 4 route + error handler (422/500)
│   ├── config.py             # env: OPENAI_API_KEY, model, port, provider
│   ├── schemas.py            # Pydantic: JDResult, CVResult, MatchResult, dst (mirror kontrak §1)
│   ├── llm/
│   │   ├── base.py           # LLMProvider interface (chat_json, embed)
│   │   ├── openai_provider.py# default (keputusan user)
│   │   └── ollama_provider.py# opsional, sesuai BLUEPRINT (privasi) — stub dulu
│   ├── services/
│   │   ├── pdf.py            # PyMuPDF: teks + analisis struktur (Momen A) + fallback pdfminer/OCR
│   │   ├── jd_analyzer.py    # /analyze/jd
│   │   ├── cv_parser.py      # /parse/cv (teks + sections + structure_report + bullet IDs)
│   │   ├── matcher.py        # /match (skor deterministik + reason LLM)
│   │   └── rewriter.py       # /rewrite (formula XYZ, anti-mengarang)
│   └── prompts/              # template prompt terversion (BLUEPRINT §9)
│       ├── jd_extract.txt
│       ├── cv_sections.txt
│       ├── match_reason.txt
│       └── rewrite_xyz.txt
├── src/                      # ← LAMA: mode HRD batch (dipertahankan, dirapikan share util)
├── data/, outputs/           # ← LAMA: artefak batch HRD
├── requirements.txt          # + fastapi, uvicorn, pymupdf, python-multipart
├── .env                      # OPENAI_API_KEY (sudah ada)
└── ADJUSTMENT_PLAN.md        # dokumen ini
```

Menjalankan (sesuai BLUEPRINT §10 LANGKAH 2 & `BE/.env` `AI_SERVICE_URL=http://localhost:8000`):
```powershell
uvicorn app.main:app --reload --port 8000
```

---

## 4. Peta alur end-to-end (yang sudah dipatok BE)

`BE/internal/analyses/pipeline.go` memanggil berurutan (async, 1 worker):
```
FE POST /analyses (jobText + cvFile) → 202 {analysisId, PENDING}
BE worker:
  step=analyzing_jd → AI POST /analyze/jd   {text}                 → JDResult   → simpan job
  step=parsing_cv   → AI POST /parse/cv      (multipart file)       → CVResult   → simpan cv
  step=matching     → AI POST /match         {jd_json, cv_json}     → MatchResult→ simpan analysis
  (best-effort)     → AI POST /rewrite  ×N   {bullet, jd_context}   → RewriteResult (5 bullet terlemah)
  → status=DONE
FE poll GET /analyses/{id} tiap 2s → render saat DONE
```
Rescore (Momen D) — `pipeline.go:173`:
```
FE POST rescore (appliedRewrites[]) → BE reuse JD+CV tersimpan → AI POST /match lagi → skor baru
```
⚠️ **Titik penting rescore** dibahas di §8.

---

## 5. Keputusan LLM: OpenAI vs Ollama (dan kenapa pakai seam)

**Keputusan user:** pakai **OpenAI** ("biar lebih mudah, tidak perlu install Ollama"). Sah — kode lama sudah pakai OpenAI.

**Konflik yang harus disadari:** BLUEPRINT §0/§14 mengunci janji **"PRIVAT — proses AI jalan lokal/offline, CV tidak ke cloud"**. Memakai OpenAI berarti **teks CV & JD dikirim ke server OpenAI**. Ini melanggar janji privasi produk. Dua sikap yang jujur:
1. **Untuk dev/MVP sekarang:** pakai OpenAI (cepat, tak perlu GPU). **Update copy produk** agar tidak mengklaim "100% lokal" selama masih OpenAI.
2. **Untuk rilis publik:** sediakan jalan balik ke Ollama demi menepati janji privasi.

**Solusi engineering — `LLMProvider` seam** (`app/llm/base.py`): matcher/parser/rewriter hanya tahu interface `chat_json(system, user, schema) -> dict` dan `embed(texts) -> vectors`. Default `OpenAIProvider`; `OllamaProvider` bisa diisi belakangan **tanpa menyentuh logika bisnis**. Pilih via env `LLM_PROVIDER=openai|ollama`. Ini menepati BLUEPRINT §7 ("swap provider lewat 1 config") sekaligus keinginan user sekarang.

**Model OpenAI yang disarankan** (ganti `gpt-4` lama):
- Ekstraksi/parse (`/analyze/jd`, `/parse/cv` sections): model kecil-cepat-murah (mis. `gpt-4o-mini` / `gpt-4.1-mini`), `temperature≈0.2`, **JSON mode** (`response_format={"type":"json_object"}`).
- Reason match & rewrite: model lebih kuat (mis. `gpt-4o` / `gpt-4.1`), rewrite `temperature≈0.4`.
- Semua nama model **dari `config.py`** (env), jangan hardcode.
- Semantic (opsional): `text-embedding-3-small`.

> Verifikasi nama & harga model OpenAI terbaru saat implementasi (jangan dari ingatan) — cutoff pengetahuan bisa tertinggal.

---

## 6. Rancangan tiap endpoint

### 6.1 `/analyze/jd` — `services/jd_analyzer.py`
- Basis: `gpt_vacancy_parser.py`, tapi **ganti skema** ke §1.1 (title, company, skills[], keywords[], experience:str, education:str).
- Prompt Indonesia, JSON mode, larang mengarang perusahaan bila tak tersebut → `company: ""`.
- `skills` = hard skill/tools; `keywords` = frasa ATS penting (metodologi, sertifikasi) yang bukan skill murni.
- Validasi Pydantic; kalau LLM balas non-JSON → coba 1x repair, gagal → 500 (BE `AI_BAD_OUTPUT`).

### 6.2 `/parse/cv` — `services/pdf.py` + `services/cv_parser.py`
Dua lapis:
1. **Deterministik (PyMuPDF)** — `pdf.py`:
   - Ekstrak `raw_text` (fallback ke pdfminer bila kosong; fallback OCR Tesseract bila hasil scan → opsional fase berikut).
   - **`structure_report` (Momen A)** dari layout, bukan LLM: deteksi
     - `multi_column` (fatal) — >1 blok teks berdampingan horizontal per halaman,
     - `photo`/`image` (warning) — `page.get_images()`,
     - `table` (warning) — `page.find_tables()`,
     - `header_footer` (warning) — teks di margin atas/bawah,
     - `nonstandard_font` (warning) — font di luar whitelist umum.
   - Kembalikan `severity` hanya `fatal`/`warning`, `detail` Indonesia (contoh sudah ada di mock).
   - **Kalau `raw_text` kosong / bukan PDF valid → raise → handler balas HTTP 422.**
2. **LLM (sections)** — `cv_parser.py`:
   - Kirim `raw_text` ke LLM, minta JSON `{profile, experience[], skills[], education[]}`.
   - **Beri ID bullet deterministik**: `b1, b2, …` urut kemunculan. Simpan pemetaan ID→teks agar konsisten (ID = urutan, bukan hash acak, supaya rescore stabil).
   - Larang menambah skill yang tak ada di CV (BLUEPRINT §9).

### 6.3 `/match` — `services/matcher.py` (jantung "kejujuran")
Pendekatan **hibrida**: angka deterministik + alasan LLM. Formula skor akhir mengikuti **BLUEPRINT §9**:
```
score = round(100 * (0.30*keyword + 0.30*semantic + 0.20*skill_coverage + 0.20*ats_readability))
```
Komponen:
- **keyword** (deterministik): overlap `jd.skills ∪ jd.keywords` vs token `cv.raw_text` + `cv.sections.skills` (exact + sinonim ringan/lowercase). `matched` = yang ada, `missing` = yang tak ada.
- **skill_coverage** (deterministik): fraksi `jd.skills` (wajib) yang tercakup CV.
- **ats_readability** (deterministik): turunkan dari `cv.structure_report.issues` — mis. mulai 100, tiap `fatal` −25, tiap `warning` −8, clamp 0–100. Ini yang bikin skor **jujur & bisa dijelaskan**.
- **semantic** (pilih satu, rekomendasi A untuk MVP):
  - **A. Embeddings** (`text-embedding-3-small`): cosine rata-rata antara requirement JD dan bullet CV. Reproducible & murah.
  - B. LLM judge (0–100). Lebih gampang tapi kurang deterministik.
- **reason tiap komponen + `skill_gap` + `experience_gap` + `weak_bullets`**: **1 panggilan LLM terstruktur** yang menerima jd_json + cv_json + angka yang sudah dihitung, lalu menuliskan alasan Indonesia dan menandai bullet lemah. `weak_bullets[].id` **wajib** dari `sections.experience[].id`.
- `experience_gap` = **string** (bukan array).

> Kenapa angka deterministik, alasan LLM? Menepati BLUEPRINT §2 "skor jujur & transparan, tidak di-inflate" — LLM tidak boleh mengarang angka; ia hanya menjelaskan.

### 6.4 `/rewrite` — `services/rewriter.py`
- Input `bullet` + `jd_context`. Output `{suggestion, reasoning}` Indonesia.
- **Formula XYZ** (BLUEPRINT Momen B): "Melakukan X, dengan alat Y, menghasilkan dampak Z terukur."
- **Aturan keras anti-mengarang** (BLUEPRINT §2/§13): hanya menonjolkan yang tersirat di bullet asli; jika tak ada metrik, sarankan placeholder eksplisit (mis. "[isi jumlah/%]") — jangan mengarang angka.
- `temperature≈0.4`.

---

## 7. Detail teknis yang mudah terlewat

1. **Bahasa:** semua `reason`, `detail`, `suggestion`, `reasoning`, `experience_gap` **Bahasa Indonesia** (mock & FE Indonesia).
2. **`score` integer**, bukan float. `breakdown[*].score` juga 0–100 integer.
3. **`experience_gap` string**, `matched/missing/skill_gap` array string.
4. **Bullet ID stabil** lintas parse→match→rewrite→rescore.
5. **422 vs 500**: 422 hanya untuk CV tak terbaca di `/parse/cv`. Selebihnya sukses 200 atau error 5xx.
6. **CORS tidak perlu**: hanya BE (server-to-server) yang memanggil AI Service; FE tak pernah langsung (invariant memory). Tak perlu buka CORS ke browser.
7. **Ukuran file**: BE sudah batasi `MAX_CV_SIZE_MB=5` sebelum kirim; AI Service tetap defensif.
8. **Timeout**: BE beri 90–120s/endpoint. Panggilan OpenAI jauh lebih cepat dari Ollama lokal, jadi aman.
9. **`python-multipart`** wajib di requirements agar FastAPI baca `UploadFile`.
10. **Idempindependen**: service **stateless** — tak simpan apa pun (privasi + BE yang punya DB). Jangan tulis ke `outputs/` dari jalur service.

---

## 8. ✅ [SELESAI 2026-07-03] Titik rawan: Rescore (Momen D) harus JUJUR — perlu ubahan kecil di BE

**Temuan:** Saat rescore, BE (`pipeline.go:runRescore`) memanggil `/match` ulang **memakai `sections` CV yang LAMA** dan hanya menambahkan penanda `APPLIED_REWRITES=n` ke `raw_text`. Teks bullet hasil perbaikan (`AppliedRewrite.NewText`) **sudah tersedia di `j.applied` tapi tidak dipakai** untuk matching — hanya jumlahnya (`len(j.applied)`) yang dipakai.

`MockClient` "curang" jujur-jujuran: ia menaikkan skor sebesar `n*9` berdasar penanda itu. Untuk AI **sungguhan**, menaikkan skor dari sekadar hitungan = **melanggar janji "skor jujur"** (BLUEPRINT §2) — CV yang di-match tetap CV lama.

**Rekomendasi (pilih 1):**
- **8A (disarankan, ubahan BE minimal).** Di `runRescore`, sebelum panggil `/match`, **substitusikan** `NewText` tiap `AppliedRewrite` ke `cv.Sections.experience[]` yang `id`-nya cocok. Dengan begitu AI me-*match* CV yang **benar-benar diperbaiki** → skor naik secara jujur. Penanda `APPLIED_REWRITES` bisa dibuang. Data sudah ada di `j.applied`; ini ±15 baris Go.
- **8B (tanpa ubah BE).** AI Service membaca penanda `APPLIED_REWRITES=n` dan menaikkan skor seperti mock. **Tidak disarankan** — meniru kecurangan mock, bukan penilaian nyata.

➡️ **Sudah diterapkan** (2026-07-03): `applyRewrites()` di `BE/internal/analyses/pipeline.go` men-splice `AppliedRewrite.NewText` ke `sections.experience[]` (match by `id`) dan ke `rawText` (best-effort substring replace) sebelum `runRescore` memanggil `/match`. `AppliedMarker` tetap dipertahankan di `rawText` hanya untuk kompatibilitas `MockClient` (`AI_MOCK=true`) — AI Service sungguhan cukup membaca `sections`/`raw_text` yang sudah diperbarui, tidak perlu memedulikan marker itu. Diuji via `BE/internal/analyses/pipeline_test.go` (`TestApplyRewrites`, `TestApplyRewritesNoop`) + full suite BE hijau (10/10).

---

## 9. Perubahan dependensi & konfigurasi

`requirements.txt` — **tambah**:
```
fastapi
uvicorn[standard]
python-multipart
pymupdf            # fitz — teks + analisis struktur (Momen A)
# (opsional fase lanjut) pytesseract, pillow  # OCR CV hasil scan
```
Sudah ada & dipakai ulang: `openai`, `python-dotenv`, `pydantic`, `pdfminer.six`, `python-docx`, `spacy`/`en_core_web_sm` (opsional heuristik exp/edu).

`.env` (sudah ada `OPENAI_API_KEY`) — **tambah**:
```
LLM_PROVIDER=openai
OPENAI_MODEL_EXTRACT=gpt-4o-mini
OPENAI_MODEL_REASON=gpt-4o
OPENAI_EMBED_MODEL=text-embedding-3-small
AI_PORT=8000
```
`BE/.env` sudah benar: `AI_SERVICE_URL=http://localhost:8000`, tinggal `AI_MOCK=false` saat siap.

---

## 10. Fase implementasi (urutan kerja)

**Fase A — Kerangka service (bisa dites tanpa LLM):**
1. `app/config.py`, `app/schemas.py` (Pydantic mirror §1), `app/main.py` dengan 4 route + handler 422/500.
2. Route balas **data statis meniru mock** dulu → jalankan `uvicorn`, arahkan BE ke sana (`AI_MOCK=false`), pastikan seluruh alur FE↔BE↔AI **hijau** dengan data statis. (Membuktikan wiring sebelum LLM.)

**Fase B — PDF & struktur (Momen A):**
3. `services/pdf.py` PyMuPDF: `raw_text` + `structure_report`. Uji dengan `data/cvs/` & `data/job/Vacancy.pdf` yang sudah ada + beberapa CV nyata (BLUEPRINT Fase 0).
4. `/parse/cv` balas struktur nyata; sisanya masih statis.

**Fase C — LLM nyata:**
5. `app/llm/openai_provider.py` + `base.py` (seam).
6. `jd_analyzer.py` → `/analyze/jd` nyata.
7. `cv_parser.py` → sections + bullet IDs.
8. `matcher.py` → skor deterministik + reason LLM (+ embeddings semantic).
9. `rewriter.py` → XYZ.

**Fase D — Rescore jujur:**
10. Terapkan **§8A** di `BE/internal/analyses/pipeline.go` (`runRescore`).

**Fase E — Verifikasi & tuning:**
11. Flip `AI_MOCK=false`, jalankan ulang skenario E2E FE. Kalibrasi bobot/threshold skor.

---

## 11. Checklist "Definition of Done"

- [x] `uvicorn app.main:app --port 8090` (8000 dipakai proses lain di mesin dev) hidup; `GET /health` OK — selesai 2026-07-03.
- [x] `/analyze/jd` balas skema §1.1 (Indonesia), lulus validasi Pydantic; diuji: tidak mengarang `company` saat tak disebutkan (balas `""`).
- [x] `/parse/cv` balas `raw_text`+`sections`(+bullet IDs)+`structure_report`; **422** untuk CV tak terbaca (diuji dg file kosong & PDF corrupt).
- [x] `structure_report.issues[].severity ∈ {fatal,warning}`; deteksi multi_column/photo diuji lolos dg PDF sintetis 2-kolom+gambar; table/header_footer/nonstandard_font terimplementasi belum diuji dg kasus positif nyata.
- [x] `/match`: `score` int 0–100; `breakdown` **4 kunci** persis; `weak_bullets[].id` cocok `sections.experience[].id`; `experience_gap` string. Diuji end-to-end dg OpenAI asli.
- [x] `/rewrite`: XYZ, Indonesia, tak mengarang angka — diuji: LLM memakai placeholder `[isi jumlah/persentase dampaknya]` alih-alih mengarang metrik.
- [x] BE `AI_MOCK=false` → alur penuh backend hijau (via API langsung, bukan lewat FE browser): create analysis → poll → DONE → **rescore skor naik jujur (62→81, keyword 43→86) karena teks bullet benar-benar berubah** → before/after tersimpan. *(FE belum diklik manual di browser — lihat §11a.)*
- [x] **§8A** diterapkan di BE (rescore memakai teks bullet baru) — selesai 2026-07-03, diverifikasi dg AI asli (bukan cuma mock).
- [ ] Mode HRD lama (`main.py` / `dashboard.py`) **masih jalan** (tidak diregres) — belum diuji ulang sejak requirements.txt disentuh.
- [x] Copy produk/janji privasi disesuaikan (§5) — BLUEPRINT.md, BACKEND.md, dan 2 string user-facing (`BE/internal/httpx/errors.go`, `FE/lib/copy.ts`) sudah diperbaiki.

### 11a. Yang BELUM diverifikasi (jujur, bukan diklaim selesai)
- [x] ~~FE di browser belum diklik manual~~ **Sudah** (2026-07-03, via Playwright): analyze→upload CV nyata→result→apply rewrite→rescore→history, semua render benar dg AI asli (lihat §11c).
- **Kalibrasi bobot skor** (§9 BLUEPRINT) baru diuji dg 2 CV (1 sintetis + 1 nyata); perlu lebih banyak CV nyata beragam format sebelum dianggap terkalibrasi.
- **OCR fallback** (CV hasil scan) belum diimplementasikan — `pdf.py` akan raise `PDFUnreadableError` (422) untuk PDF tanpa teks.
- **Mode HRD lama** (`main.py`/`dashboard.py`, dependency spaCy/streamlit) belum dites ulang setelah venv baru dibuat — venv ini fokus ke `app/` (FastAPI), belum tentu semua dependency lama (spaCy model, dll) terpasang di venv yang sama.

### 11b. Testing dengan data nyata (2026-07-03, folder `Testing/`)
Diuji dengan CV PDF nyata (Raisul Agung Prabankoro, ada foto + sedikit layout 2-kolom di bagian skills) vs JD nyata (Mobile Developer Flutter, Meratus Group). Hasil kualitatif masuk akal: `matched`/`missing` keywords akurat (Flutter/RESTful API cocok; BLoC/Provider/Riverpod/GetX/Agile hilang — memang benar tak disebut di CV), `experience_gap` akurat, rewrite memakai placeholder bukan mengarang angka.

**Bug ditemukan & diperbaiki**: heuristik `multi_column` di `pdf.py` awalnya false-positive pada CV single-column nyata ini — ia hanya menghitung jumlah blok teks per sisi halaman, tanpa mengecek apakah blok kiri & kanan benar-benar tumpang-tindih di rentang-y yang sama. CV ini punya strip kontak (header) dan grid skill kecil yang sengaja 2 kolom, tapi badan CV (pengalaman kerja) sepenuhnya 1 kolom — ini ter-flag `fatal` secara keliru, menjatuhkan `ats_readability` (59→84 setelah fix). Diperbaiki dengan `_has_real_multi_column()`: sekarang mensyaratkan overlap-y kiri/kanan mencakup >25% tinggi halaman sebelum menandai fatal. Divalidasi dengan 2 kasus lokal (tanpa panggilan OpenAI, jadi tanpa biaya): CV nyata ini (tidak lagi ter-flag) dan PDF sintetis 2-kolom penuh-halaman (tetap ter-flag benar).

**Optimasi biaya token** (diterapkan sebelum testing nyata): `max_tokens` output dibatasi di tiap panggilan (500 utk /analyze/jd, 900 utk sections CV, 500 utk match reasoning, 250 utk rewrite); input JD/CV dipotong ke `MAX_JD_CHARS`/`MAX_CV_CHARS`=6000 karakter sebelum dikirim; list skill/bullet di context match dibatasi (`[:30]`/`[:20]`) jaga-jaga CV/JD tak wajar panjang; `format_issues` di context match hanya kirim `type`+`severity` (buang `detail` yang panjang); model reasoning default diturunkan dari `gpt-4o` ke `gpt-4o-mini` (jauh lebih murah, cukup untuk tugas terstruktur pendek ini).

### 11c. Verifikasi FE di browser (2026-07-03, via Playwright headless)
Alur penuh diklik lewat FE sungguhan (bukan curl): landing → /analyze (paste JD nyata + upload CV PDF nyata) → submit → result page (poll sampai DONE) → klik "Apply" rewrite → klik "Hitung Ulang Skor" (rescore) → /history. Semua render benar: skor, rincian 4 komponen, laporan format ATS (0 fatal setelah fix §11b), kecocokan keyword, kesenjangan skill, 5 kartu usulan rewrite — semua konsisten dg data yang sama saat dites lewat curl.

**Bug ditemukan & diperbaiki**: `components/result/before-after.tsx` (Momen D) selalu menampilkan badge hijau "🎉 Momen naik level" apa pun hasilnya — termasuk saat skor rescore justru **turun** (49→48 di test ini, karena bullet yang di-"Apply" — proyek WordPress kampus — memang kurang relevan ke lowongan Mobile Developer Flutter, jadi wajar tak menaikkan skor). Teks "Naik 0 poin" juga menyembunyikan bahwa skor sebenarnya turun. Ini melanggar prinsip "JUJUR/tidak di-inflate" (BLUEPRINT §0/§2). Diperbaiki: komponen sekarang kondisional — hijau+"naik level" hanya jika skor benar naik; abu-abu+teks jujur ("Turun N poin — bullet kurang relevan, coba yang lain" / "Skor belum berubah") jika turun/tetap. Dicek: FE recompile bersih tanpa error (Turbopack, gratis — tidak perlu re-run OpenAI). Halaman `/history` sudah lebih dulu jujur (pewarnaan skor absolut, bukan klaim "naik"), tidak perlu diubah.

**Catatan non-bug**: console log sempat menampilkan 2x `401` dari `/auth/me` — ini expected (dicek `auth-context.tsx`: 401 di-catch dan diperlakukan sebagai "belum login/guest", bukan error yang bocor ke UI).

---

## 12. Risiko & keputusan terbuka

| Risiko / Pertanyaan | Catatan |
|---|---|
| **Privasi vs OpenAI** | Melanggar janji "lokal" BLUEPRINT §14. Perlu keputusan: ubah copy sekarang, siapkan Ollama untuk rilis (seam §5 menjaga pintu ini). |
| **ats_readability perlu PDF** | Skor readability hanya bermakna untuk PDF. DOCX/teks → beri nilai netral + catatan. |
| **Konsistensi bullet ID** | Kalau CV di-parse ulang, ID harus sama. Pakai urutan kemunculan, bukan hash isi. |
| **Kalibrasi skor** | Bobot §6.3 dari BLUEPRINT; perlu diuji dgn CV nyata agar tak terlalu keras/lunak. |
| **Biaya OpenAI** | Tiap analisis = beberapa panggilan. Pakai model mini untuk ekstraksi menekan biaya. |
| **OCR CV scan** | Ditunda (fase lanjut) — Tesseract fallback bila `raw_text` kosong. |

---

## 13. Yang TIDAK berubah (jaga stabilitas)

- Kontrak `BE/internal/aiclient/*` & `FE/lib/types.ts` — AI Service menyesuaikan diri ke sana, **bukan sebaliknya**. Satu-satunya usul ubah BE = §8A (logika rescore, bukan kontrak wire).
- Envelope, status enum, auth cookie, integer ID — ranah BE/FE, tak tersentuh.
- Mode HRD batch (`src/`, `main.py`, `dashboard.py`, `outputs/`) tetap ada.
```
