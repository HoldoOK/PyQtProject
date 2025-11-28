import sys
import datetime
import os
from uis import Ui_MainWindow, Ui_OfferPage, Ui_Form
from PyQt6.QtGui import QPixmap

import sqlite3
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox, QPushButton, QHBoxLayout, QLabel, QFileDialog)

from PyQt6 import QtCore

convert = {
    "Модель": "model",
    "Марка": "manufacturer",
    "Пробег <": "mileage",
    "Цвет": "color",
    "Год выпуска": "year",
    "Владельцев <": "owners"
}


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.con = sqlite3.connect("rent.db")
        self.cursor = self.con.cursor()

        self.form = FormWindow()
        self.offerpage = offerPage()

        self.isloggedin = False
        self.isadmin = False
        self.userid = None
        self.city = None
        self.phone = None
        self.displayname = None

        self.editing_offer_id = None

        self._setup_initial_visibility()
        self._setup_connections()

        self.search()
        self.load_my_offers()

    def _setup_initial_visibility(self):

        self.loginWidget.hide()
        self.signupWidget.hide()

    def _setup_connections(self):

        self.loginButton.clicked.connect(self.loginshow)
        self.sugnupButton.clicked.connect(self.signupshow)
        self.loginCompleteButton.clicked.connect(self.login)
        self.signupCompleteButton.clicked.connect(self.signup)
        self.createNewButton.clicked.connect(self.createOffer)
        self.searchButton.clicked.connect(self.search)
        self.openOfferPageButton.clicked.connect(self.seeOfferPage)
        self.form.createButton.clicked.connect(self.pushOffer)
        self.offerpage.buyButton.clicked.connect(self.checkout)
        self.offerpage.callButton.clicked.connect(self.seephone)
        self.tabWidget.currentChanged.connect(self.on_tab_changed)
        self.form.chooseIntButton.clicked.connect(self.choose_int_image)
        self.form.chooseExtButton.clicked.connect(self.choose_ext_image)

    def on_tab_changed(self, index):

        tab_text = self.tabWidget.tabText(index)
        if tab_text == "Мои предложения":
            self.load_my_offers()

    def loginshow(self):
        self.loginWidget.show()
        self.signupWidget.hide()

    def signupshow(self):
        self.loginWidget.hide()
        self.signupWidget.show()

    def checkout(self):

        offer_id = getattr(self, "current_offer_id", None)
        if offer_id is None:
            QMessageBox.warning(self, "Ошибка", "ID объявления неизвестен. Откройте страницу объявления снова.")
            return

        try:
            offer = self.cursor.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка БД", f"Ошибка при обращении к базе: {e}")
            return

        if not offer:
            QMessageBox.warning(self, "Ошибка", "Объявление не найдено в базе.")
            return

        seller = self.cursor.execute(
            "SELECT display_name, phone, city FROM accounts WHERE userid = ?", (offer[1],)
        ).fetchone()
        seller_name = seller[0] if seller else "Unknown"
        seller_phone = seller[1] if seller else "-"
        seller_city = seller[2] if seller else "-"

        offer_data = {
            "ID": offer[0],
            "Продавец": seller_name,
            "Телефон продавца": seller_phone,
            "Город продажи": seller_city,
            "Дата размещения": offer[3],
            "Марка": offer[5],
            "Модель": offer[4],
            "Год": offer[6],
            "Цена": self.format_price(offer[7]),
            "Цвет": offer[8],
            "Пробег": f"{offer[9]}",
            "Владельцев": offer[10],
            "КПП": offer[11],
            "Привод": offer[12],
            "Состояние": offer[13],
            "Тип двигателя": offer[14]
        }

        try:
            base_dir = os.path.dirname(__file__)
        except NameError:
            base_dir = os.path.dirname(sys.argv[0]) or os.getcwd()
        receipts_dir = os.path.join(base_dir, "receipts")
        os.makedirs(receipts_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"receipt_offer_{offer_id}_{timestamp}"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить чек",
            os.path.join(receipts_dir, default_name),
            "Текстовый файл (*.txt)"
        )

        if not path:
            return

        try:
            if path.lower().endswith(".txt"):
                with open(path, "w", encoding="utf-8") as f:
                    f.write("Данные о покупке\n\n")
                    for k, v in offer_data.items():
                        f.write(f"{k}: {v}\n")

            QMessageBox.information(self, "Готово", f"Чек успешно сохранён:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка записи", f"Не удалось сохранить файл: {e}")

    def login(self):

        login_text = self.loginLogin.text()
        passwd_text = self.loginPasswd.text()
        loginInfo = self.cursor.execute(
            "SELECT * FROM accounts where login = ? and password = ?",
            (login_text, passwd_text)
        ).fetchone()
        if loginInfo is None:
            self.loginHint.setText("Неверный логин или пароль")
            return

        self.isloggedin = True
        self.userid = loginInfo[5]
        self.city = loginInfo[4]
        self.phone = loginInfo[3]
        self.displayname = loginInfo[2]
        self.isadmin = (loginInfo[6] == 'admin')
        self.loginHint.setText("")
        self.loginsignupWidget.hide()
        self.loginWidget.hide()
        self.loggedAs.setText(f'Вы вошли как: {self.displayname}')

        self.load_my_offers()

    def signup(self):

        login_text = self.signupLogin.text()
        passwd_text = self.signupPasswd.text()
        display_name = self.signupDisplayName.text()
        city = self.signupCity.text()
        phone = self.signupPhone.text()

        if login_text == "" or passwd_text == "" or display_name == "" or city == "" or phone == "":
            self.signupHint.setText("Незаполненные данные")
            return

        existing = self.cursor.execute("SELECT * FROM accounts where login = ?", (login_text,)).fetchone()
        if existing is not None:
            self.signupHint.setText("Логин занят")
            return

        self.cursor.execute(
            "INSERT INTO accounts(login, password, display_name, phone, city, access) VALUES (?,?,?,?,?,?)",
            (login_text, passwd_text, display_name, phone, city, "user")
        )
        self.con.commit()
        self.signupHint.setText("Вы успешно зарегистрировались. Войдите в аккаунт")

    def createOffer(self):

        self.editing_offer_id = None
        self.form.formHInt.setText("")
        self._clear_form_fields()
        self.form.show()

    def _clear_form_fields(self):

        self.form.modelEdit.setText("")
        self.form.manufacturerEdit.setText("")
        self.form.priceEdit.setText("")
        self.form.yearEdit.setText("")
        self.form.colorEdit.setText("")
        self.form.stateCombo.setCurrentIndex(0)
        self.form.privodCombo.setCurrentIndex(0)
        self.form.kppCombo.setCurrentIndex(0)
        self.form.engineTypeCombo.setCurrentIndex(0)
        self.form.ownerEdit.setText("")
        self.form.mileageEdit.setText("")
        self.form.descriptionEdit.setText("")
        self.form.exterEdit.setText("")
        self.form.interEdit.setText("")

    def _fill_form_from_offer(self, offer_row):

        self.form.modelEdit.setText(str(offer_row[4]))
        self.form.manufacturerEdit.setText(str(offer_row[5]))
        self.form.yearEdit.setText(str(offer_row[6]))
        self.form.priceEdit.setText(str(offer_row[7]))
        self.form.colorEdit.setText(str(offer_row[8]))
        self.form.mileageEdit.setText(str(offer_row[9]))
        self.form.ownerEdit.setText(str(offer_row[10]))
        self._set_combobox_text(self.form.kppCombo, offer_row[11])
        self._set_combobox_text(self.form.privodCombo, offer_row[12])
        self._set_combobox_text(self.form.stateCombo, offer_row[13])
        self._set_combobox_text(self.form.engineTypeCombo, offer_row[14])
        self.form.descriptionEdit.setText(str(offer_row[2]))
        self.form.exterEdit.setText(str(offer_row[15]))
        self.form.interEdit.setText(str(offer_row[16]))

    def _set_combobox_text(self, combobox, text):

        for i in range(combobox.count()):
            if combobox.itemText(i) == text:
                combobox.setCurrentIndex(i)
                return
        combobox.setCurrentIndex(0)

    def pushOffer(self):

        if not self.isloggedin:
            self.form.formHInt.setText("Вы не вошли в аккаунт")
            return

        try:
            year_val = int(self.form.yearEdit.text())
            price_val = int(self.form.priceEdit.text())
            mileage_val = int(self.form.mileageEdit.text())
            owners_val = int(self.form.ownerEdit.text())
        except Exception:
            self.form.formHInt.setText("Неверные числовые значения")
            return

        required_texts = [
            self.form.modelEdit.text(),
            self.form.manufacturerEdit.text(),
            self.form.descriptionEdit.text()
        ]
        if not all(map(lambda s: s.strip() != "", required_texts)):
            self.form.formHInt.setText("Не все поля заполнены")
            return

        if self.editing_offer_id is None:
            self.cursor.execute(
                "INSERT INTO offers(userid, date, description, manufacturer, model, year, price, kpp, privod, color, state, enginetype, mileage, owners, extimglink, intimglink) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (self.userid,
                 datetime.datetime.now().strftime("%d.%m.%Y"),
                 self.form.descriptionEdit.text(),
                 self.form.manufacturerEdit.text(),
                 self.form.modelEdit.text(),
                 year_val,
                 price_val,
                 self.form.kppCombo.currentText(),
                 self.form.privodCombo.currentText(),
                 self.form.colorEdit.text(),
                 self.form.stateCombo.currentText(),
                 self.form.engineTypeCombo.currentText(),
                 mileage_val,
                 owners_val,
                 self.form.exterEdit.text(),
                 self.form.interEdit.text())
            )
            self.con.commit()
            self.form.hide()
            self.show_message("Создано", "Объявление успешно создано")
        else:
            self.cursor.execute(
                "UPDATE offers SET description=?, manufacturer=?, model=?, year=?, price=?, kpp=?, privod=?, color=?, state=?, enginetype=?, mileage=?, owners=?, extimglink=?, intimglink=? "
                "WHERE id = ?",
                (self.form.descriptionEdit.text(),
                 self.form.manufacturerEdit.text(),
                 self.form.modelEdit.text(),
                 year_val,
                 price_val,
                 self.form.kppCombo.currentText(),
                 self.form.privodCombo.currentText(),
                 self.form.colorEdit.text(),
                 self.form.stateCombo.currentText(),
                 self.form.engineTypeCombo.currentText(),
                 mileage_val,
                 owners_val,
                 self.form.exterEdit.text(),
                 self.form.interEdit.text(),
                 self.editing_offer_id)
            )
            self.con.commit()
            self.form.hide()
            self.show_message("Сохранено", "Объявление успешно обновлено")
            self.editing_offer_id = None

        self.search()
        self.load_my_offers()

    def search(self):

        searchtext = self.searchBox.text().strip()
        searchfilter_display = self.searchFilterBox.currentText()
        pricemin = self.priceMin.text().strip()
        pricemax = self.priceMax.text().strip()
        enginetype = self.engineTypeCombo_2.currentText()
        privod = self.privodCombo_2.currentText()
        kpp = self.kppCombo_2.currentText()
        state = self.stateCombo_2.currentText()

        column = convert.get(searchfilter_display, "model")

        where_clauses = []
        params = []

        if searchfilter_display in ("Пробег <", "Владельцев <"):
            if searchtext != "":
                try:
                    num = int(searchtext)
                    where_clauses.append(f"{column} < ?")
                    params.append(num)
                except ValueError:
                    pass
        else:
            if searchtext != "":
                where_clauses.append(f"{column} LIKE ?")
                params.append(f"%{searchtext}%")

        if pricemin != "":
            try:
                pmin = int(pricemin)
                where_clauses.append("price >= ?")
                params.append(pmin)
            except ValueError:
                pass
        if pricemax != "":
            try:
                pmax = int(pricemax)
                where_clauses.append("price <= ?")
                params.append(pmax)
            except ValueError:
                pass

        if enginetype != "":
            where_clauses.append("enginetype = ?")
            params.append(enginetype)
        if privod != "":
            where_clauses.append("privod = ?")
            params.append(privod)
        if kpp != "":
            where_clauses.append("kpp = ?")
            params.append(kpp)
        if state != "":
            where_clauses.append("state = ?")
            params.append(state)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        sql = f"SELECT * FROM offers {where_sql} ORDER BY date DESC"
        try:
            data = self.cursor.execute(sql, tuple(params)).fetchall()
        except Exception as e:
            print("SQL search error:", e)
            data = []

        datashort = []
        for row in data:
            seller_display = self.cursor.execute("SELECT display_name FROM accounts WHERE userid = ?",
                                                 (row[1],)).fetchone()
            seller_name = seller_display[0] if seller_display else "Unknown"
            datashort.append([
                seller_name, row[3], row[5], row[4], row[6], self.format_price(row[7]), row[8], row[9], row[10], row[0]
            ])

        self.populate_search_table(datashort)

    def populate_search_table(self, datashort):

        if not datashort:
            self.searchTableWidget.clear()
            self.searchTableWidget.setRowCount(0)
            self.searchTableWidget.setColumnCount(0)
            return

        headers = ("Продавец", "Дата создания", "Марка", "Модель", "Год выпуска", "Цена", "Цвет", "Пробег",
                   "Кол-во владельцев", "ID")
        self.searchTableWidget.clear()
        self.searchTableWidget.setRowCount(len(datashort))
        self.searchTableWidget.setColumnCount(len(headers))
        self.searchTableWidget.setHorizontalHeaderLabels(headers)

        for r, row in enumerate(datashort):
            for c, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                self.searchTableWidget.setItem(r, c, item)

        header = self.searchTableWidget.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)

        id_col_index = len(headers) - 1
        self.searchTableWidget.setColumnHidden(id_col_index, True)

    def get_items_by_row(self, row_index):

        items_in_row = []
        for col in range(self.searchTableWidget.columnCount()):
            item = self.searchTableWidget.item(row_index, col)
            items_in_row.append(item.text() if item is not None else "")
        return items_in_row

    def choose_int_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите фото интерьера", "", "Изображения (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if path:
            self.form.interEdit.setText(path)

    def choose_ext_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите фото экстерьера", "", "Изображения (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if path:
            self.form.exterEdit.setText(path)

    def seeOfferPage(self):

        row = self.searchTableWidget.currentRow()
        if row < 0:
            self.show_message("Ошибка", "Не выбрана строка")
            return

        id_index = self.searchTableWidget.columnCount() - 1
        id_item = self.searchTableWidget.item(row, id_index)
        if id_item is None:
            self.show_message("Ошибка", "Не удалось получить ID объявления")
            return
        try:
            offer_id = int(id_item.text())
        except ValueError:
            self.show_message("Ошибка", "Некорректный ID")
            return

        data = self.cursor.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone()
        if data is None:
            self.show_message("Ошибка", "Объявление не найдено")
            return

        phone_res = self.cursor.execute("SELECT phone FROM accounts WHERE userid = ?", (data[1],)).fetchone()
        self.offerphone = phone_res if phone_res else ("",)

        price = data[7] if data[7] is not None else 0
        formatted_price = self.format_price(price)

        try:
            if data[15]:
                response = data[15]
                pixmap = QPixmap(response)
                self.offerpage.imageExt.setPixmap(pixmap)
            else:
                self.offerpage.imageExt.clear()
        except Exception as e:
            print("Image ext load error:", e)
            self.offerpage.imageExt.clear()

        try:
            if data[16]:
                response = data[16]
                pixmap = QPixmap(response)
                self.offerpage.imageInt.setPixmap(pixmap)
            else:
                self.offerpage.imageInt.clear()
        except Exception as e:
            print("Image int load error:", e)
            self.offerpage.imageInt.clear()

        self.offerpage.nameLabel.setText(f"{data[5]}, {data[4]}, {data[6]}")
        self.offerpage.modelLabel.setText(f"Модель: {data[4]}")
        self.offerpage.manuLabel.setText(f"Марка: {data[5]}")
        self.offerpage.yearLabel.setText(f"Год выпуска: {data[6]}")
        self.offerpage.priceLabel.setText(f"{formatted_price}  руб")
        self.offerpage.colorLabel.setText(f"Цвет: {data[8]}")
        self.offerpage.mileageLabel.setText(f"Пробег: {data[9]}")
        self.offerpage.ownersLabel.setText(f"Кол-во владельцев: {data[10]}")
        self.offerpage.kppLabel.setText(f"Тип КПП: {data[11]}")
        self.offerpage.privodLabel.setText(f"Привод: {data[12]}")
        self.offerpage.stateLabel.setText(f"Состояние: {data[13]}")
        self.offerpage.engineLabel.setText(f"Тип двигателя: {data[14]}")
        self.offerpage.dateLabel.setText(f"Дата создания объявления: {data[3]}")
        self.offerpage.textEdit.setHtml(f"{data[2]}")

        self.offerpage.showMaximized()
        self.current_offer_id = offer_id

    def seephone(self):

        self.msg_box = QMessageBox()
        self.msg_box.setWindowTitle("Контактный номер телефона:")
        self.msg_box.setText(f"{self.offerphone[0]}")
        self.msg_box.exec()

    def load_my_offers(self):

        headers = ("ID", "Дата", "Марка", "Модель", "Год", "Цена", "Цвет", "Пробег", "Владельцы", "Действия")

        try:
            self.myTableWidget.clearContents()
            self.myTableWidget.clearSpans()
        except Exception:
            pass

        self.myTableWidget.setColumnCount(len(headers))
        self.myTableWidget.setHorizontalHeaderLabels(headers)

        if not self.isloggedin:
            self.myTableWidget.setRowCount(1)
            for r in range(self.myTableWidget.rowCount()):
                for c in range(self.myTableWidget.columnCount()):
                    w = self.myTableWidget.cellWidget(r, c)
                    if w is not None:
                        w.deleteLater()
                        self.myTableWidget.removeCellWidget(r, c)

            lbl = QLabel("Войдите, чтобы увидеть ваши объявления")
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.myTableWidget.setSpan(0, 0, 1, len(headers))
            self.myTableWidget.setCellWidget(0, 0, lbl)
            return

        if self.isadmin:
            rows = self.cursor.execute("SELECT * FROM offers ORDER BY date DESC").fetchall()
        else:
            rows = self.cursor.execute("SELECT * FROM offers WHERE userid = ? ORDER BY date DESC",
                                       (self.userid,)).fetchall()

        for r in range(self.myTableWidget.rowCount()):
            for c in range(self.myTableWidget.columnCount()):
                w = self.myTableWidget.cellWidget(r, c)
                if w is not None:
                    w.deleteLater()
                    self.myTableWidget.removeCellWidget(r, c)

        self.myTableWidget.setRowCount(len(rows))

        for r, row in enumerate(rows):
            offer_id = row[0]
            date = row[3]
            manufacturer = row[5]
            model = row[4]
            year = row[6]
            price = self.format_price(row[7])
            color = row[8]
            mileage = row[9]
            owners = row[10]

            cells = [
                str(offer_id), date, manufacturer, model, str(year), price, str(color), str(mileage), str(owners)
            ]
            for c, cell_val in enumerate(cells):
                item = QTableWidgetItem(cell_val)
                self.myTableWidget.setItem(r, c, item)

            btn_widget = QWidget()
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)

            edit_btn = QPushButton("Редактировать")
            edit_btn.setProperty("offer_id", offer_id)
            edit_btn.clicked.connect(self.on_edit_clicked)
            layout.addWidget(edit_btn)

            delete_btn = QPushButton("Удалить")
            delete_btn.setProperty("offer_id", offer_id)
            delete_btn.clicked.connect(self.on_delete_clicked)
            # Права: удалить может админ или владелец объявления
            try:
                offer_owner_id = int(row[1])
            except Exception:
                offer_owner_id = None
            can_delete = self.isadmin or (
                    offer_owner_id is not None and self.isloggedin and int(self.userid) == offer_owner_id)
            delete_btn.setEnabled(can_delete)
            layout.addWidget(delete_btn)
            btn_widget.setLayout(layout)
            self.myTableWidget.setCellWidget(r, len(headers) - 1, btn_widget)

        header = self.myTableWidget.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False)

    def on_edit_clicked(self):

        btn = self.sender()
        offer_id = btn.property("offer_id")
        if offer_id is None:
            self.show_message("Ошибка", "Не удалось определить объявление для редактирования")
            return
        offer_row = self.cursor.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone()
        if offer_row is None:
            self.show_message("Ошибка", "Объявление не найдено")
            return

        if not self.isadmin and int(offer_row[1]) != int(self.userid):
            self.show_message("Ошибка прав", "Вы можете редактировать только свои объявления")
            return

        self.editing_offer_id = offer_id
        self._fill_form_from_offer(offer_row)
        self.form.show()

    def on_delete_clicked(self):
        """Слот для нажатия кнопки Удалить в myTableWidget."""
        btn = self.sender()
        offer_id = btn.property("offer_id")
        if offer_id is None:
            self.show_message("Ошибка", "Не удалось определить объявление для удаления")
            return

        # получаем строку объявления, чтобы знать владельца
        offer_row = self.cursor.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone()
        if offer_row is None:
            self.show_message("Ошибка", "Объявление не найдено")
            return

        offer_owner_id = offer_row[1]

        # Проверка прав: админ может удалять любое, пользователь — только своё
        if not self.isadmin:
            if not self.isloggedin or int(self.userid) != int(offer_owner_id):
                self.show_message("Ошибка прав", "Удалять это объявление можно только администратору или его владельцу")
                return

        # подтверждение удаления
        if not self.confirm_dialog("Подтвердите удаление", "Вы действительно хотите удалить объявление?"):
            return

        # выполняем удаление
        try:
            self.cursor.execute("DELETE FROM offers WHERE id = ?", (offer_id,))
            self.con.commit()
        except Exception as e:
            self.show_message("Ошибка", f"Не удалось удалить объявление: {e}")
            return

        self.show_message("Удалено", "Объявление успешно удалено")
        # обновляем таблицы
        self.load_my_offers()
        self.search()

    def show_message(self, title, text):

        QMessageBox.information(self, title, text)

    def confirm_dialog(self, title, text):

        reply = QMessageBox.question(self, title, text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        return reply == QMessageBox.StandardButton.Yes

    def format_price(self, price):

        try:
            val = float(price)
            s = f"{val:,.2f}"
            s = s.replace(",", " ")
            return s
        except Exception:
            return str(price)

    def closeEvent(self, event):

        try:
            self.con.close()
        except Exception:
            pass
        event.accept()


class FormWindow(QWidget, Ui_Form):
    def __init__(self):
        super().__init__()
        self.setupUi(self)


class offerPage(QWidget, Ui_OfferPage):
    def __init__(self):
        super().__init__()
        self.setupUi(self)


def except_hook(cls, exception, traceback):
    sys.__excepthook__(cls, exception, traceback)


def main():
    sys.excepthook = except_hook
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
