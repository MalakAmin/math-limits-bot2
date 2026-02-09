# 🧮 بوت اختبارات رياضيات النهايات - مع Keep-alive
# 🔧 يعمل 24/7 على Render

import os
import asyncio
import json
import random
import threading
import time
import requests
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# 🔐 التوكن من متغيرات البيئة
TOKEN = os.environ.get('TELEGRAM_TOKEN')
TEACHER_ID = 8422436251  # غير هذا الرقم!

# 🌐 Flask لإبقاء البوت نشطاً
app = Flask(__name__)

@app.route('/')
def home():
    return """
    <html>
        <head>
            <title>بوت الرياضيات</title>
            <style>
                body { font-family: Arial; text-align: center; padding: 50px; }
                h1 { color: #2c3e50; }
                .status { color: #27ae60; font-size: 24px; }
            </style>
        </head>
        <body>
            <h1>🤖 بوت اختبارات الرياضيات</h1>
            <div class="status">✅ يعمل بنجاح!</div>
            <p>⏰ يعمل 24/7 على Render</p>
            <p>👨🏫 للمعلم: استخدم /stats في Telegram</p>
            <p>📱 للطلاب: ابحث عن @mathimatical_testBot</p>
        </body>
    </html>
    """

@app.route('/health')
def health():
    return {"status": "active", "timestamp": datetime.now().isoformat()}

@app.route('/ping')
def ping():
    return "pong"

# 🔄 وظيفة لإرسال طلبات دورية
def keep_alive():
    """إبقاء البوت نشطاً بإرسال طلبات دورية"""
    def ping_server():
        while True:
            try:
                # الحصول على رابط Render تلقائياً
                render_url = os.environ.get('RENDER_URL', '')
                if not render_url:
                    # محاولة تخمين الرابط
                    service_name = os.environ.get('RENDER_SERVICE_NAME', '')
                    if service_name:
                        render_url = f"https://{service_name}.onrender.com"
                
                if render_url:
                    response = requests.get(f"{render_url}/ping", timeout=10)
                    print(f"✅ Keep-alive ping: {response.status_code} at {datetime.now().strftime('%H:%M:%S')}")
                else:
                    print("⚠️ لا يمكن تحديد رابط Render")
            except Exception as e:
                print(f"⚠️ Keep-alive failed: {e}")
            time.sleep(300)  # كل 5 دقائق
    
    thread = threading.Thread(target=ping_server, daemon=True)
    thread.start()

# 📊 قاعدة البيانات
class Database:
    def __init__(self):
        self.data_file = 'data.json'
        self.data = self.load_data()
    
    def load_data(self):
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {'students': {}, 'total_questions': 0, 'correct_answers': 0}
    
    def save_data(self):
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def register_student(self, user_id, name):
        user_id = str(user_id)
        if user_id not in self.data['students']:
            self.data['students'][user_id] = {
                'name': name,
                'correct': 0,
                'total': 0,
                'joined': datetime.now().strftime('%Y-%m-%d'),
                'last_active': datetime.now().isoformat()
            }
            self.save_data()
            return True
        return False
    
    def update_score(self, user_id, is_correct):
        user_id = str(user_id)
        if user_id in self.data['students']:
            self.data['students'][user_id]['total'] += 1
            self.data['students'][user_id]['last_active'] = datetime.now().isoformat()
            
            if is_correct:
                self.data['students'][user_id]['correct'] += 1
            
            self.data['total_questions'] += 1
            if is_correct:
                self.data['correct_answers'] += 1
            
            self.save_data()
            return self.data['students'][user_id]

db = Database()

# 📚 الأسئلة المعدلة من الملفين المرفقين
TRUE_FALSE_QUESTIONS = [
    # من الملف الأول (2.2) - 10 أسئلة
    {"id": 1, "q": "If lim x→5 f(x) = 0, lim x→5 g(x) = 5, then lim x→5 f(x) g(x) D.N.E", "ans": False, "exp": "النهاية = 0 × 5 = 0، لأن نهاية حاصل الضرب = حاصل ضرب النهايات"},
    {"id": 2, "q": "If lim x→0 f(x) = ∞, lim x→0 g(x) = ∞, then lim x→5 f(x) - g(x) = 0", "ans": False, "exp": "خطأ، ∞ - ∞ صيغة غير معينة (indeterminate form)"},
    {"id": 3, "q": "lim x→a n√f(x) ≠ n√lim x→a f(x)", "ans": False, "exp": "خطأ، نهاية الجذر = جذر النهاية (بشروط معينة)"},
    {"id": 4, "q": "lim x→0 tan6x = 2", "ans": False, "exp": "خطأ، lim x→0 tan(6x) = tan(0) = 0"},
    {"id": 5, "q": "lim x→0 1 - cosx = 0", "ans": True, "exp": "صحيح، 1 - cos(0) = 1 - 1 = 0"},
    {"id": 6, "q": "lim x→1 sin(π/x) = 1", "ans": False, "exp": "خطأ، sin(π) = 0 ليس 1"},
    {"id": 7, "q": "lim x→0 tan(ax)/sin(bx) = a/b", "ans": True, "exp": "صحيح، باستخدام النهاية الأساسية lim┬(x→0)〖tan(ax)/(ax)〗 × lim┬(x→0)〖(bx)/sin(bx)〗 × (a/b) = a/b"},
    {"id": 8, "q": "lim x→a x = 0", "ans": False, "exp": "خطأ، lim x→a x = a ليس 0"},
    {"id": 9, "q": "lim x→5 [f(x)/g(x)] عندما lim g(x)=0 → ∞", "ans": False, "exp": "خطأ، يعتمد على إشارة البسط والمقام"},
    {"id": 10, "q": "lim x→∞ (1/x) = 0", "ans": True, "exp": "صحيح، نهاية أساسية"},
    
    # من الملف الثاني (2.1) - 10 أسئلة
    {"id": 11, "q": "If lim x→0+ tan(x)/2√x = 1/2", "ans": True, "exp": "صحيح، لأن tan(x) ≈ x عندما x→0"},
    {"id": 12, "q": "If lim x→2- 5/(x-2)² = ∞", "ans": True, "exp": "صحيح، المقام → 0 والبسط ثابت موجب"},
    {"id": 13, "q": "If lim x→a f(x) = 2, lim x→a g(x) = 3, then lim┬(x→a) (f(x)+g(x))² = 25", "ans": True, "exp": "صحيح، (2+3)² = 25"},
    {"id": 14, "q": "From graph, lim x→2 f(x) + f(2) = 0", "ans": False, "exp": "تعتمد على الرسم البياني، تحتاج إلى فحص"},
    {"id": 15, "q": "From graph, lim x→0- f(x) - lim x→0+ f(x) = -3", "ans": False, "exp": "تعتمد على الرسم البياني، تحتاج إلى فحص"},
    {"id": 16, "q": "lim x→c f(x) exists if and only if lim x→c+ f(x) = lim x→c- f(x)", "ans": True, "exp": "صحيح، تعريف وجود النهاية"},
    {"id": 17, "q": "If f(1) = 5 then lim x→1 f(x) = 5", "ans": False, "exp": "خطأ، قيمة الدالة عند نقطة ≠ نهاية الدالة عند تلك النقطة"},
    {"id": 18, "q": "lim x→0 sin(1/x) exists", "ans": False, "exp": "خطأ، النهاية غير موجودة (تذبذب)"},
    {"id": 19, "q": "If lim x→a f(x) exists, then f is continuous at x=a", "ans": False, "exp": "خطأ، يجب أيضًا أن تساوي النهاية f(a)"},
    {"id": 20, "q": "lim x→∞ (1+1/x)^x = e", "ans": True, "exp": "صحيح، نهاية أساسية"}
]

MCQ_QUESTIONS = [
    # من الملف الأول (2.2) - 15 سؤال
    {
        "id": 1,
        "q": "if f(x) = 4x and g(x) = 2x, then lim┬(x→2) [g(x) - f(x)] = ?",
        "ops": ["-4", "-1", "∞", "4"],
        "ans": 0,
        "exp": "g(x)-f(x)=2x-4x=-2x، عند x=2 → -4"
    },
    {
        "id": 2,
        "q": "lim┬(x→1) (x+√x)^5 = ?",
        "ops": ["0", "32", "243", "1"],
        "ans": 1,
        "exp": "(1+√1)^5 = (1+1)^5 = 2^5 = 32"
    },
    {
        "id": 3,
        "q": "lim┬(x→2) √(x-10)/3 = ?",
        "ops": ["√(-8)/3", "0", "غير معرف", "2/3"],
        "ans": 2,
        "exp": "جذر عدد سالب غير معرف في الأعداد الحقيقية"
    },
    {
        "id": 4,
        "q": "lim┬(x→-2) (x³+8)/(x²-4) = ?",
        "ops": ["0", "3", "-3", "غير معرف"],
        "ans": 1,
        "exp": "بتحليل: (x+2)(x²-2x+4)/((x+2)(x-2)) = (x²-2x+4)/(x-2) → (4+4+4)/(-4) = 12/(-4) = -3"
    },
    {
        "id": 5,
        "q": "lim┬(x→-5) 3x/(-2x+10) = ?",
        "ops": ["-1.5", "0.75", "-0.75", "1.5"],
        "ans": 2,
        "exp": "3(-5)/(-2(-5)+10) = -15/(10+10) = -15/20 = -0.75"
    },
    {
        "id": 6,
        "q": "lim┬(x→3) (√(x+1)-2)/(x-3) = ?",
        "ops": ["1/4", "1/2", "1", "2"],
        "ans": 0,
        "exp": "بضرب في المرافق: 1/(√(x+1)+2) → 1/(√4+2) = 1/(2+2) = 1/4"
    },
    {
        "id": 7,
        "q": "lim┬(t→4) (√(t+1)-√5)/(t-4) = ?",
        "ops": ["1/(2√5)", "√5/2", "1/√5", "0"],
        "ans": 0,
        "exp": "باستخدام قاعدة لوبيتال أو الضرب بالمرافق → 1/(2√5)"
    },
    {
        "id": 8,
        "q": "lim┬(x→9) (x-9)/(√x-3) = ?",
        "ops": ["0", "3", "6", "9"],
        "ans": 2,
        "exp": "بضرب في المرافق (√x+3): (x-9)(√x+3)/(x-9) = √x+3 → 3+3=6"
    },
    {
        "id": 9,
        "q": "lim┬(x→2) (√(x+5)-√7)/(x-2) = ?",
        "ops": ["1/(2√7)", "2√7", "√7/2", "0"],
        "ans": 0,
        "exp": "باستخدام قاعدة لوبيتال أو الضرب بالمرافق → 1/(2√7)"
    },
    {
        "id": 10,
        "q": "lim┬(x→0) tan(6x)/x = ?",
        "ops": ["0", "1", "6", "∞"],
        "ans": 2,
        "exp": "باستخدام lim┬(x→0) tan(ax)/x = a → 6"
    },
    {
        "id": 11,
        "q": "If lim x→a f(x)=2, lim x→a g(x)=3, then lim x→a [2f(x)-g(x)] = ?",
        "ops": ["1", "4", "7", "6"],
        "ans": 0,
        "exp": "2×2 - 3 = 4-3 = 1"
    },
    {
        "id": 12,
        "q": "lim┬(x→0) (1-cosx)/x = ?",
        "ops": ["0", "1", "∞", "غير موجود"],
        "ans": 0,
        "exp": "باستخدام المتطابقة أو قاعدة لوبيتال → 0"
    },
    {
        "id": 13,
        "q": "lim┬(x→∞) (2x²+3)/(x²-1) = ?",
        "ops": ["0", "1", "2", "∞"],
        "ans": 2,
        "exp": "نقسم على x²: (2+3/x²)/(1-1/x²) → 2"
    },
    {
        "id": 14,
        "q": "lim┬(x→0) sin(3x)/sin(5x) = ?",
        "ops": ["0", "3/5", "1", "5/3"],
        "ans": 1,
        "exp": "باستخدام lim┬(x→0) sin(ax)/sin(bx) = a/b → 3/5"
    },
    {
        "id": 15,
        "q": "lim┬(x→1) ln(x)/(x-1) = ?",
        "ops": ["0", "1", "e", "∞"],
        "ans": 1,
        "exp": "نهاية أساسية أو قاعدة لوبيتال → 1"
    },
    
    # من الملف الثاني (2.1) - 15 سؤال
    {
        "id": 16,
        "q": "From graph, lim┬(x→-4-) g(x) = ?",
        "ops": ["-1", "3", "1", "-3"],
        "ans": 1,
        "exp": "من الرسم البياني تقترب من 3 من اليسار"
    },
    {
        "id": 17,
        "q": "From graph, f(2) = ?",
        "ops": ["3", "1", "0", "4"],
        "ans": 0,
        "exp": "من الرسم البياني قيمة الدالة عند x=2 هي 3"
    },
    {
        "id": 18,
        "q": "From graph, 1+f(-2) = ?",
        "ops": ["2", "4", "undefined", "0"],
        "ans": 1,
        "exp": "من الرسم البياني f(-2)=3 → 1+3=4"
    },
    {
        "id": 19,
        "q": "From graph, f(1) = ?",
        "ops": ["1", "undefined", "-1", "2"],
        "ans": 1,
        "exp": "من الرسم البياني الدالة غير معرفة عند x=1"
    },
    {
        "id": 20,
        "q": "From graph, lim┬(x→-1) f(x) = ?",
        "ops": ["1", "2", "D.N.E", "-2"],
        "ans": 2,
        "exp": "من الرسم البياني النهاية غير موجودة (D.N.E)"
    },
    {
        "id": 21,
        "q": "From graph, lim┬(x→1) f(x) = ?",
        "ops": ["1", "2", "D.N.E", "-2"],
        "ans": 2,
        "exp": "من الرسم البياني النهاية غير موجودة (D.N.E)"
    },
    {
        "id": 22,
        "q": "From graph, lim┬(x→0-) f(x) = ?",
        "ops": ["-1", "0", "D.N.E", "-2"],
        "ans": 0,
        "exp": "من الرسم البياني تقترب من -1 من اليسار"
    },
    {
        "id": 23,
        "q": "From graph, lim┬(x→-2) f(x) = ?",
        "ops": ["1", "4", "D.N.E", "-2"],
        "ans": 1,
        "exp": "من الرسم البياني النهاية = 1"
    },
    {
        "id": 24,
        "q": "From graph, g(3) = ?",
        "ops": ["1", "undefined", "-3", "4"],
        "ans": 1,
        "exp": "من الرسم البياني g(3) غير معرفة"
    },
    {
        "id": 25,
        "q": "From graph, lim┬(x→3) g(x) = ?",
        "ops": ["-3", "1", "D.N.E", "4"],
        "ans": 0,
        "exp": "من الرسم البياني النهاية = -3"
    },
    {
        "id": 26,
        "q": "From graph, lim┬(x→1) g(x) = ?",
        "ops": ["1", "3", "D.N.E", "-2"],
        "ans": 2,
        "exp": "من الرسم البياني النهاية غير موجودة (D.N.E)"
    },
    {
        "id": 27,
        "q": "From graph, lim┬(x→0+) g(x) = ?",
        "ops": ["1", "2", "D.N.E", "3"],
        "ans": 0,
        "exp": "من الرسم البياني تقترب من 1 من اليمين"
    },
    {
        "id": 28,
        "q": "From graph, lim┬(x→-2) g(x) = ?",
        "ops": ["1", "5", "D.N.E", "-2"],
        "ans": 2,
        "exp": "من الرسم البياني النهاية غير موجودة (D.N.E)"
    },
    {
        "id": 29,
        "q": "If lim┬(x→2) f(x)=4 and lim┬(x→2) g(x)=-2, then lim┬(x→2) [f(x)² - g(x)] = ?",
        "ops": ["14", "18", "16", "20"],
        "ans": 1,
        "exp": "4² - (-2) = 16 + 2 = 18"
    },
    {
        "id": 30,
        "q": "lim┬(x→0) (e^x - 1 - x)/x² = ?",
        "ops": ["0", "1/2", "1", "∞"],
        "ans": 1,
        "exp": "باستخدام متسلسلة تايلور أو قاعدة لوبيتال مرتين → 1/2"
    }
]

# 🎯 دوال البوت (نفس الدوال السابقة)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_new = db.register_student(user.id, user.first_name)
    
    if is_new:
        msg = f"🎉 أهلاً {user.first_name}!\nتم تسجيلك في بوت اختبارات النهايات."
    else:
        student = db.data['students'].get(str(user.id), {})
        msg = f"👋 أهلًا بعودتك {user.first_name}!\nنتيجتك: {student.get('correct', 0)}/{student.get('total', 0)}"
    
    msg += "\n\n📋 الأوامر:\n/start - البداية\n/truefalse - أسئلة صح/خطأ\n/mcq - أسئلة خيارات\n/score - نتيجتك\n/top - المتصدرين"
    
    await update.message.reply_text(msg)

async def truefalse_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = random.choice(TRUE_FALSE_QUESTIONS)
    buttons = [
        [InlineKeyboardButton("✅ صحيح", callback_data=f"tf_{q['id']}_true")],
        [InlineKeyboardButton("❌ خطأ", callback_data=f"tf_{q['id']}_false")]
    ]
    text = f"🔵 سؤال صح/خطأ:\n\n❓ {q['q']}"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def mcq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = random.choice(MCQ_QUESTIONS)
    buttons = []
    letters = ['أ', 'ب', 'ج', 'د']
    for i, option in enumerate(q['ops']):
        buttons.append([InlineKeyboardButton(f"{letters[i]}. {option}", callback_data=f"mcq_{q['id']}_{i}")])
    text = f"🔴 سؤال خيارات:\n\n❓ {q['q']}"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    q_type, q_id, answer = data[0], int(data[1]), data[2]
    
    if q_type == 'tf':
        q = next((q for q in TRUE_FALSE_QUESTIONS if q['id'] == q_id), None)
        if q:
            is_correct = ((answer == 'true') == q['ans'])
            msg = f"✅ صحيح!\n\n{q['exp']}" if is_correct else f"❌ خطأ!\n\n{q['exp']}"
            db.update_score(query.from_user.id, is_correct)
    
    elif q_type == 'mcq':
        q = next((q for q in MCQ_QUESTIONS if q['id'] == q_id), None)
        if q:
            is_correct = (int(answer) == q['ans'])
            letters = ['أ', 'ب', 'ج', 'د']
            if is_correct:
                msg = f"✅ إجابة صحيحة!\n\n{q['exp']}"
            else:
                correct = letters[q['ans']]
                msg = f"❌ إجابة خاطئة!\nالصحيحة: {correct}\n\n{q['exp']}"
            db.update_score(query.from_user.id, is_correct)
    
    user_id = str(query.from_user.id)
    if user_id in db.data['students']:
        student = db.data['students'][user_id]
        msg += f"\n\n📊 نتيجتك: {student['correct']}/{student['total']}"
    
    msg += "\n\n🔁 /truefalse - /mcq"
    await query.edit_message_text(msg)

async def score_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in db.data['students']:
        await update.message.reply_text("⚠️ اكتب /start أولاً")
        return
    
    student = db.data['students'][user_id]
    total, correct = student['total'], student['correct']
    percent = (correct/total*100) if total > 0 else 0
    
    report = f"📊 نتيجتك:\n✅ {correct} صحيح\n❌ {total-correct} خطأ\n🎯 {percent:.1f}%\n📅 {student['joined']}"
    await update.message.reply_text(report)

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض المتصدرين"""
    students = db.data['students']
    
    # ترتيب الطلاب حسب نسبة الإجابات الصحيحة
    sorted_students = []
    for user_id, data in students.items():
        if data['total'] > 0:
            percent = (data['correct'] / data['total']) * 100
        else:
            percent = 0
        sorted_students.append({
            'name': data['name'],
            'correct': data['correct'],
            'total': data['total'],
            'percent': percent
        })
    
    # الترتيب تنازلياً حسب النسبة
    sorted_students.sort(key=lambda x: x['percent'], reverse=True)
    
    if not sorted_students:
        await update.message.reply_text("📭 لا يوجد طلاب بعد!")
        return
    
    msg = "🏆 المتصدرين:\n\n"
    for i, student in enumerate(sorted_students[:10]):
        msg += f"{i+1}. {student['name']}: {student['correct']}/{student['total']} ({student['percent']:.1f}%)\n"
    
    msg += f"\n👥 إجمالي الطلاب: {len(students)}"
    await update.message.reply_text(msg)

# 🔧 تشغيل Flask في خيط منفصل
def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# 🔧 تشغيل البوت
def run_telegram_bot():
    print("=" * 50)
    print("🧮 بوت اختبارات رياضيات النهايات")
    print("=" * 50)
    print(f"📅 بدأ التشغيل: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"👥 الطلاب المسجلين: {len(db.data['students'])}")
    print(f"📚 عدد أسئلة True/False: {len(TRUE_FALSE_QUESTIONS)}")
    print(f"📚 عدد أسئلة MCQ: {len(MCQ_QUESTIONS)}")
    print("✅ البوت يعمل 24/7 مع Keep-alive!")
    print("=" * 50)
    
    # بدء Keep-alive
    keep_alive()
    
    # تشغيل البوت
    async def main():
        app = Application.builder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("truefalse", truefalse_command))
        app.add_handler(CommandHandler("mcq", mcq_command))
        app.add_handler(CommandHandler("score", score_command))
        app.add_handler(CommandHandler("top", top_command))
        app.add_handler(CallbackQueryHandler(handle_answer, pattern="^tf_"))
        app.add_handler(CallbackQueryHandler(handle_answer, pattern="^mcq_"))
        
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        # استمر في التشغيل
        while True:
            await asyncio.sleep(3600)
    
    asyncio.run(main())

# 🚀 نقطة البداية
if __name__ == "__main__":
    # تشغيل Flask في خيط منفصل
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # تشغيل البوت بعد ثانيتين
    time.sleep(2)
    run_telegram_bot()
