# Application icon / 应用图标

`app-icon.png` is the transparent high-resolution master. `app-icon.icns` is
used by the macOS bundle; `web/app-icon.png` is the browser favicon.
Run `bash packaging/build-icons.sh` to regenerate the derived sizes with
macOS `sips` and `iconutil`. The release build runs this automatically.

`app-icon.png` 为透明背景高清原图；`.icns` 用于 macOS 应用，网页使用
`web/app-icon.png`。打包时自动生成各尺寸，也可单独运行上述脚本。

Created using the built-in image generation tool (imagegen skill). No existing
third-party icon or trademark was used as a reference.

## Generation prompt

Use case: logo-brand. Asset type: production macOS application icon, one square 1024x1024 image. Create an original polished icon for Multitrack Audio Exporter, a local professional audio track processing app. A dark graphite/green rounded-square tile with subtle bevel and restrained soft lighting. Central bold luminous lime-yellow (#D2F26C) emblem: three clearly separated horizontal audio waveform lanes, each with a handful of thick vertical rounded bars, integrated with a simple bold right-facing export arrow on the right. Clean precise geometry, balanced silhouette, highly legible at 32px, not a detailed DAW screenshot. Front-facing, not tilted. Tile centered with modest equal transparent margin on all sides (approximately 8%); outside tile genuinely transparent. No text, no letters, no numerals, no musical note, no brand trademarks, no watermark. Restrained premium macOS aesthetic, strong contrast, no busy fine detail, no exaggerated glow, no surrounding scene. Single icon only, no contact sheet.
