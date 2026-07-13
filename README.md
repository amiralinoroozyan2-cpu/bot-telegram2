# 🎮 ربات واسطه خرید و فروش اکانت بازی

ربات تلگرام برای خرید و فروش اکانت بازی‌های کلش آف کلنز، فری‌فایر، پابجی و کالاف دیوتی.

## ✨ امکانات

- ✅ عضویت اجباری در کانال
- 📢 ثبت آگهی فروش با مراحل کامل (عکس، فیلم، اطلاعات محرمانه)
- 🛒 فلوی خرید با ارسال رسید و تأیید ادمین
- 📋 مدیریت آگهی‌های خودم
- 👮 پنل ادمین (ban/unban/broadcast/users)
- ⏰ تایمر ۷۲ ساعته برای مسدود خودکار فروشنده‌های متخلف
- 🔒 ذخیره ایمیل/رمز فقط در دیتابیس (هرگز در کانال نشان داده نمی‌شود)

---

## 🚀 نصب و راه‌اندازی روی Render

### ۱. کلون کردن روی GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/USERNAME/REPO.git
git push -u origin main
```

### ۲. ساختن سرویس روی Render
- به [render.com](https://render.com) برو و یک **Web Service** جدید بساز
- به ریپو گیت‌هاب خود وصل شو
- تنظیمات:
  - **Build Command:** `pip install -r requirements.txt`
  - **Start Command:** `python main.py`
  - **Instance Type:** Free

### ۳. متغیرهای محیطی
در پنل Render بخش **Environment Variables** این‌ها را اضافه کن:

| کلید | مقدار |
|------|-------|
| `BOT_TOKEN` | توکن ربات از @BotFather |
| `CHANNEL_ID` | یوزرنیم کانال مثل `@mychannel` |
| `ADMIN_IDS` | آیدی عددی ادمین‌ها با کاما جدا (مثل `123456789`) |
| `CARD_NUMBER` | شماره کارت برای پرداخت |
| `PORT` | `8080` |

### ۴. UptimeRobot (جلوگیری از خواب رفتن)
- به [uptimerobot.com](https://uptimerobot.com) برو
- یک مانیتور **HTTP(s)** بساز
- آدرس: `https://your-app-name.onrender.com/`
- هر ۵ دقیقه پینگ بشه

---

## 📁 ساختار فایل‌ها

```
├── main.py              # نقطه ورود اصلی
├── keep_alive.py        # وب‌سرور Flask برای UptimeRobot
├── storage.py           # ذخیره‌سازی JSON
├── handlers/
│   ├── start.py         # استارت و منوی اصلی
│   ├── listing.py       # ثبت آگهی فروش
│   ├── purchase.py      # خرید اکانت
│   ├── my_ads.py        # مدیریت آگهی‌ها
│   └── admin.py         # پنل ادمین
├── requirements.txt
├── Procfile
└── .env.example         # نمونه متغیرهای محیطی
```

---

## 🛡️ نکات امنیتی
- ایمیل، رمز عبور و شماره تماس **هرگز** در کانال منتشر نمی‌شوند
- فقط در `data.json` و نزد ادمین ذخیره می‌شوند
- فایل `data.json` را هرگز در گیت‌هاب پوش نکنید (در `.gitignore` است)

---

## 📞 دستورات ادمین

| دستور | توضیح |
|-------|-------|
| `/ban 123456` | مسدود کردن کاربر |
| `/unban 123456` | رفع مسدودیت |
| `/users` | آمار کاربران |
| `/broadcast` | ارسال پیام همگانی |
