# استفاده از یک image پایه سبک پایتون
FROM python:3.11-slim-bullseye

# تنظیم دایرکتوری کار
WORKDIR /app

# نصب واتساپ و سایر dependencies سیستمی
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# کپی فایل requirements و نصب dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# کپی بقیه فایل‌های اپلیکیشن
COPY . .

# اجرای اسکریپت پایتون
CMD ["python", "bot.py"]
