# 哈Gemi (Desktop Gemini Girl)

> **元气毒舌的 AI 桌面陪伴桌宠 · 实时视觉多模态屏幕感知 · 少女音锐评吐槽**  
> 支持 **Google Gemini 官方原生接口 (AI Studio)**、**Google Cloud Vertex AI (GCP 算力/赠金通道，支持 Gemini 4 Argon)**、**Google Antigravity 订阅通道 (免Key/烧会员额度)** 与 **OpenRouter / OpenAI 兼容自定义接口**。

---

## 核心特性

- **全局屏幕多模态感知**：
  - 自动识别当前活跃窗口，针对不同场景智能唤醒多模态视觉推理：
    - **游戏战况锐评**：识别逆风劣势、逆天死法与下饭操作，毒舌不留情！
    - **视频与直播接梗**：深度参与 UP 主台词与弹幕互动，弹幕接梗妙语连珠！
    - **码字与工作摸鱼抓包**：报错抓现行、代码发呆吐槽、摸鱼立刻警告！
- **多模型与多服务商全渠道支持**：
  - **Google Antigravity 订阅通道 (全新！免Key/烧会员额度)**：
    - 针对有 Antigravity 会员订阅的开发者量身打造，**无需申请或配置任何 API Key**；
    - 自动复用本机已登录的 Google Antigravity 会员凭证（支持 `google-antigravity` Python SDK 与 `agy` 原生 CLI 双通道桥接）；
    - 支持 `gemini-3.8-flash-high`、`claude-sonnet-4-6`、`claude-opus-4-6-thinking` 等顶级订阅模型；
    - 彻底远离 AI Studio 429 免费池排队限流，也无需担心 Vertex AI 产生意外账单扣费，真正实现“桌宠整天挂机随心烧会员算力”。
  - **Google Cloud Vertex AI (GCP 算力/赠金通道)**：
    - 针对 AI Studio 高峰期频繁忙碌 (429 / Resource Exhausted) 的高可用解决方案；
    - 完整支持 **`gemini-4-argon`**（Google 最新旗舰推理与 Agent 思考大模型）、`gemini-2.5-flash`、`gemini-2.5-pro` 等；
    - 默认采用 `global` 全球调度区域（自动跨地区负载均衡，超高可用与抗并发）；
    - 支持三种免折腾认证方式：**GCP 服务账号 JSON 密钥文件**、**本地 gcloud CLI / ADC 自动免密读取**、或 **Vertex API Key / Bearer Token**；
    - 自动过滤思考模型的思维链路（Thought/Reasoning），保证桌宠气泡播报纯净灵动。
  - **Google Gemini 原生 (AI Studio)**：内置 `gemini-3.8-flash`、`gemini-2.5-flash`、`gemini-1.5-pro` 等标准 API 接口；
  - **OpenRouter / OpenAI 兼容接口**：支持自定义 API URL（如 OpenRouter、OneAPI、第三方中转站），自由填入 `anthropic/claude-3.5-sonnet`、`openai/gpt-4o`、`deepseek/deepseek-chat` 等视觉大模型。
- **表情工坊与立绘差分**：
  - 内置 4 套情绪立绘差分（自信傲娇、呆萌疑惑、抱头震惊、无语擦汗）；
  - 根据 AI 评论的情绪标签（`[shocked]`、`[curious]`、`[relieved]`、`[confident]`）全自动无缝切换立绘姿态；
  - **支持本地上传任意立绘**：内置智能去白底抠图算法，任意白底 JPG/PNG 自动秒转透明背景立绘。
- **自适应漫画气泡框**：
  - 纯白可爱圆角漫画气泡框配黑色粗体字体，自带萌系小尾巴；
  - 动态预计算尺寸，根据长短句自动缩放，逐字打字机动效，支持右上角一键关闭与自由拖拽。
- **Edge-TTS 萝莉/少女音播报**：
  - 集成微软高品质神经语音（晓伊、晓晓、云健等），吐槽文字同步语音播报；
  - 支持随时快捷键一键静音。
- **现代化独立 GUI 控制台与系统托盘**：
  - 完整的管理中心（核心感知设置、立绘工坊、口癖与人设调教、实时运行流水日志）；
  - 支持 Windows 开机自启、托盘小图标双击唤出、桌宠右键菜单。
- **安全与隐私保护**：
  - 密钥纯本地存储在 `config.json` 中，绝不上报任何云端服务器；
  - 拥有专属“桌宠自免盾”，永远不会检索或锐评自己与控制台窗口。

---

## 常用快捷键

| 快捷键 / 交互 | 功能说明 |
| :--- | :--- |
| **`Ctrl + F9`** 或 **双击桌宠** | 立即召唤哈Gemi对当前屏幕/窗口进行视觉锐评 |
| **`Ctrl + F10`** | 切换语音播报（开启 / 静音） |
| **`Ctrl + F1`** | 开始录音；再次按下后停止并通过腾讯云识别，识别文字会发送给桌宠 |
| **`Ctrl + F11`** 或 **鼠标滚轮滑动立绘** | 瞬间循环切换下一个立绘姿态/表情差分 |
| **鼠标中键点击桌宠** | 快速切换立绘姿态 |
| **右键点击桌宠** / **双击托盘图标** | 打开【控制台与设置中心】 |
| **点击气泡右上角 `×`** | 快速关闭当前说话气泡 |

---

## 快速上手

### 方式一：源码运行（开发者）

1. **克隆仓库并安装依赖**：
   ```bash
   git clone https://github.com/LYW199911/DesktopGeminiGirl.git
   cd DesktopGeminiGirl
   pip install -r requirements.txt
   ```

2. **配置 API 渠道**：
   - 复制配置模板：
     ```bash
     cp config.example.json config.json
     ```
   - 运行桌面宠：
     ```bash
     python main.py
     # 或直接双击运行 start_pet.bat
     ```
   - 启动后右键桌宠或双击右下角托盘图标，在【核心与感知】中选择你的接口类型：
     - **Google Antigravity 订阅通道 (推荐)**：
       1. 零配置，无需填任何 Key；
       2. 模型可选 `gemini-3.8-flash-high`、`claude-sonnet-4-6` 等；
       3. 点击【测试连接】即可直接使用本机 Antigravity 会员配额！
     - **Google Cloud Vertex AI (GCP 算力/赠金)**：
       1. 区域推荐 `global`，模型推荐 `gemini-4-argon`（体验最新思考推理大模型）或 `gemini-2.5-flash`；
       2. 填入 GCP 项目 ID；
       3. 认证方式任选其一：点击【浏览】选择 GCP 服务账号 JSON 密钥文件（需在 GCP IAM 赋予 `Vertex AI User` 权限），或若本地已登录 gcloud 则直接留空凭据即可自动识别！
     - **Google Gemini 官方原生接口 (AI Studio)**：填入 AI Studio API Key 即可。
     - **OpenRouter / OpenAI 兼容接口**：填入 URL 与 Key。
   - 点击【测试连接】并保存即可！
   - 若使用语音输入，还需在同一设置页填写腾讯云 `SecretId` 和 `SecretKey`，并在腾讯云控制台开通语音识别。

### 方式二：单机 EXE 一键打包

如果你想打包免安装独立版本发布给朋友：
```bash
# 执行打包脚本
build_exe.bat
```
打包成功后，可在 `dist/Ha-Gemi/` 目录下找到 `Ha-Gemi.exe`。

---

## 目录结构

```text
DesktopGeminiGirl/
├── assets/                     # 桌宠立绘、图标与表情差分
│   ├── app_icon.ico            # 托盘与窗口图标
│   ├── avatar_standing.png     # 傲娇自信立绘
│   ├── avatar_bust.png         # 疑惑Q版立绘
│   ├── avatar_shocked.png      # 震惊表情
│   └── avatar_relieved.png     # 害羞擦汗表情
├── brain/                      # AI 推理大脑
│   ├── gemini_client.py        # Gemini 原生 / Vertex AI / Antigravity 订阅 / OpenRouter 调度引擎
│   ├── prompts.py              # 元气毒舌人设与多场景提示词构建
│   └── rate_limiter.py         # 智能感知冷却与场景限流器
├── perception/                 # 屏幕与桌面环境感知
│   ├── window_tracker.py       # 前台活跃窗口与游戏/视频/代码场景分类识别
│   ├── screen_capture.py       # 高性能局部/全屏屏幕截图与多模态图像压缩
│   ├── tencent_asr.py          # 腾讯云一句话语音识别
│   └── hotkey_listener.py      # 全局键盘全局快捷键监听 (pynput)
├── tts/                        # 语音播报模块
│   └── edge_speaker.py         # 微软 Edge-TTS 异步语音生成与播放
├── ui/                         # 界面与交互设计
│   ├── bubble_widget.py        # 自适应防塌陷漫画白气泡框
│   ├── pet_widget.py           # 悬浮桌宠挂件（支持拖拽、右键菜单、悬浮晃动）
│   ├── settings_window.py      # 全功能 GUI 设置中心 (含 Vertex AI、Antigravity 会员与各渠道配置)
│   ├── tray_icon.py            # Windows 系统托盘菜单
│   └── img_utils.py            # 智能白色背景抠图转换工具
├── config_manager.py           # 配置读取保存与 Windows 注册表自启管理
├── log_manager.py              # Qt 线程安全日志系统
├── app_paths.py                # PyInstaller 冻结路径解析
├── main.py                     # 程序入口与生命周期管理
├── config.example.json         # 配置文件示例（不含敏感 API Key）
├── requirements.txt            # Python 运行环境依赖
├── build_exe.bat               # PyInstaller 一键编译脚本
└── start_pet.bat               # Windows 一键启动脚本
```

---

## 隐私与安全性

- **无隐私上传**：所有的配置、立绘和音频缓存均保存在本地计算机上；
- **透明开源**：代码 100% 开源，API 请求直连官方或你指定的 API 代理，不经过任何中间遥测收集服务器。

---

## 鸣谢与版权致谢 (Credits)

- **桌宠立绘与表情差分出处**：感谢 B 站 UP 主 **[@Xx勿忘xX](https://space.bilibili.com/25914748)** 制作并分享的 Gemini 表情包与立绘差分（动态专栏原帖：[⭐Gemini⭐分享几个Gemini的表情包和立绘无耳差分](https://www.bilibili.com/opus/1264669110489317411)）。
- **原立绘人设原创**：原版 Gemini 娘人设与主立绘出处为画师大佬 **@zipzip**。
- **开源生态**：感谢 PyQt6、Edge-TTS 与 Google Gemini 提供的强大生态支持。
