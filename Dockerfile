FROM python:3.11-slim

# أدوات نظام يحتاجها marker/torch لمعالجة الصور والـ PDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# تحميل نماذج الذكاء الاصطناعي أثناء البناء حتى لا يتأخر أول طلب
RUN python -c "from marker.models import create_model_dict; create_model_dict()"

COPY app.py .

ENV PORT=8000
EXPOSE 8000
CMD ["python", "app.py"]
