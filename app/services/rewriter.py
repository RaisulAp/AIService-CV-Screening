# FASE C: /rewrite nyata — formula XYZ, aturan keras anti-mengarang (BLUEPRINT §2/§13).

from app.config import settings
from app.llm import get_provider
from app.schemas import RewriteResult

_SYSTEM_PROMPT = """Tulis ulang SATU bullet CV pakai formula XYZ: aksi konkret (X) + alat/metode yang dipakai (Y) + dampak terukur (Z), digabung jadi 1-2 kalimat yang mengalir wajar.

ATURAN BAHASA (penting, DUA field beda aturan):
- "suggestion": deteksi bahasa "Bullet asli" di bawah, lalu tulis dalam BAHASA YANG SAMA PERSIS dengan bullet asli itu — kalau bullet asli Bahasa Inggris, balas Bahasa Inggris; kalau Indonesia, balas Indonesia. Wajib, karena teks ini ditempel langsung menggantikan bullet itu di CV asli.
- "reasoning": SELALU Bahasa Indonesia, apa pun bahasa bullet aslinya — ini penjelasan untuk pengguna aplikasi (berbahasa Indonesia), bukan teks yang masuk ke CV.

ATURAN KETAT:
- HANYA tonjolkan yang tersirat di bullet asli — JANGAN mengarang skill/alat/angka yang tak ada.
- Jika tak ada dampak terukur di bullet asli, pakai placeholder eksplisit sesuai bahasa bullet (mis. "[isi jumlah/persentase dampaknya]" utk Indonesia, "[add the quantified impact]" utk Inggris) — JANGAN mengarang angka.
- JANGAN PERNAH menulis label formula ("X", "Y", "Z", atau bracket seperti "[X-tindakan]") secara literal di "suggestion" — itu hanya panduan struktur untukmu, bukan teks yang boleh muncul di hasil akhir.
- Konteks lowongan hanya untuk pilih kata kunci relevan, BUKAN menambah klaim baru.

Contoh 1 — bullet asli Bahasa Indonesia "Mengurus media sosial organisasi." -> suggestion BENAR (tetap Bahasa Indonesia): "Mengelola media sosial organisasi menggunakan Instagram dan Canva, menghasilkan [isi jumlah/persentase dampaknya]." (SALAH: pakai label harfiah spt "[Y-alat]")

Contoh 2 — bullet asli Bahasa Inggris "Managed the organization's social media." -> suggestion BENAR (tetap Bahasa Inggris, JANGAN diterjemahkan ke Indonesia): "Managed the organization's social media using Instagram and Canva, resulting in [add the quantified impact]." (SALAH: menerjemahkan ke Bahasa Indonesia, atau pakai label harfiah)

Balas HANYA JSON: {"suggestion": "...", "reasoning": "..."}"""


def rewrite(bullet: str, jd_context: str) -> RewriteResult:
    provider = get_provider()
    data = provider.chat_json(
        system=_SYSTEM_PROMPT,
        user=f"Bullet asli: {bullet}\nKonteks lowongan: {jd_context}",
        model=settings.openai_model_reason,
        temperature=0.4,
        max_tokens=250,
    )
    return RewriteResult(
        suggestion=(data.get("suggestion") or "").strip(),
        reasoning=(data.get("reasoning") or "").strip(),
    )
