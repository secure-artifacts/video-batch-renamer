# 视频批量命名工具

从 Google Sheet 复制「序号 + 文案」，一键给一批视频改名。Mac / Windows 通用。

## 命名规则

新文件名 = `序号 文案.原扩展名`

- **序号**：从原文件名里抽出的数字（`clip 001` / `01` / `video-1` 都行），补零对齐
- **文案**：第 1 句取前 10 字（钩子）+ 空格 + 第 2 句起的内容，**去掉所有标点**，整体截到 50 字

例：
```
clip 001.mp4  ->  001 被选中的人不会跳过这 已经有两个人这么做了我希望你不是第三个诗篇917说虽有千人仆倒在你旁边万人仆倒.mp4
```

> 钩子只留 10 字、正文从第二句起 —— 这样即使多个视频开头文案相同，也能靠第二句（不同经文出处等）区分开。

## 怎么用

1. 点 **选择文件夹**，选中放视频的文件夹
2. 在 Google Sheet 里选中「序号」和「文案」两列一起复制，粘贴到文本框
3. 点 **预览**，核对 `原文件名 → 序号 → 新文件名` 对照表
   - 绿色「可改名」=会改；橙色=有问题（无序号 / 序号重复 / 无对应文案），不会动
4. 确认无误，点 **应用改名**
5. 改错了？点 **撤销上次** 一键还原（依赖文件夹里自动生成的 `.rename_log.json`）

## 运行环境

需要 Python 3（自带 tkinter）。

### Mac

系统自带 Python 3 一般可直接跑：
```bash
python3 video_renamer.py
```
若提示缺少 tkinter：`brew install python-tk`

### Windows

装 [Python 3](https://www.python.org/downloads/)（安装时勾选 *Add to PATH* 和 *tcl/tk*），然后双击 `video_renamer.py`，或命令行：
```cmd
python video_renamer.py
```

## 打包成免安装程序（可选）

让别人不装 Python 也能双击运行：

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name 视频批量命名 video_renamer.py
```

- 在 **Windows** 上跑这条命令 → 得到 `dist/视频批量命名.exe`
- 在 **Mac** 上跑这条命令 → 得到 `dist/视频批量命名.app`

> 注意：PyInstaller 不能跨平台打包。要 Windows 的 `.exe` 必须在 Windows 上打包，要 Mac 的 `.app` 必须在 Mac 上打包。

## 下载最新版本

直接从右侧 **Releases** 栏下载，无需懂代码：

1. 点右侧「**Releases**」→ 找到最新版（如 `v1.0.0`）
2. 在「Assets」里下载 `video-batch-renamer-v1.0.0.zip`
3. 解压后按照**怎么用**一节运行即可

> 每个发布版本均附有 **构建来源证明（Build Provenance Attestation）**，可通过 GitHub 验证文件完整性，确保下载的程序未被篡改。

---

## 技术说明

- Google Sheet 复制出来是 **TSV**（Tab 分隔，含换行的长单元格被双引号包裹），用 `csv` 解析器按 Tab 解析，不是简单按行切分
- 文件名做 NFC 规范化，保证 Mac（默认 NFD）和 Windows（NFC）下中英文显示一致
- 自动剔除所有标点和 Windows 非法字符（`\ / : * ? " < > |`）、换行、首尾空格，规避保留名
- 50 个汉字远在两个系统的文件名长度上限内（Windows 255 字符 / Mac 255 字节）
