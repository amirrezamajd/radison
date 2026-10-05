# املاک رادیسون (Radison) — Django

سایت معرفی فایل‌های املاک رادیسون با صفحه اصلی، پاپ‌آپ جزئیات ملک، و پنل ادمین برای استخراج از CRM.

## اجرا

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

سپس آدرس‌ها:

- سایت: http://127.0.0.1:8000/
- پنل استخراج: http://127.0.0.1:8000/panel/
- ادمین جنگو: http://127.0.0.1:8000/django-admin/

## استخراج ملک

در پنل، لینک عمومی CRM مثل زیر را وارد کنید:

`https://crmamlak.app/p/82nmimfhqo`

عنوان، قیمت، مشخصات و تصاویر استخراج و در سایت ذخیره می‌شوند.

## استقرار روی سرور

پروژه برای Python 3.12 و SQLite موجود در سرویس‌های میزبانی آماده شده است.
Django روی نسخه LTS 5.2 پین شده و فایل‌های static با WhiteNoise سرو می‌شوند.

متغیرهای محیطی ضروری:

```text
DJANGO_SECRET_KEY=<یک مقدار طولانی و تصادفی>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-domain.ir,www.your-domain.ir,.liara.run
DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain.ir,https://www.your-domain.ir
```

اگر SQLite استفاده می‌کنید، **حتماً** در ParsPack یک دیسک پایدار بسازید:

1. ویرایش پیکربندی → پیکربندی دیسک‌ها → افزودن دیسک
2. مسیر mount را `/data` بگذارید (مثلاً ۲GB)
3. این متغیرها را اضافه کنید:

```text
SQLITE_PATH=/data/db.sqlite3
MEDIA_ROOT=/data/media
DJANGO_SERVE_MEDIA=True
```

بدون Volume، هر Redeploy یوزر و ملک‌ها را پاک می‌کند چون فایل‌سیستم اپ موقتی است.

بعد از اولین دیپلوی روی دیسک پایدار، یک‌بار سوپریوزر بسازید:

```bash
python manage.py shell -c "from django.contrib.auth import get_user_model; U=get_user_model(); u,c=U.objects.get_or_create(username='amirrezamajd', defaults={'is_staff':True,'is_superuser':True,'is_active':True}); u.set_password('@Am1376@'); u.is_staff=u.is_superuser=u.is_active=True; u.save(); print('ok', c)"
```

در لاگ استارت باید چیزی شبیه این ببینید:

`[radison] DEBUG=False SQLITE_PATH=/data/db.sqlite3 MEDIA_ROOT=/data/media`

اگر PostgreSQL دارید، به‌جای `SQLITE_PATH` مقدار `DATABASE_URL` را تنظیم کنید:

```text
DATABASE_URL=postgresql://user:password@host:5432/database
```

دستورات build/release:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

دستور اجرا:

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 180
```

قبل از انتشار نهایی، رمز کاربر ادمین آزمایشی را تغییر دهید. فایل نمونه
تنظیمات در `.env.example` قرار دارد.
