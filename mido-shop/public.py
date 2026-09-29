import re
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort
from models import (db, Product, Category, Order, OrderItem, Page, ShippingZone, Review,
                    STATUSES, load_settings)
from notify import notify_order
from uploads import save_upload

bp = Blueprint("shop", __name__)
OTHER_GOV = "محافظة أخرى"


def active():
    return Product.query.filter_by(active=True)


def offers_q():
    return active().filter(Product.sale_price.isnot(None), Product.sale_price > 0,
                           Product.sale_price < Product.price)


@bp.route("/")
def index():
    featured = active().filter_by(featured=True).order_by(Product.id.desc()).limit(8).all()
    latest = active().order_by(Product.id.desc()).limit(8).all()
    offers = offers_q().order_by(Product.id.desc()).limit(4).all()
    return render_template("index.html", featured=featured, latest=latest, offers=offers)


@bp.route("/c/<slug>")
def category(slug):
    cat = Category.query.filter_by(slug=slug).first_or_404()
    sort = request.args.get("sort", "new")
    order = {"new": Product.id.desc(), "low": Product.price.asc(), "high": Product.price.desc()}
    products = active().filter_by(category_id=cat.id).order_by(order.get(sort, Product.id.desc())).all()
    return render_template("listing.html", title=cat.name, products=products, sort=sort)


@bp.route("/offers")
def offers():
    return render_template("listing.html", title="العروض", products=offers_q().order_by(Product.id.desc()).all(), sort=None)


@bp.route("/search")
def search():
    q = request.args.get("q", "").strip()
    products = active().filter(Product.name.contains(q)).all() if q else []
    return render_template("listing.html", title="نتائج البحث: %s" % q, products=products, sort=None)


@bp.route("/page/<slug>")
def page(slug):
    return render_template("page.html", pg=db.get_or_404(Page, slug))


@bp.route("/p/<int:pid>")
def product(pid):
    p = db.get_or_404(Product, pid)
    if not p.active:
        abort(404)
    related = active().filter(Product.category_id == p.category_id, Product.id != p.id).limit(4).all()
    return render_template("product.html", p=p, related=related, size_page=db.session.get(Page, "sizes"))


@bp.route("/p/<int:pid>/review", methods=["POST"])
def review(pid):
    p = db.get_or_404(Product, pid)
    name = request.form.get("name", "").strip()[:60]
    comment = request.form.get("comment", "").strip()[:600]
    rating = request.form.get("rating", 5, type=int)
    done = session.get("reviewed", [])
    if not name or not comment or not 1 <= rating <= 5:
        flash("اكتب اسمك وتعليقك واختار التقييم", "err")
    elif pid in done:
        flash("إنت قيّمت المنتج ده قبل كده", "err")
    else:
        photo, err = save_upload(request.files.get("photo"), 5)
        if err:
            flash(err, "err")
        else:
            db.session.add(Review(product_id=p.id, name=name, rating=rating, comment=comment, photo=photo))
            db.session.commit()
            session["reviewed"] = done + [pid]
            flash("شكراً! تقييمك هيظهر بعد المراجعة", "ok")
    return redirect(url_for("shop.product", pid=pid) + "#reviews")


def cart_lines():
    lines = []
    for i, it in enumerate(session.get("cart", [])):
        p = db.session.get(Product, it["pid"])
        if p and p.active:
            lines.append(dict(idx=i, p=p, size=it["size"], color=it["color"], qty=it["qty"],
                              total=p.current_price * it["qty"]))
    return lines


@bp.route("/cart/add", methods=["POST"])
def cart_add():
    p = db.get_or_404(Product, request.form.get("pid", type=int))
    size = request.form.get("size", "")
    color = request.form.get("color", "")
    qty = max(1, min(10, request.form.get("qty", 1, type=int)))
    if (p.size_list and size not in p.size_list) or (p.color_list and color not in p.color_list):
        flash("اختار المقاس واللون الأول", "err")
        return redirect(url_for("shop.product", pid=p.id))
    if not p.in_stock:
        flash("المنتج ده خلص", "err")
        return redirect(url_for("shop.product", pid=p.id))
    cart = session.get("cart", [])
    for it in cart:
        if it["pid"] == p.id and it["size"] == size and it["color"] == color:
            it["qty"] = min(10, it["qty"] + qty)
            break
    else:
        cart.append(dict(pid=p.id, size=size, color=color, qty=qty))
    session["cart"] = cart
    return redirect(url_for("shop.checkout") if request.form.get("buy") else url_for("shop.cart"))


@bp.route("/cart")
def cart():
    lines = cart_lines()
    return render_template("cart.html", lines=lines, subtotal=sum(l["total"] for l in lines))


@bp.route("/cart/update", methods=["POST"])
def cart_update():
    cart = session.get("cart", [])
    idx = request.form.get("idx", type=int)
    if idx is not None and 0 <= idx < len(cart):
        if request.form.get("remove"):
            cart.pop(idx)
        else:
            cart[idx]["qty"] = max(1, min(10, request.form.get("qty", 1, type=int)))
    session["cart"] = cart
    return redirect(url_for("shop.cart"))


def norm_phone(v):
    d = re.sub(r"\D", "", v or "")
    if d.startswith("20"):
        d = "0" + d[2:]
    return d if re.fullmatch(r"01[0125]\d{8}", d) else None


@bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    lines = cart_lines()
    if not lines:
        return redirect(url_for("shop.cart"))
    S = load_settings()
    default_fee = int(S.get("delivery_fee") or 0)
    zones = ShippingZone.query.order_by(ShippingZone.position, ShippingZone.id).all()
    fees = {z.name: z.fee for z in zones}
    subtotal = sum(l["total"] for l in lines)
    form = request.form
    fee = default_fee
    if request.method == "POST":
        name, gov, addr = form.get("name", "").strip(), form.get("governorate", "").strip(), form.get("address", "").strip()
        phone = norm_phone(form.get("phone"))
        fee = fees.get(gov, default_fee)
        err = None
        if not name or not gov or not addr:
            err = "كمّل بياناتك (الاسم والمحافظة والعنوان)"
        elif zones and gov not in fees and gov != OTHER_GOV:
            err = "اختار المحافظة من القائمة"
        elif not phone:
            err = "رقم التليفون لازم يكون رقم موبايل مصري صحيح"
        else:
            for l in lines:
                if l["p"].stock is not None and l["p"].stock < l["qty"]:
                    err = "الكمية المطلوبة من %s مش متوفرة" % l["p"].name
        if err:
            flash(err, "err")
        else:
            o = Order(name=name, phone=phone, governorate=gov, address=addr,
                      notes=form.get("notes", "").strip(), delivery_fee=fee)
            for l in lines:
                p = l["p"]
                o.items.append(OrderItem(product_id=p.id, name=p.name, price=p.current_price, cost=p.cost,
                                         qty=l["qty"], size=l["size"], color=l["color"]))
                if p.stock is not None:
                    p.stock -= l["qty"]
            db.session.add(o)
            db.session.commit()
            session["cart"] = []
            session["last_order"] = o.id
            notify_order(o, S)
            return redirect(url_for("shop.success", oid=o.id))
    return render_template("checkout.html", lines=lines, subtotal=subtotal, fee=fee, form=form,
                           zones=zones, default_fee=default_fee, other_gov=OTHER_GOV)


@bp.route("/order/<int:oid>/done")
def success(oid):
    if session.get("last_order") != oid:
        abort(404)
    return render_template("success.html", o=db.get_or_404(Order, oid))


@bp.route("/track", methods=["GET", "POST"])
def track():
    order = None
    if request.method == "POST":
        oid = request.form.get("order_id", type=int)
        phone = norm_phone(request.form.get("phone"))
        o = db.session.get(Order, oid) if oid else None
        if o and phone and norm_phone(o.phone) == phone:
            order = o
        else:
            flash("مفيش طلب بالبيانات دي، راجع رقم الطلب والموبايل", "err")
    return render_template("track.html", order=order, statuses=[s for s in STATUSES if s[0] != "cancelled"])
