import os
import sys
import platform
import threading
import urllib.parse
import requests
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QLineEdit, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QPixmap
from app_paths import ASSETS_DIR
from version import VERSION


QQ_GROUP = "1135775083"
DEV_EMAIL = "linyuwei199911@gmail.com"
FORMSUBMIT_AJAX_URL = f"https://formsubmit.co/ajax/{DEV_EMAIL}"
GITHUB_ISSUES_URL = "https://github.com/LYW199911/DesktopGeminiGirl/issues/new"


class FeedbackDialog(QDialog):
    """意见反馈与交流中心弹窗：支持免梯子一键直达作者邮箱提交，以及 QQ 群/GitHub Issue。"""

    _submit_finished = pyqtSignal(bool, str)

    def __init__(self, parent=None, is_dynamic: bool = False):
        super().__init__(parent)
        self.is_dynamic = is_dynamic
        self._submit_finished.connect(self._on_submit_finished)
        self.setWindowTitle("哈Gemi · 意见反馈与交流中心")
        self.setMinimumSize(660, 600)
        self.resize(690, 640)
        self.setStyleSheet("""
            QDialog {
                background-color: #161224;
                color: #f4f1fa;
                font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
            }
            QFrame#Card {
                background-color: #1f1a30;
                border: 1px solid #352c52;
                border-radius: 10px;
            }
            QLabel {
                color: #e6e1f2;
                font-size: 13px;
            }
            QLabel#SectionTitle {
                color: #ff6ea1;
                font-size: 14px;
                font-weight: bold;
            }
            QLabel#HighlightText {
                color: #8be9fd;
                font-size: 14px;
                font-weight: bold;
            }
            QLineEdit, QComboBox, QTextEdit {
                background-color: #141020;
                color: #f8f9fa;
                border: 1px solid #3b3159;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 1px solid #ff4e88;
            }
            QPushButton {
                background-color: #ff4e88;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 7px 14px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff699b;
            }
            QPushButton:disabled {
                background-color: #5c3a4c;
                color: #b8a8b2;
            }
            QPushButton#SecondaryBtn {
                background-color: #2b2442;
                color: #e4dff0;
                border: 1px solid #443966;
                font-weight: normal;
            }
            QPushButton#SecondaryBtn:hover {
                background-color: #393057;
                border: 1px solid #ff4e88;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        edition = "动态版" if self.is_dynamic else "经典静态版"
        title = QLabel(f"💬 意见反馈与交流社区（当前：{edition} {VERSION}）")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)

        sub = QLabel("无需登录 GitHub，填写下方内容即可一键直达开发者邮箱，或加入 QQ 群交流分享立绘/语音包。")
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #a9a0c0; font-size: 12px;")
        layout.addWidget(sub)

        # Card 1: Direct Contact (QQ Group + Gmail + QR Code)
        contact_card = QFrame()
        contact_card.setObjectName("Card")
        cc_outer = QHBoxLayout(contact_card)
        cc_outer.setContentsMargins(14, 12, 14, 12)
        cc_outer.setSpacing(14)

        cc_l = QVBoxLayout()
        cc_l.setSpacing(10)

        lbl_c_title = QLabel("交流群与作者直连")
        lbl_c_title.setObjectName("SectionTitle")
        cc_l.addWidget(lbl_c_title)

        qq_row = QHBoxLayout()
        qq_row.addWidget(QLabel("交流反馈 QQ 群："))
        lbl_qq = QLabel(QQ_GROUP)
        lbl_qq.setObjectName("HighlightText")
        lbl_qq.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        qq_row.addWidget(lbl_qq)
        qq_row.addStretch()
        self.btn_copy_qq = QPushButton("复制群号")
        self.btn_copy_qq.setObjectName("SecondaryBtn")
        self.btn_copy_qq.setFixedWidth(86)
        self.btn_copy_qq.clicked.connect(lambda: self._copy_with_tip(QQ_GROUP, self.btn_copy_qq, "复制群号"))
        qq_row.addWidget(self.btn_copy_qq)
        cc_l.addLayout(qq_row)

        mail_row = QHBoxLayout()
        mail_row.addWidget(QLabel("作者 Gmail："))
        lbl_mail = QLabel(DEV_EMAIL)
        lbl_mail.setObjectName("HighlightText")
        lbl_mail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        mail_row.addWidget(lbl_mail)
        mail_row.addStretch()
        self.btn_copy_mail = QPushButton("复制邮箱")
        self.btn_copy_mail.setObjectName("SecondaryBtn")
        self.btn_copy_mail.setFixedWidth(86)
        self.btn_copy_mail.clicked.connect(lambda: self._copy_with_tip(DEV_EMAIL, self.btn_copy_mail, "复制邮箱"))
        mail_row.addWidget(self.btn_copy_mail)

        btn_open_mail = QPushButton("发邮件")
        btn_open_mail.setObjectName("SecondaryBtn")
        btn_open_mail.setFixedWidth(68)
        btn_open_mail.clicked.connect(self._open_mailto)
        mail_row.addWidget(btn_open_mail)
        cc_l.addLayout(mail_row)
        cc_l.addStretch()
        cc_outer.addLayout(cc_l, 1)

        qr_path = os.path.join(ASSETS_DIR, "qq_group_qr.png")
        if os.path.exists(qr_path):
            qr_box = QVBoxLayout()
            qr_box.setSpacing(4)
            qr_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_qr = QLabel()
            pm = QPixmap(qr_path).scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_qr.setPixmap(pm)
            lbl_qr.setFixedSize(102, 102)
            lbl_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_qr.setStyleSheet("background-color: #ffffff; border-radius: 8px; padding: 3px;")
            lbl_qr.setToolTip("打开手机 QQ 扫一扫加入交流反馈群 1135775083")
            qr_box.addWidget(lbl_qr)
            lbl_qr_cap = QLabel("QQ 扫码加群")
            lbl_qr_cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_qr_cap.setStyleSheet("color: #a9a0c0; font-size: 11px;")
            qr_box.addWidget(lbl_qr_cap)
            cc_outer.addLayout(qr_box)

        layout.addWidget(contact_card)

        # Card 2: In-app One-Click Feedback Form
        form_card = QFrame()
        form_card.setObjectName("Card")
        fc_l = QVBoxLayout(form_card)
        fc_l.setContentsMargins(14, 12, 14, 12)
        fc_l.setSpacing(8)

        lbl_f_title = QLabel("一键直达反馈（免翻墙 / 免 GitHub 账号）")
        lbl_f_title.setObjectName("SectionTitle")
        fc_l.addWidget(lbl_f_title)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("反馈类型:"))
        self.combo_type = QComboBox()
        self.combo_type.addItems(["Bug 反馈", "功能建议", "立绘 / 语音包交流", "使用咨询"])
        type_row.addWidget(self.combo_type, 1)
        fc_l.addLayout(type_row)

        self.input_title = QLineEdit()
        self.input_title.setPlaceholderText("一句话概括问题或建议（必填，例如：高分屏静态版立绘偏模糊）")
        fc_l.addWidget(self.input_title)

        self.input_contact = QLineEdit()
        self.input_contact.setPlaceholderText("您的联系方式（选填：QQ号 / 邮箱，方便作者给您回复）")
        fc_l.addWidget(self.input_contact)

        self.input_body = QTextEdit()
        self.input_body.setPlaceholderText("请描述具体情况、复现步骤或屏幕分辨率/系统信息（提交时将自动附带版本号与系统环境）...")
        self.input_body.setMinimumHeight(120)
        fc_l.addWidget(self.input_body)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color: #50fa7b; font-size: 12px;")
        self.lbl_status.hide()
        fc_l.addWidget(self.lbl_status)

        layout.addWidget(form_card, 1)

        # Bottom action buttons
        btn_row = QHBoxLayout()
        self.btn_submit_direct = QPushButton("🚀 一键直接提交")
        self.btn_submit_direct.setToolTip("无需打开网页或登录 GitHub，直接把反馈发送给开发者")
        self.btn_submit_direct.clicked.connect(self._submit_direct_async)
        btn_row.addWidget(self.btn_submit_direct)

        self.btn_copy_report = QPushButton("复制文本")
        self.btn_copy_report.setObjectName("SecondaryBtn")
        self.btn_copy_report.setToolTip("复制完整反馈文本，方便直接粘贴到 QQ 群")
        self.btn_copy_report.clicked.connect(self._copy_full_report)
        btn_row.addWidget(self.btn_copy_report)

        btn_github = QPushButton("GitHub Issue")
        btn_github.setObjectName("SecondaryBtn")
        btn_github.setToolTip("可选：跳转到 GitHub 网页提交 Issue")
        btn_github.clicked.connect(self._open_github_issue)
        btn_row.addWidget(btn_github)

        btn_close = QPushButton("关闭")
        btn_close.setObjectName("SecondaryBtn")
        btn_close.setFixedWidth(72)
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def _copy_with_tip(self, text: str, btn: QPushButton, orig_label: str):
        QApplication.clipboard().setText(text)
        btn.setText("已复制 ✓")
        QTimer.singleShot(1600, lambda: btn.setText(orig_label))

    def _build_report_text(self) -> tuple[str, str]:
        kind = self.combo_type.currentText()
        title = self.input_title.text().strip() or f"{kind} - 来自哈Gemi桌面端"
        contact = self.input_contact.text().strip() or "未填写"
        desc = self.input_body.toPlainText().strip() or "(未填写详细描述)"
        edition = "Dynamic" if self.is_dynamic else "Classic"
        env_info = f"Version: {VERSION} ({edition}) | OS: {platform.system()} {platform.release()} | Python: {sys.version.split()[0]}"
        body = (
            f"反馈类型: {kind}\n"
            f"联系方式: {contact}\n"
            f"运行环境: {env_info}\n\n"
            f"详细描述:\n{desc}\n"
        )
        return title, body

    def _submit_direct_async(self):
        if not self.input_title.text().strip() and not self.input_body.toPlainText().strip():
            QMessageBox.warning(self, "提示", "请先填写反馈标题或详细描述后再提交喵~")
            return

        title, body = self._build_report_text()
        kind = self.combo_type.currentText()
        contact = self.input_contact.text().strip() or "匿名用户"

        self.btn_submit_direct.setEnabled(False)
        self.btn_submit_direct.setText("发送中...")
        self.lbl_status.setStyleSheet("color: #f1fa8c; font-size: 12px;")
        self.lbl_status.setText("⏳ 正在直连发送反馈，请稍候...")
        self.lbl_status.show()

        def worker():
            try:
                payload = {
                    "_subject": f"[哈Gemi反馈] {kind} - {title}",
                    "_template": "table",
                    "_captcha": "false",
                    "title": title,
                    "type": kind,
                    "contact": contact,
                    "message": body,
                }
                resp = requests.post(
                    FORMSUBMIT_AJAX_URL,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "Origin": "https://lyw199911.github.io",
                        "Referer": "https://lyw199911.github.io/",
                        "User-Agent": "Mozilla/5.0",
                    },
                    timeout=12,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success") in ("true", True):
                        self._submit_finished.emit(True, "✅ 反馈已成功一键发送给作者！感谢您的宝贵意见喵~")
                        return
                    err_detail = data.get("message") or f"返回异常 ({resp.status_code})"
                    self._submit_finished.emit(False, err_detail)
                    return
                self._submit_finished.emit(False, f"发送服务返回异常 ({resp.status_code})")
            except Exception as exc:
                self._submit_finished.emit(False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_submit_finished(self, ok: bool, msg: str):
        self.btn_submit_direct.setEnabled(True)
        self.btn_submit_direct.setText("🚀 一键直接提交")
        if ok:
            self.lbl_status.setStyleSheet("color: #50fa7b; font-size: 12px;")
            self.lbl_status.setText(msg)
            self.input_title.clear()
            self.input_body.clear()
        else:
            _, body = self._build_report_text()
            QApplication.clipboard().setText(f"【{self.input_title.text().strip() or '哈Gemi反馈'}】\n{body}")
            self.lbl_status.setStyleSheet("color: #ff6e6e; font-size: 12px;")
            self.lbl_status.setText(f"⚠️ 直连发送失败（{msg}），已自动为您复制完整反馈文本，可直接粘贴到 QQ 群 {QQ_GROUP}！")

    def _copy_full_report(self):
        title, body = self._build_report_text()
        full = f"【{title}】\n{body}"
        self._copy_with_tip(full, self.btn_copy_report, "📋 复制文本")

    def _open_github_issue(self):
        title, body = self._build_report_text()
        qs = urllib.parse.urlencode({"title": title, "body": body})
        QDesktopServices.openUrl(QUrl(f"{GITHUB_ISSUES_URL}?{qs}"))

    def _open_mailto(self):
        title, body = self._build_report_text()
        qs = urllib.parse.urlencode({"subject": f"[哈Gemi反馈] {title}", "body": body})
        QDesktopServices.openUrl(QUrl(f"mailto:{DEV_EMAIL}?{qs}"))
