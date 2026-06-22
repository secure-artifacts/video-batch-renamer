#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频批量命名小工具 (Mac / Windows 通用)

用法:
  1. 点「选择文件夹」选中放视频的文件夹
  2. 从 Google Sheet 复制「序号 + 文案」两列, 粘贴到下方文本框
  3. 点「预览」核对 原名 -> 新名 对照表
  4. 确认无误后点「应用改名」; 改错了点「撤销上次」即可还原

命名规则:
  <序号补零> <文案>.<原扩展名>
  文案 = 第1句前10字 + 空格 + 第2句起内容, 全部去标点, 共截到50字
  序号来自每个原文件名里抽出的数字, 与表格序号对应
"""

import csv
import io
import json
import os
import re
import sys
import time
import unicodedata

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ---- 可调参数 -------------------------------------------------------------
HOOK_LEN = 10            # 钩子(第1句)保留字数
MAX_LEN = 50             # 文案总字数上限
SEP = " "               # 钩子与正文之间的分隔符
SENT_SPLIT = r"[。！？!?；;\n\r]"   # 切句符号
VIDEO_EXT = {            # 识别为视频的扩展名
    ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv",
    ".flv", ".webm", ".mpg", ".mpeg", ".ts", ".m2ts",
}
RESERVED = {             # Windows 保留文件名
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
LOG_NAME = ".rename_log.json"
# --------------------------------------------------------------------------


def clean(s: str) -> str:
    """只保留汉字/字母/数字, 其余(标点/符号)全部丢弃, 多个空白压成一个空格。"""
    out = []
    for ch in s:
        if ch.isspace():
            out.append(" ")
        elif ch.isalnum():        # 汉字在 Python 里 isalnum()==True, 标点为 False
            out.append(ch)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def build_caption(text: str) -> str:
    """按规则把一段文案压成文件名用的短标题。"""
    parts = [clean(p) for p in re.split(SENT_SPLIT, text)]
    parts = [p for p in parts if p]
    if not parts:
        return ""
    hook = parts[0][:HOOK_LEN]
    body = "".join(parts[1:])     # 第2句起连写
    cap = hook + SEP + body if body else hook
    # NFC 规范化, 保证 Mac(NFD) 与 Windows(NFC) 显示一致
    cap = unicodedata.normalize("NFC", cap)
    return cap[:MAX_LEN].strip()


def parse_sheet(raw: str) -> dict:
    """解析从 Google Sheet 粘贴的内容 -> {序号: 文案}。

    粘贴格式是 TSV: 同行用 Tab 分隔, 含换行的长单元格被双引号包裹,
    所以必须用 csv 解析器(tab 分隔), 不能按行硬切。
    """
    result = {}
    reader = csv.reader(io.StringIO(raw), delimiter="\t")
    for row in reader:
        if len(row) < 2:
            continue
        nums = re.findall(r"\d+", row[0])
        if not nums:
            continue
        num = int(nums[0])
        text = row[1].strip()
        if text:
            result[num] = text
    return result


def extract_number(stem: str):
    """从文件名(去扩展名)里抽出序号, 取最后一组数字。返回 (值, 原始位宽)。"""
    nums = re.findall(r"\d+", stem)
    if not nums:
        return None, 0
    last = nums[-1]
    return int(last), len(last)


def safe_stem(num: int, width: int, caption: str) -> str:
    stem = f"{num:0{width}d}{SEP}{caption}".strip()
    head = stem.split(SEP)[0].upper()
    if head in RESERVED:
        stem = "_" + stem
    return stem


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("视频批量命名工具")
        self.geometry("1040x680")
        self.folder = ""
        self.plan = []          # [(old_path, new_name, status)]
        self._build_ui()

    # ---- UI ----
    def _build_ui(self):
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="选择文件夹", command=self.pick_folder).pack(side="left")
        self.folder_lbl = ttk.Label(top, text="未选择文件夹", foreground="#888")
        self.folder_lbl.pack(side="left", padx=10)

        mid = ttk.Frame(self, padding=(8, 0))
        mid.pack(fill="x")
        ttk.Label(mid, text="粘贴 Google Sheet 内容(序号 + 文案 两列):").pack(anchor="w")
        self.paste = tk.Text(mid, height=8, wrap="word", undo=True)
        self.paste.pack(fill="x", pady=(2, 6))

        btns = ttk.Frame(self, padding=(8, 0))
        btns.pack(fill="x")
        ttk.Button(btns, text="预览", command=self.preview).pack(side="left")
        self.apply_btn = ttk.Button(btns, text="应用改名", command=self.apply, state="disabled")
        self.apply_btn.pack(side="left", padx=6)
        ttk.Button(btns, text="撤销上次", command=self.undo).pack(side="left")

        cols = ("num", "old", "new", "status")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=18)
        for c, t, w in (("num", "序号", 60), ("old", "原文件名", 280),
                        ("new", "新文件名", 560), ("status", "状态", 110)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        self.tree.tag_configure("ok", foreground="#0a7d18")
        self.tree.tag_configure("warn", foreground="#c25400")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        self.status = ttk.Label(self, text="就绪", relief="sunken", anchor="w", padding=4)
        self.status.pack(fill="x", side="bottom")

    # ---- actions ----
    def pick_folder(self):
        d = filedialog.askdirectory(title="选择放视频的文件夹")
        if d:
            self.folder = d
            self.folder_lbl.config(text=d, foreground="#000")

    def list_videos(self):
        files = []
        for name in os.listdir(self.folder):
            p = os.path.join(self.folder, name)
            if os.path.isfile(p) and os.path.splitext(name)[1].lower() in VIDEO_EXT:
                files.append(name)
        return files

    def preview(self):
        if not self.folder:
            messagebox.showwarning("提示", "请先选择文件夹")
            return
        sheet = parse_sheet(self.paste.get("1.0", "end-1c"))
        if not sheet:
            messagebox.showwarning("提示", "没解析到表格内容, 请检查粘贴的数据")
            return

        videos = self.list_videos()
        if not videos:
            messagebox.showwarning("提示", "该文件夹里没找到视频文件")
            return

        # 位宽: 用原文件名里的数字位宽, 至少 2, 保证排序正确
        widths = [extract_number(os.path.splitext(v)[0])[1] for v in videos]
        width = max([w for w in widths if w] + [len(str(max(sheet)))] + [2])

        rows = []
        seen_nums = {}
        for v in videos:
            stem, ext = os.path.splitext(v)
            num, _ = extract_number(stem)
            if num is None:
                rows.append((9_999_999, v, "", "无序号", "warn"))
                continue
            if num in seen_nums:
                rows.append((num, v, "", f"序号{num}重复", "warn"))
                continue
            seen_nums[num] = v
            if num not in sheet:
                rows.append((num, v, "", "无对应文案", "warn"))
                continue
            caption = build_caption(sheet[num])
            new = safe_stem(num, width, caption) + ext.lower()
            rows.append((num, v, new, "可改名", "ok"))

        rows.sort(key=lambda r: r[0])
        # 重名兜底
        used = set()
        self.plan = []
        self.tree.delete(*self.tree.get_children())
        for num, old, new, st, tag in rows:
            if new and new in used:
                base, ext = os.path.splitext(new)
                k = 2
                while f"{base} ({k}){ext}" in used:
                    k += 1
                new = f"{base} ({k}){ext}"
            if new:
                used.add(new)
            shown = num if num != 9_999_999 else ""
            self.tree.insert("", "end", values=(shown, old, new, st), tags=(tag,))
            if tag == "ok":
                self.plan.append((os.path.join(self.folder, old), new))

        n_ok = len(self.plan)
        self.apply_btn.config(state="normal" if n_ok else "disabled")
        self.status.config(text=f"可改名 {n_ok} 个 / 共 {len(videos)} 个视频")

    def apply(self):
        if not self.plan:
            return
        if not messagebox.askyesno("确认", f"确定要改名 {len(self.plan)} 个文件吗?"):
            return
        log = []
        done = 0
        for old_path, new_name in self.plan:
            new_path = os.path.join(self.folder, new_name)
            if os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(old_path):
                continue
            try:
                os.rename(old_path, new_path)
                log.append({"old": os.path.basename(old_path), "new": new_name})
                done += 1
            except OSError as e:
                messagebox.showerror("出错", f"{os.path.basename(old_path)} 改名失败:\n{e}")
                break
        if log:
            with open(os.path.join(self.folder, LOG_NAME), "w", encoding="utf-8") as f:
                json.dump({"ts": time.time(), "items": log}, f, ensure_ascii=False, indent=2)
        self.status.config(text=f"已改名 {done} 个, 撤销记录已写入 {LOG_NAME}")
        self.apply_btn.config(state="disabled")
        messagebox.showinfo("完成", f"已改名 {done} 个文件")

    def undo(self):
        if not self.folder:
            messagebox.showwarning("提示", "请先选择文件夹")
            return
        path = os.path.join(self.folder, LOG_NAME)
        if not os.path.exists(path):
            messagebox.showinfo("提示", "该文件夹没有撤销记录")
            return
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        done = 0
        for it in data["items"]:
            cur = os.path.join(self.folder, it["new"])
            orig = os.path.join(self.folder, it["old"])
            if os.path.exists(cur) and not os.path.exists(orig):
                os.rename(cur, orig)
                done += 1
        os.remove(path)
        self.status.config(text=f"已还原 {done} 个文件")
        self.tree.delete(*self.tree.get_children())
        messagebox.showinfo("完成", f"已还原 {done} 个文件")


if __name__ == "__main__":
    App().mainloop()
