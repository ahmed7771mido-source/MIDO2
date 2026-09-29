import threading
import urllib.parse
import urllib.request
from models import local


def _post(url, data):
    try:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
        urllib.request.urlopen(req, timeout=8)
    except Exception:
        pass


def notify_order(order, settings):
    token = settings.get("telegram_bot_token")
    chat  = settings.get("telegram_chat_id")
    if not token or not chat:
        return

    # بناء تفاصيل المنتجات
    items_text = ""
    for i in order.items:
        opts = " ".join(x for x in (i.size, i.color) if x)
        items_text += "  • %s %s × %d = %d ج\n" % (i.name, ("(%s)" % opts) if opts else "", i.qty, i.price * i.qty)

    msg = (
        "🛍 طلب جديد #%d\n"
        "━━━━━━━━━━━━━━━━━\n"
        "👤 الاسم: %s\n"
        "📞 التليفون: %s\n"
        "📍 المحافظة: %s\n"
        "🏠 العنوان: %s\n"
        "━━━━━━━━━━━━━━━━━\n"
        "🛒 المنتجات:\n%s"
        "━━━━━━━━━━━━━━━━━\n"
        "🚚 التوصيل: %d ج\n"
        "💰 الإجمالي: %d ج\n"
        "%s"
        "⏰ %s"
    ) % (
        order.id,
        order.name,
        order.phone,
        order.governorate or "—",
        order.address or "—",
        items_text,
        order.delivery_fee or 0,
        order.total,
        ("📝 ملاحظات: %s\n" % order.notes) if order.notes else "",
        local(order.created_at).strftime("%Y-%m-%d %H:%M"),
    )

    threading.Thread(
        target=_post, daemon=True,
        args=(
            "https://api.telegram.org/bot%s/sendMessage" % token,
            {"chat_id": chat, "text": msg}
        )
    ).start()
