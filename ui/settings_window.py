import os
import shutil
import time
from typing import Callable, Optional
from PyQt6.QtWidgets import (
    QWidget, QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QSlider, QSpinBox, QCheckBox, QComboBox,
    QTextEdit, QTextBrowser, QFileDialog, QMessageBox, QGroupBox, QScrollArea,
    QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QPixmap, QTextCursor

from config_manager import ConfigManager
from log_manager import get_log_manager
from app_paths import ASSETS_DIR
from version import VERSION
from .img_utils import remove_white_background

PERSONA_PRESETS = {
    "元气毒舌 (默认)": {
        "style": "元气毒舌",
        "catchphrases": "喵~, 喵？！, 哼~, 盯——",
        "desc": "活泼元气，笑容灿烂，嘴硬毒舌，一针见血嘲讽主人的菜操作与摸鱼行为。"
    },
    "傲娇大小姐": {
        "style": "傲娇大小姐",
        "catchphrases": "哼~, 笨蛋！, 才没有在关心你呢, 盯——",
        "desc": "高高在上又极度傲娇，明明很在乎主人却绝不承认，说话充满娇蛮大小姐范。"
    },
    "软萌治愈猫娘": {
        "style": "软萌治愈",
        "catchphrases": "喵呜~, 主人最棒啦, 蹭蹭~, 喵~",
        "desc": "极度温柔软萌，遇到主人打游戏逆风或写代码报错会送上摸头安慰与元气加油。"
    },
    "高冷毒舌监工": {
        "style": "高冷监工",
        "catchphrases": "呵。, 愚蠢。, 还不去干活？, 盯——",
        "desc": "冷峻严格的桌面监工，对任何怠惰和低级失误施以冷酷无情的犀利吐槽。"
    }
}

TTS_VOICES = [
    ("zh-TW-HsiaoChenNeural", "晓臻 (台湾软萌甜美 / 超自然不生硬 / 强烈推荐)"),
    ("zh-CN-XiaoyiNeural", "晓伊 (活泼元气少女 / 经典傲娇)"),
    ("zh-CN-XiaoxiaoNeural", "晓晓 (知性温柔清澈)"),
    ("zh-TW-HsiaoYuNeural", "晓雨 (台湾柔和少女)"),
    ("zh-CN-liaoning-XiaobeiNeural", "晓北 (东北幽默萌妹)"),
    ("zh-CN-shaanxi-XiaoniNeural", "晓妮 (陕西可爱方言妹)"),
    ("zh-HK-HiuMaanNeural", "晓曼 (粤语甜美少女)"),
    ("zh-CN-YunxiNeural", "云希 (温润清爽少年)"),
    ("zh-CN-YunjianNeural", "云健 (元气活力正太)"),
    ("ja-JP-NanamiNeural", "七海 Nanami (日系萌系二次元少女)"),
    ("ja-JP-AoiNeural", "葵 Aoi (日系清纯少女)"),
    ("custom", "自定义 (在下方输入 Edge-TTS 音色代码)")
]

class SettingsWindow(QMainWindow):
    settings_applied = pyqtSignal()
    request_manual_critique = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_mgr = ConfigManager()
        self.logger = get_log_manager()

        self.setWindowTitle(f"哈Gemi · 控制台与设置中心 {VERSION}")
        self.setMinimumSize(820, 640)
        self.resize(860, 680)

        icon_path = os.path.join(ASSETS_DIR, "app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._init_ui()
        self._load_values()

        # Connect log stream
        self.logger.log_added.connect(self._append_log)

    def _init_ui(self):
        # Central widget with styling
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Style sheet (Anime Dark Studio Style)
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1a162b;
                color: #e4e0f0;
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
            }
            QTabWidget::pane {
                border: 1.5px solid #362d52;
                border-radius: 10px;
                background-color: #211c38;
                padding: 10px;
            }
            QTabBar::tab {
                background-color: #26203f;
                color: #a49cb8;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 8px 18px;
                margin-right: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background-color: #ff4e88;
                color: #ffffff;
            }
            QGroupBox {
                border: 1px solid #3d335c;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 14px;
                font-weight: bold;
                color: #ff7aa6;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
            QLineEdit, QComboBox, QTextEdit, QSpinBox {
                background-color: #171326;
                border: 1px solid #3d335c;
                border-radius: 6px;
                padding: 6px 10px;
                color: #ffffff;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 1.5px solid #ff4e88;
            }
            QPushButton {
                background-color: #ff4e88;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #ff689a;
            }
            QPushButton:pressed {
                background-color: #e03b73;
            }
            QPushButton#SecondaryBtn {
                background-color: #2f2747;
                border: 1px solid #4a3e6b;
                color: #c9c3dd;
            }
            QPushButton#SecondaryBtn:hover {
                background-color: #3f345e;
                color: #ffffff;
            }
            QCheckBox {
                color: #e4e0f0;
                spacing: 8px;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #4a3e6b;
                background-color: #171326;
            }
            QCheckBox::indicator:checked {
                background-color: #ff4e88;
                border-color: #ff4e88;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #2a2245;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #ff4e88;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 2px solid #ff4e88;
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }
        """)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.tab_general = QWidget()
        self.tab_avatar = QWidget()
        self.tab_persona = QWidget()
        self.tab_logs = QWidget()

        self.tabs.addTab(self.tab_general, "核心与感知")
        self.tabs.addTab(self.tab_avatar, "立绘与表情工坊")
        self.tabs.addTab(self.tab_persona, "人设与口癖调教")
        self.tabs.addTab(self.tab_logs, "实时日志与记录")

        self._build_general_tab()
        self._build_avatar_tab()
        self._build_persona_tab()
        self._build_logs_tab()

        # Bottom Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(4, 4, 4, 0)

        self.btn_manual_test = QPushButton("立即让哈Gemi锐评测试", self)
        self.btn_manual_test.setObjectName("SecondaryBtn")
        self.btn_manual_test.clicked.connect(self.request_manual_critique.emit)
        bottom_bar.addWidget(self.btn_manual_test)

        lbl_ver = QLabel(f"Dashboard · {VERSION}", self)
        lbl_ver.setStyleSheet("color: #7d7594; font-size: 11px; font-weight: bold; padding-left: 8px;")
        bottom_bar.addWidget(lbl_ver)

        bottom_bar.addStretch()

        self.btn_save = QPushButton("保存并立即生效", self)
        self.btn_save.clicked.connect(self.save_and_apply)
        bottom_bar.addWidget(self.btn_save)

        self.btn_hide = QPushButton("最小化到托盘", self)
        self.btn_hide.setObjectName("SecondaryBtn")
        self.btn_hide.clicked.connect(self.hide)
        bottom_bar.addWidget(self.btn_hide)

        main_layout.addLayout(bottom_bar)

    # ==========================
    # Tab 1: General & Senses
    # ==========================
    def _build_general_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(14)

        # 1. API Box
        box_api = QGroupBox("AI 算力与大模型接口设置")
        box_api_l = QGridLayout(box_api)
        box_api_l.setSpacing(10)

        # Provider Selector
        box_api_l.addWidget(QLabel("接口类型 (Provider):"), 0, 0)
        self.combo_provider = QComboBox()
        self.combo_provider.addItem("Google Gemini 官方原生接口 (AI Studio)", "gemini")
        self.combo_provider.addItem("Google Cloud Vertex AI (GCP 算力/赠金)", "vertex")
        self.combo_provider.addItem("Google Antigravity 订阅通道 (免Key/烧会员额度)", "antigravity")
        self.combo_provider.addItem("OpenRouter / OpenAI 兼容接口 (第三方/中转/自定义)", "openai_compatible")
        self.combo_provider.currentIndexChanged.connect(self._on_provider_changed)
        box_api_l.addWidget(self.combo_provider, 0, 1, 1, 3)

        # API Base URL (OpenAI compatible)
        self.lbl_api_url = QLabel("API 接口地址 (URL):")
        box_api_l.addWidget(self.lbl_api_url, 1, 0)
        self.input_api_url = QLineEdit()
        self.input_api_url.setPlaceholderText("https://openrouter.ai/api/v1 或中转站地址")
        box_api_l.addWidget(self.input_api_url, 1, 1, 1, 3)

        # Vertex AI Location / Region
        self.lbl_vertex_loc = QLabel("Vertex 区域 (Location):")
        box_api_l.addWidget(self.lbl_vertex_loc, 2, 0)
        self.combo_vertex_loc = QComboBox()
        self.combo_vertex_loc.setEditable(True)
        self.combo_vertex_loc.addItems([
            "global",
            "us-central1",
            "us-east4",
            "us-west1",
            "asia-southeast1",
            "asia-northeast1",
            "europe-west2",
            "europe-west4"
        ])
        box_api_l.addWidget(self.combo_vertex_loc, 2, 1, 1, 3)

        # Vertex AI Project ID
        self.lbl_vertex_project = QLabel("GCP 项目 ID (Project ID):")
        box_api_l.addWidget(self.lbl_vertex_project, 3, 0)
        self.input_vertex_project = QLineEdit()
        self.input_vertex_project.setPlaceholderText("例如: my-project-id (留空可从密钥文件或 gcloud 自动提取)")
        box_api_l.addWidget(self.input_vertex_project, 3, 1, 1, 3)

        # Vertex AI Service Account JSON credentials file
        self.lbl_vertex_creds = QLabel("服务账号密钥 (JSON 路径):")
        box_api_l.addWidget(self.lbl_vertex_creds, 4, 0)
        self.input_vertex_creds = QLineEdit()
        self.input_vertex_creds.setPlaceholderText("选择 service-account.json 文件路径 (若已登录 gcloud 可留空)")
        box_api_l.addWidget(self.input_vertex_creds, 4, 1, 1, 2)
        self.btn_browse_creds = QPushButton("浏览...")
        self.btn_browse_creds.setObjectName("SecondaryBtn")
        self.btn_browse_creds.setFixedWidth(90)
        self.btn_browse_creds.clicked.connect(self._browse_vertex_creds)
        box_api_l.addWidget(self.btn_browse_creds, 4, 3)

        # Antigravity CLI Path (Custom)
        self.lbl_agy_path = QLabel("Antigravity CLI 路径:")
        box_api_l.addWidget(self.lbl_agy_path, 4, 0)
        self.input_agy_path = QLineEdit()
        self.input_agy_path.setPlaceholderText("留空自动探测；或手动指定 agy.exe / agy 路径")
        box_api_l.addWidget(self.input_agy_path, 4, 1, 1, 2)
        self.btn_browse_agy = QPushButton("浏览...")
        self.btn_browse_agy.setObjectName("SecondaryBtn")
        self.btn_browse_agy.setFixedWidth(90)
        self.btn_browse_agy.clicked.connect(self._browse_agy_cli)
        box_api_l.addWidget(self.btn_browse_agy, 4, 3)

        # API Key
        self.lbl_key = QLabel("API 密钥 (API Key):")
        box_api_l.addWidget(self.lbl_key, 5, 0)
        self.input_key = QLineEdit()
        self.input_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_key.setPlaceholderText("填入 API 密钥")
        box_api_l.addWidget(self.input_key, 5, 1)

        self.btn_show_key = QPushButton("显示")
        self.btn_show_key.setObjectName("SecondaryBtn")
        self.btn_show_key.setFixedWidth(75)
        self.btn_show_key.clicked.connect(self._toggle_key_visibility)
        box_api_l.addWidget(self.btn_show_key, 5, 2)

        self.btn_test_key = QPushButton("测试连接")
        self.btn_test_key.setObjectName("SecondaryBtn")
        self.btn_test_key.setFixedWidth(90)
        self.btn_test_key.clicked.connect(self._test_api_connection)
        box_api_l.addWidget(self.btn_test_key, 5, 3)

        # Model Selector (Editable)
        box_api_l.addWidget(QLabel("视觉推理模型 (Model):"), 6, 0)
        self.combo_model = QComboBox()
        self.combo_model.setEditable(True)
        box_api_l.addWidget(self.combo_model, 6, 1, 1, 3)

        # Vertex Tips Hint
        self.lbl_vertex_hint = QLabel("💡 提示：使用 Google Cloud Vertex AI 时，推荐模型填入 gemini-4-argon（前沿推理大模型）或 gemini-3.8-flash；区域推荐 global（全球调度，抗429更稳定）；服务账号需在 GCP 控制台赋予 Vertex AI User (roles/aiplatform.user) 权限。")
        self.lbl_vertex_hint.setWordWrap(True)
        self.lbl_vertex_hint.setStyleSheet("color: #ff99bb; font-size: 11px;")
        box_api_l.addWidget(self.lbl_vertex_hint, 7, 0, 1, 4)

        layout.addWidget(box_api)

        # Tencent Cloud speech recognition credentials
        box_asr = QGroupBox("语音输入 (腾讯云一句话识别)")
        box_asr_l = QGridLayout(box_asr)
        box_asr_l.setSpacing(10)
        box_asr_l.addWidget(QLabel("腾讯云 SecretId:"), 0, 0)
        self.input_tencent_secret_id = QLineEdit()
        self.input_tencent_secret_id.setPlaceholderText("腾讯云 API 密钥管理中的 SecretId")
        box_asr_l.addWidget(self.input_tencent_secret_id, 0, 1, 1, 3)
        box_asr_l.addWidget(QLabel("腾讯云 SecretKey:"), 1, 0)
        self.input_tencent_secret_key = QLineEdit()
        self.input_tencent_secret_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_tencent_secret_key.setPlaceholderText("腾讯云 API 密钥管理中的 SecretKey")
        box_asr_l.addWidget(self.input_tencent_secret_key, 1, 1, 1, 3)
        asr_hint = QLabel("按 Ctrl+F1 开始/结束录音；停止后自动识别并发送。录音最长 55 秒，音频仅暂存在内存并发送给腾讯云，不写入本地文件。")
        asr_hint.setWordWrap(True)
        asr_hint.setStyleSheet("color: #a49cb8; font-size: 11px;")
        box_asr_l.addWidget(asr_hint, 2, 0, 1, 4)
        layout.addWidget(box_asr)

        # 2. Perception & Autostart Box
        box_sense = QGroupBox("自动感知与场景设置")
        box_sense_l = QGridLayout(box_sense)

        self.chk_auto = QCheckBox("启用全自动感知模式（定时巡逻屏幕与活跃窗口）")
        box_sense_l.addWidget(self.chk_auto, 0, 0, 1, 2)

        box_sense_l.addWidget(QLabel("自动锐评冷却时间:"), 1, 0)
        cooldown_box = QHBoxLayout()
        self.slider_cooldown = QSlider(Qt.Orientation.Horizontal)
        self.slider_cooldown.setRange(15, 120)
        self.lbl_cooldown_val = QLabel("45 秒")
        self.slider_cooldown.valueChanged.connect(lambda v: self.lbl_cooldown_val.setText(f"{v} 秒"))
        cooldown_box.addWidget(self.slider_cooldown)
        cooldown_box.addWidget(self.lbl_cooldown_val)
        box_sense_l.addLayout(cooldown_box, 1, 1)

        # Scene preference checkboxes
        scene_h = QHBoxLayout()
        self.chk_game = QCheckBox("打游戏战况锐评")
        self.chk_video = QCheckBox("看视频/直播弹幕互动")
        self.chk_work = QCheckBox("码字/写代码摸鱼抓包")
        scene_h.addWidget(self.chk_game)
        scene_h.addWidget(self.chk_video)
        scene_h.addWidget(self.chk_work)
        box_sense_l.addLayout(scene_h, 2, 0, 1, 2)

        # Autostart checkbox
        self.chk_autostart = QCheckBox("开机自动在后台启动哈Gemi (Windows 自启动)")
        box_sense_l.addWidget(self.chk_autostart, 3, 0, 1, 2)

        # Persistent Memory checkbox
        self.chk_memory = QCheckBox("开启长期记忆 (跨会话/开机后依然记住前情，保存在本地 memory.json)")
        box_sense_l.addWidget(self.chk_memory, 4, 0, 1, 2)

        layout.addWidget(box_sense)

        # 3. Voice & Appearance Box
        box_voice = QGroupBox("语音播报 (TTS) 与桌宠外观")
        box_voice_l = QGridLayout(box_voice)

        self.chk_tts = QCheckBox("启用少女音语音吐槽播报")
        box_voice_l.addWidget(self.chk_tts, 0, 0, 1, 2)

        # TTS Engine selector
        box_voice_l.addWidget(QLabel("语音引擎类型:"), 1, 0)
        self.combo_tts_engine = QComboBox()
        self.combo_tts_engine.addItem("Edge-TTS (微软云端神经网络 / 免费免配置)", "edge_tts")
        self.combo_tts_engine.addItem("自定义兼容接口 (GPT-SoVITS / CosyVoice / Fish Audio / OpenAI)", "openai_tts")
        self.combo_tts_engine.currentIndexChanged.connect(self._on_tts_engine_changed)
        box_voice_l.addWidget(self.combo_tts_engine, 1, 1, 1, 2)

        # Edge-TTS Voice options
        self.lbl_voice_choice = QLabel("语音音色:")
        box_voice_l.addWidget(self.lbl_voice_choice, 2, 0)
        self.combo_voice = QComboBox()
        for v_id, label in TTS_VOICES:
            self.combo_voice.addItem(label, v_id)
        self.combo_voice.currentIndexChanged.connect(self._on_voice_changed)
        box_voice_l.addWidget(self.combo_voice, 2, 1)

        self.btn_test_tts = QPushButton("试听发音")
        self.btn_test_tts.setObjectName("SecondaryBtn")
        self.btn_test_tts.clicked.connect(self._test_voice)
        box_voice_l.addWidget(self.btn_test_tts, 2, 2)

        # Custom Edge-TTS input
        self.lbl_custom_voice = QLabel("自定义音色代码:")
        self.input_custom_voice = QLineEdit()
        self.input_custom_voice.setPlaceholderText("例如: zh-TW-HsiaoChenNeural 或 ja-JP-NanamiNeural")
        box_voice_l.addWidget(self.lbl_custom_voice, 3, 0)
        box_voice_l.addWidget(self.input_custom_voice, 3, 1, 1, 2)

        # Rate slider
        self.lbl_rate = QLabel("语音语速:")
        box_voice_l.addWidget(self.lbl_rate, 4, 0)
        rate_box = QHBoxLayout()
        self.slider_rate = QSlider(Qt.Orientation.Horizontal)
        self.slider_rate.setRange(-30, 50)
        self.slider_rate.setValue(10)
        self.lbl_rate_val = QLabel("+10%")
        self.slider_rate.valueChanged.connect(lambda v: self.lbl_rate_val.setText(f"{v:+d}%"))
        rate_box.addWidget(self.slider_rate)
        rate_box.addWidget(self.lbl_rate_val)
        box_voice_l.addLayout(rate_box, 4, 1, 1, 2)

        # Pitch slider
        self.lbl_pitch = QLabel("语音语调 (音高):")
        box_voice_l.addWidget(self.lbl_pitch, 5, 0)
        pitch_box = QHBoxLayout()
        self.slider_pitch = QSlider(Qt.Orientation.Horizontal)
        self.slider_pitch.setRange(-20, 30)
        self.slider_pitch.setValue(10)
        self.lbl_pitch_val = QLabel("+10Hz")
        self.slider_pitch.valueChanged.connect(lambda v: self.lbl_pitch_val.setText(f"{v:+d}Hz"))
        pitch_box.addWidget(self.slider_pitch)
        pitch_box.addWidget(self.lbl_pitch_val)
        box_voice_l.addLayout(pitch_box, 5, 1, 1, 2)

        # Custom TTS API fields (OpenAI / GPT-SoVITS)
        self.lbl_tts_url = QLabel("TTS API 接口地址:")
        self.input_tts_url = QLineEdit()
        self.input_tts_url.setPlaceholderText("例如: http://127.0.0.1:9880/v1/audio/speech 或 http://localhost:5000/tts")
        box_voice_l.addWidget(self.lbl_tts_url, 6, 0)
        box_voice_l.addWidget(self.input_tts_url, 6, 1, 1, 2)

        self.lbl_tts_key = QLabel("TTS API Key (可选):")
        self.input_tts_key = QLineEdit()
        self.input_tts_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_tts_key.setPlaceholderText("本地服务通常留空；第三方服务填入 Key")
        box_voice_l.addWidget(self.lbl_tts_key, 7, 0)
        box_voice_l.addWidget(self.input_tts_key, 7, 1, 1, 2)

        self.lbl_tts_model = QLabel("TTS 模型/音色 (可选):")
        self.input_tts_model = QLineEdit()
        self.input_tts_model.setPlaceholderText("例如: default / tts-1 / cosyvoice")
        box_voice_l.addWidget(self.lbl_tts_model, 8, 0)
        box_voice_l.addWidget(self.input_tts_model, 8, 1, 1, 2)

        box_voice_l.addWidget(QLabel("桌宠立绘高度:"), 9, 0)
        size_box = QHBoxLayout()
        self.slider_height = QSlider(Qt.Orientation.Horizontal)
        self.slider_height.setRange(160, 380)
        self.lbl_height_val = QLabel("250 px")
        self.slider_height.valueChanged.connect(lambda v: self.lbl_height_val.setText(f"{v} px"))
        size_box.addWidget(self.slider_height)
        size_box.addWidget(self.lbl_height_val)
        box_voice_l.addLayout(size_box, 9, 1, 1, 2)

        layout.addWidget(box_voice)

        scroll.setWidget(content)
        v = QVBoxLayout(self.tab_general)
        v.addWidget(scroll)

    # ==========================
    # Tab 2: Avatar & Outfits
    # ==========================
    def _build_avatar_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(16)

        desc = QLabel("在这里可以为哈Gemi的 4 套情绪表情上传自定义立绘。支持 PNG、JPG、WebP，可一键自动去除白色背景！")
        desc.setStyleSheet("color: #ff99bb; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.outfit_cards = {}
        emotions = [
            ("confident", "自信傲娇 (默认站姿)", "avatar_standing.png", "日常元气站姿、傲娇嘴硬或调侃"),
            ("curious", "呆萌疑惑 (Q版抓头)", "avatar_bust.png", "盯——、摸鱼抓现行、感到疑惑"),
            ("shocked", "抱头震惊 (抓狂冒汗)", "avatar_shocked.png", "游戏离谱暴毙、下饭反转、弹幕刷问号"),
            ("relieved", "害羞擦汗 (无语扶额)", "avatar_relieved.png", "代码满屏报错、长吁短叹、感到无语")
        ]

        grid = QGridLayout()
        grid.setSpacing(14)

        for idx, (emo_key, title, default_fn, tip) in enumerate(emotions):
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #241d3d;
                    border: 1px solid #3d335c;
                    border-radius: 8px;
                    padding: 8px;
                }
            """)
            card_l = QVBoxLayout(card)
            card_l.setSpacing(6)

            lbl_t = QLabel(title)
            lbl_t.setStyleSheet("font-weight: bold; color: #ff7aa6; font-size: 13px;")
            card_l.addWidget(lbl_t)

            lbl_tip = QLabel(tip)
            lbl_tip.setStyleSheet("color: #a49cb8; font-size: 11px;")
            card_l.addWidget(lbl_tip)

            # Preview label
            lbl_prev = QLabel()
            lbl_prev.setFixedSize(140, 160)
            lbl_prev.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_prev.setStyleSheet("background-color: #171326; border-radius: 6px; border: 1px dashed #3d335c;")
            card_l.addWidget(lbl_prev, alignment=Qt.AlignmentFlag.AlignCenter)

            # Buttons
            btn_h = QHBoxLayout()
            btn_upload = QPushButton("更换图片")
            btn_upload.setObjectName("SecondaryBtn")
            btn_upload.clicked.connect(lambda checked=False, k=emo_key: self._upload_avatar(k))
            btn_h.addWidget(btn_upload)

            btn_reset = QPushButton("恢复默认")
            btn_reset.setObjectName("SecondaryBtn")
            btn_reset.clicked.connect(lambda checked=False, k=emo_key, df=default_fn: self._reset_avatar(k, df))
            btn_h.addWidget(btn_reset)
            card_l.addLayout(btn_h)

            row = idx // 2
            col = idx % 2
            grid.addWidget(card, row, col)

            self.outfit_cards[emo_key] = {
                "label_prev": lbl_prev,
                "filename": default_fn,
                "default_fn": default_fn
            }

        layout.addLayout(grid)
        scroll.setWidget(content)
        v = QVBoxLayout(self.tab_avatar)
        v.addWidget(scroll)

    # ==========================
    # Tab 3: Persona & Prompt
    # ==========================
    def _build_persona_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(14)

        box_p = QGroupBox("角色基本设定与口癖")
        box_p_l = QGridLayout(box_p)

        box_p_l.addWidget(QLabel("桌宠名字:"), 0, 0)
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("例如: 哈Gemi")
        box_p_l.addWidget(self.input_name, 0, 1)

        box_p_l.addWidget(QLabel("常用口癖 (英文或中文逗号分隔):"), 1, 0)
        self.input_catchphrases = QLineEdit()
        self.input_catchphrases.setPlaceholderText("例如: 喵~, 喵？！, 哼~, 盯——, 笨蛋主人")
        box_p_l.addWidget(self.input_catchphrases, 1, 1)

        box_p_l.addWidget(QLabel("快速性格预设:"), 2, 0)
        self.combo_persona = QComboBox()
        self.combo_persona.addItems(list(PERSONA_PRESETS.keys()))
        self.combo_persona.currentTextChanged.connect(self._on_persona_preset_changed)
        box_p_l.addWidget(self.combo_persona, 2, 1)

        self.lbl_persona_desc = QLabel()
        self.lbl_persona_desc.setStyleSheet("color: #a49cb8; font-size: 11px;")
        box_p_l.addWidget(self.lbl_persona_desc, 3, 1)

        layout.addWidget(box_p)

        box_custom = QGroupBox("高级自定义 System Prompt (留空则使用内置精调设定)")
        box_c_l = QVBoxLayout(box_custom)

        self.txt_custom_prompt = QTextEdit()
        self.txt_custom_prompt.setPlaceholderText("在这里可自定义完整的猫娘 Prompt 指令。留空会自动应用上方的口癖和性格预设~")
        box_c_l.addWidget(self.txt_custom_prompt)

        btn_h = QHBoxLayout()
        btn_reset_prompt = QPushButton("一键恢复官方推荐 Prompt")
        btn_reset_prompt.setObjectName("SecondaryBtn")
        btn_reset_prompt.clicked.connect(lambda: self.txt_custom_prompt.clear())
        btn_h.addWidget(btn_reset_prompt)
        btn_h.addStretch()
        box_c_l.addLayout(btn_h)

        layout.addWidget(box_custom)

        scroll.setWidget(content)
        v = QVBoxLayout(self.tab_persona)
        v.addWidget(scroll)

    # ==========================
    # Tab 4: Live Logs
    # ==========================
    def _build_logs_tab(self):
        layout = QVBoxLayout(self.tab_logs)
        layout.setSpacing(10)

        # Toolbar
        tb = QHBoxLayout()
        lbl = QLabel(f"实时感知流水线与 AI 锐评记录 ({VERSION}):")
        lbl.setStyleSheet("font-weight: bold; color: #ff7aa6;")
        tb.addWidget(lbl)
        tb.addStretch()

        btn_open_file = QPushButton("打开日志文件")
        btn_open_file.setObjectName("SecondaryBtn")
        btn_open_file.clicked.connect(self._open_log_file)
        tb.addWidget(btn_open_file)

        btn_refresh = QPushButton("刷新日志")
        btn_refresh.setObjectName("SecondaryBtn")
        btn_refresh.clicked.connect(self._refresh_log_display)
        tb.addWidget(btn_refresh)

        btn_clear = QPushButton("清空日志")
        btn_clear.setObjectName("SecondaryBtn")
        btn_clear.clicked.connect(self._clear_logs)
        tb.addWidget(btn_clear)

        layout.addLayout(tb)

        # Toolbar 2: Persistent Memory
        tb_mem = QHBoxLayout()
        self.lbl_mem_info = QLabel("长期记忆管理 (memory.json):")
        self.lbl_mem_info.setStyleSheet("font-weight: bold; color: #f1fa8c;")
        tb_mem.addWidget(self.lbl_mem_info)
        tb_mem.addStretch()

        btn_view_mem = QPushButton("查看记忆明细")
        btn_view_mem.setObjectName("SecondaryBtn")
        btn_view_mem.clicked.connect(self._view_memory_details)
        tb_mem.addWidget(btn_view_mem)

        btn_open_mem = QPushButton("打开记忆文件")
        btn_open_mem.setObjectName("SecondaryBtn")
        btn_open_mem.clicked.connect(self._open_memory_file)
        tb_mem.addWidget(btn_open_mem)

        btn_clear_mem = QPushButton("清空长期记忆")
        btn_clear_mem.setObjectName("SecondaryBtn")
        btn_clear_mem.clicked.connect(self._clear_memory)
        tb_mem.addWidget(btn_clear_mem)

        layout.addLayout(tb_mem)

        self.log_browser = QTextBrowser()
        self.log_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #120f20;
                border: 1.5px solid #2e2647;
                border-radius: 8px;
                padding: 10px;
                font-family: "Consolas", "Microsoft YaHei Mono", monospace;
                font-size: 12px;
                line-height: 140%;
            }
        """)
        layout.addWidget(self.log_browser)

    # ==========================
    # Logic & Event Handlers
    # ==========================
    def _load_values(self):
        self._is_loading = True
        try:
            cfg = self.config_mgr.config

            # 1. General & API
            prov = cfg.get("api_provider", "gemini")
            idx = self.combo_provider.findData(prov)
            if idx >= 0:
                self.combo_provider.setCurrentIndex(idx)
            else:
                self.combo_provider.setCurrentIndex(0)

            self.input_api_url.setText(cfg.get("custom_api_url", "https://openrouter.ai/api/v1"))
            self.input_vertex_project.setText(cfg.get("vertex_project_id", ""))
            v_loc = cfg.get("vertex_location", "global")
            v_idx = self.combo_vertex_loc.findText(v_loc)
            if v_idx >= 0:
                self.combo_vertex_loc.setCurrentIndex(v_idx)
            else:
                self.combo_vertex_loc.setCurrentText(v_loc)
            self.input_vertex_creds.setText(cfg.get("vertex_credentials_file", ""))
            self._on_provider_changed()

            self.input_key.setText(cfg.get("api_key", ""))
            self.combo_model.setCurrentText(cfg.get("model", "gemini-3.8-flash"))
            self.input_tencent_secret_id.setText(cfg.get("tencent_secret_id", ""))
            self.input_tencent_secret_key.setText(cfg.get("tencent_secret_key", ""))
            self.chk_auto.setChecked(cfg.get("auto_mode", True))
            self.slider_cooldown.setValue(int(cfg.get("cooldown_seconds", 45)))
            self.lbl_cooldown_val.setText(f"{self.slider_cooldown.value()} 秒")

            self.chk_game.setChecked(cfg.get("comment_on_games", True))
            self.chk_video.setChecked(cfg.get("comment_on_videos", True))
            self.chk_work.setChecked(cfg.get("comment_on_work", True))

            self.chk_autostart.setChecked(self.config_mgr.is_autostart_enabled())
            self.chk_memory.setChecked(cfg.get("enable_persistent_memory", True))

            self.input_agy_path.setText(cfg.get("antigravity_cli_path", ""))

            self.chk_tts.setChecked(cfg.get("enable_tts", True))
            tts_engine = cfg.get("tts_engine", "edge_tts")
            e_idx = self.combo_tts_engine.findData(tts_engine)
            if e_idx >= 0:
                self.combo_tts_engine.setCurrentIndex(e_idx)

            current_voice = cfg.get("tts_voice", "zh-TW-HsiaoChenNeural")
            voice_found = False
            for i in range(self.combo_voice.count()):
                if self.combo_voice.itemData(i) == current_voice:
                    self.combo_voice.setCurrentIndex(i)
                    voice_found = True
                    break
            if not voice_found:
                c_idx = self.combo_voice.findData("custom")
                if c_idx >= 0:
                    self.combo_voice.setCurrentIndex(c_idx)
                self.input_custom_voice.setText(current_voice)

            # Parse rate (e.g. "+12%" -> 12)
            try:
                rate_val = int(str(cfg.get("tts_rate", "+10%")).replace("%", "").replace("+", ""))
            except Exception:
                rate_val = 10
            self.slider_rate.setValue(rate_val)
            self.lbl_rate_val.setText(f"{rate_val:+d}%")

            # Parse pitch (e.g. "+15Hz" -> 15)
            try:
                pitch_val = int(str(cfg.get("tts_pitch", "+10Hz")).replace("Hz", "").replace("+", ""))
            except Exception:
                pitch_val = 10
            self.slider_pitch.setValue(pitch_val)
            self.lbl_pitch_val.setText(f"{pitch_val:+d}Hz")

            self.input_tts_url.setText(cfg.get("tts_api_url", ""))
            self.input_tts_key.setText(cfg.get("tts_api_key", ""))
            self.input_tts_model.setText(cfg.get("tts_model", ""))
            self._on_tts_engine_changed()

            self.slider_height.setValue(int(cfg.get("target_height", 250)))
            self.lbl_height_val.setText(f"{self.slider_height.value()} px")

            # 2. Avatar Outfits
            outfits = cfg.get("outfits", {})
            for emo, card in self.outfit_cards.items():
                fn = outfits.get(emo, card["default_fn"])
                card["filename"] = fn
                self._refresh_avatar_preview(emo, fn)

            # 3. Persona
            self.input_name.setText(cfg.get("pet_name", "哈Gemi"))
            c_list = cfg.get("catchphrases", ["喵~", "喵？！", "哼~", "盯——"])
            self.input_catchphrases.setText(", ".join(c_list))

            p_style = cfg.get("persona_style", "元气毒舌 (默认)")
            if p_style in PERSONA_PRESETS:
                self.combo_persona.setCurrentText(p_style)
            self._update_persona_desc(self.combo_persona.currentText())

            self.txt_custom_prompt.setPlainText(cfg.get("custom_system_prompt", ""))
        finally:
            self._is_loading = False

    def _refresh_avatar_preview(self, emo_key: str, filename: str):
        full_path = os.path.join(ASSETS_DIR, filename)
        lbl = self.outfit_cards[emo_key]["label_prev"]
        if os.path.exists(full_path):
            pix = QPixmap(full_path)
            scaled = pix.scaled(130, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl.setPixmap(scaled)
        else:
            lbl.setText("暂无图片")

    def _upload_avatar(self, emo_key: str):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择立绘图片", "", "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not file_path:
            return

        # Ask if user wants to auto remove white background
        ret = QMessageBox.question(
            self, "透明通道处理",
            "所选图片是否含有白色背景？\n点击【是】将自动智能抠除白色背景为透明通道，点击【否】直接保留原图格式。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        out_name = f"custom_{emo_key}_{int(time.time())}.png"
        out_path = os.path.join(ASSETS_DIR, out_name)

        if ret == QMessageBox.StandardButton.Yes:
            ok = remove_white_background(file_path, out_path, tolerance=22)
            if not ok:
                shutil.copy2(file_path, out_path)
        else:
            # Direct convert / copy to PNG
            shutil.copy2(file_path, out_path)

        self.outfit_cards[emo_key]["filename"] = out_name
        self._refresh_avatar_preview(emo_key, out_name)
        QMessageBox.information(self, "成功", f"表情【{emo_key}】立绘已成功更新并保存！")

    def _reset_avatar(self, emo_key: str, default_fn: str):
        self.outfit_cards[emo_key]["filename"] = default_fn
        self._refresh_avatar_preview(emo_key, default_fn)

    def _browse_agy_cli(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 Antigravity (agy) 可执行文件",
            "",
            "Executable Files (*.exe *.cmd *.bat agy*);;All Files (*)"
        )
        if file_path:
            self.input_agy_path.setText(file_path)

    def _on_tts_engine_changed(self):
        engine = self.combo_tts_engine.currentData() or "edge_tts"
        is_edge = (engine == "edge_tts")

        self.lbl_voice_choice.setVisible(is_edge)
        self.combo_voice.setVisible(is_edge)
        self.lbl_rate.setVisible(is_edge)
        self.slider_rate.setVisible(is_edge)
        self.lbl_rate_val.setVisible(is_edge)
        self.lbl_pitch.setVisible(is_edge)
        self.slider_pitch.setVisible(is_edge)
        self.lbl_pitch_val.setVisible(is_edge)

        is_custom_voice = (is_edge and self.combo_voice.currentData() == "custom")
        self.lbl_custom_voice.setVisible(is_custom_voice)
        self.input_custom_voice.setVisible(is_custom_voice)

        self.lbl_tts_url.setVisible(not is_edge)
        self.input_tts_url.setVisible(not is_edge)
        self.lbl_tts_key.setVisible(not is_edge)
        self.input_tts_key.setVisible(not is_edge)
        self.lbl_tts_model.setVisible(not is_edge)
        self.input_tts_model.setVisible(not is_edge)

    def _on_voice_changed(self):
        is_custom = (self.combo_voice.currentData() == "custom")
        self.lbl_custom_voice.setVisible(is_custom)
        self.input_custom_voice.setVisible(is_custom)

    def _browse_vertex_creds(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 Google Cloud 服务账号 JSON 密钥文件", "", "JSON 密钥文件 (*.json);;所有文件 (*.*)"
        )
        if file_path:
            self.input_vertex_creds.setText(file_path)
            if not self.input_vertex_project.text().strip():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        d = json.load(f)
                        pid = d.get("project_id", "")
                        if pid:
                            self.input_vertex_project.setText(pid)
                except Exception:
                    pass

    def _on_provider_changed(self):
        prov = self.combo_provider.currentData()
        curr_text = self.combo_model.currentText()
        self.combo_model.clear()

        is_vertex = (prov == "vertex")
        is_agy = (prov == "antigravity")
        is_openai = (prov == "openai_compatible")
        is_gemini = (prov == "gemini")

        self.lbl_api_url.setVisible(is_openai)
        self.input_api_url.setVisible(is_openai)

        self.lbl_vertex_loc.setVisible(is_vertex)
        self.combo_vertex_loc.setVisible(is_vertex)
        self.lbl_vertex_project.setVisible(is_vertex)
        self.input_vertex_project.setVisible(is_vertex)
        self.lbl_vertex_creds.setVisible(is_vertex)
        self.input_vertex_creds.setVisible(is_vertex)
        self.btn_browse_creds.setVisible(is_vertex)
        self.lbl_vertex_hint.setVisible(is_vertex or is_agy)

        # Restore key inputs if moving away from antigravity
        if not is_agy:
            self.input_key.setEnabled(True)
            self.btn_show_key.setVisible(True)
            if self.input_key.text().startswith("✅ 已自动识别"):
                self.input_key.setText(self.config_mgr.get("api_key", ""))
                self.input_key.setEchoMode(QLineEdit.EchoMode.Password)

        if is_gemini:
            self.lbl_key.setText("Gemini API Key:")
            self.input_key.setPlaceholderText("填入 Gemini 官方 API 密钥 (AQ. 或 AIzaSy 开头)")
            items = [
                "gemini-3.8-flash",
                "gemini-4-argon"
            ]
            self.combo_model.addItems(items)
            if curr_text in items:
                self.combo_model.setCurrentText(curr_text)
            elif curr_text and not any(t in curr_text for t in ("2.5", "2.0", "1.5", "3.8-flash-")):
                self.combo_model.setCurrentText(curr_text)
            else:
                self.combo_model.setCurrentIndex(0)
        elif is_vertex:
            self.lbl_vertex_hint.setText("💡 提示：使用 Google Cloud Vertex AI 时，推荐模型填入 gemini-4-argon（前沿推理大模型）或 gemini-3.8-flash；区域推荐 global（全球调度，抗429更稳定）；服务账号需在 GCP 控制台赋予 Vertex AI User (roles/aiplatform.user) 权限。")
            self.lbl_key.setText("API Key / Token (可选):")
            self.input_key.setPlaceholderText("若使用服务账号 JSON 则此处留空；或填入 Vertex API Key / ya29 Access Token")
            items = [
                "gemini-4-argon",
                "gemini-3.8-flash",
                "claude-3-5-sonnet-v2@20241022"
            ]
            self.combo_model.addItems(items)
            if curr_text in items:
                self.combo_model.setCurrentText(curr_text)
            elif curr_text and not any(t in curr_text for t in ("2.5", "2.0", "1.5", "3.8-flash-")):
                self.combo_model.setCurrentText(curr_text)
            else:
                self.combo_model.setCurrentText("gemini-4-argon")
        elif is_agy:
            from brain.gemini_client import AntigravityEngineHelper
            probe_helper = AntigravityEngineHelper(config_mgr=self.config_mgr)
            found_bin = probe_helper._find_agy_binary(self.input_agy_path.text().strip())
            if found_bin:
                status_tip = f"✅ 已自动识别本机 Antigravity CLI ({os.path.basename(found_bin)})"
                self.lbl_vertex_hint.setText(f"💡 提示：Antigravity 订阅通道完全免 Key！已成功适配本机 agy 命令行：{found_bin}，直接消耗会员算力，免受 429 限流。")
            else:
                status_tip = "⚠️ 未在标准目录找到 agy 命令行，请在下方点击「浏览」指定"
                self.lbl_vertex_hint.setText("💡 提示：若未在默认目录找到 agy，请在下方「Antigravity CLI 路径」点击「浏览」选中您的 agy.exe / agy 路径即可。")

            self.lbl_key.setText("本地订阅凭据:")
            self.input_key.setEnabled(False)
            self.input_key.setEchoMode(QLineEdit.EchoMode.Normal)
            self.input_key.setText(status_tip)
            self.btn_show_key.setVisible(False)
            items = [
                "gemini-3.8-flash-high",
                "gemini-3.8-flash-medium",
                "gemini-3.8-flash-low",
                "gemini-3.8-flash",
                "gemini-4-argon",
                "claude-sonnet-4-6",
                "claude-opus-4-6-thinking",
                "gpt-oss-120b-medium"
            ]
            self.combo_model.addItems(items)
            if curr_text in items:
                self.combo_model.setCurrentText(curr_text)
            else:
                self.combo_model.setCurrentText("gemini-3.8-flash-high")
        else:
            self.lbl_key.setText("OpenRouter / API Key:")
            self.input_key.setPlaceholderText("填入 sk-or-v1-... 或 sk-... 密钥")
            items = [
                "google/gemini-3.8-flash",
                "google/gemini-4-argon",
                "anthropic/claude-3.5-sonnet",
                "openai/gpt-4o-mini",
                "openai/gpt-4o",
                "deepseek/deepseek-chat"
            ]
            self.combo_model.addItems(items)
            if curr_text in items or (curr_text and not any(t in curr_text for t in ("2.5", "2.0", "1.5")) and curr_text not in ["gemini-3.8-flash", "gemini-4-argon", "gemini-3.8-flash-high"]):
                self.combo_model.setCurrentText(curr_text)
            else:
                self.combo_model.setCurrentIndex(0)

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_log_display()

    def _on_persona_preset_changed(self, text: str):
        self._update_persona_desc(text)
        if getattr(self, "_is_loading", False):
            return
        if text in PERSONA_PRESETS:
            p = PERSONA_PRESETS[text]
            self.input_catchphrases.setText(p["catchphrases"])

    def _update_persona_desc(self, text: str):
        if text in PERSONA_PRESETS:
            p = PERSONA_PRESETS[text]
            self.lbl_persona_desc.setText(f"说明: {p['desc']}")

    def _toggle_key_visibility(self):
        if self.input_key.echoMode() == QLineEdit.EchoMode.Password:
            self.input_key.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_show_key.setText("隐藏")
        else:
            self.input_key.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_show_key.setText("显示")

    def _test_api_connection(self):
        prov = self.combo_provider.currentData()
        key = self.input_key.text().strip()
        if key.startswith("✅ 已自动识别"):
            key = self.config_mgr.get("api_key", "")
        model = self.combo_model.currentText().strip()
        custom_url = self.input_api_url.text().strip()
        vertex_loc = self.combo_vertex_loc.currentText().strip() or "global"
        vertex_proj = self.input_vertex_project.text().strip()
        vertex_creds = self.input_vertex_creds.text().strip()

        if prov == "antigravity":
            # Antigravity uses local credentials
            pass
        elif prov != "vertex" and not key:
            QMessageBox.warning(self, "提示", "请先填入 API Key！")
            return
        elif prov == "vertex" and not key and not vertex_creds:
            reply = QMessageBox.question(
                self,
                "提示",
                "未填写服务账号 JSON 密钥文件路径或 API Key。\n是否尝试使用本地 gcloud / ADC 自动凭据进行测试？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        from brain.gemini_client import GeminiCritiqueEngine, is_valid_gemini_key
        # 若为 Gemini 官方端点且格式不符合常见特征 (兼容 AIzaSy 与 AQ 前缀)，做温和提示但允许用户继续
        if prov == "gemini" and not is_valid_gemini_key(key):
            reply = QMessageBox.question(
                self,
                "提示",
                "检测到输入的 API Key 格式可能不属于标准的 Gemini 官方 Key (通常为 AIzaSy... 或 AQ... 开头)。\n是否仍要继续测试？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        engine = GeminiCritiqueEngine()
        ok, msg = engine.test_connection(
            key=key,
            model=model,
            provider=prov,
            custom_url=custom_url,
            vertex_location=vertex_loc,
            vertex_project_id=vertex_proj,
            vertex_creds_file=vertex_creds
        )
        if ok:
            QMessageBox.information(self, "连接成功", msg)
        else:
            QMessageBox.critical(self, "连接失败", msg)

    def _test_voice(self):
        engine_type = self.combo_tts_engine.currentData() or "edge_tts"
        voice = self.combo_voice.currentData()
        if voice == "custom":
            voice = self.input_custom_voice.text().strip() or "zh-TW-HsiaoChenNeural"

        rate_val = self.slider_rate.value()
        rate_str = f"{rate_val:+d}%"
        pitch_val = self.slider_pitch.value()
        pitch_str = f"{pitch_val:+d}Hz"
        api_url = self.input_tts_url.text().strip()
        api_key = self.input_tts_key.text().strip()
        model = self.input_tts_model.text().strip()

        from tts.edge_speaker import EdgeSpeaker
        speaker = EdgeSpeaker(
            voice=voice,
            rate=rate_str,
            pitch=pitch_str,
            enabled=True,
            engine_type=engine_type,
            api_url=api_url,
            api_key=api_key,
            model=model
        )
        name = self.input_name.text().strip() or "哈Gemi"
        speaker.speak_async(f"主人你好呀！我是你的桌面专属猫娘{name}喵~")

    def _open_log_file(self):
        log_f = getattr(self.logger, "log_file", "")
        if log_f and os.path.exists(log_f):
            try:
                os.startfile(log_f)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法打开日志文件: {e}")
        else:
            QMessageBox.information(self, "提示", "日志文件尚未生成或暂无记录。")

    def _refresh_log_display(self):
        self.log_browser.clear()
        for item in self.logger.get_all_logs():
            self._append_log(item["time"], item["level"], item["message"])
        self.log_browser.moveCursor(QTextCursor.MoveOperation.End)

    def _clear_logs(self):
        self.logger.clear()
        self.log_browser.clear()

    def _view_memory_details(self):
        from brain.context_memory import ContextMemoryManager
        memories = ContextMemoryManager().get_all_memories()
        self.log_browser.append("<br><span style='color:#f1fa8c; font-weight:bold;'>=== 长期上下文记忆明细库 (memory.json) ===</span>")
        if not memories:
            self.log_browser.append("<span style='color:#6272a4;'>[提示] 暂无持久化记忆记录，和哈Gemi一起看视频或吐槽互动后会自动生成喵~</span>")
        else:
            self.log_browser.append(f"<span style='color:#50fa7b;'>共记录 {len(memories)} 条跨会话前情回忆：</span>")
            for idx, m in enumerate(memories):
                dt = m.get("datetime", "近期")
                scene = m.get("scene", "general")
                title = m.get("title", "桌面互动")
                text = m.get("text", "")
                self.log_browser.append(
                    f"<span style='color:#bd93f9;'>#{idx+1} [{dt}] [{scene}]</span> "
                    f"<span style='color:#8be9fd;'>{title[:25]}...</span><br>"
                    f"&nbsp;&nbsp;<span style='color:#f8f8f2;'>{text}</span>"
                )
        self.log_browser.moveCursor(QTextCursor.MoveOperation.End)

    def _open_memory_file(self):
        from app_paths import MEMORY_FILE
        if os.path.exists(MEMORY_FILE):
            try:
                os.startfile(MEMORY_FILE)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法打开记忆文件: {e}")
        else:
            QMessageBox.information(self, "提示", "记忆文件尚未生成（和哈Gemi产生互动后会自动写入本地 memory.json 喵）。")

    def _clear_memory(self):
        ret = QMessageBox.question(
            self, "清空长期记忆",
            "确定要清空所有的前情记忆吗？\n清空后哈Gemi将忘掉之前所有的视频/游戏吐槽记忆，回到最初的初见状态喵！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if ret == QMessageBox.StandardButton.Yes:
            from brain.context_memory import ContextMemoryManager
            ContextMemoryManager().clear()
            self.logger.info("用户在控制台清空了全部前情上下文记忆！")
            self.log_browser.append("<br><span style='color:#ff5555; font-weight:bold;'>[MEMORY] 长期上下文记忆已全部清空归零。</span>")
            QMessageBox.information(self, "已清空", "长期记忆已全部清空归零喵！")

    def _append_log(self, t_str: str, level: str, text: str):
        color_map = {
            "INFO": "#8ce99a",
            "CRITIQUE": "#ff79c6",
            "SCENE": "#8be9fd",
            "MEMORY": "#f1fa8c",
            "ERROR": "#ff5555"
        }
        color = color_map.get(level, "#ffffff")
        html = f"<span style='color:#6272a4;'>[{t_str}]</span> <span style='color:{color}; font-weight:bold;'>[{level}]</span> <span style='color:#f8f8f2;'>{text}</span>"
        self.log_browser.append(html)
        self.log_browser.moveCursor(QTextCursor.MoveOperation.End)

    def save_and_apply(self):
        # Gather all values
        api_provider = self.combo_provider.currentData()
        custom_api_url = self.input_api_url.text().strip() or "https://openrouter.ai/api/v1"
        key = self.input_key.text().strip()
        if key.startswith("✅ 已自动识别"):
            key = self.config_mgr.get("api_key", "")
        model = self.combo_model.currentText().strip()
        vertex_project_id = self.input_vertex_project.text().strip()
        vertex_location = self.combo_vertex_loc.currentText().strip() or "global"
        vertex_credentials_file = self.input_vertex_creds.text().strip()
        auto_mode = self.chk_auto.isChecked()
        cooldown = self.slider_cooldown.value()
        comment_games = self.chk_game.isChecked()
        comment_videos = self.chk_video.isChecked()
        comment_work = self.chk_work.isChecked()
        enable_persistent_memory = self.chk_memory.isChecked()

        antigravity_cli_path = self.input_agy_path.text().strip()

        enable_tts = self.chk_tts.isChecked()
        tts_engine = self.combo_tts_engine.currentData() or "edge_tts"
        tts_voice = self.combo_voice.currentData()
        if tts_voice == "custom":
            tts_voice = self.input_custom_voice.text().strip() or "zh-TW-HsiaoChenNeural"
        tts_rate = f"{self.slider_rate.value():+d}%"
        tts_pitch = f"{self.slider_pitch.value():+d}Hz"
        tts_api_url = self.input_tts_url.text().strip()
        tts_api_key = self.input_tts_key.text().strip()
        tts_model = self.input_tts_model.text().strip()

        target_height = self.slider_height.value()
        tencent_secret_id = self.input_tencent_secret_id.text().strip()
        tencent_secret_key = self.input_tencent_secret_key.text().strip()

        pet_name = self.input_name.text().strip() or "哈Gemi"
        c_raw = self.input_catchphrases.text().replace("，", ",")
        catchphrases = [c.strip() for c in c_raw.split(",") if c.strip()]
        if not catchphrases:
            catchphrases = ["喵~", "喵？！", "哼~", "盯——"]

        persona_style = self.combo_persona.currentText()
        custom_prompt = self.txt_custom_prompt.toPlainText().strip()

        outfits = {emo: card["filename"] for emo, card in self.outfit_cards.items()}

        # Save to config
        new_cfg = {
            "api_provider": api_provider,
            "custom_api_url": custom_api_url,
            "api_key": key,
            "vertex_project_id": vertex_project_id,
            "vertex_location": vertex_location,
            "vertex_credentials_file": vertex_credentials_file,
            "model": model,
            "tencent_secret_id": tencent_secret_id,
            "tencent_secret_key": tencent_secret_key,
            "auto_mode": auto_mode,
            "cooldown_seconds": cooldown,
            "comment_on_games": comment_games,
            "comment_on_videos": comment_videos,
            "comment_on_work": comment_work,
            "enable_persistent_memory": enable_persistent_memory,
            "antigravity_cli_path": antigravity_cli_path,
            "enable_tts": enable_tts,
            "tts_engine": tts_engine,
            "tts_voice": tts_voice,
            "tts_rate": tts_rate,
            "tts_pitch": tts_pitch,
            "tts_api_url": tts_api_url,
            "tts_api_key": tts_api_key,
            "tts_model": tts_model,
            "target_height": target_height,
            "pet_name": pet_name,
            "catchphrases": catchphrases,
            "persona_style": persona_style,
            "custom_system_prompt": custom_prompt,
            "outfits": outfits
        }
        self.config_mgr.save(new_cfg)

        # Autostart
        self.config_mgr.set_autostart(self.chk_autostart.isChecked())

        # Notify running app
        self.settings_applied.emit()
        self.logger.info("用户保存并应用了新的控制台设置！")

        QMessageBox.information(self, "已保存", "设置已成功保存并立即同步至桌面桌宠！")
