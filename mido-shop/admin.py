import csv
import io
import os
import re
import time
import secrets
from collections import defaultdict
from datetime import date
from functools import wraps
from flask import (Blueprint, render_template, request, redirect, url_for, session, flash,
                   jsonify, Response, send_file)
from models import (db, AdminUser, Category, Product, ProductImage, Order, Expense, Setting, Page,
                    ShippingZone, Review, DEFAULT_SETTINGS, STATUSES, STATUS_LABEL, utcnow, local,
                    load_settings)
from uploads import save_upload, remove_upload
from backup import make_backup

bp = Blueprint("admin", __name__)
_fails = defaultdict(list)


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("admin_id"):
            return redirect(url_for("admin.login"))
        return f(*a, **kw)
    return wrapper


@bp.context_processor
def admin_ctx():
    if session.get("admin_id"):
        last = db.session.query(db.func.max(Order.id)).scalar() or 0
        return dict(unseen=Order.query.filter_by(seen=False).count(), last_order_id=last,
                    pending_reviews=Review.query.filter_by(approved=False).count(), STATUSES=STATUSES)
    return {}


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = request.remote_addr
        now = time.time()
        _fails[ip] = [t for t in _fails[ip] if now - t < 600]
        if len(_fails[ip]) >= 8:
            flash("محاولات كتير، جرب بعد شوية", "err")
        else:
            u = AdminUser.query.filter_by(username=request.form.get("username", "").strip()).first()
            if u and u.check_password(request.form.get("password", "")):
                session.clear()
                session["admin_id"] = u.id
                return redirect(url_for("admin.dashboard"))
            _fails[ip].append(now)
            flash("بيانات الدخول غلط", "err")
    return render_template("admin/login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


def month_keys(n=12):
    now = local(utcnow())
    y, m = now.year, now.month
    keys = []
    for _ in range(n):
        keys.append("%d-%02d" % (y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return keys[::-1]


@bp.route("/")
@login_required
def dashboard():
    keys = month_keys()
    sel = request.args.get("month")
    sel = sel if sel in keys else keys[-1]
    series = {k: dict(orders=0, revenue=0, gross=0, expenses=0) for k in keys}
    status_count = defaultdict(int)
    top_month, top_all = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for o in Order.query.all():
        k = local(o.created_at).strftime("%Y-%m")
        if k == sel:
            status_count[o.status] += 1
        if o.status == "cancelled":
            continue
        if k in series:
            d = series[k]
            d["orders"] += 1
            d["revenue"] += o.subtotal
            d["gross"] += o.profit
        for i in o.items:
            top_all[i.name][0] += i.qty
            top_all[i.name][1] += i.price * i.qty
            if k == sel:
                top_month[i.name][0] += i.qty
                top_month[i.name][1] += i.price * i.qty
    for e in Expense.query.all():
        k = e.date.strftime("%Y-%m")
        if k in series:
            series[k]["expenses"] += e.amount
    for d in series.values():
        d["net"] = d["gross"] - d["expenses"]

    def top(dct):
        return sorted(([n, v[0], v[1]] for n, v in dct.items()), key=lambda r: -r[1])[:8]

    return render_template(
        "admin/dashboard.html", keys=keys, sel=sel, cur=series[sel], series=series,
        top_month=top(top_month), top_all=top(top_all),
        status_rows=[(lbl, status_count.get(k, 0)) for k, lbl in STATUSES],
        low_stock=Product.query.filter(Product.active.is_(True), Product.stock.isnot(None),
                                       Product.stock <= int(load_settings().get("low_stock_threshold") or 0)).order_by(Product.stock).all(),
        pending=Order.query.filter(Order.status.in_(["new", "confirmed", "shipping"])).count())


@bp.route("/api/new")
@login_required
def api_new():
    after = request.args.get("after", 0, type=int)
    new = Order.query.filter(Order.id > after).order_by(Order.id).all()
    return jsonify(unseen=Order.query.filter_by(seen=False).count(),
                   latest=max([o.id for o in new], default=after),
                   orders=[dict(id=o.id, name=o.name, total=o.total) for o in new])


@bp.route("/orders")
@login_required
def orders():
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()
    query = Order.query
    if status in STATUS_LABEL:
        query = query.filter_by(status=status)
    if q:
        query = query.filter(db.or_(Order.name.contains(q), Order.phone.contains(q)))
    return render_template("admin/orders.html", orders=query.order_by(Order.id.desc()).limit(300).all(),
                           status=status, q=q)


def restock(o, sign):
    for it in o.items:
        p = db.session.get(Product, it.product_id) if it.product_id else None
        if p and p.stock is not None:
            p.stock += sign * it.qty


@bp.route("/orders/<int:oid>", methods=["GET", "POST"])
@login_required
def order_detail(oid):
    o = db.get_or_404(Order, oid)
    if request.method == "POST":
        new = request.form.get("status")
        if new in STATUS_LABEL and new != o.status:
            if new == "cancelled":
                restock(o, +1)
            elif o.status == "cancelled":
                restock(o, -1)
            o.status = new
        o.admin_note = request.form.get("admin_note", "").strip()
        db.session.commit()
        flash("اتحفظ", "ok")
        return redirect(url_for("admin.order_detail", oid=oid))
    if not o.seen:
        o.seen = True
        db.session.commit()
    return render_template("admin/order_detail.html", o=o)


@bp.route("/orders/<int:oid>/quick", methods=["POST"])
@login_required
def order_quick_action(oid):
    o = db.get_or_404(Order, oid)
    action = request.form.get("action")
    
    if action == "delete":
        if o.status != "cancelled":
            restock(o, +1)
        db.session.delete(o)
        db.session.commit()
        flash("تم حذف الطلب نهائياً", "ok")
        return redirect(url_for("admin.orders"))
    
    if action in ["delivered", "cancelled"]:
        if action == "cancelled" and o.status != "cancelled":
            restock(o, +1)
        elif action == "delivered" and o.status == "cancelled":
            restock(o, -1)
        o.status = action
        db.session.commit()
        flash("تم تحديث حالة الطلب", "ok")
    
    return redirect(url_for("admin.orders"))


@bp.route("/orders/<int:oid>/delete", methods=["POST"])
@login_required
def order_delete(oid):
    o = db.get_or_404(Order, oid)
    if o.status != "cancelled":
        restock(o, +1)
    db.session.delete(o)
    db.session.commit()
    return redirect(url_for("admin.orders"))


@bp.route("/products")
@login_required
def products():
    return render_template("admin/products.html", products=Product.query.order_by(Product.id.desc()).all())


@bp.route("/offers", methods=["GET", "POST"])
@login_required
def offers():
    if request.method == "POST":
        try:
            product_ids = request.form.getlist("product_ids")
            discount_percent = int(request.form.get("discount_percent", 0))
            
            if discount_percent < 1 or discount_percent > 99:
                flash("نسبة الخصم يجب أن تكون بين 1% و 99%", "err")
            elif product_ids:
                for pid in product_ids:
                    p = db.session.get(Product, int(pid))
                    if p:
                        # حساب سعر العرض بناءً على النسبة المئوية
                        sale_price = int(p.price * (1 - discount_percent / 100))
                        p.sale_price = sale_price
                db.session.commit()
                flash(f"تم تطبيق خصم {discount_percent}% على {len(product_ids)} منتج", "ok")
            else:
                flash("اختر منتجات أولاً", "err")
        except (ValueError, KeyError):
            flash("راجع البيانات", "err")
        return redirect(url_for("admin.offers"))
    
    # المنتجات على العروض
    on_sale = Product.query.filter(Product.sale_price.isnot(None), Product.sale_price < Product.price).all()
    # المنتجات بدون عروض
    available = Product.query.filter(db.or_(Product.sale_price.is_(None), Product.sale_price >= Product.price)).all()
    
    return render_template("admin/offers.html", on_sale=on_sale, available=available)


@bp.route("/offers/<int:pid>/remove", methods=["POST"])
@login_required
def offer_remove(pid):
    p = db.get_or_404(Product, pid)
    p.sale_price = None
    db.session.commit()
    flash("تم إزالة العرض من المنتج", "ok")
    return redirect(url_for("admin.offers"))


def save_images(files, product):
    pos = len(product.images)
    for f in files:
        name, err = save_upload(f)
        if err:
            flash(err, "err")
        if name:
            product.images.append(ProductImage(filename=name, position=pos))
            pos += 1


def fill_product(p, f):
    p.name = f["name"].strip()
    p.category_id = int(f["category_id"])
    p.description = f.get("description", "").strip()
    p.price = int(f.get("price") or 0)
    sp = f.get("sale_price", "").strip()
    p.sale_price = int(sp) if sp else None
    p.cost = int(f.get("cost") or 0)
    st = f.get("stock", "").strip()
    p.stock = int(st) if st else None
    p.sizes = f.get("sizes", "").strip()
    p.colors = f.get("colors", "").strip()
    p.active = "active" in f
    p.featured = "featured" in f


def product_form(p):
    cats = Category.query.order_by(Category.position, Category.id).all()
    is_new = p is None
    if request.method == "POST":
        try:
            p = p or Product(category_id=0)
            fill_product(p, request.form)
            if is_new:
                db.session.add(p)
            save_images(request.files.getlist("images"), p)
            db.session.commit()
            flash("المنتج اتحفظ", "ok")
            return redirect(url_for("admin.product_edit", pid=p.id))
        except (ValueError, KeyError):
            db.session.rollback()
            flash("راجع الأرقام والحقول المطلوبة", "err")
    return render_template("admin/product_form.html", p=p, cats=cats)


@bp.route("/products/new", methods=["GET", "POST"])
@login_required
def product_new():
    return product_form(None)


@bp.route("/products/<int:pid>", methods=["GET", "POST"])
@login_required
def product_edit(pid):
    return product_form(db.get_or_404(Product, pid))


@bp.route("/products/<int:pid>/delete", methods=["POST"])
@login_required
def product_delete(pid):
    p = db.get_or_404(Product, pid)
    for im in p.images:
        _rm(im.filename)
    for r in p.reviews:
        _rm(r.photo)
    db.session.delete(p)
    db.session.commit()
    return redirect(url_for("admin.products"))


_rm = remove_upload


@bp.route("/images/<int:iid>/delete", methods=["POST"])
@login_required
def image_delete(iid):
    im = db.get_or_404(ProductImage, iid)
    pid = im.product_id
    _rm(im.filename)
    db.session.delete(im)
    db.session.commit()
    return redirect(url_for("admin.product_edit", pid=pid))


@bp.route("/images/<int:iid>/main", methods=["POST"])
@login_required
def image_main(iid):
    im = db.get_or_404(ProductImage, iid)
    for x in im.product.images:
        x.position = 1
    im.position = 0
    db.session.commit()
    return redirect(url_for("admin.product_edit", pid=im.product_id))


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "cat-" + secrets.token_hex(3)


@bp.route("/categories", methods=["GET", "POST"])
@login_required
def categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            slug = slugify(request.form.get("slug") or name)
            if Category.query.filter_by(slug=slug).first():
                slug += "-" + secrets.token_hex(2)
            db.session.add(Category(name=name, slug=slug, position=request.form.get("position", 0, type=int)))
            db.session.commit()
        return redirect(url_for("admin.categories"))
    return render_template("admin/categories.html", cats=Category.query.order_by(Category.position, Category.id).all())


@bp.route("/categories/<int:cid>", methods=["POST"])
@login_required
def category_update(cid):
    c = db.get_or_404(Category, cid)
    if request.form.get("delete"):
        if c.products:
            flash("مينفعش تمسح قسم فيه منتجات، انقلهم الأول", "err")
        else:
            db.session.delete(c)
    else:
        c.name = request.form.get("name", c.name).strip() or c.name
        c.position = request.form.get("position", c.position, type=int)
    db.session.commit()
    return redirect(url_for("admin.categories"))


@bp.route("/expenses", methods=["GET", "POST"])
@login_required
def expenses():
    if request.method == "POST":
        try:
            db.session.add(Expense(title=request.form["title"].strip(), amount=int(request.form["amount"]),
                                   date=date.fromisoformat(request.form["date"])))
            db.session.commit()
        except (ValueError, KeyError):
            flash("راجع البيانات", "err")
        return redirect(url_for("admin.expenses"))
    return render_template("admin/expenses.html", items=Expense.query.order_by(Expense.date.desc(), Expense.id.desc()).all(),
                           today=local(utcnow()).date().isoformat())


@bp.route("/expenses/<int:eid>/delete", methods=["POST"])
@login_required
def expense_delete(eid):
    db.session.delete(db.get_or_404(Expense, eid))
    db.session.commit()
    return redirect(url_for("admin.expenses"))


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        for k in DEFAULT_SETTINGS:
            if k in request.form:
                row = db.session.get(Setting, k) or Setting(key=k)
                row.value = request.form[k].strip()
                db.session.add(row)
        db.session.commit()
        flash("الإعدادات اتحفظت", "ok")
        return redirect(url_for("admin.settings"))
    return render_template("admin/settings.html")


@bp.route("/password", methods=["POST"])
@login_required
def password():
    u = db.session.get(AdminUser, session["admin_id"])
    new = request.form.get("new", "")
    if not u.check_password(request.form.get("old", "")):
        flash("الباسورد القديم غلط", "err")
    elif len(new) < 8:
        flash("الباسورد الجديد لازم يكون 8 حروف على الأقل", "err")
    else:
        u.set_password(new)
        db.session.commit()
        flash("الباسورد اتغير", "ok")
    return redirect(url_for("admin.settings"))


def csv_response(name, header, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=%s" % name})


@bp.route("/orders/<int:oid>/print")
@login_required
def order_print(oid):
    return render_template("admin/order_print.html", o=db.get_or_404(Order, oid))


@bp.route("/export/orders.csv")
@login_required
def export_orders():
    rows = []
    for o in Order.query.order_by(Order.id).all():
        items = " + ".join("%s %s %s x%d" % (i.name, i.size, i.color, i.qty) for i in o.items)
        rows.append([o.id, local(o.created_at).strftime("%Y-%m-%d %H:%M"), o.name, o.phone, o.governorate,
                     o.address, o.status_label, items, o.subtotal, o.delivery_fee, o.total, o.profit])
    return csv_response("orders.csv", ["#", "التاريخ", "الاسم", "التليفون", "المحافظة", "العنوان", "الحالة",
                                       "المنتجات", "المجموع", "التوصيل", "الإجمالي", "الربح"], rows)


@bp.route("/export/expenses.csv")
@login_required
def export_expenses():
    return csv_response("expenses.csv", ["التاريخ", "البند", "المبلغ"],
                        [[e.date.isoformat(), e.title, e.amount] for e in Expense.query.order_by(Expense.date).all()])


def customer_rows():
    data = {}
    for o in Order.query.filter(Order.status != "cancelled").order_by(Order.id).all():
        d = data.setdefault(o.phone, dict(name=o.name, phone=o.phone, gov=o.governorate, orders=0, total=0, last=o.created_at))
        d.update(name=o.name, gov=o.governorate, last=o.created_at)
        d["orders"] += 1
        d["total"] += o.total
    return sorted(data.values(), key=lambda r: (-r["orders"], -r["total"]))


@bp.route("/customers")
@login_required
def customers():
    rows = customer_rows()
    repeat = bool(request.args.get("repeat"))
    if repeat:
        rows = [r for r in rows if r["orders"] >= 2]
    return render_template("admin/customers.html", rows=rows, repeat=repeat)


@bp.route("/export/customers.csv")
@login_required
def export_customers():
    return csv_response("customers.csv", ["الاسم", "التليفون", "المحافظة", "عدد الطلبات", "إجمالي الشراء", "آخر طلب"],
                        [[r["name"], r["phone"], r["gov"], r["orders"], r["total"],
                          local(r["last"]).strftime("%Y-%m-%d")] for r in customer_rows()])


@bp.route("/reviews")
@login_required
def reviews():
    return render_template("admin/reviews.html", items=Review.query.order_by(Review.approved, Review.id.desc()).all())


@bp.route("/reviews/<int:rid>", methods=["POST"])
@login_required
def review_update(rid):
    r = db.get_or_404(Review, rid)
    if request.form.get("delete"):
        _rm(r.photo)
        db.session.delete(r)
    else:
        r.approved = request.form.get("approve") == "1"
    db.session.commit()
    return redirect(url_for("admin.reviews"))


@bp.route("/zones", methods=["GET", "POST"])
@login_required
def zones():
    if request.method == "POST":
        try:
            db.session.add(ShippingZone(name=request.form["name"].strip(), fee=int(request.form["fee"]),
                                        position=request.form.get("position", 0, type=int)))
            db.session.commit()
        except (ValueError, KeyError):
            flash("راجع البيانات", "err")
        return redirect(url_for("admin.zones"))
    return render_template("admin/zones.html", zones=ShippingZone.query.order_by(ShippingZone.position, ShippingZone.id).all())


@bp.route("/zones/<int:zid>", methods=["POST"])
@login_required
def zone_update(zid):
    z = db.get_or_404(ShippingZone, zid)
    if request.form.get("delete"):
        db.session.delete(z)
    else:
        try:
            z.name = request.form.get("name", z.name).strip() or z.name
            z.fee = int(request.form.get("fee", z.fee))
            z.position = request.form.get("position", z.position, type=int)
        except ValueError:
            flash("راجع الأرقام", "err")
    db.session.commit()
    return redirect(url_for("admin.zones"))


@bp.route("/pages")
@login_required
def pages():
    return render_template("admin/pages.html", pages=Page.query.order_by(Page.slug).all())


@bp.route("/pages/<slug>", methods=["GET", "POST"])
@login_required
def page_edit(slug):
    pg = db.get_or_404(Page, slug)
    if request.method == "POST":
        pg.title = request.form.get("title", pg.title).strip() or pg.title
        pg.body = request.form.get("body", "").strip()
        db.session.commit()
        flash("الصفحة اتحفظت", "ok")
        return redirect(url_for("admin.page_edit", slug=slug))
    return render_template("admin/page_form.html", pg=pg)


@bp.route("/backup", methods=["POST"])
@login_required
def backup():
    buf = io.BytesIO()
    make_backup(buf)
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name="mido-backup-%s.zip" % local(utcnow()).strftime("%Y%m%d-%H%M"))
