import os
import sys
import logging
import asyncio
import json

# إعداد logging أولاً
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# استيراد المكتبات
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application, 
        CommandHandler, 
        CallbackQueryHandler,
        ContextTypes,
        filters
    )
    from dotenv import load_dotenv
    import pandas as pd
    logger.info("✅ جميع المكتبات مثبتة بنجاح")
except ImportError as e:
    logger.error(f"❌ خطأ في استيراد المكتبات: {e}")
    sys.exit(1)

# تحميل متغيرات البيئة
load_dotenv()

# متغيرات
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
PORT = int(os.environ.get('PORT', 10000))
IMAGES_BASE_DIR = 'Images'

# تحميل الإجابات الصحيحة
def load_correct_answers():
    """تحميل الإجابات الصحيحة من ملف Excel"""
    try:
        df = pd.read_excel('Answers.xlsx')
        logger.info(f"✅ تم تحميل ملف Excel بنجاح")
        
        # تنظيف أسماء الأعمدة
        df.columns = df.columns.str.strip()
        
        # التحقق من الأعمدة
        logger.info(f"📋 أسماء الأعمدة: {list(df.columns)}")
        
        # إنشاء قاموس للإجابات الصحيحة
        correct_answers = {}
        
        for idx, row in df.iterrows():
            try:
                question_num = int(row['image number'])
                q_type = str(row['Question Type']).strip().lower()
                answer = str(row['answer']).strip().lower()
                
                correct_answers[question_num] = {
                    'type': q_type,
                    'correct_answer': answer,
                    'user_answer': None,
                    'is_correct': False
                }
                
            except Exception as e:
                logger.warning(f"⚠️ خطأ في الصف {idx+1}: {e}")
                continue
        
        logger.info(f"📊 تم تحميل {len(correct_answers)} إجابة صحيحة")
        return correct_answers
    
    except Exception as e:
        logger.error(f"❌ خطأ في تحميل ملف Excel: {e}")
        # إنشاء بيانات وهمية
        return create_mock_data()

def create_mock_data():
    """إنشاء بيانات وهمية للاختبار"""
    mock_data = {}
    
    for i in range(1, 20):
        mock_data[i] = {
            'type': 'tf',
            'correct_answer': 't' if i % 2 == 0 else 'f',
            'user_answer': None,
            'is_correct': False
        }
    
    for i in range(20, 46):
        answers = ['a', 'b', 'c', 'd']
        mock_data[i] = {
            'type': 'mcq',
            'correct_answer': answers[i % 4],
            'user_answer': None,
            'is_correct': False
        }
    
    logger.info(f"📝 تم إنشاء {len(mock_data)} سؤال وهمي")
    return mock_data

def get_image_path(question_num):
    """الحصول على مسار الصورة بناءً على رقم السؤال"""
    if 1 <= question_num <= 19:
        folder = "True or False"
    elif 20 <= question_num <= 45:
        folder = "mcq"
    else:
        return None
    
    # مسارات محتملة
    base_path = os.path.join(IMAGES_BASE_DIR, folder)
    
    if not os.path.exists(base_path):
        logger.error(f"❌ المجلد غير موجود: {base_path}")
        return None
    
    # البحث عن الصورة بأي امتداد
    possible_extensions = ['.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG']
    
    for ext in possible_extensions:
        path = os.path.join(base_path, f"{question_num}{ext}")
        if os.path.exists(path):
            logger.debug(f"📸 وجدت صورة: {path}")
            return path
    
    # محاولة العثور على أي ملف يبدأ برقم السؤال
    try:
        files = os.listdir(base_path)
        for file in files:
            if file.startswith(str(question_num)):
                path = os.path.join(base_path, file)
                logger.debug(f"📸 وجدت صورة (بالاسم): {path}")
                return path
    except Exception as e:
        logger.error(f"❌ خطأ في قراءة المجلد: {e}")
    
    logger.warning(f"⚠️ لم أجد صورة للسؤال {question_num}")
    return None

# قاموس لحفظ إجابات المستخدمين
user_sessions = {}
correct_answers = load_correct_answers()

# تعريف الدوال
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء الاختبار"""
    user_id = update.effective_user.id
    logger.info(f"👤 المستخدم {user_id} بدأ الجلسة")
    
    await update.message.reply_text(
        "📚 **مرحباً بك في بوت اختبار الرياضيات!**\n\n"
        "🎯 **معلومات عن الاختبار:**\n"
        "• الأسئلة 1-19: صح/خطأ ✅/❌\n"
        "• الأسئلة 20-45: اختيار من متعدد 🔠\n\n"
        "🔄 **لبدء الاختبار:**\n"
        "اضغط /begin"
    )

async def begin_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إرسال الأسئلة"""
    user_id = update.effective_user.id
    
    # تهيئة جلسة المستخدم
    user_sessions[user_id] = {
        'current_question': 1,
        'total_questions': len(correct_answers),
        'score': 0,
        'answers': {},
        'completed': False,
        'username': update.effective_user.username or update.effective_user.first_name,
        'message_id': None  # لحفظ معرف الرسالة
    }
    
    # نسخ الإجابات الصحيحة
    for q_num, data in correct_answers.items():
        user_sessions[user_id]['answers'][q_num] = {
            'type': data['type'],
            'correct_answer': data['correct_answer'],
            'user_answer': None,
            'is_correct': False
        }
    
    await update.message.reply_text(
        f"✅ **تم تهيئة الاختبار!**\n"
        f"📊 عدد الأسئلة: {len(correct_answers)}\n\n"
        "⏳ جاري إرسال أول سؤال..."
    )
    
    # إرسال أول سؤال
    await send_question(update, context, user_id)

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """إرسال سؤال للمستخدم"""
    session = user_sessions[user_id]
    question_num = session['current_question']
    
    if question_num > session['total_questions']:
        logger.info(f"🏁 المستخدم {user_id} أنهى جميع الأسئلة")
        await show_results(update, context, user_id)
        return
    
    logger.info(f"📨 إرسال السؤال {question_num} للمستخدم {user_id}")
    
    # الحصول على مسار الصورة
    image_path = get_image_path(question_num)
    
    if not image_path:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"⚠️ لم أجد صورة للسؤال {question_num}\n"
                 f"جاري الانتقال للسؤال التالي..."
        )
        session['current_question'] += 1
        await asyncio.sleep(1)
        await send_question(update, context, user_id)
        return
    
    # تحديد نوع السؤال وبناء الأزرار
    question_data = session['answers'][question_num]
    
    if question_data['type'] == 'tf':
        keyboard = [
            [
                InlineKeyboardButton("✅ صح (True)", callback_data=f"ans_{question_num}_t"),
                InlineKeyboardButton("❌ خطأ (False)", callback_data=f"ans_{question_num}_f")
            ]
        ]
        question_type_text = "📝 **سؤال صح/خطأ**"
    else:
        keyboard = [
            [
                InlineKeyboardButton("أ", callback_data=f"ans_{question_num}_a"),
                InlineKeyboardButton("ب", callback_data=f"ans_{question_num}_b"),
                InlineKeyboardButton("ج", callback_data=f"ans_{question_num}_c"),
                InlineKeyboardButton("د", callback_data=f"ans_{question_num}_d")
            ]
        ]
        question_type_text = "🔠 **سؤال اختيار من متعدد**"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        with open(image_path, 'rb') as photo:
            # إرسال الصورة مع الأزرار
            message = await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=photo,
                caption=f"**السؤال رقم: {question_num}**\n{question_type_text}\n\nاختر الإجابة الصحيحة:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            # حفظ معرف الرسالة
            session['message_id'] = message.message_id
            
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال الصورة: {e}")
        # إرسال رسالة نصية بديلة
        message = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"**السؤال رقم: {question_num}**\n{question_type_text}\n\nاختر الإجابة الصحيحة:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        session['message_id'] = message.message_id

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إجابة المستخدم"""
    query = update.callback_query
    
    # الرد على callback query أولاً
    await query.answer()
    
    user_id = query.from_user.id
    logger.info(f"📝 المستخدم {user_id} ضغط على زر: {query.data}")
    
    if user_id not in user_sessions:
        await query.edit_message_text("⚠️ الجلسة منتهية. اضغط /start للبدء")
        return
    
    session = user_sessions[user_id]
    
    # استخراج البيانات من callback_data
    data = query.data
    logger.info(f"🔍 بيانات callback: {data}")
    
    try:
        # التنسيق: ans_رقم_إجابة
        parts = data.split('_')
        if len(parts) != 3:
            logger.error(f"❌ تنسيق callback_data غير صحيح: {data}")
            return
        
        question_num = int(parts[1])
        user_answer = parts[2].lower()
        
        logger.info(f"🔍 معالجة: سؤال {question_num}، إجابة {user_answer}")
        
        # التحقق من صحة الإجابة
        if question_num not in session['answers']:
            logger.error(f"❌ السؤال {question_num} غير موجود في الجلسة")
            return
        
        # حفظ إجابة المستخدم
        session['answers'][question_num]['user_answer'] = user_answer
        
        # التحقق إذا كانت الإجابة صحيحة
        correct_answer = session['answers'][question_num]['correct_answer']
        if user_answer == correct_answer:
            session['answers'][question_num]['is_correct'] = True
            session['score'] += 1
            logger.info(f"✅ إجابة صحيحة! السؤال: {question_num}")
        else:
            logger.info(f"❌ إجابة خاطئة! السؤال: {question_num}")
        
        # تحديث زر الإجابة لإظهار الاختيار
        await update_button_with_selection(query, question_num, user_answer, correct_answer)
        
        # الانتقال للسؤال التالي بعد تأخير
        session['current_question'] += 1
        await asyncio.sleep(1)
        
        # إرسال السؤال التالي
        await send_question(update, context, user_id)
        
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الإجابة: {e}", exc_info=True)
        await query.edit_message_text("⚠️ حدث خطأ في معالجة إجابتك. الرجاء المحاولة مرة أخرى.")

async def update_button_with_selection(query, question_num, user_answer, correct_answer):
    """تحديث الأزرار لإظهار الإجابة المختارة"""
    try:
        # الحصول على الرسالة الأصلية
        original_text = query.message.caption or query.message.text
        
        # تحديث النص لإظهار الإجابة المختارة
        updated_text = f"{original_text}\n\n✅ **تم الاختيار: {user_answer.upper()}**"
        
        # إزالة الأزرار بعد الاختيار
        await query.edit_message_caption(
            caption=updated_text,
            reply_markup=None,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"❌ خطأ في تحديث الأزرار: {e}")
        # إذا فشل تحديث الصورة، حاول تحديث الرسالة النصية
        try:
            await query.edit_message_text(
                text=f"✅ **تم اختيار الإجابة: {user_answer.upper()}**\n\nجاري تحميل السؤال التالي...",
                reply_markup=None,
                parse_mode='Markdown'
            )
        except Exception as e2:
            logger.error(f"❌ خطأ في تحديث النص: {e2}")

async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None):
    """عرض النتائج"""
    if user_id is None:
        user_id = update.effective_user.id
    
    if user_id not in user_sessions:
        if hasattr(update, 'message'):
            await update.message.reply_text("⚠️ لا توجد جلسة نشطة. اضغط /start للبدء")
        return
    
    session = user_sessions[user_id]
    
    # حساب النتيجة
    total = session['total_questions']
    score = session['score']
    percentage = (score / total) * 100 if total > 0 else 0
    
    # إنشاء تفاصيل الإجابات
    details = "📊 **تفاصيل الإجابات:**\n\n"
    
    for q_num in sorted(session['answers'].keys()):
        ans = session['answers'][q_num]
        user_ans = ans['user_answer'] or "لم يُجب"
        correct_ans = ans['correct_answer']
        is_correct = ans['is_correct']
        
        emoji = "✅" if is_correct else "❌"
        details += f"{emoji} سؤال {q_num}: إجابتك ({user_ans.upper()}) | الصحيحة ({correct_ans.upper()})\n"
    
    # رسالة النتيجة
    result_message = (
        f"🎉 **تم الانتهاء من الاختبار!**\n\n"
        f"📈 **النتيجة النهائية:**\n"
        f"• عدد الأسئلة: {total}\n"
        f"• الإجابات الصحيحة: {score}\n"
        f"• النسبة المئوية: {percentage:.1f}%\n"
        f"• المستوى: {'ممتاز 🏆' if percentage >= 90 else 'جيد جداً ⭐' if percentage >= 75 else 'مقبول ✓' if percentage >= 50 else 'ضعف 📉'}\n\n"
        f"{details}\n"
        f"🔄 لإعادة الاختبار: /start"
    )
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id if hasattr(update, 'message') else update.callback_query.message.chat.id,
        text=result_message,
        parse_mode='Markdown'
    )
    
    session['completed'] = True
    logger.info(f"📊 المستخدم {user_id} حصل على {score}/{total} ({percentage:.1f}%)")

async def results_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض النتيجة الحالية"""
    await show_results(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض رسالة المساعدة"""
    help_text = (
        "🤖 **بوت اختبار الرياضيات**\n\n"
        "📋 **الأوامر:**\n"
        "/start - بدء جلسة جديدة\n"
        "/begin - بدء الاختبار\n"
        "/results - عرض النتائج\n"
        "/help - المساعدة\n\n"
        "🎯 **أنواع الأسئلة:**\n"
        "• 1-19: صح/خطأ\n"
        "• 20-45: اختيار من متعدد"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def test_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختبار الأزرار"""
    keyboard = [
        [
            InlineKeyboardButton("زر اختبار 1", callback_data="test_1"),
            InlineKeyboardButton("زر اختبار 2", callback_data="test_2")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔘 **اختبار الأزرار**\n\nاضغط على أي زر:",
        reply_markup=reply_markup
    )

async def handle_test_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أزرار الاختبار"""
    query = update.callback_query
    await query.answer(f"ضغطت على: {query.data}")
    
    await query.edit_message_text(
        text=f"✅ **تم الضغط بنجاح!**\n\nالزر: {query.data}\n\nهذا يثبت أن الأزرار تعمل.",
        parse_mode='Markdown'
    )

def main():
    """الدالة الرئيسية"""
    logger.info("🚀 بدء تشغيل بوت الرياضيات...")
    
    if not TOKEN:
        logger.error("❌ TOKEN غير موجود!")
        return
    
    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()
    
    # إضافة handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("begin", begin_test))
    application.add_handler(CommandHandler("results", results_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("test", test_buttons))  # لأغراض الاختبار
    
    # handler للأسئلة
    application.add_handler(CallbackQueryHandler(handle_answer, pattern="^ans_"))
    
    # handler لأزرار الاختبار
    application.add_handler(CallbackQueryHandler(handle_test_button, pattern="^test_"))
    
    # التحقق إذا كان على Render
    is_render = os.getenv('RENDER', '').lower() in ['true', '1', 'yes']
    
    if is_render:
        # استخدام webhook
        render_service_name = os.getenv('RENDER_SERVICE_NAME', 'math-limits-bot2')
        webhook_url = f"https://{render_service_name}.onrender.com/{TOKEN}"
        
        logger.info(f"🌐 استخدام webhook: {webhook_url}")
        
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=webhook_url,
            drop_pending_updates=True
        )
    else:
        # استخدام polling
        logger.info("💻 التشغيل محلياً")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )

if __name__ == '__main__':
    main()
