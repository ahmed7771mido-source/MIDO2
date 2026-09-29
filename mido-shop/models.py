from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()
TZ = ZoneInfo("Africa/Cairo")


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local(dt):
    return dt.replace(tzinfo=timezone.utc).astimezone(TZ)


STATUSES = [("new", "جديد"), ("confirmed", "مؤكد"), ("shipping", "في الطريق"),
            ("delivered", "تم التسليم"), ("cancelled", "ملغي")]
STATUS_LABEL = dict(STATUSES)

DEFAULT_SETTINGS = {
    "site_name": "MIDO",
    "tagline": "لبس شباب من بني سويف",
    "announcement": "توصيل داخل بني سويف والدفع عند الاستلام",
    "hero_title": "لبس شباب من بني سويف",
    "hero_text": "هوديز وتيشيرتات وجواكت وساعات بخامة ممتازة، وتوصيل لحد باب البيت.",
    "about_text": "الخامة دي بلبسها أنا بنفسي. اخترت مصنع في بني سويف وجربت شغله قبل ما أعرضه عليك.",
    "footer_address": "اهناسيا، بني سويف",
    "whatsapp": "",
    "facebook": "",
    "instagram": "",
    "telegram_link": "",
    "delivery_fee": "0",
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "low_stock_threshold": "3",
}


class Setting(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text, default="")


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    for r in Setting.query.all():
        s[r.key] = r.value or ""
    return s


class AdminUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    position = db.Column(db.Integer, default=0)
    products = db.relationship("Product", backref="category")


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default="")
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    price = db.Column(db.Integer, nullable=False, default=0)
    sale_price = db.Column(db.Integer)
    cost = db.Column(db.Integer, nullable=False, default=0)
    stock = db.Column(db.Integer)  # None = unlimited
    sizes = db.Column(db.String(200), default="")
    colors = db.Column(db.String(200), default="")
    active = db.Column(db.Boolean, default=True)
    featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    images = db.relationship("ProductImage", backref="product", cascade="all, delete-orphan",
                             order_by="ProductImage.position, ProductImage.id")

    @property
    def main_image(self):
        return self.images[0].filename if self.images else None

    @property
    def on_sale(self):
        return bool(self.sale_price) and self.sale_price < self.price

    @property
    def current_price(self):
        return self.sale_price if self.on_sale else self.price

    @property
    def size_list(self):
        return [x.strip() for x in (self.sizes or "").split(",") if x.strip()]

    @property
    def color_list(self):
        return [x.strip() for x in (self.colors or "").split(",") if x.strip()]

    @property
    def in_stock(self):
        return self.stock is None or self.stock > 0

    @property
    def approved_reviews(self):
        return sorted([r for r in self.reviews if r.approved], key=lambda r: -r.id)

    @property
    def avg_rating(self):
        rs = [r.rating for r in self.reviews if r.approved]
        return round(sum(rs) / len(rs), 1) if rs else None


class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    filename = db.Column(db.String(120), nullable=False)
    position = db.Column(db.Integer, default=0)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    governorate = db.Column(db.String(60), default="")
    address = db.Column(db.Text, default="")
    notes = db.Column(db.Text, default="")
    delivery_fee = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="new")
    admin_note = db.Column(db.Text, default="")
    seen = db.Column(db.Boolean, default=False)
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")

    @property
    def subtotal(self):
        return sum(i.price * i.qty for i in self.items)

    @property
    def total(self):
        return self.subtotal + (self.delivery_fee or 0)

    @property
    def profit(self):
        return sum((i.price - i.cost) * i.qty for i in self.items)

    @property
    def status_label(self):
        return STATUS_LABEL.get(self.status, self.status)


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer)
    name = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    cost = db.Column(db.Integer, nullable=False, default=0)
    qty = db.Column(db.Integer, nullable=False, default=1)
    size = db.Column(db.String(30), default="")
    color = db.Column(db.String(30), default="")


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, nullable=False)


class Page(db.Model):
    slug = db.Column(db.String(50), primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, default="")


class ShippingZone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    fee = db.Column(db.Integer, nullable=False, default=0)
    position = db.Column(db.Integer, default=0)


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    name = db.Column(db.String(60), nullable=False)
    rating = db.Column(db.Integer, nullable=False, default=5)
    comment = db.Column(db.Text, default="")
    photo = db.Column(db.String(120))
    approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    product = db.relationship("Product", backref=db.backref("reviews", cascade="all, delete-orphan"))
