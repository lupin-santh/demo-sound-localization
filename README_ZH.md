[English](README.md)

# 声向 · Sound Direction

面向 **Quectel PI M2** 与 **Quectel VA60X-GL** 六麦阵列板的本地人声方向定位和中英文离线转写应用。

当前默认模式在人声方向积累约 0.16 秒有效证据后更新实时指针，无需等待转写。持续检测到人声时，即使短暂缺少有效定位帧，也会保留最近的稳定指向；人声结束后再短暂保持。SenseVoice 在后台识别并为文字附上该段方向；方向未知时界面只显示转写文字。音频和转写均在本机处理，不上传。

![Sound Localization v2.0 应用界面](images/sound-localization-v2.0.png)

## 当前能力

- VA60X-GL 八通道 USB 音频自动检测，USB VID:PID 为 `0bda:4cf0`；不依赖固定 ALSA 卡号。
- 六个物理麦克风参与 GCC-PHAT / SRP 水平方位估计；空通道与回采通道不参与定位。
- 三路分散麦克风的 WebRTC VAD 多数投票，用于确认人声和切分语句。
- SenseVoice INT8 离线识别；当前配置固定为中文 `zh`，可改为 `auto` 自动判断模型支持的语言。
- 实时人声方向使用短时圆周平均、±55° 方向锁、大跳变确认和结束后 0.4 秒保持。
- 锁外候选方向无需等待 VAD 静音即可交接，但至少需要 0.4 秒证据、占近期合格方向帧 75%，且圆周一致性达到 0.85；旧方向最近 0.25 秒至多 1 帧时放宽为 0.80。
- 一句话结束后另行汇总该段方向，量化为默认 30° 扇区并附在转写前，例如 `[方向约 060° ±15°] 你好`。
- 中英文界面即时切换；保存按钮持久化界面语言和基础电平门限。
- USB 重插或声卡号变化后，可在界面点击“重新检测设备”。
- 提供真实采集探测、八通道 WAV 回放和合成演示模式。

## 硬件与通道

当前固件采集格式为 **8 通道、16 kHz、16 位有符号 PCM、交错采样**。硬件说明使用 1 起始通道号，程序配置使用 0 起始索引：

| 物理位置 | 硬件通道 | 程序索引 | 用途 |
| --- | ---: | ---: | --- |
| MIC_1 | 1 | 0 | 定位、VAD、默认 ASR |
| MIC_2 | 5 | 4 | 定位 |
| MIC_4 | 6 | 5 | 定位、VAD 投票 |
| MIC_5 | 2 | 1 | 定位 |
| MIC_6 | 3 | 2 | 定位、VAD 投票 |
| MIC_8 | 4 | 3 | 定位 |
| 空 | 7 | 6 | 不使用 |
| 回采 | 8 | 7 | 不使用 |

因此 `channels` 必须保持为 `8`，六麦的物理环形顺序配置为：

```json
"mic_channels": [0, 4, 5, 1, 2, 3]
```

算法暂按 MIC_1、MIC_2、MIC_4、MIC_5、MIC_6、MIC_8 顺时针、间隔 60° 建模，并把 MIC_1 径向定义为 0°。这只是软件坐标系，不等于设备安装后的“正前方”。实际安装后应从已知方向发声进行标定：用 `angle_offset_deg` 修正整体旋转，角度增大方向相反时设置 `mirror: true`。当前 `radius_m: 0.035` 是依据板形尺寸的估计值，获得精确麦克风中心坐标后应替换。

## 环境准备

全新开发板先克隆源码仓库，再按[全新开发板部署说明](docs/deployment.md)单独下载 SenseVoice 模型。模型就位后，在项目根目录运行 `bash scripts/deploy.sh`。

在 PI M2 图形桌面的终端中执行：

```bash
git clone <repository-url> demo-sound-localization
cd demo-sound-localization
# 按 docs/deployment.md 单独下载并解压模型
bash scripts/deploy.sh
```

源码仓库不分发 SenseVoice INT8 模型。部署脚本不会下载模型，只会校验单独准备的模型文件并安装运行环境。

应用规范模型目录为：

```text
models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/
├── model.int8.onnx   # 必需
└── tokens.txt        # 必需
```

为兼容旧项目迁移，如果规范目录不存在，当前代码还会查找相邻的 `../sound_loca_demo/models/` 下同名目录。新部署应把单独下载的模型解压到当前项目的规范 `models/` 目录。

只有 SSH 终端而没有图形会话时，GUI 无法打开；可先用 `--probe` 验证采集。

## 运行与诊断

```bash
bash run.sh                         # 完整 GUI：定位、VAD、离线转写
bash run.sh --probe --seconds 5     # 无界面采集诊断，输出 JSON
bash run.sh --no-vad --no-asr      # 不加载可选依赖的实时定位界面
bash run.sh --wav recording.wav    # 回放 8ch/16kHz/S16_LE PCM WAV
bash run.sh --demo                 # 合成方向演示，不启用 VAD/ASR
bash test.sh                       # 运行全部单元与集成测试
```

`run.sh` 会优先使用项目 `.venv`。若缺少 WebRTC VAD 或 SenseVoice，它会打印提示并关闭相应功能，而不是静默失败。

设备基础检查：

```bash
cat /proc/asound/cards
arecord -l
bash run.sh --probe --seconds 5
```

不要把一次枚举出的 `hw:3,0` 长期写死；USB 重插后卡号可能变化。默认的 `device: auto` 会按 VID:PID 重新解析设备。

## 一句话的方向如何产生

每个 512 采样块约 32 ms，定位器在 250–4000 Hz 语音频段对六麦的 15 个麦克风对做 GCC-PHAT 延时估计，并以 2° 步长扫描 0–358°。只有同时满足以下条件的块才进入该句话的方向汇总：

1. VAD 多数投票认为当前有人声；
2. 语音频段电平和相对噪声的信噪比通过检查；
3. 六麦综合电平达到基础硬门限 `gate_dbfs`；
4. 当前方向评分达到 `min_confidence`。

实时指针只使用最近 0.25 秒的有效人声方向；累计至少 0.16 秒且方向集中程度达到 0.7 时出现。一段连续语音内，短暂 VAD 掉票可保持 0.45 秒；普通更新使用当前锚点 ±55° 内的帧。锁外帧进入独立的 0.55 秒交接窗口，不会直接推动旧指针。交接至少需要 0.4 秒候选证据、占同期合格方向帧 75%，且圆周一致性达到 0.85；旧方向最近 0.25 秒至多出现 1 帧合格证据时，一致性门槛放宽为 0.80。低于 3 dB 的已校准信噪比帧不更新指针；确认语音结束后再保持 0.4 秒。

转写条目的方向独立按整段有效时长和评分做圆周加权平均。当前配置要求：有效方向累计至少 0.2 秒、覆盖语音时长至少 30%、圆周集中程度至少 0.7。通过后，结果四舍五入到最近的 30° 扇区；例如 68° 显示为 `60° ±15°`，352° 显示为 `0° ±15°`。说话者移动时，当前指针与已完成片段的方向可能不同。

低于基础门限的语音仍可进入 ASR；方向未知时，界面只显示转写文字，终端默认输出方向证据诊断。将 `direction_unknown_log_enabled` 设为 `false` 可关闭该日志。

## 门限调节

首次启动后先安静 2–3 秒，让程序学习稳定噪声频谱，再以正常音量从预期距离说话。将基础门限放在环境声之上、正常语音之下。例如环境约 -45 dBFS、语音约 -32 dBFS时，可从 -39 至 -37 dBFS开始尝试。

- 更负的值（如 -40）更灵敏，也更容易接收噪声。
- 更接近 0 的值（如 -30）更严格，也更容易得到“方向未知”。
- 粉色标线是当前基础门限；点击“保存”写入 `config.json`。
- 自适应人声门限只辅助 VAD，不会替代 `gate_dbfs` 这个方向证据硬门限。

## 为什么出现“方向未知”

这不是单一错误，而是方向证据没有通过完整判定链。按以下顺序排查：

1. 用 `--probe` 确认六个有效通道都有合理电平，程序索引 6、7 不应被当作麦克风。
2. 正常说话时若综合电平经常低于当前 `gate_dbfs: -40`，可小幅调整门限并观察方向显示是否改善。
3. 短词可能达不到 `asr_direction_min_seconds: 0.2`；连续说完整一句再比较。
4. 混响、多个人同时说话、播放声和移动声源会降低 `asr_direction_min_consistency: 0.7`。
5. 说话片段中有效定位过少会低于 `asr_direction_min_coverage: 0.3`。
6. 通道顺序、0° 方位或顺逆时针假设错误时，先做几何标定，不要用降低一致性门限掩盖映射问题。

需要调试时一次只修改一个参数，并保留同一距离、同一方向和近似音量作为对照。

## 配置速查

| 参数 | 默认值 | 作用 |
| --- | ---: | --- |
| `device` | `auto` | 按 USB VID:PID 自动寻找 ALSA 设备；也可临时指定 `hw:CARD,DEV` |
| `ui_language` | `zh` | 界面语言：`zh` 或 `en`，不改变识别语言 |
| `usb_vid_pid` | `0bda:4cf0` | 当前已验证固件的 USB 标识 |
| `rate` / `channels` | `16000` / `8` | 采样率与采集通道数 |
| `frame_size` | `512` | 每个定位块的每通道采样数 |
| `mic_channels` | `[0,4,5,1,2,3]` | 六麦按物理环形顺序排列的程序索引 |
| `radius_m` | `0.035` | 麦克风环半径估计值，单位米 |
| `gate_dbfs` | `-40` | 语句方向证据的基础硬门限 |
| `min_confidence` | `0.2` | 单块方向评分门限；是启发式分数，不是正确率 |
| `angle_offset_deg` | `0` | 显示方向整体旋转角度 |
| `mirror` | `false` | 翻转角度增长方向 |
| `hold_seconds` | `0.55` | 无 VAD 或演示模式使用的原有跟踪器保持时间 |
| `live_direction_window_seconds` | `0.25` | 实时人声方向的滚动观察窗口 |
| `live_direction_min_seconds` | `0.16` | 首次显示实时方向所需的有效音频时长 |
| `live_direction_min_consistency` | `0.7` | 实时窗口内的最小方向集中程度 |
| `live_direction_hold_seconds` | `0.4` | 确认语音结束后的短时保持 |
| `live_direction_speech_gap_seconds` | `0.45` | 允许连续说话中短暂 VAD 掉票的时长 |
| `live_direction_jump_confirm_seconds` | `0.35` | 大角度跳变需稳定持续的时长 |
| `live_direction_min_snr_db` | `3.0` | 已建立噪声模型时，实时方向帧的最低信噪比 |
| `live_direction_lock_degrees` | `55.0` | 连续语音期间相对首次方向的最大允许偏移 |
| `live_direction_handoff_window_seconds` | `0.55` | 锁定范围外候选方向的观察窗口 |
| `live_direction_handoff_min_seconds` | `0.4` | 确认新方向至少需要的有效音频时长 |
| `live_direction_handoff_min_consistency` | `0.85` | 新方向候选的最小圆周集中程度 |
| `live_direction_handoff_relaxed_consistency` | `0.8` | 旧方向近期缺少合格帧时的交接一致性门槛 |
| `live_direction_handoff_min_share` | `0.75` | 新方向证据占近期合格方向证据的最低比例 |
| `live_direction_handoff_old_evidence_window_seconds` | `0.25` | 判断旧方向近期合格帧的观察窗口 |
| `live_direction_handoff_old_evidence_max_frames` | `1` | 使用宽松门槛时，窗口内允许的旧方向合格帧数上限 |
| `vad_mode` | `2` | WebRTC VAD 严格度，范围 0–3，数值越大越严格 |
| `vad_channel` | `0` | 三路 VAD 选点的起始物理麦克风 |
| `asr_language` | `zh` | 当前固定中文；也可设为 `auto` 或 `en` |
| `asr_channel` | `0` | ASR 使用的原始程序通道索引 |
| `asr_pre_roll_seconds` | `0.3` | 人声触发前保留音频 |
| `asr_silence_seconds` | `0.6` | 判定句尾的连续静音 |
| `asr_min_speech_seconds` | `0.24` | 丢弃过短触发片段的下限 |
| `asr_max_seconds` | `5` | 单个识别片段最大时长；允许配置到 30 秒 |
| `asr_direction_min_seconds` | `0.2` | 一句话所需的最短有效方向时长 |
| `asr_direction_min_coverage` | `0.3` | 有效方向占语音时长的最低比例 |
| `asr_direction_min_consistency` | `0.7` | 句内方向圆周集中程度下限 |
| `direction_unknown_log_enabled` | `true` | 是否在终端输出方向未知的详细诊断 |
| `direction_sector_deg` | `30` | 实时指针范围和转写方向扇区宽度，当前为 ±15° |

## 常见问题

### `Capture error: overrun` / `xrun: prepare error: Input/output error`

这表示 ALSA/USB 采集缓冲未被及时读取，随后驱动恢复失败。常见原因是 USB 链路不稳、设备被另一进程占用、重插后仍使用旧卡号，或系统负载导致调度延迟。先关闭其他录音进程，重新插拔阵列板，然后点击“重新检测设备”；仍失败时检查：

```bash
fuser /dev/snd/*
cat /proc/asound/cards
bash run.sh --probe --seconds 5
```

### ASR 不打印或界面一直没有文字

启动日志若提示 SenseVoice 不可用，检查 `.venv`、`requirements-asr.txt` 与模型目录；按部署文档下载或校验模型后，再运行：

```bash
.venv/bin/python scripts/transcribe.py \
  --file models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/test_wavs/zh.wav
```

后台识别队列最多等待两段语音；计算繁忙时新片段会被跳过，以免阻塞持续采集。正常运行只在内存中保留最近 20 条转写，不把录音或文本写入磁盘。

### 独立 WAV 转写

```bash
.venv/bin/python scripts/transcribe.py --file your.wav --channel 0 --segment
```

接受单声道或多声道 16 位 PCM WAV；长录音应加 `--segment`。单声道文件没有阵列几何信息，因此只转写、不计算方向。

## 项目结构

- `sound_direction/`：采集、定位、人声检测、ASR、界面与翻译模块。
- `tests/`：单元测试及可选的真实模型集成测试。
- `docs/`：全新开发板部署说明。
- `README.md`：英文主项目说明。
- `src/app.py`：桌面应用与探针入口。
- `scripts/`：开发板部署与独立 WAV 转写工具。
- `run.sh` / `test.sh` / `env.sh`：启动、测试和环境脚本。
- `config.json`：硬件、定位、VAD、ASR 与显示参数。

硬件依据：Quectel VA60X-GL 用户手册 V1.0.0 Preliminary（2026-03-06）及当前固件实测 USB/ALSA 描述。

## 技术支持

如在使用过程中遇到问题，欢迎在[移远官方论坛](https://forumschinese.quectel.com/c/quectel-pi/58)提交技术咨询，移远技术支持团队将及时为您解答。
