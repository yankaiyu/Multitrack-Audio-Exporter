# Apple Silicon build / Apple Silicon 打包

The source distribution (`start.command`, Homebrew setup and uninstall) remains supported. This build adds a separate app ZIP; it does not replace that workflow.

Build on an arm64 Mac running macOS 26+ with Xcode Command Line Tools, Python 3 and pkg-config. Run from the repository:

```bash
bash packaging/build-arm64.sh
```

The build downloads checksum-pinned FFmpeg 8.1.2 and LAME 3.100 sources, builds static libraries, bundles them with Python using PyInstaller, audits library paths and arm64 architecture, then runs a synthetic over-0-dBFS conversion/waveform smoke test with Homebrew removed from PATH. Build dependencies are installed into `.build-venv`; outputs go into `dist`.

The initial compatibility floor is macOS 26, not all macOS versions supported by M1 hardware. Test on a clean Mac before declaring wider compatibility. Developer ID signing and notarization are intentionally absent. PyInstaller's automatic local ad-hoc signature is required by Apple Silicon and needs no developer account.

Upload the ZIP and `SHA256SUMS.txt` to a GitHub Release alongside the normal source archives. Keep binaries and build dependencies out of git. The app includes the exact FFmpeg/LAME sources, build script and license notices in `Contents/Resources/ThirdParty` (or its linked Frameworks location). Keep these with redistributed copies. A custom app icon and older-macOS builds can be added separately.

---

源码分发（`start.command`、Homebrew 安装与卸载）继续保留。本脚本额外生成独立的应用 ZIP。

在安装了 Xcode Command Line Tools、Python 3、pkg-config 的 Apple Silicon、macOS 26+ 机器上运行上述命令。编译发生在维护者机器，用户无需编译。

构建会验证源码校验值、内置依赖、检查 arm64 与动态库路径，并用合成的超 0 dBFS 音频验证转换和波形。首次兼容下限定为 macOS 26，不能将 M1 支持等同于支持所有旧 macOS。发布前仍应在未安装开发环境的 Mac 上实测。

将 `dist` 内的 ZIP 和校验文件作为 GitHub Release 附件，保留源码下载。尚未使用 Developer ID 签名或公证；自动的本地 ad-hoc 签名无需账号。FFmpeg/LAME 源码、许可与构建脚本随包附带，分发时应保留。
