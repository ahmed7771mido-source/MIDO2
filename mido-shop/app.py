import os
import secrets
from pathlib import Path
from flask import Flask, session, request, abort
from markupsafe import Markup, escape
from werkzeug.middleware.proxy_fix import ProxyFix
from models import db, AdminUser, Category, Page, load_settings, local

BASE = Path(__file__).resolve().parent


def create_app():
    app = Flask(__name__, instance_path=str(BASE / "instance"))
    inst = Path(app.instance_path)
    inst.mkdir(exist_ok=True)
    upload = BASE / "static" / "uploads"
    upload.mkdir(parents=True, exist_ok=True)
    key_file = inst / "secret_key"
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32))
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or key_file.read_text().strip(),
        SQLALCHEMY_DATABASE_URI="sqlite:///" + (inst / "mido.db").as_posix(),
        UPLOAD_DIR=str(upload),
        MAX_CONTENT_LENGTH=25 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    db.init_app(app)

    from public import bp as shop_bp
    from admin import bp as admin_bp
    from chatbot import bp as chatbot_bp
    app.register_blueprint(shop_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(chatbot_bp)

    @app.before_request
    def csrf_protect():
        if request.method == "POST":
            # chatbot API مش محتاج CSRF
            if request.path == "/api/chat":
                return
            sent = request.form.get("csrf") or request.headers.get("X-CSRF") or ""
            tok = session.get("_csrf") or ""
            if not tok or not secrets.compare_digest(tok, sent):
                abort(400)

    @app.context_processor
    def inject():
        if "_csrf" not in session:
            session["_csrf"] = secrets.token_hex(16)
        return dict(
            csrf=session["_csrf"],
            S=load_settings(),
            nav_categories=Category.query.order_by(Category.position, Category.id).all(),
            footer_pages=Page.query.order_by(Page.slug).all(),
            cart_count=sum(i["qty"] for i in session.get("cart", [])),
        )

    @app.template_filter("dt")
    def dt_filter(v, fmt="%Y-%m-%d %H:%M"):
        return local(v).strftime(fmt) if v else ""

    @app.template_filter("money")
    def money(v):
        return "{:,}".format(int(v or 0))

    @app.template_filter("richtext")
    def richtext(text):
        out, rows = [], []

        def flush():
            if rows:
                t = "<table class='rt'>"
                for n, r in enumerate(rows):
                    tag = "th" if n == 0 else "td"
                    t += "<tr>" + "".join("<%s>%s</%s>" % (tag, escape(c.strip()), tag) for c in r) + "</tr>"
                out.append(t + "</table>")
                rows.clear()

        for line in (text or "").splitlines():
            if "|" in line:
                rows.append(line.split("|"))
            else:
                flush()
                if line.strip():
                    out.append("<p>%s</p>" % escape(line.strip()))
        flush()
        return Markup("".join(out))

    with app.app_context():
        db.create_all()
        seed()
    return app


DEFAULT_PAGES = [
    ("returns", "سياسة الاستبدال والاسترجاع",
     "تقدر تستبدل المنتج خلال 3 أيام من الاستلام لو مش مقاسك.\nالمنتج لازم يكون بحالته الأصلية ومن غير استخدام أو غسيل.\nلو فيه عيب تصنيع بنستبدله أو نرجعلك فلوسك.\nكلمنا على واتساب برقم الطلب وهنرتب الاستبدال."),
    ("about", "عن البراند",
     "بدأنا في بني سويف بفكرة بسيطة: لبس شبابي بخامة ممتازة وسعر مناسب.\nبنصنع منتجاتنا في مصنع محلي جربنا شغله بنفسنا قبل ما نعرضه عليك."),
    ("contact", "تواصل معانا",
     "لأي استفسار أو طلب استبدال كلمنا على واتساب أو صفحاتنا، وهنرد عليك في أقرب وقت."),
    ("sizes", "جدول المقاسات",
     "المقاس | عرض الصدر (سم) | الطول (سم)\nM | 54 | 68\nL | 56 | 70\nXL | 58 | 72\nXXL | 60 | 74\nالأرقام تقريبية، قيس هودي عندك وقارن بالجدول."),
]


def seed():
    for slug, title, body in DEFAULT_PAGES:
        if not db.session.get(Page, slug):
            db.session.add(Page(slug=slug, title=title, body=body))
    if not Category.query.count():
        for i, (name, slug) in enumerate([("هوديز", "hoodies"), ("تيشيرتات", "tshirts"),
                                          ("جواكت", "jackets"), ("ساعات", "watches")]):
            db.session.add(Category(name=name, slug=slug, position=i))
    if not AdminUser.query.count():
        user = os.environ.get("ADMIN_USER", "admin")
        pw = os.environ.get("ADMIN_PASSWORD")
        generated = not pw
        pw = pw or secrets.token_urlsafe(9)
        u = AdminUser(username=user)
        u.set_password(pw)
        db.session.add(u)
        if generated:
            print("\n" + "=" * 50)
            print(" Admin created  ->  user: %s   password: %s" % (user, pw))
            print(" غيّر الباسورد من صفحة الإعدادات بعد أول دخول")
            print("=" * 50 + "\n")
    db.session.commit()


app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
