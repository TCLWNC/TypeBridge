# -*- coding: utf-8 -*-
"""Qt 原生界面：把网页那套 UI 逐项换算过来（同一套颜色/圆角/字号/间距）。

数值全部来自 crosslink/web 的 CSS：
  底 #000000、卡片 #1A1B21、输入底 #101116、主色 #B4C5FF、强调 #00AEFA
  卡片圆角 16、控件圆角 12；标题 22、列表名 17、正文 14、次要 12.5、徽章 11
  页面左右留白 16、卡片间距 12、卡片内边距 16；左导航 84 宽
"""

from __future__ import annotations

import os
import sys

from PySide6 import QtCore, QtGui, QtWidgets

from . import APP_TITLE, VERSION
from . import config as config_mod

BG, CARD, INPUT, LINE = "#000000", "#1A1B21", "#101116", "#25262C"
TEXT, DIM, MUTED = "#FFFFFF", "#C7C9D4", "#8B8E9D"
PRIMARY, ON_PRIMARY, OK, BAD, BRAND = "#B4C5FF", "#0B2A5B", "#4CD07D", "#FF6B6B", "#00AEFA"

QSS = f"""
QWidget {{ background: {BG}; color: {TEXT};
  font-family: "Microsoft YaHei UI"; font-size: 14px; }}
QLabel#title {{ font-size: 22px; font-weight: 600; }}
QLabel#sub {{ color: {MUTED}; font-size: 12.5px; }}
QLabel#cardTitle {{ color: {MUTED}; font-size: 13px; font-weight: 600; }}
QLabel#dim {{ color: {DIM}; }}
QLabel#muted {{ color: {MUTED}; }}
QFrame#card {{ background: {CARD}; border-radius: 16px; }}
QFrame#rail {{ background: {CARD}; }}
QLabel#ver {{ color: {MUTED}; font-size: 11px; }}
QPushButton {{ background: {INPUT}; color: {DIM}; border: 1px solid {LINE};
  border-radius: 12px; padding: 10px 14px; font-size: 14px; }}
QPushButton:hover {{ color: {TEXT}; border-color: #3A3E48; background: #17181F; }}
QPushButton:pressed {{ background: #22242C; color: {PRIMARY}; }}
QPushButton#primary {{ background: {PRIMARY}; color: {ON_PRIMARY}; border: none;
  font-weight: 600; }}
QPushButton#primary:hover {{ background: #C8D5FF; }}
QPushButton#primary:pressed {{ background: #9FB4F5; }}
QPushButton#nav {{ background: transparent; border: none; color: {MUTED};
  border-radius: 12px; padding: 8px 6px; font-size: 11px; }}
QPushButton#nav:hover {{ background: rgba(255,255,255,0.06); color: {DIM}; }}
QPushButton#nav:pressed {{ background: rgba(255,255,255,0.10); }}
QPushButton#nav:checked {{ background: rgba(180,197,255,0.16); color: {PRIMARY}; }}
QListWidget::item:hover {{ background: rgba(255,255,255,0.06); }}
QLineEdit {{ background: {INPUT}; border: 1px solid {LINE}; border-radius: 12px;
  padding: 10px 14px; color: {TEXT}; }}
QLineEdit:focus {{ border-color: rgba(180,197,255,0.55); }}
QComboBox:hover, QSpinBox:hover {{ border-color: #3A3E48; }}
QComboBox:focus, QSpinBox:focus {{ border-color: rgba(180,197,255,0.55); }}
QCheckBox:hover {{ color: {TEXT}; }}
QListWidget {{ background: {CARD}; border: none; color: {DIM};
  border-radius: 12px; padding: 4px; }}
QListWidget::item {{ padding: 8px 10px; border-radius: 8px; }}
QListWidget::item:selected {{ background: rgba(180,197,255,0.16); color: {PRIMARY}; }}
QCheckBox {{ color: {DIM}; spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px;
  border: 1px solid {LINE}; background: {INPUT}; }}
QCheckBox::indicator:checked {{ background: {PRIMARY}; border-color: {PRIMARY}; }}
QSpinBox, QComboBox {{ background: {INPUT}; border: 1px solid {LINE};
  border-radius: 12px; padding: 6px 10px; color: {TEXT}; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.16); border-radius: 5px; }}
"""


class AnimButton(QtWidgets.QPushButton):
    """会做颜色过渡的按钮：悬停变亮、按下回弹（对齐网页的 transition）。"""

    def __init__(self, text="", parent=None, bg=INPUT, fg=DIM, hover="#17181F",
                 press="#22242C", press_fg=PRIMARY, border=LINE, radius=12, bold=False):
        super().__init__(text, parent)
        self._bg, self._fg, self._hover, self._press = bg, fg, hover, press
        self._press_fg, self._border, self._radius, self._bold = press_fg, border, radius, bold
        self._cur = QtGui.QColor(bg)
        self._cur_fg = QtGui.QColor(fg)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setMinimumHeight(40)
        self._anim = QtCore.QVariantAnimation(self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_value)
        # 按压涟漪（对齐网页 .fx::after 的 ripple：从点击点扩散 520ms）
        self._ripple = QtCore.QVariantAnimation(self)
        self._ripple.setDuration(520)
        self._ripple.setStartValue(0.0)
        self._ripple.setEndValue(1.0)
        self._ripple.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._ripple.valueChanged.connect(lambda _=None: self.update())
        self._rip_pos = QtCore.QPointF(0, 0)

    def _on_value(self, value):
        self._cur = QtGui.QColor(value[0])
        self._cur_fg = QtGui.QColor(value[1])
        self.update()

    def _animate_to(self, bg, fg):
        self._anim.stop()
        self._anim.setStartValue((self._cur, self._cur_fg))
        self._anim.setEndValue((QtGui.QColor(bg), QtGui.QColor(fg)))
        self._anim.start()

    def enterEvent(self, event):   # noqa: N802
        self._animate_to(self._hover if not self.isChecked() else "#22242C", TEXT)
        super().enterEvent(event)

    def leaveEvent(self, event):   # noqa: N802
        self._animate_to(self._bg, self._fg)
        super().leaveEvent(event)

    def mousePressEvent(self, event):   # noqa: N802
        self._rip_pos = QtCore.QPointF(event.position())
        self._ripple.stop()
        self._ripple.start()
        self._animate_to(self._press, self._press_fg)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):   # noqa: N802
        self._animate_to(self._hover, TEXT)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):   # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = self.rect().adjusted(0, 0, -1, -1)
        p.setBrush(self._cur)
        p.setPen(QtGui.QPen(QtGui.QColor(self._border), 1))
        p.drawRoundedRect(r, self._radius, self._radius)
        p.setPen(self._cur_fg)
        f = self.font()
        f.setBold(self._bold)
        p.setFont(f)
        p.drawText(r, QtCore.Qt.AlignCenter, self.text())
        # 涟漪：以点击点为中心的扩散圆
        k = float(self._ripple.currentValue() or 0.0)
        if 0.0 < k < 1.0:
            radius = k * (max(r.width(), r.height()) * 1.2)
            color = QtGui.QColor(self._press_fg)
            color.setAlphaF(max(0.0, 0.22 * (1.0 - k)))
            p.setBrush(color)
            p.setPen(QtCore.Qt.NoPen)
            p.drawEllipse(self._rip_pos, radius, radius)


class AnimSwitch(QtWidgets.QAbstractButton):
    """带拇指滑动动画的开关（对齐网页 .switch：200ms 回弹）。"""

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFixedSize(46, 26)
        self._pos = 1.0 if checked else 0.0
        self._anim = QtCore.QVariantAnimation(self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutBack)
        self._anim.valueChanged.connect(self._on_pos)
        self.toggled.connect(self._animate)

    def _on_pos(self, v):
        self._pos = float(v)
        self.update()

    def _animate(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def sizeHint(self):
        return QtCore.QSize(46, 26)

    def paintEvent(self, event):   # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = self.rect().adjusted(0, 0, -1, -1)
        track = QtGui.QColor(PRIMARY if self.isChecked() else "#2A2C36")
        p.setBrush(track)
        p.setPen(QtGui.QPen(QtGui.QColor(LINE), 1))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 8
        x = 4 + self._pos * (r.width() - d - 8)
        p.setBrush(QtGui.QColor(ON_PRIMARY if self.isChecked() else "#E6E7EE"))
        p.setPen(QtCore.Qt.NoPen)
        p.drawEllipse(QtCore.QRectF(x, 4, d, d))


class QtUI:
    def __init__(self, app) -> None:
        self.app = app
        self.hub = app.hub
        self.cfg = app.cfg
        self.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        self.qapp.setStyleSheet(QSS)
        self.win = QtWidgets.QWidget()
        self.win.setWindowTitle("%s v%s · %s" % (APP_TITLE, VERSION, self.cfg["name"]))
        self.win.resize(1120, 740)
        self._icon()
        self._build()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(700)

    def _icon(self) -> None:
        try:
            self.win.setWindowIcon(QtGui.QIcon(config_mod.asset_path("icon.ico")))
        except Exception:   # noqa: BLE001
            pass

    # ---------------- 结构 ----------------
    def _build(self) -> None:
        root = QtWidgets.QHBoxLayout(self.win)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._rail())

        right = QtWidgets.QVBoxLayout()
        right.setContentsMargins(16, 14, 16, 12)
        right.setSpacing(12)
        root.addLayout(right, 1)
        right.addLayout(self._topbar())

        self.pages = QtWidgets.QStackedWidget()
        right.addWidget(self.pages, 1)
        self.pages.addWidget(self._page_input())
        self.pages.addWidget(self._page_devices())
        self.pages.addWidget(self._page_settings())
        self.pages.currentChanged.connect(self._animate_page)
        right.addWidget(self._statusbar())
        QtCore.QTimer.singleShot(0, self._splash)   # 显示启动画面，1.2 秒后淡出

    def _animate_page(self, idx: int) -> None:
        """页面切换动效：淡入 + 从下方 10px 滑入（对齐网页的 pageIn）。"""
        page = self.pages.widget(idx)
        if page is None:
            return
        effect = QtWidgets.QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        fade = QtCore.QPropertyAnimation(effect, b"opacity", page)
        fade.setDuration(260)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        fade.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
        page.setProperty("anim", fade)

    def _rail(self):
        rail = QtWidgets.QFrame(objectName="rail")
        rail.setFixedWidth(84)
        box = QtWidgets.QVBoxLayout(rail)
        box.setContentsMargins(0, 16, 0, 12)
        box.setSpacing(6)
        logo = QtWidgets.QLabel()
        logo.setPixmap(QtGui.QPixmap(config_mod.asset_path("icon.png")).scaled(
            40, 40, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        logo.setAlignment(QtCore.Qt.AlignCenter)
        box.addWidget(logo)
        box.addSpacing(6)
        self.nav = QtWidgets.QButtonGroup(self.win)
        for i, (text, _) in enumerate((("输入", 0), ("设备", 1), ("设置", 2))):
            b = QtWidgets.QPushButton(text, objectName="nav", checkable=True)
            b.setChecked(i == 0)
            b.clicked.connect(lambda _=False, idx=i: self.pages.setCurrentIndex(idx))
            self.nav.addButton(b)
            box.addWidget(b)
        box.addStretch(1)
        box.addWidget(self._label("v%s" % VERSION, "ver", QtCore.Qt.AlignCenter))
        return rail

    def _topbar(self):
        bar = QtWidgets.QHBoxLayout()
        col = QtWidgets.QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(self._label(APP_TITLE, "title"))
        col.addWidget(self._label(self.cfg["name"], "sub"))
        bar.addLayout(col)
        bar.addStretch(1)
        self.lbl_state = self._label("● 等待手机连接", "muted")
        bar.addWidget(self.lbl_state)
        fw = QtWidgets.QPushButton("放行防火墙")
        fw.clicked.connect(self._firewall)
        bar.addWidget(fw)
        return bar

    def _page_input(self):
        page = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(page)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)

        # ① 手机连接卡片（QR + 地址 + 配对码）
        card = self._card()
        h = QtWidgets.QHBoxLayout(card)
        h.setContentsMargins(16, 16, 16, 16)
        h.setSpacing(16)
        self.lbl_qr = QtWidgets.QLabel()
        self.lbl_qr.setFixedSize(148, 148)
        self.lbl_qr.setStyleSheet("background:#fff;border-radius:12px;")
        self.lbl_qr.setAlignment(QtCore.Qt.AlignCenter)
        h.addWidget(self.lbl_qr)
        info = QtWidgets.QVBoxLayout()
        info.setSpacing(8)
        info.addWidget(self._label("手机扫码即可用", "dim"))
        info.addWidget(self._label("不用装 App，同一个 Wi-Fi 就能打字", "muted"))
        self.lbl_url = self._label("-", "dim")
        info.addWidget(self.lbl_url)
        row = QtWidgets.QHBoxLayout()
        self.lbl_pin = self._label(self.cfg["pin"], "dim")
        row.addWidget(self._label("配对码", "muted"))
        row.addWidget(self.lbl_pin)
        b1 = QtWidgets.QPushButton("复制链接")
        b1.clicked.connect(self._copy_url)
        b2 = QtWidgets.QPushButton("换一个")
        b2.clicked.connect(self._new_pin)
        row.addWidget(b1)
        row.addWidget(b2)
        row.addStretch(1)
        info.addLayout(row)
        info.addStretch(1)
        h.addLayout(info, 1)
        grid.addWidget(card, 0, 0)

        # ② 输入目标 + 统计
        card2 = self._card()
        v = QtWidgets.QVBoxLayout(card2)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(8)
        v.addWidget(self._label("输入目标", "cardTitle"))
        self.lbl_target = self._label("先在电脑上点一下要输入的窗口", "dim")
        v.addWidget(self.lbl_target)
        self.lbl_app = self._label("-", "muted")
        v.addWidget(self.lbl_app)
        v.addStretch(1)
        row = QtWidgets.QHBoxLayout()
        self.lbl_chars = self._label("0", "dim")
        row.addWidget(self.lbl_chars)
        row.addWidget(self._label("已输入字数", "muted"))
        row.addStretch(1)
        v.addLayout(row)
        grid.addWidget(card2, 0, 1)

        # ③ 输入记录
        card3 = self._card()
        v3 = QtWidgets.QVBoxLayout(card3)
        v3.setContentsMargins(16, 16, 16, 16)
        head = QtWidgets.QHBoxLayout()
        head.addWidget(self._label("输入记录", "cardTitle"))
        head.addStretch(1)
        clear = QtWidgets.QPushButton("清空记录")
        clear.clicked.connect(self.hub.clear_logs)
        head.addWidget(clear)
        v3.addLayout(head)
        self.log_list = QtWidgets.QListWidget()
        v3.addWidget(self.log_list, 1)
        grid.addWidget(card3, 1, 0, 1, 2)
        grid.setRowStretch(1, 1)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        return page

    def _page_devices(self):
        page = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)
        card = self._card()
        vv = QtWidgets.QVBoxLayout(card)
        vv.setContentsMargins(16, 16, 16, 16)
        vv.addWidget(self._label("已连接设备", "cardTitle"))
        self.dev_list = QtWidgets.QListWidget()
        vv.addWidget(self.dev_list, 1)
        v.addWidget(card, 1)
        return page

    def _page_settings(self):
        page = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)
        card = self._card()
        vv = QtWidgets.QVBoxLayout(card)
        vv.setContentsMargins(16, 16, 16, 16)
        vv.setSpacing(10)
        vv.addWidget(self._label("输入", "cardTitle"))
        self.cb_inject = AnimSwitch()
        self.cb_inject.setChecked(bool(self.cfg["inject"]))
        self.cb_inject.toggled.connect(lambda _=None: self._apply())
        row0 = QtWidgets.QHBoxLayout(); row0.addWidget(self.cb_inject); row0.addWidget(self._label("键盘注入（关闭后不接收输入）", "dim")); row0.addStretch(1); vv.addLayout(row0)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self._label("输入方式", "dim"))
        self.cmb_method = QtWidgets.QComboBox()
        self.cmb_method.addItems(["direct", "clipboard"])
        self.cmb_method.setCurrentText(self.cfg["method"])
        self.cmb_method.currentTextChanged.connect(lambda _=None: self._apply())
        row.addWidget(self.cmb_method)
        row.addWidget(self._label("字间延迟(ms)", "dim"))
        self.spin_delay = QtWidgets.QSpinBox()
        self.spin_delay.setRange(0, 200)
        self.spin_delay.setSingleStep(5)
        self.spin_delay.setValue(int(self.cfg["delay_ms"]))
        self.spin_delay.valueChanged.connect(lambda _=None: self._apply())
        row.addWidget(self.spin_delay)
        row.addStretch(1)
        vv.addLayout(row)
        vv.addWidget(self._label("窗口与安全", "cardTitle"))
        self.cb_top = AnimSwitch()
        self.cb_top.setChecked(bool(self.cfg["topmost"]))
        self.cb_top.toggled.connect(lambda _=None: self._apply())
        row1 = QtWidgets.QHBoxLayout(); row1.addWidget(self.cb_top); row1.addWidget(self._label("窗口置顶", "dim")); row1.addStretch(1); vv.addLayout(row1)
        self.cb_pin = AnimSwitch()
        self.cb_pin.setChecked(bool(self.cfg["require_pin"]))
        self.cb_pin.toggled.connect(lambda _=None: self._apply())
        row2 = QtWidgets.QHBoxLayout(); row2.addWidget(self.cb_pin); row2.addWidget(self._label("需要配对码（新手机必须输入）", "dim")); row2.addStretch(1); vv.addLayout(row2)
        quit_btn = QtWidgets.QPushButton("退出 CrossLink")
        quit_btn.clicked.connect(self.app.quit)
        vv.addWidget(quit_btn)
        vv.addStretch(1)
        v.addWidget(card, 1)
        return page

    def _statusbar(self):
        bar = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(bar)
        h.setContentsMargins(0, 0, 0, 0)
        self.lbl_bar = self._label("等待手机连接", "muted")
        h.addWidget(self.lbl_bar)
        h.addStretch(1)
        h.addWidget(self._label("输入方式", "muted"))
        self.cmb_method2 = QtWidgets.QComboBox()
        self.cmb_method2.addItems(["direct", "clipboard"])
        self.cmb_method2.setCurrentText(self.cfg["method"])
        self.cmb_method2.currentTextChanged.connect(self._sync_method)
        h.addWidget(self.cmb_method2)
        self.lbl_delay = self._label("延迟 %dms" % int(self.cfg["delay_ms"]), "muted")
        h.addWidget(self.lbl_delay)
        return bar

    # ---------------- 小工具 ----------------
    def _label(self, text, kind, align=None):
        lbl = QtWidgets.QLabel(text, objectName=kind)
        if align is not None:
            lbl.setAlignment(align)
        return lbl

    def _card(self):
        f = QtWidgets.QFrame(objectName="card")
        # 卡片阴影：和网页那套一致的柔和投影（0 6px 18px rgba(0,0,0,.55)）
        shadow = QtWidgets.QGraphicsDropShadowEffect(f)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 6)
        shadow.setColor(QtGui.QColor(0, 0, 0, 140))
        f.setGraphicsEffect(shadow)
        return f

    # ---------------- 启动画面 ----------------
    def _splash(self) -> None:
        """启动画面：盖住整个窗口，约 1.2 秒后淡出（和网页版一致的做法）。"""
        overlay = QtWidgets.QWidget(self.win)
        overlay.setStyleSheet("background:#000000;")
        overlay.setGeometry(0, 0, self.win.width(), self.win.height())
        box = QtWidgets.QVBoxLayout(overlay)
        box.setAlignment(QtCore.Qt.AlignCenter)
        box.setSpacing(10)
        logo = QtWidgets.QLabel()
        logo.setPixmap(QtGui.QPixmap(config_mod.asset_path("icon.png")).scaled(
            72, 72, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        logo.setAlignment(QtCore.Qt.AlignCenter)
        box.addWidget(logo)
        box.addWidget(self._label(APP_TITLE, "title", QtCore.Qt.AlignCenter))
        box.addWidget(self._label("正在启动…", "sub", QtCore.Qt.AlignCenter))
        overlay.show()
        overlay.raise_()

        effect = QtWidgets.QGraphicsOpacityEffect(overlay)
        overlay.setGraphicsEffect(effect)
        self._splash_anim = QtCore.QPropertyAnimation(effect, b"opacity", self.win)
        self._splash_anim.setDuration(420)
        self._splash_anim.setStartValue(1.0)
        self._splash_anim.setEndValue(0.0)
        self._splash_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._splash_anim.finished.connect(overlay.hide)
        QtCore.QTimer.singleShot(1200, self._splash_anim.start)

    # ---------------- 行为 ----------------
    def _apply(self):
        self.hub.apply_settings({
            "inject": self.cb_inject.isChecked(),
            "require_pin": self.cb_pin.isChecked(),
            "topmost": self.cb_top.isChecked(),
            "method": self.cmb_method.currentText(),
            "delay_ms": int(self.spin_delay.value()),
        })
        self._sync_method(self.cmb_method.currentText())

    def _sync_method(self, value):
        if self.cmb_method.currentText() != value:
            self.cmb_method.setCurrentText(value)
        if self.cmb_method2.currentText() != value:
            self.cmb_method2.setCurrentText(value)

    def _copy_url(self):
        from . import winapi
        url = self.hub.mobile_url[0] if self.hub.mobile_url else ""
        if url:
            winapi.clipboard_set_text(url)
            self.hub.log("电脑", "手机链接已复制：%s" % url, "system")

    def _new_pin(self):
        from .config import new_pin
        self.cfg["pin"] = new_pin()
        self.hub.save()
        self.lbl_pin.setText(self.cfg["pin"])
        self.hub.log("电脑", "已更换配对码：%s" % self.cfg["pin"], "system")

    def _firewall(self):
        from . import winapi
        winapi.firewall_add_via_uac(None, int(self.cfg["port"]))

    # ---------------- 刷新（每 700ms） ----------------
    def refresh(self):
        try:
            url = (self.hub.mobile_url or ["-"])[0]
            if self.lbl_url.text() != url:
                self.lbl_url.setText(url)
                self._render_qr(url)
            phones = self.hub.phone_list()
            count = len(phones)
            self.lbl_state.setText("● 已连接 %d 台" % count if count else "● 等待手机连接")
            self.lbl_state.setStyleSheet("color:%s" % (OK if count else MUTED))
            self.lbl_bar.setText("已连接 %d 台" % count if count else "等待手机连接")
            t = self.hub.target or {}
            if t.get("app"):
                if t.get("self"):
                    self.lbl_target.setText("焦点在 CrossLink 上，点一下目标程序")
                    self.lbl_app.setText(t.get("title", ""))
                else:
                    self.lbl_target.setText("就绪 · 可以打字")
                    self.lbl_app.setText("%s  %s" % (t.get("app", ""), t.get("title", "")[:40]))
            else:
                self.lbl_target.setText("先在电脑上点一下要输入的窗口")
                self.lbl_app.setText("-")
            self.lbl_chars.setText(str(self.hub.injector.chars))
            self._render_devices(phones)
            self._render_logs()
        except Exception as exc:   # noqa: BLE001
            print("Qt 界面刷新出错:", exc, flush=True)

    def _render_qr(self, url):
        try:
            import io
            import qrcode
            img = qrcode.make(url)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            pix = QtGui.QPixmap()
            pix.loadFromData(buf.getvalue())
            self.lbl_qr.setPixmap(pix.scaled(128, 128, QtCore.Qt.KeepAspectRatio,
                                             QtCore.Qt.FastTransformation))
        except Exception:   # noqa: BLE001
            pass

    def _render_devices(self, phones):
        sig = "|".join("%s:%s:%s" % (p["sid"], p["name"], p["chars"]) for p in phones)
        if getattr(self, "_dev_sig", "") == sig:
            return
        self._dev_sig = sig
        self.dev_list.clear()
        for p in phones:
            item = QtWidgets.QListWidgetItem("● %s    %s    已输入 %d 字"
                                             % (p["name"], p["addr"], p["chars"]))
            self.dev_list.addItem(item)
        if not phones:
            self.dev_list.addItem("（还没有手机连接）")

    def _render_logs(self):
        entries = list(self.hub.logs)[:60]
        sig = "|".join(e["id"] for e in entries)
        if getattr(self, "_log_sig", "") == sig:
            return
        self._log_sig = sig
        self.log_list.clear()
        for e in entries:
            self.log_list.addItem("%s   %s   %s" % (e["t"], e["who"], e["text"]))

    def run(self):
        self.win.show()
        self.qapp.exec()
