# المحوّل البحثي — الـ Backend (FastAPI)

يلفّ محرّك **marker-pdf** (نفس المحرّك الدقيق في `ultimate_converter.py`) ويعرضه كـ API
يبثّ خطوات التنفيذ لحظياً إلى الموقع، فتظهر في شاشة اللوج والدائرة والنسبة تلقائياً.

---

## 1. التشغيل محلياً (للتجربة)

```bash
cd backend
python -m venv venv
source venv/bin/activate        # على ويندوز: venv\Scripts\activate
pip install -r requirements.txt

# (اختياري) تحميل النماذج مقدّماً حتى لا يتأخر أول طلب:
python -c "from marker.models import create_model_dict; create_model_dict()"

python app.py                    # يعمل على http://localhost:8000
```

أول تشغيل هيحمّل نماذج الذكاء الاصطناعي (مئات الميجابايت) مرّة واحدة، وبعدها بتبقى جاهزة.

تأكّد إنه شغّال:
```bash
curl http://localhost:8000/health
```

---

## 2. ربطه بالموقع

في ملف `index.html`، غيّر سطر الإعدادات في أول الـ `<script>`:

```js
const CONFIG = {
  apiEndpoint: "http://localhost:8000/convert",   // أو رابط السيرفر بعد النشر + /convert
  showAdSlot: true,
  accurateEstimateMs: 12000
};
```

كده الوضع **الدقيق** هيرسل الملف للـ API، وشاشة اللوج هتعرض الخطوات **الحقيقية** من marker
(تحليل التخطيط، المعادلات، الجداول) مع نسبة تقدّم فعلية.

> **مهم للإنتاج:** لو الموقع والـ API على نطاقين مختلفين، حدّد نطاق موقعك في متغيّر البيئة
> `ALLOWED_ORIGINS` بدل `*`، مثلاً: `ALLOWED_ORIGINS=https://yourdomain.com`.

---

## 3. النشر بـ Docker

```bash
cd backend
docker build -t research-md-api .
docker run -p 8000:8000 -e ALLOWED_ORIGINS=https://yourdomain.com research-md-api
```

الـ `Dockerfile` بيحمّل النماذج وقت البناء، فأول طلب بيبقى سريع.

**استضافات مناسبة** (marker يحتاج ذاكرة كبيرة، وأسرع بكثير على GPU):
Railway, Render, Fly.io, Hugging Face Spaces، أو أي VPS. للسرعة القصوى استخدم سيرفر فيه
كرت شاشة NVIDIA وثبّت torch بنسخة CUDA المناسبة.

---

## صيغة البثّ (NDJSON)

الـ API بيرجّع `application/x-ndjson` — سطر JSON مستقل لكل حدث، والموقع بيقرأها لحظياً:

```
{"stage": "acc_stage1"}
{"log": "loading layout model"}
{"progress": 42}
{"log": "Recognizing tables 100% 8/8"}
{"markdown": "# العنوان\n\n..."}
```

عند الفشل يُرسَل سطر واحد: `{"error": "..."}`.

---

## تقليل وقت التحويل

- **النماذج تُحمَّل مرّة واحدة** عند الإقلاع (مطبَّق بالفعل) — أكبر مكسب.
- **استخدم GPU**: ثبّت torch بنسخة CUDA؛ يقلّل الوقت لأضعاف.
- على أجهزة أبل: `export TORCH_DEVICE=mps`.
- للملفات المكرّرة، ممكن تضيف كاش بمفتاح = هاش الملف (SHA-256) لإرجاع نتيجة محفوظة فوراً.
- التحويلات حالياً بالتتابع (قفل واحد). لو محتاج توازي، شغّل أكثر من نسخة/‏worker
  كلٌّ بذاكرته الخاصة، أو استخدم طابور مهام (مثل Celery/RQ).
