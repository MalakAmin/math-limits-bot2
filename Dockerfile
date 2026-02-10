FROM python:3.11-slim

WORKDIR /app

# تثبيت مكتبات النظام المطلوبة
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# نسخ متطلبات المشروع
COPY requirements.txt .

# تثبيت مكتبات Python
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي الملفات
COPY . .

# تشغيل البوت
CMD ["python", "app.py"]
