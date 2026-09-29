"""
AI Chatbot للمساعدة في الموقع
يستخدم Groq API (مجاني وسريع) أو يمكن استبداله بـ OpenAI
"""
import os
import json
from flask import Blueprint, request, jsonify
from models import Product, Category, load_settings, db

bp = Blueprint("chatbot", __name__)

# يمكنك استخدام Groq (مجاني) أو OpenAI
# للحصول على API Key: https://console.groq.com/keys
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
USE_AI = bool(GROQ_API_KEY)

def get_context():
    """جلب معلومات الموقع للـ AI"""
    settings = load_settings()
    products = Product.query.filter_by(active=True).limit(50).all()
    categories = Category.query.all()
    
    context = f"""
أنت مساعد ذكي لمتجر {settings.get('site_name')} للملابس الشبابية.

معلومات المتجر:
- الاسم: {settings.get('site_name')}
- الوصف: {settings.get('tagline')}
- العنوان: {settings.get('footer_address')}
- رسوم التوصيل: {settings.get('delivery_fee')} جنيه

الأقسام المتوفرة:
{', '.join([c.name for c in categories])}

بعض المنتجات المتوفرة:
"""
    
    for p in products[:20]:
        price_text = f"{p.current_price} جنيه"
        if p.on_sale:
            price_text = f"{p.sale_price} جنيه (بدلاً من {p.price} جنيه)"
        context += f"\n- {p.name}: {price_text}"
    
    context += """

مهامك:
1. الرد على استفسارات العملاء عن المنتجات والأسعار
2. مساعدتهم في اختيار المقاس المناسب
3. شرح سياسة الاستبدال والإرجاع
4. الإجابة عن التوصيل والدفع
5. كن ودوداً ومحترفاً وساعدهم في الشراء

ملاحظات:
- اذكر الأسعار بالجنيه المصري
- لو سألوا عن منتج معين، حاول تقترح منتجات مشابهة
- شجعهم على إضافة المنتجات للسلة
- اذا سألوا عن التوصيل، اذكر رسوم التوصيل
"""
    
    return context


def get_ai_response(message, conversation_history=[]):
    """الحصول على رد من الـ AI"""
    if not USE_AI:
        return get_fallback_response(message)
    
    try:
        import requests
        
        context = get_context()
        
        messages = [
            {"role": "system", "content": context}
        ]
        
        # إضافة السجل السابق
        messages.extend(conversation_history[-6:])  # آخر 3 رسائل فقط
        
        # إضافة الرسالة الجديدة
        messages.append({"role": "user", "content": message})
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 500
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        else:
            return get_fallback_response(message)
            
    except Exception as e:
        print(f"AI Error: {e}")
        return get_fallback_response(message)


def get_fallback_response(message):
    """ردود افتراضية لو الـ AI مش شغال"""
    message_lower = message.lower()
    
    if any(word in message_lower for word in ["مرحبا", "السلام", "هاي", "هلو"]):
        return "مرحباً بك! أنا المساعد الذكي لمتجر MIDO. كيف يمكنني مساعدتك اليوم؟ 😊"
    
    elif any(word in message_lower for word in ["سعر", "كام", "ثمن", "تمن"]):
        products = Product.query.filter_by(active=True).limit(5).all()
        response = "هذه بعض المنتجات المتوفرة:\n\n"
        for p in products:
            response += f"• {p.name}: {p.current_price} جنيه\n"
        return response
    
    elif any(word in message_lower for word in ["توصيل", "شحن", "ديليفري"]):
        settings = load_settings()
        return f"رسوم التوصيل: {settings.get('delivery_fee')} جنيه\n\nبنوصل لكل المحافظات، والدفع عند الاستلام متاح! 📦"
    
    elif any(word in message_lower for word in ["استبدال", "ارجاع", "مرتجع"]):
        return "سياسة الاستبدال:\n• تقدر تستبدل المنتج خلال 3 أيام من الاستلام\n• المنتج لازم يكون بحالته الأصلية\n• لو فيه عيب تصنيع بنستبدله أو نرجعلك فلوسك\n\nكلمنا على واتساب لترتيب الاستبدال! 🔄"
    
    elif any(word in message_lower for word in ["مقاس", "مقاسات", "سايز"]):
        return "جدول المقاسات التقريبي:\n\nM: عرض صدر 54 سم، طول 68 سم\nL: عرض صدر 56 سم، طول 70 سم\nXL: عرض صدر 58 سم، طول 72 سم\nXXL: عرض صدر 60 سم، طول 74 سم\n\nقيس هودي عندك وقارن بالجدول! 📏"
    
    elif any(word in message_lower for word in ["عروض", "خصم", "تخفيض"]):
        on_sale = Product.query.filter(Product.sale_price.isnot(None), Product.sale_price < Product.price).limit(5).all()
        if on_sale:
            response = "العروض المتاحة حالياً:\n\n"
            for p in on_sale:
                discount = int((p.price - p.sale_price) / p.price * 100)
                response += f"• {p.name}: {p.sale_price} جنيه بدلاً من {p.price} جنيه (خصم {discount}%) 🔥\n"
            return response
        else:
            return "للأسف مفيش عروض متاحة حالياً، لكن تابعنا عشان تعرف بالعروض الجديدة! 👀"
    
    else:
        return "عفواً، لم أفهم سؤالك جيداً. يمكنني مساعدتك في:\n\n• معرفة الأسعار والمنتجات\n• شرح سياسة الاستبدال\n• معلومات عن التوصيل\n• اختيار المقاس المناسب\n• معرفة العروض المتاحة\n\nاسألني أي سؤال! 😊"


@bp.route("/api/chat", methods=["POST"])
def chat():
    """API للمحادثة مع الـ AI"""
    try:
        data = request.get_json()
        message = data.get("message", "").strip()
        history = data.get("history", [])
        
        if not message:
            return jsonify({"error": "الرسالة فارغة"}), 400
        
        response = get_ai_response(message, history)
        
        return jsonify({
            "response": response,
            "success": True
        })
        
    except Exception as e:
        return jsonify({
            "response": "عذراً، حدث خطأ. حاول مرة أخرى.",
            "success": False,
            "error": str(e)
        }), 500
