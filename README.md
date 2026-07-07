# AI Service — CV Screening ("Teman Melamar Kerja")

Layanan Python yang menjadi "otak AI" dari sistem CV Screening. Dipanggil oleh **Web Backend (Go)** lewat HTTP — tidak pernah diakses langsung oleh Frontend. Referensi desain lengkap: [`../Brain/BLUEPRINT.md`](../Brain/BLUEPRINT.md) dan [`ADJUSTMENT_PLAN.md`](ADJUSTMENT_PLAN.md).

Folder ini punya **dua mode**, keduanya berbagi Python environment yang sama:

| Mode | Lokasi kode | Untuk apa |
|---|---|---|
| **AI Service (utama)** | `app/` — FastAPI | Dipakai produk sungguhan: 1 CV vs 1 lowongan → skor, laporan ATS, rewrite. Ini yang dipanggil BE. |
| **HRD Batch Tool (legacy)** | `src/`, `main.py`, `dashboard.py` | Alat terpisah: banyak CV vs 1 lowongan → ranking CSV + dashboard Streamlit. Tidak dipanggil BE, dijalankan manual kalau perlu. |

---

## 1. Prasyarat

- **Python 3.11+** untuk AI Service (mode utama) — sudah diuji jalan mulus di Python 3.14 juga, semua dependency (FastAPI/PyMuPDF/OpenAI) punya wheel yang cocok.
  > Kalau juga mau pakai **HRD Batch Tool** (legacy, §4): dependency-nya (spaCy dkk) **belum mendukung Python 3.14+** (paket `blis` mensyaratkan `<3.14`). Pakai **Python 3.11–3.13** kalau butuh mode ini.
- **API key OpenAI aktif** dengan **billing/kredit sudah diisi** — akun baru tanpa billing akan gagal dengan error `insufficient_quota` (bukan error key salah). Isi billing di platform OpenAI (Settings → Billing) sebelum lanjut.
- **Jalankan semua perintah di bawah dari PowerShell atau Command Prompt Windows** — bukan dari WSL/Git Bash. Venv yang dibuat `python -m venv venv` di Windows berisi `python.exe` (binary Windows), tidak bisa diaktifkan/dipakai langsung dari shell WSL (`.\venv\Scripts\Activate.ps1` juga sintaks PowerShell, tidak dikenali bash). Kalau memang mau kerja dari WSL, buat venv Linux terpisah di sana (`python3 -m venv venv-wsl && source venv-wsl/bin/activate && pip install -r requirements.txt`).
  > Kalau PowerShell menolak `Activate.ps1` dengan error *"execution of scripts is disabled"*, jalankan sekali: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, lalu ulangi.

---

## 2. Setup (sekali saja)

```powershell
cd AIService

# 1. Buat virtual environment
python -m venv venv

# 2. Aktifkan venv
.\venv\Scripts\Activate.ps1

# 3. Install dependency AI Service (mode utama — cukup ini untuk dipanggil BE)
pip install -r requirements.txt

# 3b. (Opsional) mau juga pakai HRD Batch Tool? Tambah dependency legacy-nya
#     (butuh Python 3.11-3.13, lihat §1):
# pip install -r requirements-hrd.txt

# 4. Salin template env, lalu isi API key-mu
copy .env.example .env
notepad .env
```

Isi `.env` minimal:
```
OPENAI_API_KEY=sk-...isi-punyamu...
```
Baris lain di `.env.example` sudah punya default yang masuk akal (lihat §5) — tidak wajib diubah untuk mulai.

> **Catatan biaya**: field `OPENAI_MODEL_*` di `.env.example` sudah diarahkan ke model yang murah (`gpt-4o-mini`), dan panjang input yang dikirim ke OpenAI sudah dibatasi (`MAX_JD_CHARS`/`MAX_CV_CHARS`) supaya JD/CV yang sangat panjang tidak membengkakkan biaya per analisis.

---

## 3. Menjalankan AI Service (mode utama — dipanggil BE)

```powershell
cd AIService
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

- Server jalan di `http://localhost:8000` (harus sama dengan `AI_SERVICE_URL` di `BE/.env`).
- **Kalau port 8000 sudah dipakai proses lain** di komputermu, jalankan di port lain, mis. `--port 8090`, lalu ubah `AI_SERVICE_URL=http://localhost:8090` di `BE/.env` supaya BE menemukannya.
- `--reload` bikin server restart otomatis tiap kali file `app/` berubah — enak untuk development, hapus flag ini kalau menjalankan di production.

### Cek server hidup
```powershell
curl http://localhost:8000/health
# -> {"status":"ok"}
```

### Endpoint yang diekspos (dipanggil BE, bukan untuk dipanggil FE langsung)

| Endpoint | Body | Balasan | Catatan |
|---|---|---|---|
| `GET /health` | – | `{"status":"ok"}` | cek hidup |
| `POST /analyze/jd` | `{"text": "..."}` | title, company, skills, keywords, experience, education | ekstrak requirement lowongan |
| `POST /parse/cv` | multipart file (PDF) | raw_text, sections, structure_report | ekstrak CV + laporan format ATS. Balas **HTTP 422** kalau CV tak terbaca |
| `POST /match` | `{"jd_json", "cv_json"}` | score (0-100), breakdown 4 komponen, matched/missing, skill_gap, experience_gap, weak_bullets | skor deterministik + alasan dari LLM |
| `POST /rewrite` | `{"bullet", "jd_context"}` | suggestion, reasoning | rewrite 1 bullet CV (formula XYZ) |

Dokumentasi interaktif otomatis (Swagger) tersedia di `http://localhost:8000/docs` selama server jalan.

---

## 4. Menjalankan HRD Batch Tool (mode legacy, opsional)

> Butuh **Python 3.11–3.13** (bukan 3.14+, lihat §1) dan `pip install -r requirements-hrd.txt` sudah dijalankan (§2 langkah 3b).

Alat terpisah untuk HRD: taruh banyak file CV di `data/cvs/` dan 1 lowongan di `data/job/`, lalu:

```powershell
.\venv\Scripts\Activate.ps1

# Jalankan pipeline lengkap (ekstrak teks -> parse -> vectorize -> scoring -> plot)
python main.py

# ATAU buka dashboard interaktif Streamlit
streamlit run dashboard.py
```

Hasil masuk ke folder `outputs/` (`ranking.csv`, `entities.json`, `plots/`). Dashboard Streamlit juga punya fitur upload CV/lowongan dan "Deep Analysis (GPT)" per kandidat — pakai `OPENAI_API_KEY` yang sama dari `.env`.

---

## 5. Konfigurasi (`.env`)

| Variabel | Default | Keterangan |
|---|---|---|
| `OPENAI_API_KEY` | *(wajib diisi)* | API key OpenAI-mu, billing harus aktif |
| `LLM_PROVIDER` | `openai` | Seam provider — `ollama` direncanakan untuk mode privasi-penuh, belum diimplementasikan |
| `OPENAI_MODEL_EXTRACT` | `gpt-4o-mini` | Model untuk `/analyze/jd` & ekstraksi section CV (murah, cukup untuk tugas ekstraksi terstruktur) |
| `OPENAI_MODEL_REASON` | `gpt-4o-mini` | Model untuk alasan `/match` & `/rewrite`. Bisa dinaikkan ke `gpt-4o` kalau kualitas tulisan dirasa kurang tajam (lebih mahal) |
| `OPENAI_EMBED_MODEL` | `text-embedding-3-small` | Model embedding untuk skor semantic di `/match` |
| `MAX_JD_CHARS` | `6000` | Batas panjang teks lowongan yang dikirim ke LLM (hemat biaya kalau JD sangat panjang) |
| `MAX_CV_CHARS` | `6000` | Batas panjang teks CV yang dikirim ke LLM |
| `MAX_EMBED_CHARS` | `4000` | Batas panjang teks untuk panggilan embedding |
| `AI_PORT` | `8000` | Informasional saja — port sungguhan ditentukan oleh flag `--port` saat menjalankan `uvicorn` |

---

## 6. Struktur folder

```
AIService/
├── app/                     # ← AI Service utama (FastAPI, dipanggil BE)
│   ├── main.py              # route: /health, /analyze/jd, /parse/cv, /match, /rewrite
│   ├── config.py            # baca .env -> Settings
│   ├── schemas.py           # skema Pydantic — cerminan persis kontrak BE
│   ├── llm/
│   │   ├── base.py          # interface LLMProvider (seam ganti provider)
│   │   └── openai_provider.py
│   └── services/
│       ├── pdf.py           # PyMuPDF: ekstrak teks + deteksi struktur (Momen A)
│       ├── jd_analyzer.py   # /analyze/jd
│       ├── cv_parser.py     # /parse/cv (raw_text nyata + sections via LLM)
│       ├── matcher.py       # /match (skor deterministik + alasan LLM)
│       └── rewriter.py      # /rewrite (formula XYZ)
├── src/                     # ← HRD Batch Tool (legacy, tidak dipanggil BE)
│   ├── text_extraction.py, entity_extraction.py, gpt_vacancy_parser.py,
│   │   vectorize.py, scoring.py, plot_results.py, utils.py
├── data/cvs/, data/job/     # input untuk HRD Batch Tool
├── outputs/                 # hasil HRD Batch Tool (ranking.csv, plots, dll)
├── dashboard.py             # dashboard Streamlit (HRD Batch Tool)
├── main.py                  # entrypoint pipeline HRD Batch Tool
├── requirements.txt         # dependency AI Service utama (Python 3.11+)
├── requirements-hrd.txt     # dependency TAMBAHAN utk HRD Batch Tool (Python 3.11-3.13 saja)
├── .env / .env.example
└── ADJUSTMENT_PLAN.md       # dokumen rencana & histori adjust ke kontrak BE
```

---

## 7. Troubleshooting

| Gejala | Penyebab | Solusi |
|---|---|---|
| `insufficient_quota` saat panggil OpenAI | Billing belum aktif di akun OpenAI | Isi payment method di platform OpenAI, key yang sama akan langsung jalan (tak perlu generate ulang) |
| BE gagal konek, error `AI_SERVICE_DOWN` | AI Service belum jalan / port tak cocok | Pastikan `uvicorn` jalan, cek `AI_SERVICE_URL` di `BE/.env` cocok dengan port AI Service |
| `422` saat `/parse/cv` | CV memang tak terbaca (hasil scan gambar tanpa teks, atau file bukan PDF valid) | OCR belum diimplementasikan (lihat `ADJUSTMENT_PLAN.md` §11a) — export CV sebagai PDF berbasis teks |
| Port 8000 dipakai proses lain | Aplikasi lain (mis. dev server bahasa lain) sudah pakai port itu | Jalankan AI Service di port lain (`--port 8090`) + sesuaikan `AI_SERVICE_URL` di `BE/.env` |
| `pip install -r requirements-hrd.txt` gagal: `No matching distribution found for blis==1.3.0` | Kamu pakai Python 3.14+; `blis` (dependency spaCy, dipakai HRD Batch Tool) belum punya wheel untuk versi itu | Pakai Python 3.11–3.13 khusus untuk mode HRD Batch Tool (buat venv terpisah kalau perlu). AI Service utama (`requirements.txt` saja) tidak terpengaruh, tetap jalan di 3.14+ |

---

## 8. Menjalankan bersama BE & FE (urutan startup)

```
1. AI Service     uvicorn app.main:app --port 8000          (folder ini)
2. Web Backend    go run ./cmd/server                        (../BE, AI_MOCK=false)
3. Frontend       npm run dev                                (../FE)
```
Buka `http://localhost:3000` untuk mulai memakai aplikasi. Detail tiap service ada di README masing-masing (`../BE/README.md`, `../FE/README.md`).
