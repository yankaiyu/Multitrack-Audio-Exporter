# Changelog

## Unreleased

### Added

- Optional per-track transient control (off by default), 0–12 dB drive, same-position before/after audition, measured maximum gain reduction and limited-time percentage. Processing uses a stereo-linked 5 ms lookahead / 50 ms release-time-constant gain envelope relative to the trimmed, locally edited signal's peak; 0 dB bypasses. Bounded-memory double-float processing preserves headroom above 0 dBFS until final normalization/encoding, without shifting audio. It affects export independently of preview-gain settings; audition remains before final normalization and retains preview gain/limiter settings. Trim or local-edit changes require reapplying the effect; stale previews cannot be played/exported as if current. Added synthetic float, flat-top, silence, short-file, stereo, timing, preview/export parity and browser regressions. All seven locales updated.
- Remembered, opt-in audible-track selection on waveform load. It takes precedence over reused selections, uses the existing empty-track threshold, and still allows manual overrides. Enabling it on loaded tracks applies immediately; later threshold changes do not silently replace manual selections.
- Added a custom multitrack-waveform/export icon for the macOS app and browser tab, with reproducible native icon-size generation during packaging.
- Optional conservative peak detection within selected trim ranges, review markers, original/edited audition, adjustable local gain/ranges and undo. Confirmed edits use the same smooth float envelope in preview and export, before normalization, independently of preview-volume export settings.
- Reuse the previous track-selection mask by list position for matching track counts (including exports without reloading waveforms); count mismatches default to all selected and stereo-split changes reset the mask. Trims, gains and edits are not transferred.
- Ignore stale waveform responses after folder changes. Added synthetic peak/edit/export regressions and UI coverage.
- The packaged app now appears in the Dock, handles reopening the browser, and cleans up its server on native Quit / ⌘Q.
- Added a separate self-contained Apple Silicon macOS 26+ app/ZIP build with bundled Python, FFmpeg and FFprobe; retained the source distribution and its dependency setup.

- Support for WAV, AIFF, FLAC, MP3, M4A, and AAC input.
- MP3, M4A (AAC), and selectable 32-bit float, 24-bit PCM, or 16-bit PCM WAV output.
- Waveform preview, direct waveform-marker dragging for shared and individual trim, single-track trim audition, track selection, and audible-track selection.
- ZIP share packages, per-job progress, and selectable per-job track concurrency.
- English, Simplified Chinese, Traditional Chinese, Japanese, Spanish, French, and Korean interface.
- Locale files are discovered automatically, so a new complete JSON locale adds a UI language.
- Optional stereo-to-independent-mono splitting with separate waveform preview, trim, and export for left/right channels.
- Per-track preview volume from −60 dB to +12 dB and an optional playback limiter for safer 32-bit float auditioning. The limiter is enabled on first launch and remembers the last choice.
- Original-level export mode skips normalization and can apply each track’s preview volume gain.
- Replaced the standalone safe-level mode with independent toggles for applying preview gains and enforcing the safety ceiling.
- Added −0.1 dBFS and −0.3 dBFS final output safety-ceiling options for WAV, MP3, and M4A exports.
- Added an abort button for running exports and a remembered option to open the output folder in Finder when complete.
- Added linked or independent preview playheads, synchronized multi-track playback, and playhead reset controls.
- Added per-track preview mute/unmute controls; muted preview tracks are exported muted only when preview-volume export is enabled.

### Safety and behavior

- 32-bit float samples above 0 dBFS are measured and safely reduced before encoding.
- NaN and Infinity samples are replaced before analysis or export.
- Generated outputs are peak-checked and retried at a lower gain when necessary.
- Exports from the same source folder are serialized to protect output files.

---

# 更新日志

## 未发布

### 新增

- 增加默认关闭的逐轨瞬态控制：0–12 dB 驱动增益、同位置处理前后试听、实测最大降幅和限幅时间占比。以裁剪及局部修正后的峰值为参考，采用立体声联动、5 毫秒前瞻和 50 毫秒释放时间常数的增益包络；0 dB 直接旁路。使用内存有界的双精度浮点处理，在最终标准化/编码前保留超过 0 dBFS 的余量，不移动音频时序。此功能独立于试听增益选项，会应用到导出；试听处于最终标准化之前，仍受试听音量/限幅器影响。修改裁剪或局部修正后需重新应用，防止使用过期试听结果。新增合成浮点、平顶瞬态、静音、短文件、立体声、时序、试听/导出一致性和浏览器回归测试；更新全部七种语言。
- 增加可记忆的“加载波形后自动只选有声轨道”开关，初次默认关闭。开启时优先于上一组勾选，使用现有底噪阈值，并允许手动改选。已有波形时开启会立即筛选；之后调整阈值不会静默覆盖手动勾选。
- 增加多轨波形与导出箭头应用图标，用于 macOS 应用和网页标签页；打包时通过原生工具自动生成各尺寸。
- 可选的保守峰值检测：仅检查已选轨道的裁剪范围，提供标记、原始/处理后试听、局部增益与范围调整及撤销。确认后的处理在试听和导出中共用平滑浮点增益包络，先局部降幅再标准化，不受试听音量导出设置影响。
- 相同轨道数量时，按列表位置沿用上一组勾选（未重新加载波形时导出也适用）；数量不同默认全选，改变立体声拆分会重置。裁剪、音量和局部处理不会跨文件夹继承。
- 切换文件夹后忽略过期波形请求；增加合成音频的峰值、局部处理、导出与界面回归测试。
- 打包应用显示 Dock 图标，支持再次打开网页，并在原生退出 / ⌘Q 时清理后台服务器。
- 增加内置 Python、FFmpeg 和 FFprobe 的 Apple Silicon macOS 26+ 应用/ZIP 构建；继续保留源码版及依赖配置流程。

- 支持 WAV、AIFF、FLAC、MP3、M4A、AAC 输入。
- 支持 MP3、M4A（AAC）输出，以及可选 32-bit float、24-bit PCM、16-bit PCM WAV 输出。
- 支持波形预览、直接拖动波形标记进行裁剪、轨道选择和只选择有声轨道。
- 支持 ZIP 分享包、任务进度和单任务内轨道并发设置。
- 提供英文、简体中文、繁体中文、日文、西班牙语、法语与韩文界面。
- 支持每轨 −60 dB 至 +12 dB 的试听音量，以及可选试听限幅器，方便安全试听 32-bit float 音频。首次打开时默认开启，并记住上次选择。
- 增加“不做标准化”导出模式：跳过标准化，并可将每轨试听增益应用到导出文件。
- 将单独的安全音量模式改为两个独立选项：是否应用试听增益，以及是否确保通过安全峰值检测。
- 明确安全峰值选项适用于所有标准化模式：关闭时仍使用所选峰值作为初始目标，仅跳过最终复检和重试。
- 增加 −0.1 dBFS 和 −0.3 dBFS 最终输出安全峰值选项，适用于 WAV、MP3 和 M4A 导出。
- 增加转换中的取消按钮，以及完成后自动在 Finder 中打开输出文件夹的记忆选项。
- 增加联动或独立试听播放头、同步多轨试听和播放头重置控制。
- 增加每轨试听静音/取消静音按钮；只有启用“将试听音量应用到导出”时，试听静音状态才会影响导出。

### 安全与行为

- 会测量高于 0 dBFS 的 32-bit float 信号，并在编码前安全降低。
- 在分析或导出前替换 NaN 与 Infinity 样本。
- 对生成文件检查峰值；必要时以更低增益重新编码。
- 同一源文件夹的任务会串行处理，保护输出文件。
