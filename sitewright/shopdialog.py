"""Tools > Shop manager: products, payment setup, currency, shipping and tax."""
import copy

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                             QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QTabWidget, QVBoxLayout,
                             QWidget)

from . import shop


class ShopManager(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.work = copy.deepcopy(win.doc.shop)
        self.cur = None
        self.setWindowTitle("Shop manager")
        self.resize(1000, 680)
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs)
        self.tabs.addTab(self.products_tab(), "Products")
        self.tabs.addTab(self.payment_tab(), "Payments")
        self.tabs.addTab(self.store_tab(), "Currency, shipping, tax")
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.fill_list()
        if self.work["products"]:
            self.list.setCurrentRow(0)
        else:
            self.enable(False)

    # -- products
    def products_tab(self):
        w = QWidget()
        row = QHBoxLayout(w)
        left = QVBoxLayout()
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self.pick)
        left.addWidget(self.list, 1)
        for label, fn in (("New product", self.new), ("Duplicate", self.duplicate), ("Delete", self.delete),
                          ("Import CSV...", self.import_csv), ("Export CSV...", self.export_csv)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            left.addWidget(b)
        row.addLayout(left, 1)
        form = QFormLayout()
        self.name = QLineEdit()
        self.price = QDoubleSpinBox()
        self.price.setRange(0, 1_000_000)
        self.price.setDecimals(2)
        self.desc = QPlainTextEdit()
        self.desc.setFixedHeight(90)
        self.sku = QLineEdit()
        self.active = QCheckBox("For sale (untick to hide it from the shop)")
        pic = QHBoxLayout()
        self.thumb = QLabel("No picture")
        self.thumb.setFixedSize(100, 70)
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setStyleSheet("border:1px solid #bbb;background:#eef")
        pic.addWidget(self.thumb)
        b1, b2 = QPushButton("Choose picture..."), QPushButton("Remove")
        b1.clicked.connect(self.choose_picture)
        b2.clicked.connect(self.remove_picture)
        pic.addWidget(b1)
        pic.addWidget(b2)
        pic.addStretch()
        self.shopify = QLineEdit()
        self.shopify.setPlaceholderText("Shopify variant number (filled in when you import)")
        self.woo = QLineEdit()
        self.woo.setPlaceholderText("WooCommerce product number (filled in when you import)")
        self.link = QLineEdit()
        self.link.setPlaceholderText("Optional Stripe Payment Link (https://buy.stripe.com/...)")
        form.addRow("Name", self.name)
        form.addRow("Price", self.price)
        form.addRow("Description", self.desc)
        form.addRow("Picture", pic)
        form.addRow("Product code (SKU)", self.sku)
        form.addRow("", self.active)
        form.addRow("Shopify", self.shopify)
        form.addRow("WooCommerce", self.woo)
        form.addRow("Stripe link", self.link)
        row.addLayout(form, 3)
        return w

    def enable(self, on):
        for w in (self.name, self.price, self.desc, self.sku, self.active, self.shopify, self.woo, self.link):
            w.setEnabled(on)

    def fill_list(self, keep=None):
        self.list.blockSignals(True)
        self.list.clear()
        cur = self.work["currency"]
        for p in self.work["products"]:
            it = QListWidgetItem("%s%s\n%s" % ("" if p.get("active", True) else "[hidden] ", p["name"], shop.money(p["price"], cur)))
            self.list.addItem(it)
        self.list.blockSignals(False)
        if keep is not None:
            self.list.setCurrentRow(keep)

    def save_current(self):
        p = self.cur
        if p is None:
            return
        p.update(name=self.name.text().strip() or "Product", price=round(self.price.value(), 2),
                 desc=self.desc.toPlainText().strip(), sku=self.sku.text().strip(), active=self.active.isChecked(),
                 shopify_variant=self.shopify.text().strip(), woo_id=self.woo.text().strip(),
                 stripe_link=self.link.text().strip())

    def pick(self, row):
        self.save_current()
        if row < 0 or row >= len(self.work["products"]):
            self.cur = None
            self.enable(False)
            return
        p = self.cur = self.work["products"][row]
        self.enable(True)
        self.name.setText(p["name"])
        self.price.setValue(float(p["price"]))
        self.desc.setPlainText(p.get("desc", ""))
        self.sku.setText(p.get("sku", ""))
        self.active.setChecked(p.get("active", True))
        self.shopify.setText(str(p.get("shopify_variant", "")))
        self.woo.setText(str(p.get("woo_id", "")))
        self.link.setText(p.get("stripe_link", ""))
        self.show_thumb()

    def new(self):
        self.save_current()
        self.work["products"].append(shop.new_product())
        self.fill_list(len(self.work["products"]) - 1)
        self.name.setFocus()
        self.name.selectAll()

    def duplicate(self):
        self.save_current()
        if self.cur is None:
            return
        p = copy.deepcopy(self.cur)
        p["id"] = shop.new_id()
        p["name"] += " copy"
        self.work["products"].append(p)
        self.fill_list(len(self.work["products"]) - 1)

    def delete(self):
        row = self.list.currentRow()
        if row < 0:
            return
        if QMessageBox.question(self, "WebPlus", "Delete \"%s\"?" % self.work["products"][row]["name"]) != QMessageBox.Yes:
            return
        self.cur = None
        del self.work["products"][row]
        self.fill_list()
        if self.work["products"]:
            self.list.setCurrentRow(min(row, len(self.work["products"]) - 1))
        else:
            self.enable(False)

    def choose_picture(self):
        if self.cur is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Choose a picture", "", "Pictures (*.png *.jpg *.jpeg *.gif *.webp)")
        if path:
            self.cur["asset"] = self.win.doc.add_asset(path)
            self.cur["image_url"] = ""
            self.show_thumb()

    def remove_picture(self):
        if self.cur is not None:
            self.cur["asset"] = self.cur["image_url"] = ""
            self.show_thumb()

    def show_thumb(self):
        pm = self.win.pixmap(self.cur.get("asset")) if self.cur and self.cur.get("asset") else None
        if pm is not None and not pm.isNull():
            self.thumb.setPixmap(pm.scaled(98, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.thumb.setPixmap(QPixmap())
            self.thumb.setText("No picture")

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import products", "", "CSV files (*.csv *.txt)")
        if not path:
            return
        self.save_current()
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            new = shop.products_from_csv(f.read())
        if not new:
            QMessageBox.information(self, "WebPlus", "No products were found. The first line must name the columns "
                                    "(name, price, description, image_url...).")
            return
        self.work["products"].extend(new)
        self.fill_list(len(self.work["products"]) - 1)

    def export_csv(self):
        self.save_current()
        path, _ = QFileDialog.getSaveFileName(self, "Export products", "products.csv", "CSV files (*.csv)")
        if path:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(shop.products_to_csv(self.work["products"]))

    # -- payments
    def payment_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        top = QFormLayout()
        self.provider = QComboBox()
        for k, label in shop.PROVIDERS:
            self.provider.addItem(label, k)
        self.provider.setCurrentIndex(max(self.provider.findData(self.work["provider"]), 0))
        top.addRow("Customers pay with", self.provider)
        lay.addLayout(top)
        note = QLabel("Money goes straight to the payment company or your own store. WebPlus never sees card numbers.")
        note.setWordWrap(True)
        lay.addWidget(note)
        g = QGroupBox("PayPal")
        f = QFormLayout(g)
        self.pp_client = QLineEdit(self.work.get("paypal_client", ""))
        self.pp_client.setPlaceholderText("Client ID from developer.paypal.com (Apps & Credentials, Live)")
        self.pp_email = QLineEdit(self.work.get("paypal_email", ""))
        self.pp_email.setPlaceholderText("Or just your PayPal email address (simple cart button)")
        f.addRow("Client ID", self.pp_client)
        f.addRow("PayPal email", self.pp_email)
        f.addRow(self.wrap("With a Client ID buyers get the PayPal buttons (PayPal, cards, Pay Later). With only an email "
                           "they are sent to PayPal's cart page. PayPal emails you every order: check the amount before you ship."))
        lay.addWidget(g)
        g = QGroupBox("Stripe")
        f = QFormLayout(g)
        self.st_key = QLineEdit(self.work.get("stripe_secret", ""))
        self.st_key.setPlaceholderText("Secret or restricted key (sk_live_... or rk_live_...)")
        f.addRow("Secret key", self.st_key)
        f.addRow(self.wrap("The key is written to a private folder on your web host (PHP needed). Use a restricted key "
                           "that can only create Checkout Sessions. Prices are checked on your host, so a buyer cannot change them."))
        lay.addWidget(g)
        g = QGroupBox("Shopify")
        f = QFormLayout(g)
        self.sh_domain = QLineEdit(self.work.get("shopify_domain", ""))
        self.sh_domain.setPlaceholderText("your-store.myshopify.com")
        self.sh_token = QLineEdit(self.work.get("shopify_token", ""))
        self.sh_token.setPlaceholderText("Storefront API access token (public)")
        imp = QPushButton("Bring in my Shopify products")
        imp.clicked.connect(self.import_shopify)
        f.addRow("Store address", self.sh_domain)
        f.addRow("Storefront token", self.sh_token)
        f.addRow(imp)
        f.addRow(self.wrap("The cart on your page sends buyers to your Shopify checkout with their items filled in."))
        lay.addWidget(g)
        g = QGroupBox("WooCommerce")
        f = QFormLayout(g)
        self.woo_url = QLineEdit(self.work.get("woo_url", ""))
        self.woo_url.setPlaceholderText("https://your-store.com")
        imp = QPushButton("Bring in my WooCommerce products")
        imp.clicked.connect(self.import_woo)
        f.addRow("Store address", self.woo_url)
        f.addRow(imp)
        f.addRow(self.wrap("WooCommerce adds one product at a time, so each item has its own 'buy at the store' button."))
        lay.addWidget(g)
        lay.addStretch()
        return w

    @staticmethod
    def wrap(text):
        l = QLabel(text)
        l.setWordWrap(True)
        l.setStyleSheet("color:#556")
        return l

    def store_tab(self):
        w = QWidget()
        f = QFormLayout(w)
        self.currency = QComboBox()
        for c in shop.CURRENCIES:
            self.currency.addItem("%s  %s" % (c, shop.CURRENCIES[c].strip()), c)
        self.currency.setCurrentIndex(max(self.currency.findData(self.work["currency"]), 0))
        self.shipping = QDoubleSpinBox()
        self.shipping.setRange(0, 100000)
        self.shipping.setValue(float(self.work.get("shipping") or 0))
        self.tax = QDoubleSpinBox()
        self.tax.setRange(0, 100)
        self.tax.setSuffix(" %")
        self.tax.setValue(float(self.work.get("tax") or 0))
        self.thanks = QLineEdit(self.work.get("thanks", ""))
        f.addRow("Currency", self.currency)
        f.addRow("Flat shipping for each order", self.shipping)
        f.addRow("Sales tax added to the total", self.tax)
        f.addRow("Thank-you message", self.thanks)
        f.addRow(self.wrap("Shipping and tax are added to PayPal and Stripe carts. Shopify and WooCommerce work out their own at checkout."))
        return w

    # -- importing from stores
    def _busy(self, fn):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            return fn()
        except Exception as e:
            QMessageBox.warning(self, "WebPlus", "That did not work:\n%s" % e)
            return None
        finally:
            QApplication.restoreOverrideCursor()

    def _take(self, result):
        if not result:
            return
        items, cur = result
        if not items:
            QMessageBox.information(self, "WebPlus", "The store has no products to bring in.")
            return
        self.save_current()
        for p in items:
            shop.fetch_image(self.win.doc, p)
        self.work["products"].extend(items)
        if cur in shop.CURRENCIES:
            self.currency.setCurrentIndex(self.currency.findData(cur))
        self.fill_list(len(self.work["products"]) - 1)
        self.tabs.setCurrentIndex(0)
        QMessageBox.information(self, "WebPlus", "Brought in %d product(s)." % len(items))

    def import_shopify(self):
        if not self.sh_domain.text().strip() or not self.sh_token.text().strip():
            QMessageBox.information(self, "WebPlus", "Fill in the store address and the Storefront token first.")
            return
        self._take(self._busy(lambda: shop.import_shopify(self.sh_domain.text(), self.sh_token.text())))

    def import_woo(self):
        if not self.woo_url.text().strip():
            QMessageBox.information(self, "WebPlus", "Fill in the store address first.")
            return
        self._take(self._busy(lambda: shop.import_woocommerce(self.woo_url.text())))

    def accept(self):
        self.save_current()
        self.work.update(provider=self.provider.currentData(), paypal_client=self.pp_client.text().strip(),
                         paypal_email=self.pp_email.text().strip(), stripe_secret=self.st_key.text().strip(),
                         shopify_domain=self.sh_domain.text().strip(), shopify_token=self.sh_token.text().strip(),
                         woo_url=self.woo_url.text().strip(), currency=self.currency.currentData(),
                         shipping=round(self.shipping.value(), 2), tax=round(self.tax.value(), 2),
                         thanks=self.thanks.text().strip())
        super().accept()


def shop_manager(win):
    dlg = ShopManager(win)
    if dlg.exec_() == QDialog.Accepted:
        win.doc.shop = dlg.work
        win.reload({o.d["id"] for o in win.selected()})
        win.commit_if_changed("Shop")
