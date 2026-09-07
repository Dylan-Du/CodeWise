"""Codex助手 — 现代化 GUI(CustomTkinter),匹配 HTML 设计稿。"""
import platform
import queue
import threading
import webbrowser
from tkinter import messagebox

import customtkinter as ctk

import core

APP_TITLE = "Codex助手"

# 跨平台等宽字体
_SYSTEM = platform.system()
MONO_FONT = "Menlo" if _SYSTEM == "Darwin" else ("Consolas" if _SYSTEM == "Windows" else "Monospace")

# ─── 主题色(匹配 HTML 设计) ───
THEMES = {
    "light": {
        "bg": "#EEF1F8",
        "fg": "#1A1D29",
        "primary": "#4F6BFF",
        "primary_hover": "#3B56D4",
        "primary_subtle": "#E8EDFF",
        "accent": "#3ECF8E",
        "accent_hover": "#32B07A",
        "surface": "#FFFFFF",
        "surface_hover": "#E8EDFF",
        "border": "#D1D5E4",
        "border_strong": "#B8BFD4",
        "text_muted": "#6B7280",
        "text_subtle": "#9CA3AF",
        "success": "#22C55E",
        "success_bg": "#DCFCE7",
        "success_border": "#86EFAC",
        "warn": "#F59E0B",
        "warn_bg": "#FEF3C7",
        "warn_border": "#FCD34D",
        "danger": "#EF4444",
        "danger_bg": "#FEE2E2",
        "danger_border": "#FCA5A5",
        "info": "#6B7280",
        "info_bg": "#F3F4F6",
        "info_border": "#D1D5DB",
        "glass": "#FFFFFF",
        "on_primary": "#FFFFFF",
        "mesh_1": "#6B8AFF",
        "mesh_2": "#3ECF8E",
        "mesh_3": "#F97316",
    },
    "dark": {
        "bg": "#0A0C14",
        "fg": "#F0F1F5",
        "primary": "#7C8BFF",
        "primary_hover": "#5B7BFF",
        "primary_subtle": "#1E2A5E",
        "accent": "#4ADE80",
        "accent_hover": "#3ECF8E",
        "surface": "#14172A",
        "surface_hover": "#1E2A5E",
        "border": "#2A2D3E",
        "border_strong": "#3D4155",
        "text_muted": "#8B8D98",
        "text_subtle": "#6B7280",
        "success": "#4ADE80",
        "success_bg": "#064E3B",
        "success_border": "#10B981",
        "warn": "#FBBF24",
        "warn_bg": "#78350F",
        "warn_border": "#F59E0B",
        "danger": "#F87171",
        "danger_bg": "#7F1D1D",
        "danger_border": "#EF4444",
        "info": "#8B8D98",
        "info_bg": "#1F2937",
        "info_border": "#374151",
        "glass": "#14172A",
        "on_primary": "#FFFFFF",
        "mesh_1": "#4F6BFF",
        "mesh_2": "#2DD4BF",
        "mesh_3": "#FB923C",
    },
    "focus": {
        "bg": "#08090E",
        "fg": "#A0A4B0",
        "primary": "#5B7BFF",
        "primary_hover": "#4F6BFF",
        "primary_subtle": "#1A1B25",
        "accent": "#3ECF8E",
        "accent_hover": "#2DD4BF",
        "surface": "#111219",
        "surface_hover": "#1A1B25",
        "border": "#1E2030",
        "border_strong": "#2A2D3E",
        "text_muted": "#6B7280",
        "text_subtle": "#4B5563",
        "success": "#4ADE80",
        "success_bg": "#064E3B",
        "success_border": "#10B981",
        "warn": "#FBBF24",
        "warn_bg": "#78350F",
        "warn_border": "#F59E0B",
        "danger": "#F87171",
        "danger_bg": "#7F1D1D",
        "danger_border": "#EF4444",
        "info": "#6B7280",
        "info_bg": "#1F2937",
        "info_border": "#374151",
        "glass": "#111219",
        "on_primary": "#FFFFFF",
        "mesh_1": "#4F6BFF",
        "mesh_2": "#2DD4BF",
        "mesh_3": "#FB923C",
    },
}


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("520x720")
        self.minsize(480, 600)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.theme_mode = "light"
        self.colors = THEMES[self.theme_mode]

        self.runner = core.AdapterRunner(log_fn=self._enqueue_log, on_usage=self._on_usage)
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.log_expanded = True
        self._busy = False

        self.flat: list[tuple[str, str, str]] = []
        self.label_to_meta: dict[str, tuple[str, str]] = {}
        self.labels: list[str] = []

        self.model_label_var = ctk.StringVar()
        self._current_route: str = ""

        # ─── 状态 ───
        self.is_running = False
        self.timeline_collapsed = False
        self.active_tab = "ops"
        self.timeline_items: list[dict] = []

        self._build_ui()
        self._apply_theme()
        self._reload_models(initial=True)
        self._pump_log()
        self._refresh_status()
        self._refresh_token_stats()

    # ─── 主题 ───

    def _apply_theme(self):
        c = self.colors
        # 设置全局颜色
        self.configure(fg_color=c["bg"])
        # 更新所有子组件颜色
        self._update_widget_colors(self)

    def _update_widget_colors(self, widget):
        """递归更新组件颜色"""
        c = self.colors
        try:
            if isinstance(widget, ctk.CTkFrame):
                if hasattr(widget, "_fg_color") and isinstance(widget._fg_color, str):
                    pass  # 保持原色
            elif isinstance(widget, ctk.CTkLabel):
                pass
        except Exception:
            pass
        for child in widget.winfo_children():
            self._update_widget_colors(child)

    def _set_theme(self, mode: str):
        self.theme_mode = mode
        self.colors = THEMES[mode]
        self._apply_theme()
        self._rebuild_ui()

    def _rebuild_ui(self):
        """重建 UI 以应用新主题"""
        for w in self.winfo_children():
            w.destroy()
        self._build_ui()
        self._apply_theme()
        self._reload_models(initial=True)
        self._refresh_status()
        self._refresh_token_stats()

    # ─── UI 构建 ───

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        # ─── row 0: 顶部标题 + 主题切换 ───
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        top.grid_columnconfigure(0, weight=1)

        # Logo + 标题
        title_frame = ctk.CTkFrame(top, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="w")

        # Logo 圆形
        self.logo_btn = ctk.CTkButton(
            title_frame, text="",
            width=32, height=32, corner_radius=16,
            fg_color=self.colors["primary"],
            hover_color=self.colors["primary"],
            state="disabled",
        )
        self.logo_btn.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            title_frame, text=APP_TITLE,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.colors["fg"],
        ).pack(side="left")

        # 主题切换按钮
        theme_frame = ctk.CTkFrame(top, fg_color="transparent")
        theme_frame.grid(row=0, column=1, sticky="e")
        self.theme_buttons = {}
        for i, (name, label) in enumerate([("light", "☀"), ("dark", "🌙"), ("focus", "◎")]):
            btn = ctk.CTkButton(
                theme_frame, text=label, width=28, height=26, corner_radius=7,
                fg_color="transparent",
                text_color=self.colors["text_muted"],
                hover_color=self.colors["surface_hover"],
                command=lambda m=name: self._set_theme(m),
            )
            btn.pack(side="left", padx=1)
            self.theme_buttons[name] = btn

        # ─── row 1: 状态英雄区 ───
        self.status_hero = ctk.CTkFrame(self, corner_radius=16, fg_color=self.colors["glass"])
        self.status_hero.grid(row=1, column=0, sticky="ew", padx=16, pady=4)
        self.status_hero.grid_columnconfigure(1, weight=1)

        # 吉祥物
        mascot_frame = ctk.CTkFrame(self.status_hero, fg_color="transparent")
        mascot_frame.grid(row=0, column=0, rowspan=2, padx=(16, 8), pady=12)
        self.mascot_label = ctk.CTkLabel(
            mascot_frame, text="🤖",
            font=ctk.CTkFont(size=32),
        )
        self.mascot_label.pack()

        # 状态信息
        status_info = ctk.CTkFrame(self.status_hero, fg_color="transparent")
        status_info.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=(12, 0))

        status_row = ctk.CTkFrame(status_info, fg_color="transparent")
        status_row.pack(fill="x")

        # 开关按钮
        self.power_btn = ctk.CTkButton(
            status_row, text="▶",
            width=38, height=22, corner_radius=11,
            fg_color=self.colors["text_muted"],
            hover_color=self.colors["text_muted"],
            command=self._on_toggle,
        )
        self.power_btn.pack(side="left", padx=(0, 8))

        self.status_label = ctk.CTkLabel(
            status_row, text="未启动",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.colors["fg"],
        )
        self.status_label.pack(side="left")

        # 模型名称
        self.status_model = ctk.CTkLabel(
            status_info, text="Codex · ?",
            font=ctk.CTkFont(size=13),
            text_color=self.colors["text_muted"],
        )
        self.status_model.pack(anchor="w", pady=(4, 0))

        # 迷你统计
        mini_stats = ctk.CTkFrame(self.status_hero, fg_color="transparent")
        mini_stats.grid(row=1, column=1, sticky="ew", padx=(0, 16), pady=(8, 12))
        mini_stats.grid_columnconfigure((0, 1, 2), weight=1)

        self.token_input_label = self._mini_stat_box(mini_stats, "输入", 0, 0, "primary")
        self.token_output_label = self._mini_stat_box(mini_stats, "输出", 0, 1, "success")
        self.token_cache_label = self._mini_stat_box(mini_stats, "缓存", 0, 2, "warn")

        # ─── row 2: 模型药丸栏 ───
        model_card = ctk.CTkFrame(self, corner_radius=16, fg_color=self.colors["glass"])
        model_card.grid(row=2, column=0, sticky="ew", padx=16, pady=4)
        model_card.grid_columnconfigure(0, weight=1)

        pill_header = ctk.CTkFrame(model_card, fg_color="transparent")
        pill_header.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(
            pill_header, text="模型",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.colors["text_subtle"],
        ).pack(side="left")

        ctk.CTkButton(
            pill_header, text="⚙ 模型配置", width=80, height=24,
            command=self._open_model_config_dialog,
            fg_color="transparent", border_width=1,
            text_color=self.colors["primary"],
            hover_color=self.colors["surface_hover"],
            border_color=self.colors["primary"],
            font=ctk.CTkFont(size=11),
        ).pack(side="right")

        # 药丸滚动区
        self.pill_scroll = ctk.CTkScrollableFrame(model_card, orientation="horizontal", height=40)
        self.pill_scroll.pack(fill="x", padx=14, pady=(0, 12))
        self.pill_buttons: list[ctk.CTkButton] = []

        # ─── row 3: 时间线区域 ───
        self.timeline_card = ctk.CTkFrame(self, corner_radius=16, fg_color=self.colors["glass"])
        self.timeline_card.grid(row=3, column=0, sticky="nsew", padx=16, pady=4)
        self.timeline_card.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # 标签头
        tab_header = ctk.CTkFrame(self.timeline_card, fg_color="transparent")
        tab_header.pack(fill="x", padx=14, pady=(8, 0))

        self.tab_ops_btn = ctk.CTkButton(
            tab_header, text="操作日志", width=80, height=30, corner_radius=8,
            fg_color=self.colors["primary"],
            hover_color=self.colors["primary_hover"],
            command=lambda: self._switch_tab("ops"),
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.tab_ops_btn.pack(side="left", padx=(0, 4))

        self.tab_token_btn = ctk.CTkButton(
            tab_header, text="Token 统计", width=90, height=30, corner_radius=8,
            fg_color="transparent",
            hover_color=self.colors["surface_hover"],
            command=lambda: self._switch_tab("token"),
            font=ctk.CTkFont(size=12),
        )
        self.tab_token_btn.pack(side="left", padx=4)

        # 折叠按钮
        self.collapse_btn = ctk.CTkButton(
            tab_header, text="▼", width=28, height=28, corner_radius=6,
            fg_color="transparent",
            hover_color=self.colors["surface_hover"],
            command=self._toggle_timeline,
        )
        self.collapse_btn.pack(side="right")

        # 时间线内容
        self.timeline_content = ctk.CTkScrollableFrame(self.timeline_card, fg_color="transparent")
        self.timeline_content.pack(fill="both", expand=True, padx=14, pady=(4, 12))

        # 初始化时间线内容
        self._refresh_timeline()

    def _mini_stat_box(self, parent, title, row, col, color_key):
        box = ctk.CTkFrame(parent, corner_radius=6, fg_color=self.colors["surface"])
        box.grid(row=row, column=col, sticky="ew", padx=3, pady=2)
        ctk.CTkLabel(
            box, text=title,
            font=ctk.CTkFont(size=10),
            text_color=self.colors["text_subtle"],
        ).pack(pady=(4, 0))
        lbl = ctk.CTkLabel(
            box, text="0",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.colors[color_key],
        )
        lbl.pack(pady=(0, 4))
        return lbl

    # ─── 时间线 ───

    def _switch_tab(self, tab: str):
        self.active_tab = tab
        c = self.colors
        if tab == "ops":
            self.tab_ops_btn.configure(fg_color=c["primary"], text_color=c["on_primary"])
            self.tab_token_btn.configure(fg_color="transparent", text_color=c["text_muted"])
        else:
            self.tab_ops_btn.configure(fg_color="transparent", text_color=c["text_muted"])
            self.tab_token_btn.configure(fg_color=c["primary"], text_color=c["on_primary"])
        self._refresh_timeline()

    def _toggle_timeline(self):
        self.timeline_collapsed = not self.timeline_collapsed
        if self.timeline_collapsed:
            self.timeline_content.pack_forget()
            self.collapse_btn.configure(text="▶")
        else:
            self.timeline_content.pack(fill="both", expand=True, padx=14, pady=(4, 12))
            self.collapse_btn.configure(text="▼")

    def _refresh_timeline(self):
        """刷新时间线内容"""
        for w in self.timeline_content.winfo_children():
            w.destroy()

        if self.active_tab == "ops":
            self._build_ops_timeline()
        else:
            self._build_token_timeline()

    def _build_ops_timeline(self):
        """构建操作日志时间线"""
        for i, item in enumerate(self.timeline_items):
            self._add_timeline_item(item, i)

    def _build_token_timeline(self):
        """构建 Token 统计时间线"""
        # 显示汇总统计
        t = core.token_tracker.totals()
        summary = {
            "icon": "📊",
            "icon_color": self.colors["primary"],
            "desc": f"Token 统计汇总",
            "time": "现在",
            "stats": t,
        }
        self._add_timeline_item(summary, 0)

        # 显示最近记录
        for i, record in enumerate(core.token_tracker.recent(10)):
            item = {
                "icon": "📊",
                "icon_color": self.colors["primary"],
                "desc": f"{record['model']}",
                "time": record["timestamp"],
                "stats": record,
            }
            self._add_timeline_item(item, i + 1)

    def _add_timeline_item(self, item: dict, index: int):
        """添加时间线条目"""
        row = ctk.CTkFrame(self.timeline_content, fg_color="transparent")
        row.pack(fill="x", pady=2)
        row.grid_columnconfigure(1, weight=1)

        # 图标
        icon_label = ctk.CTkLabel(
            row, text=item.get("icon", "•"),
            width=28, height=28, corner_radius=14,
            fg_color=self.colors.get("primary_subtle", self.colors["primary"]),
            text_color=item.get("icon_color", self.colors["fg"]),
            font=ctk.CTkFont(size=12),
        )
        icon_label.grid(row=0, column=0, rowspan=2, padx=(0, 8), pady=2)

        # 描述
        desc = ctk.CTkLabel(
            row, text=item.get("desc", ""),
            font=ctk.CTkFont(size=12),
            text_color=self.colors["fg"],
            anchor="w",
        )
        desc.grid(row=0, column=1, sticky="w", pady=(2, 0))

        # 时间
        time_lbl = ctk.CTkLabel(
            row, text=item.get("time", ""),
            font=ctk.CTkFont(size=10),
            text_color=self.colors["text_subtle"],
            anchor="w",
        )
        time_lbl.grid(row=1, column=1, sticky="w", pady=(0, 2))

        # 统计(如果有)
        if "stats" in item:
            stats = item["stats"]
            stats_frame = ctk.CTkFrame(row, fg_color="transparent")
            stats_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
            stats_frame.grid_columnconfigure((0, 1, 2), weight=1)

            self._stat_cell(stats_frame, "输入", stats.get("input", 0), "primary", 0)
            self._stat_cell(stats_frame, "输出", stats.get("output", 0), "success", 1)
            self._stat_cell(stats_frame, "缓存", stats.get("cache", 0), "warn", 2)

    def _stat_cell(self, parent, label, value, color_key, col):
        cell = ctk.CTkFrame(parent, corner_radius=6, fg_color=self.colors["surface"])
        cell.grid(row=0, column=col, sticky="ew", padx=2, pady=2)
        ctk.CTkLabel(
            cell, text=label,
            font=ctk.CTkFont(size=9),
            text_color=self.colors["text_subtle"],
        ).pack(pady=(2, 0))
        ctk.CTkLabel(
            cell, text=f"{value:,}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.colors[color_key],
        ).pack(pady=(0, 2))

    # ─── 模型药丸 ───

    def _refresh_pills(self):
        """刷新模型药丸"""
        for btn in self.pill_buttons:
            btn.destroy()
        self.pill_buttons.clear()

        current = self.model_label_var.get()
        for label in self.labels:
            is_active = label == current
            btn = ctk.CTkButton(
                self.pill_scroll,
                text=label,
                height=32, corner_radius=16,
                fg_color=self.colors["primary"] if is_active else "transparent",
                text_color=self.colors["on_primary"] if is_active else self.colors["text_muted"],
                hover_color=self.colors["primary_hover"] if is_active else self.colors["surface_hover"],
                border_width=1 if not is_active else 0,
                border_color=self.colors["border_strong"] if not is_active else "",
                command=lambda l=label: self._on_pill_click(l),
                font=ctk.CTkFont(size=12, weight="bold" if is_active else "normal"),
            )
            btn.pack(side="left", padx=4, pady=4)
            self.pill_buttons.append(btn)

    def _on_pill_click(self, label: str):
        self.model_label_var.set(label)
        self._refresh_pills()
        self._on_model_change()

    # ─── 事件 ───

    def _on_toggle(self):
        if self._busy:
            return
        if core.adapter_running():
            self._stop_adapter()
        else:
            self._start_adapter()

    def _set_busy(self, text: str):
        self._busy = True
        self.power_btn.configure(text=text, state="disabled")

    def _start_adapter(self):
        label = self.model_label_var.get()
        if not label:
            return
        route = self._route_of_label(label)
        model = self._model_of_label(label)
        try:
            info = core.resolve_route(route, model)
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"路由错误: {e}")
            return
        if not info.get("api_key"):
            messagebox.showwarning(APP_TITLE, "该模型尚未配置 API Key,请先到「模型配置」里添加。")
            return
        self._set_busy("⏳")
        self.after(50, lambda: self._do_start(model, route, label))

    def _do_start(self, model: str, route: str, label: str):
        try:
            core.write_adapter_json(model, route)
            self._log(f"已写入翻译官配置({label})。")
            if core.backup_config_toml_if_needed():
                self._log(f"已备份原 Codex 配置 → {core.BACKUP_TOML.name}")
            core.apply_codex_config(model)
            self._log("已合并配置到 config.toml。")
        except Exception as e:
            self._log(f"配置写入失败:{e}")
            messagebox.showerror(APP_TITLE, f"配置写入失败:\n{e}")
            self._busy = False
            self._refresh_status()
            return
        if not self.runner.start():
            messagebox.showerror(APP_TITLE, "翻译官启动失败,看日志。")
            self._busy = False
            self._refresh_status()
            return
        self._log("✅ 全部就绪。打开 Codex App 即可使用。")
        self._busy = False
        self._refresh_status()

    def _stop_adapter(self):
        self._set_busy("⏳")
        self.after(50, self._do_stop)

    def _do_stop(self):
        self.runner.stop()
        try:
            msg = core.restore_openai_config()
            self._log(msg)
        except Exception as e:
            self._log(f"还原 Codex 配置失败:{e}")
            messagebox.showerror(APP_TITLE, f"还原 Codex 配置失败:\n{e}")
            self._busy = False
            self._refresh_status()
            return
        self._log("✅ 已关闭翻译官 + 切回 OpenAI 原版。重启 Codex App 生效。")
        self._busy = False
        self._refresh_status()

    # ─── 模型数据 ───

    def _reload_models(self, initial: bool = False, prefer_route: str | None = None):
        self.flat = core.flat_models()
        self.label_to_meta = {lab: (m, rt) for lab, m, rt in self.flat}
        self.labels = [lab for lab, _, _ in self.flat]

        if prefer_route:
            target = next((lab for lab, _, rt in self.flat if rt == prefer_route), None)
        else:
            cur = core.current_model()
            target = next((lab for lab, m, _ in self.flat if m == cur), None)
        if not target and self.labels:
            target = self.labels[0]
        if target:
            self.model_label_var.set(target)
            self._refresh_provider_ui(initial=initial)
        self._refresh_pills()

    def _route_of_label(self, label: str) -> str:
        return self.label_to_meta[label][1]

    def _model_of_label(self, label: str) -> str:
        return self.label_to_meta[label][0]

    def _on_model_change(self, _selected: str | None = None):
        self._refresh_provider_ui()

    def _refresh_provider_ui(self, initial: bool = False):
        label = self.model_label_var.get()
        if not label:
            return
        route = self._route_of_label(label)
        self._current_route = route
        try:
            info = core.resolve_route(route, self._model_of_label(label))
        except Exception as e:
            self._log(f"路由错误: {e}")
            return
        if not initial:
            self._log(f"已切到 {label}。")
        self._refresh_status()

    # ─── 模型配置弹窗 ───

    def _open_model_config_dialog(self):
        ModelConfigDialog(self, on_changed=self._on_model_config_changed)

    def _on_model_config_changed(self):
        n = len(core.load_custom())
        self._log(f"模型配置已更新(共 {n} 个自定义模型)。")
        self._reload_models(prefer_route=f"custom:{max(n - 1, 0)}")

    # ─── 状态轮询 ───

    def _refresh_status(self):
        if self._busy:
            self.after(800, self._refresh_status)
            return
        running = core.adapter_running()
        cur_model = core.current_model()
        codex_in_adapter = core.codex_in_adapter_mode()

        c = self.colors
        if running:
            self.power_btn.configure(fg_color=c["success"], text="■")
            self.status_label.configure(text="运行中", text_color=c["success"])
            self.is_running = True
        else:
            self.power_btn.configure(fg_color=c["text_muted"], text="▶")
            self.status_label.configure(text="未启动", text_color=c["fg"])
            self.is_running = False

        if codex_in_adapter and cur_model:
            self.status_model.configure(text=f"Codex · {cur_model}")
        elif cur_model:
            self.status_model.configure(text="Codex · OpenAI 原版")
        else:
            self.status_model.configure(text="Codex · 未初始化")

        self.after(2000, self._refresh_status)

    # ─── Token 用量 ───

    def _on_usage(self, model: str, input_tokens: int, output_tokens: int, cache_tokens: int):
        core.token_tracker.record(model, input_tokens, output_tokens, cache_tokens)
        self._refresh_token_stats()
        self._log(f"📊 {model}: 输入 {input_tokens} / 输出 {output_tokens} / 缓存 {cache_tokens}")

    def _refresh_token_stats(self):
        t = core.token_tracker.totals()
        self.token_input_label.configure(text=f"{t['input']:,}")
        self.token_output_label.configure(text=f"{t['output']:,}")
        self.token_cache_label.configure(text=f"{t['cache']:,}")

    # ─── 日志 ───

    def _enqueue_log(self, msg: str):
        self.log_queue.put(msg)

    def _log(self, msg: str):
        self.log_queue.put(msg)
        # 同时添加到时间线
        self.timeline_items.append({
            "icon": "📝",
            "icon_color": self.colors["primary"],
            "desc": msg,
            "time": "刚刚",
        })
        if len(self.timeline_items) > 50:
            self.timeline_items = self.timeline_items[-50:]
        self._refresh_timeline()

    def _pump_log(self):
        while True:
            try:
                msg = self.log_queue.get_nowait()
            except queue.Empty:
                break
        self.after(150, self._pump_log)

    def on_close(self):
        try:
            self.runner.stop()
        except Exception:
            pass
        self.destroy()


# ====================================================================
# 模型配置弹窗
# ====================================================================

class ModelConfigDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_changed):
        super().__init__(parent)
        self.parent = parent
        self.on_changed = on_changed
        self.title("模型配置")
        self.geometry("520x600")
        self.minsize(480, 500)
        self.transient(parent)
        self.after(50, self.grab_set)

        self.colors = parent.colors
        self.configure(fg_color=self.colors["bg"])

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 顶部标题 + 关闭按钮
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            header, text="← 返回", width=60, height=28,
            command=self.destroy,
            fg_color="transparent",
            text_color=self.colors["text_muted"],
            hover_color=self.colors["surface_hover"],
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header, text="模型配置",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.colors["fg"],
        ).grid(row=0, column=0)

        # 模型列表
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=4)
        self.list_frame.grid_columnconfigure(0, weight=1)

        # 新增按钮
        ctk.CTkButton(
            self, text="+ 新增模型",
            height=42, corner_radius=12,
            command=self._open_add_dialog,
            fg_color="transparent",
            border_width=1, border_color=self.colors["border_strong"],
            text_color=self.colors["text_muted"],
            hover_color=self.colors["surface_hover"],
            font=ctk.CTkFont(size=13),
        ).grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 12))

        self._reload()

    def _reload(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        items = core.load_custom()
        if not items:
            ctk.CTkLabel(
                self.list_frame, text="(还没有自定义模型,点下方「+ 新增模型」添加)",
                text_color=self.colors["text_muted"],
            ).grid(row=0, column=0, pady=30)
            return
        for i, it in enumerate(items):
            row = ctk.CTkFrame(self.list_frame, corner_radius=12, fg_color=self.colors["surface"])
            row.grid(row=i, column=0, sticky="ew", pady=4, padx=4)
            row.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                row, text=it["label"], anchor="w",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=self.colors["fg"],
            ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 0))

            ctk.CTkLabel(
                row, text=it["model"], anchor="w",
                text_color=self.colors["text_muted"],
                font=ctk.CTkFont(size=11),
            ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))

            # 编辑 + 删除
            btn_col = ctk.CTkFrame(row, fg_color="transparent")
            btn_col.grid(row=0, column=1, rowspan=2, padx=10, pady=8)

            ctk.CTkButton(
                btn_col, text="编辑", width=50, height=26,
                command=lambda idx=i: self._open_edit_dialog(idx),
                fg_color="transparent", border_width=1,
                text_color=self.colors["primary"],
                hover_color=self.colors["surface_hover"],
                border_color=self.colors["primary"],
            ).pack(side="left", padx=2)

            ctk.CTkButton(
                btn_col, text="删除", width=50, height=26,
                command=lambda idx=i: self._delete(idx),
                fg_color=self.colors["danger"],
                hover_color=self.colors["danger"],
            ).pack(side="left", padx=2)

    def _open_add_dialog(self):
        ModelEditDialog(self, on_saved=self._reload)

    def _open_edit_dialog(self, idx: int):
        items = core.load_custom()
        if idx < len(items):
            ModelEditDialog(self, item=items[idx], index=idx, on_saved=self._reload)

    def _delete(self, idx: int):
        items = core.load_custom()
        if idx >= len(items):
            return
        if not messagebox.askyesno("确认", f"删除 {items[idx]['label']}?"):
            return
        core.remove_custom(idx)
        self._reload()
        self.on_changed()


# ====================================================================
# 新增/编辑模型弹窗
# ====================================================================

class ModelEditDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_saved, item: dict | None = None, index: int = -1):
        super().__init__(parent)
        self.parent = parent
        self.on_saved = on_saved
        self.item = item
        self.index = index
        self.title("编辑模型" if item else "新增模型")
        self.geometry("480x420")
        self.resizable(False, False)
        self.transient(parent)
        self.after(50, self.grab_set)

        self.colors = parent.colors
        self.configure(fg_color=self.colors["bg"])

        # 新增模型仅提供 APINest 和自定义两个入口；编辑历史条目时保留原 provider。
        allowed_labels = {"APINest", "自定义"}
        presets = [p for p in core.PRESETS if p["label"] in allowed_labels]
        self.preset_labels = [f"{p['label']} · {p['model']}" if p['model'] else p['label']
                              for p in presets]
        self.template_var = ctk.StringVar(value=self.preset_labels[0])
        self.name_var = ctk.StringVar(value=item.get("label", "") if item else "")
        self.model_var = ctk.StringVar(value=item.get("model", "") if item else "")
        self.upstream_var = ctk.StringVar(value=item.get("upstream", "") if item else "")
        self.key_url_var = ctk.StringVar(value=item.get("key_url", "") if item else "")
        self.api_key_var = ctk.StringVar(value=item.get("api_key", "") if item else "")

        self._build()
        if not item:
            self._on_template_change(self.preset_labels[0])

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self, text="选择模板自动填充,或选「自定义」手动填写。",
            text_color=self.colors["text_muted"], font=ctk.CTkFont(size=11),
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))

        # 模板行
        trow = ctk.CTkFrame(self, fg_color="transparent")
        trow.grid(row=1, column=0, sticky="ew", padx=20, pady=4)
        trow.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(trow, text="模板", width=80, anchor="w").grid(row=0, column=0)
        ctk.CTkOptionMenu(
            trow, variable=self.template_var, values=self.preset_labels,
            command=self._on_template_change, dynamic_resizing=False,
            button_color=self.colors["primary"],
            button_hover_color=self.colors["primary_hover"],
        ).grid(row=0, column=1, sticky="ew")

        self._field("显示名", self.name_var, 2, "例:智谱 / 通义 / LongCat")
        self._field("模型 ID", self.model_var, 3, "例:glm-4-plus(向 API 提交的字符串)")
        self._field("Base URL", self.upstream_var, 4, "完整端点,含 /chat/completions")
        self._field("Key 入口", self.key_url_var, 5, "可选,注册获取 Key 的网址")
        self._field("API Key", self.api_key_var, 6, "sk-... 类型", show="●")

        # 按钮
        btnf = ctk.CTkFrame(self, fg_color="transparent")
        btnf.grid(row=7, column=0, sticky="ew", padx=20, pady=(16, 16))
        btnf.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            btnf, text="取消", command=self.destroy,
            fg_color="transparent", border_width=1,
            text_color=self.colors["text_muted"],
            hover_color=self.colors["surface_hover"],
            width=100,
        ).grid(row=0, column=1, padx=4)
        ctk.CTkButton(
            btnf, text="保存", command=self._save,
            fg_color=self.colors["primary"],
            hover_color=self.colors["primary_hover"],
            width=100,
        ).grid(row=0, column=2, padx=4)

    def _field(self, label, var, row, hint, show=None):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid(row=row, column=0, sticky="ew", padx=20, pady=2)
        f.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(f, text=label, width=80, anchor="w").grid(row=0, column=0)
        entry = ctk.CTkEntry(f, textvariable=var, placeholder_text=hint)
        if show:
            entry.configure(show=show)
        entry.grid(row=0, column=1, sticky="ew")

    def _on_template_change(self, label: str):
        for p in core.PRESETS:
            disp = f"{p['label']} · {p['model']}" if p['model'] else p['label']
            if disp == label:
                self.name_var.set(p["label"] if p["label"] != "自定义" else "")
                self.model_var.set(p["model"])
                self.upstream_var.set(p["upstream"])
                self.key_url_var.set(p["key_url"])
                return

    def _save(self):
        name = self.name_var.get().strip()
        model = self.model_var.get().strip()
        upstream = self.upstream_var.get().strip()
        key_url = self.key_url_var.get().strip()
        api_key = self.api_key_var.get().strip()
        missing = [n for n, v in (("显示名", name), ("模型 ID", model),
                                  ("Base URL", upstream), ("API Key", api_key))
                   if not v]
        if self.index < 0 and name not in {"APINest", "自定义"}:
            messagebox.showwarning("服务商限制", "新增模型服务商仅支持 APINest 或 自定义")
            return
        if missing:
            messagebox.showwarning("缺字段", "以下字段必填:\n  " + "\n  ".join(missing))
            return
        if not upstream.startswith(("http://", "https://")):
            messagebox.showwarning("Base URL 格式", "Base URL 必须以 http:// 或 https:// 开头")
            return
        try:
            items = core.load_custom()
            entry = {"label": name, "model": model, "upstream": upstream,
                     "key_url": key_url, "api_key": api_key}
            if self.index >= 0 and self.index < len(items):
                items[self.index] = entry
            else:
                items.append(entry)
            core.save_custom_list(items)
            self.on_saved()
            self.destroy()
        except Exception as e:
            messagebox.showerror("保存失败", str(e))


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
