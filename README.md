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
