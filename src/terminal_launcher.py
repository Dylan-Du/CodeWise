#!/usr/bin/env python3
"""Codex助手 — 终端 TUI 启动器。
启动控制 API 服务器,然后在终端中提供文本界面。
"""
import os
import sys
import time
import json
import urllib.request
import urllib.parse
import threading
import curses
from pathlib import Path

# 确保 src 目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import web_api
import core


API_BASE = f"http://{web_api.HOST}:{web_api.PORT}"


def api_get(path):
    try:
        req = urllib.request.Request(f"{API_BASE}{path}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return {}


def api_post(path, data=None):
    try:
        body = json.dumps(data or {}).encode()
        req = urllib.request.Request(
            f"{API_BASE}{path}",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def format_number(n):
    """格式化数字,添加千位分隔符"""
    return f"{n:,}"


class CodexTUI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.running = True
        self.current_model = None
        self.model_list = []
        self.token_stats = {"input": 0, "output": 0, "cache": 0}
        self.logs = []
        self.message = ""
        self.message_time = 0
        self.cursor_pos = 0
        self.view = "main"  # main, models, logs

        # 初始化 curses
        curses.curs_set(0)
        self.stdscr.nodelay(True)
        self.stdscr.timeout(100)

        # 初始化颜色
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)   # 成功
        curses.init_pair(2, curses.COLOR_YELLOW, -1)  # 警告
        curses.init_pair(3, curses.COLOR_RED, -1)     # 错误
        curses.init_pair(4, curses.COLOR_CYAN, -1)    # 高亮
        curses.init_pair(5, curses.COLOR_WHITE, -1)   # 普通

    def show_message(self, msg, color=1):
        self.message = msg
        self.message_time = time.time()
        self.message_color = color

    def draw_header(self):
        """绘制顶部状态栏"""
        height, width = self.stdscr.getmaxyx()

        # 获取状态
        status = api_get("/api/status")
        running = status.get("running", False)
        model = status.get("model_name", "未选择")
        self.token_stats = status.get("token", {"input": 0, "output": 0, "cache": 0})

        # 标题
        title = " Codex助手 "
        self.stdscr.addstr(0, 0, "═" * width, curses.color_pair(4))
        self.stdscr.addstr(0, (width - len(title)) // 2, title, curses.color_pair(4) | curses.A_BOLD)

        # 状态行
        status_text = "● 运行中" if running else "○ 已停止"
        status_color = 1 if running else 3
        self.stdscr.addstr(1, 2, status_text, curses.color_pair(status_color) | curses.A_BOLD)

        model_text = f"模型: {model}"
        self.stdscr.addstr(1, 20, model_text, curses.color_pair(4))

        # Token 统计
        total = self.token_stats.get("input", 0) + self.token_stats.get("output", 0) + self.token_stats.get("cache", 0)
        token_text = f"总消耗: {format_number(total)}"
        self.stdscr.addstr(1, width - len(token_text) - 2, token_text, curses.color_pair(2))

        # 分隔线
        self.stdscr.addstr(2, 0, "─" * width, curses.color_pair(4))

    def draw_main_view(self):
        """绘制主视图"""
        height, width = self.stdscr.getmaxyx()

        # 获取模型列表
        config_resp = api_get("/api/config")
        self.model_list = config_resp.get("config", [])

        # Token 统计
        y = 4
        self.stdscr.addstr(y, 2, "📊 Token 统计", curses.color_pair(4) | curses.A_BOLD)
        y += 1

        input_val = format_number(self.token_stats.get("input", 0))
        output_val = format_number(self.token_stats.get("output", 0))
        cache_val = format_number(self.token_stats.get("cache", 0))
        total_val = format_number(
            self.token_stats.get("input", 0) +
            self.token_stats.get("output", 0) +
            self.token_stats.get("cache", 0)
        )

        self.stdscr.addstr(y, 4, f"输入: {input_val}", curses.color_pair(4))
        self.stdscr.addstr(y, 25, f"输出: {output_val}", curses.color_pair(1))
        self.stdscr.addstr(y, 46, f"缓存: {cache_val}", curses.color_pair(2))
        y += 1
        self.stdscr.addstr(y, 4, f"总消耗: {total_val}", curses.color_pair(4) | curses.A_BOLD)
        y += 2

        # 模型列表
        self.stdscr.addstr(y, 2, "🤖 模型列表", curses.color_pair(4) | curses.A_BOLD)
        y += 1

        if not self.model_list:
            self.stdscr.addstr(y, 4, "(无模型, 请按 'a' 添加)", curses.color_pair(3))
            y += 1
        else:
            for i, m in enumerate(self.model_list):
                name = m.get("model", "未知")
                provider = m.get("provider", "自定义")
                has_key = "✓" if m.get("api_key") else "✗"

                # 高亮当前选中的模型
                attr = curses.A_NORMAL
                if i == self.cursor_pos:
                    attr = curses.A_REVERSE

                line = f" [{has_key}] {name} ({provider})"
                self.stdscr.addstr(y, 4, line, attr)
                y += 1

        y += 1
        self.stdscr.addstr(y, 2, "操作: [a]添加  [d]删除  [s]切换  [q]退出", curses.color_pair(5))

        # 底部消息
        if self.message and time.time() - self.message_time < 3:
            y = height - 2
            self.stdscr.addstr(y, 2, self.message, curses.color_pair(self.message_color))

    def draw_logs_view(self):
        """绘制日志视图"""
        height, width = self.stdscr.getmaxyx()

        y = 4
        self.stdscr.addstr(y, 2, "📋 操作日志", curses.color_pair(4) | curses.A_BOLD)
        y += 1

        # 获取日志
        timeline = api_get("/api/timeline")
        items = timeline.get("items", [])

        if not items:
            self.stdscr.addstr(y, 4, "(暂无日志)", curses.color_pair(5))
        else:
            # 显示最近日志
            for item in items[-(height - 8):]:
                if y >= height - 3:
                    break
                icon = item.get("icon", "📝")
                desc = item.get("desc", "")
                time_str = item.get("time", "")
                self.stdscr.addstr(y, 4, f"{time_str} {icon} {desc[:width-20]}")
                y += 1

        y = height - 2
        self.stdscr.addstr(y, 2, "按 'b' 返回主视图", curses.color_pair(5))

    def draw(self):
        """主绘制函数"""
        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()

        if height < 20 or width < 60:
            self.stdscr.addstr(0, 0, "终端窗口太小,请调整到至少 60x20", curses.color_pair(3))
            self.stdscr.refresh()
            return

        self.draw_header()

        if self.view == "main":
            self.draw_main_view()
        elif self.view == "logs":
            self.draw_logs_view()

        self.stdscr.refresh()

    def handle_input(self):
        """处理键盘输入"""
        try:
            key = self.stdscr.getch()
        except curses.error:
            return

        if key == -1:
            return

        if self.view == "main":
            if key == ord('q') or key == ord('Q'):
                self.running = False
            elif key == ord('a') or key == ord('A'):
                self.add_model()
            elif key == ord('d') or key == ord('D'):
                self.delete_model()
            elif key == ord('s') or key == ord('S'):
                self.switch_model()
            elif key == ord('l') or key == ord('L'):
                self.view = "logs"
            elif key == curses.KEY_UP:
                self.cursor_pos = max(0, self.cursor_pos - 1)
            elif key == curses.KEY_DOWN:
                self.cursor_pos = min(len(self.model_list) - 1, self.cursor_pos + 1)
            elif key == curses.KEY_RESIZE:
                pass

        elif self.view == "logs":
            if key == ord('b') or key == ord('B') or key == 27:  # ESC
                self.view = "main"

    def add_model(self):
        """添加模型"""
        # 新增模型只提供 APINest 和自定义两个服务商入口。
        providers = [
            ("APINest", "https://xn--xhqu89o.cc/v1/chat/completions", ""),
            ("自定义", "", ""),
        ]

        height, width = self.stdscr.getmaxyx()
        # 在底部显示选择
        self.stdscr.nodelay(False)
        curses.curs_set(1)

        # 显示提示
        prompt_y = height - 8
        self.stdscr.addstr(prompt_y, 2, "选择服务商:", curses.color_pair(4))
        for i, (prov, url, model) in enumerate(providers):
            self.stdscr.addstr(prompt_y + 1 + i, 4, f"{i+1}. {prov} - {model}")

        self.stdscr.addstr(prompt_y + len(providers) + 2, 2, "输入编号 (1-2): ", curses.color_pair(4))
        self.stdscr.refresh()

        # 获取输入
        curses.echo()
        try:
            choice = self.stdscr.getstr(prompt_y + len(providers) + 2, 20, 2)
            idx = int(choice.decode()) - 1
            if 0 <= idx < len(providers):
                prov, url, model = providers[idx]
                row = prompt_y + len(providers) + 3
                self.stdscr.addstr(row, 2, "模型 ID: ", curses.color_pair(4))
                self.stdscr.refresh()
                model = self.stdscr.getstr(row, 12, 50).decode().strip()
                row += 1
                if prov == "自定义":
                    self.stdscr.addstr(row, 2, "Base URL: ", curses.color_pair(4))
                    self.stdscr.refresh()
                    url = self.stdscr.getstr(row, 12, 100).decode().strip()
                    row += 1
                self.stdscr.addstr(row, 2, "API Key: ", curses.color_pair(4))
                self.stdscr.refresh()
                api_key = self.stdscr.getstr(row, 12, 100).decode().strip()

                # 保存
                resp = api_post("/api/config/save", {
                    "provider": prov,
                    "model": model,
                    "url": url,
                    "api_key": api_key,
                })
                if resp.get("ok"):
                    self.show_message(f"✓ 已添加模型: {model}", 1)
                else:
                    self.show_message(f"✗ 添加失败: {resp.get('error', '未知错误')}", 3)
            else:
                self.show_message("✗ 无效选择", 3)
        except (ValueError, UnicodeDecodeError):
            self.show_message("✗ 输入错误", 3)

        curses.noecho()
        curses.curs_set(0)
        self.stdscr.nodelay(True)
        self.stdscr.clear()

    def delete_model(self):
        """删除当前选中的模型"""
        if not self.model_list or self.cursor_pos >= len(self.model_list):
            self.show_message("✗ 没有可删除的模型", 3)
            return

        model = self.model_list[self.cursor_pos]
        resp = api_post("/api/config/delete", {"index": self.cursor_pos})
        if resp.get("ok"):
            self.show_message(f"✓ 已删除: {model.get('model', '')}", 1)
            self.cursor_pos = max(0, self.cursor_pos - 1)
        else:
            self.show_message("✗ 删除失败", 3)

    def switch_model(self):
        """切换到当前选中的模型"""
        if not self.model_list or self.cursor_pos >= len(self.model_list):
            self.show_message("✗ 没有可切换的模型", 3)
            return

        model = self.model_list[self.cursor_pos]
        resp = api_post("/api/model/select", {
            "route": f"custom:{self.cursor_pos}",
            "model": model.get("model", ""),
        })
        if resp.get("ok"):
            self.show_message(f"✓ 已切换到: {resp.get('model_name', model.get('model', ''))}", 1)
        else:
            self.show_message(f"✗ 切换失败: {resp.get('error', '未知错误')}", 3)

    def run(self):
        """主运行循环"""
        while self.running:
            self.draw()
            self.handle_input()


def main():
    # 启动 API 服务器
    web_api.start_server()
    print("控制 API 已启动,正在初始化终端界面...")
    time.sleep(1)

    def run_tui(stdscr):
        tui = CodexTUI(stdscr)
        tui.run()

    try:
        curses.wrapper(run_tui)
    except KeyboardInterrupt:
        pass
    finally:
        web_api.stop_server()
        print("\nCodex助手 已退出")


if __name__ == "__main__":
    main()
