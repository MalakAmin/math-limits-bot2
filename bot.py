# بدلاً من start_polling استخدم:
await application.run_webhook(
    listen="0.0.0.0",
    port=8443,
    url_path=TOKEN,
    webhook_url=f"https://yourservice.onrender.com/{TOKEN}"
)
