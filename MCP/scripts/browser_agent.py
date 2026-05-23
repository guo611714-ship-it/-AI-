"""browser-harness + browser-use 封装模块.

browser-harness: 通过 CDP 直接连接浏览器，命令行调用
browser-use: AI 驱动的浏览器自动化

策略：browser-harness 优先（更快更直接），browser-use 作为备选
"""

import asyncio
import time
import logging
import os
import json
import subprocess
import tempfile
from typing import Optional, Dict, Any

logger = logging.getLogger("browser_agent")

# 性能统计
_stats = {
    "harness_calls": 0,
    "harness_success": 0,
    "harness_fallback": 0,
    "use_calls": 0,
    "use_success": 0,
    "use_fallback": 0,
    "avg_response_time": 0,
    "last_error": None,
}


def get_stats() -> dict:
    """获取性能统计."""
    return _stats.copy()


class BrowserAgent:
    """浏览器操控器 — browser-harness 优先，browser-use 备选."""

    def __init__(self):
        self._harness_available = None
        self._use_available = None
        self._agents = {}
        self._llm = None

    def _check_harness(self) -> bool:
        """检测 browser-harness 是否可用."""
        if self._harness_available is not None:
            return self._harness_available

        try:
            result = subprocess.run(
                ["browser-harness", "--version"],
                capture_output=True,
                timeout=5
            )
            self._harness_available = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self._harness_available = False

        if self._harness_available:
            logger.info("browser-harness available")
        else:
            logger.info("browser-harness not available")

        return self._harness_available

    def _detect_cdp_url(self, prefer_platform: str = None) -> Optional[str]:
        """检测 CDP URL，优先返回有目标平台页面的端口."""
        import urllib.request

        # 1. 优先读取ai-chat MCP保存的端口文件
        cdp_port_file = os.path.join(os.path.dirname(__file__), ".cdp_port")
        if os.path.exists(cdp_port_file):
            try:
                with open(cdp_port_file, "r") as f:
                    saved_cdp = f.read().strip()
                if saved_cdp:
                    req = urllib.request.urlopen(f"{saved_cdp}/json/version", timeout=2)
                    if "Browser" in req.read().decode():
                        _stats["last_error"] = None
                        return saved_cdp
            except Exception:
                pass

        # 2. 扫描所有端口
        best_port = None
        for port in [9222, 9223, 9224, 9225]:
            try:
                req = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2)
                data = req.read().decode()
                if "Browser" not in data:
                    continue

                # 如果指定了平台，检查是否有该平台的标签页
                if prefer_platform:
                    req2 = urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2)
                    tabs = json.loads(req2.read())
                    platform_urls = {"doubao": "doubao.com", "deepseek": "deepseek.com", "volcengine": "volcengine"}
                    target = platform_urls.get(prefer_platform, "")
                    for t in tabs:
                        if target in t.get("url", ""):
                            return f"http://127.0.0.1:{port}"

                if best_port is None:
                    best_port = port
            except Exception:
                pass
        return f"http://127.0.0.1:{best_port}" if best_port else None

    def _check_use(self) -> bool:
        """检测 browser-use 是否可用."""
        if self._use_available is not None:
            return self._use_available

        try:
            import browser_use
            self._use_available = True
        except ImportError:
            self._use_available = False

        if self._use_available:
            logger.info("browser-use available")
        else:
            logger.info("browser-use not available")

        return self._use_available

    # ── Chrome CDP 管理 ────────────────────────────────────────────

    def _ensure_chrome_cdp(self) -> Optional[str]:
        """确保有 Chrome 实例在 CDP 端口上运行，返回 CDP URL."""
        # 先检查现有端口
        cdp_url = self._detect_cdp_url()
        if cdp_url:
            return cdp_url

        # 没有可用的 CDP 端口，启动新的 Chrome 实例
        cdp_port = 9223
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
        ]
        chrome_exe = None
        for p in chrome_paths:
            if os.path.exists(p):
                chrome_exe = p
                break
        if not chrome_exe:
            logger.error("Chrome not found")
            return None

        # 用独立 user-data-dir 启动，避免和现有 Chrome 冲突
        user_data = os.path.join(tempfile.gettempdir(), "bh-chrome-cdp")
        try:
            subprocess.Popen([
                chrome_exe,
                f"--remote-debugging-port={cdp_port}",
                f"--user-data-dir={user_data}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-networking",
                "--disable-sync",
                "--disable-translate",
                "--disable-extensions",
                "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info(f"Launched Chrome with CDP port {cdp_port}")

            # 等待端口就绪
            import urllib.request
            for _ in range(20):
                time.sleep(0.5)
                try:
                    req = urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json/version", timeout=2)
                    if "Browser" in req.read().decode():
                        cdp_url = f"http://127.0.0.1:{cdp_port}"
                        # 更新 .cdp_port 文件
                        cdp_port_file = os.path.join(os.path.dirname(__file__), ".cdp_port")
                        with open(cdp_port_file, "w") as f:
                            f.write(cdp_url)
                        logger.info(f"Chrome CDP ready at {cdp_url}")
                        return cdp_url
                except Exception:
                    pass
            logger.error(f"Chrome CDP port {cdp_port} did not become ready")
            return None
        except Exception as e:
            logger.error(f"Failed to launch Chrome CDP: {e}")
            return None

    # ── browser-harness 方法 ──────────────────────────────────────

    async def _harness_send(self, page, message: str, platform: str) -> dict:
        """使用 browser-harness 发送消息."""
        try:
            # 构造 Python 代码
            code = self._get_harness_code(message, platform)

            # 确保有 CDP 端口可用
            cdp_url = self._ensure_chrome_cdp()
            env = os.environ.copy()
            if cdp_url:
                env['BU_CDP_URL'] = cdp_url

            # 执行 browser-harness
            result = subprocess.run(
                ['browser-harness'],
                input=code,
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )

            if result.returncode == 0:
                return {"ok": True, "method": "browser-harness", "error": None, "output": result.stdout}
            else:
                return {"ok": False, "method": "browser-harness", "error": result.stderr[:200]}

        except subprocess.TimeoutExpired:
            return {"ok": False, "method": "browser-harness", "error": "timeout"}
        except Exception as e:
            logger.error(f"browser-harness send failed: {e}")
            return {"ok": False, "method": "browser-harness", "error": str(e)}

    def _get_harness_code(self, message: str, platform: str) -> str:
        """生成 browser-harness Python 代码."""
        msg_escaped = message.replace('\\', '\\\\').replace('`', '\\`').replace("'", "\\'")

        codes = {
            "doubao": f'''
# 豆包发送消息
page = ensure_real_tab()
wait_for_load()

# 查找输入框
input_info = js("""
    const sels = ['textarea', '[contenteditable="true"]', '[role="textbox"]'];
    for (const s of sels) {{
        const el = document.querySelector(s);
        if (el && el.offsetParent !== null) {{
            const rect = el.getBoundingClientRect();
            return {{x: rect.x + rect.width/2, y: rect.y + rect.height/2, found: true}};
        }}
    }}
    return {{found: false}};
""")

if input_info.get("found"):
    # 点击输入框
    click_at_xy(input_info["x"], input_info["y"])
    time.sleep(0.3)

    # 输入消息
    js(f"""
        const sels = ['textarea', '[contenteditable="true"]', '[role="textbox"]'];
        for (const s of sels) {{
            const el = document.querySelector(s);
            if (el && el.offsetParent !== null) {{
                el.focus();
                if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {{
                    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, '{msg_escaped}');
                    el.dispatchEvent(new Event('input', {{bubbles: true}}));
                }} else {{
                    el.innerText = '{msg_escaped}';
                    el.dispatchEvent(new Event('input', {{bubbles: true}}));
                }}
                break;
            }}
        }}
    """)
    time.sleep(0.3)

    # 查找并点击发送按钮
    btn_info = js("""
        for (const sel of ['button[type="submit"]', 'button[class*="send"]', 'button[aria-label*="发送"]']) {{
            const btn = document.querySelector(sel);
            if (btn && btn.offsetParent !== null && !btn.disabled) {{
                const rect = btn.getBoundingClientRect();
                return {{x: rect.x + rect.width/2, y: rect.y + rect.height/2, found: true}};
            }}
        }}
        return {{found: false}};
    """)

    if btn_info.get("found"):
        click_at_xy(btn_info["x"], btn_info["y"])
        print("OK: message sent via button click")
    else:
        # 尝试 Enter 键
        js("""
            const input = document.querySelector('textarea, [contenteditable="true"]');
            if (input) {{
                input.dispatchEvent(new KeyboardEvent('keydown', {{key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}}));
            }}
        """)
        print("OK: message sent via Enter key")
else:
    print("ERROR: input not found")
''',
            "deepseek": f'''
# DeepSeek发送消息
page = ensure_real_tab()
wait_for_load()

# 查找输入框
input_info = js("""
    const sels = ['textarea', '[contenteditable="true"]'];
    for (const s of sels) {{
        const el = document.querySelector(s);
        if (el && el.offsetParent !== null) {{
            const rect = el.getBoundingClientRect();
            return {{x: rect.x + rect.width/2, y: rect.y + rect.height/2, found: true}};
        }}
    }}
    return {{found: false}};
""")

if input_info.get("found"):
    click_at_xy(input_info["x"], input_info["y"])
    time.sleep(0.3)

    # 使用 React 兼容的方式设置值
    js(f"""
        const input = document.querySelector('textarea, [contenteditable="true"]');
        if (input) {{
            input.focus();
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
            nativeInputValueSetter.call(input, '{msg_escaped}');
            input.dispatchEvent(new Event('input', {{bubbles: true}}));
            input.dispatchEvent(new Event('change', {{bubbles: true}}));
        }}
    """)
    time.sleep(0.3)

    # 点击发送
    btn_info = js("""
        for (const sel of ['button[aria-label*="send"]', 'button[class*="send"]', 'button[type="submit"]']) {{
            const btn = document.querySelector(sel);
            if (btn && btn.offsetParent !== null && !btn.disabled) {{
                const rect = btn.getBoundingClientRect();
                return {{x: rect.x + rect.width/2, y: rect.y + rect.height/2, found: true}};
            }}
        }}
        return {{found: false}};
    """)

    if btn_info.get("found"):
        click_at_xy(btn_info["x"], btn_info["y"])
        print("OK: message sent")
    else:
        js("""
            const input = document.querySelector('textarea');
            if (input) input.dispatchEvent(new KeyboardEvent('keydown', {{key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}}));
        """)
        print("OK: message sent via Enter")
else:
    print("ERROR: input not found")
''',
            "volcengine": f'''
# 火山引擎发送消息
page = ensure_real_tab()
wait_for_load()

input_info = js("""
    const sels = ['textarea', '[role="textbox"]'];
    for (const s of sels) {{
        const el = document.querySelector(s);
        if (el && el.offsetParent !== null) {{
            const rect = el.getBoundingClientRect();
            return {{x: rect.x + rect.width/2, y: rect.y + rect.height/2, found: true}};
        }}
    }}
    return {{found: false}};
""")

if input_info.get("found"):
    click_at_xy(input_info["x"], input_info["y"])
    time.sleep(0.3)

    js(f"""
        const input = document.querySelector('textarea, [role="textbox"]');
        if (input) {{
            input.focus();
            input.value = '{msg_escaped}';
            input.dispatchEvent(new Event('input', {{bubbles: true}}));
        }}
    """)
    time.sleep(0.3)

    btn_info = js("""
        for (const sel of ['button[class*="send"]', 'button[type="submit"]']) {{
            const btn = document.querySelector(sel);
            if (btn && btn.offsetParent !== null) {{
                const rect = btn.getBoundingClientRect();
                return {{x: rect.x + rect.width/2, y: rect.y + rect.height/2, found: true}};
            }}
        }}
        return {{found: false}};
    """)

    if btn_info.get("found"):
        click_at_xy(btn_info["x"], btn_info["y"])
        print("OK: message sent")
    else:
        print("ERROR: send button not found")
else:
    print("ERROR: input not found")
''',
        }

        return codes.get(platform, codes["doubao"])

    # ── browser-use 方法 ──────────────────────────────────────────

    async def _use_send(self, page, message: str, platform: str) -> dict:
        """使用 browser-use 发送消息."""
        try:
            from browser_use import Agent

            agent = await self._get_use_agent(platform, page)
            task = self._get_use_task(message, platform)
            agent.task = task

            result = await agent.run(max_steps=5)

            if result and result.get("done"):
                return {"ok": True, "method": "browser-use", "error": None}

            return {"ok": False, "method": "browser-use", "error": "发送未完成"}

        except Exception as e:
            logger.error(f"browser-use send failed: {e}")
            return {"ok": False, "method": "browser-use", "error": str(e)}

    def _get_use_task(self, message: str, platform: str) -> str:
        """生成 browser-use 任务指令."""
        msg_preview = message[:500] + "..." if len(message) > 500 else message

        tasks = {
            "doubao": f"在豆包对话框中输入消息并发送：{msg_preview}",
            "deepseek": f"在DeepSeek对话框中输入消息并发送：{msg_preview}",
            "volcengine": f"在火山引擎对话框中输入消息并发送：{msg_preview}",
        }
        return tasks.get(platform, f"在对话框中输入并发送：{msg_preview}")

    async def _get_use_agent(self, platform: str, page=None):
        """获取或创建 browser-use Agent."""
        from browser_use import Agent

        if platform in self._agents:
            return self._agents[platform]

        llm = self._get_llm()

        from browser_use.browser.session import BrowserSession
        session = BrowserSession(headless=False)

        agent = Agent(
            task="",
            llm=llm,
            browser_session=session,
            max_actions_per_step=3,
            use_vision=True,
        )

        self._agents[platform] = agent
        return agent

    def _get_llm(self):
        """获取 LLM 实例."""
        if self._llm:
            return self._llm

        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

        if not api_key:
            raise ValueError("需要设置 ANTHROPIC_API_KEY 或 OPENAI_API_KEY 环境变量")

        try:
            from langchain_anthropic import ChatAnthropic
            self._llm = ChatAnthropic(
                model="claude-sonnet-4-20250514",
                api_key=api_key,
                base_url=base_url,
                timeout=30,
            )
        except ImportError:
            from langchain_openai import ChatOpenAI
            self._llm = ChatOpenAI(model="gpt-4o", api_key=api_key, timeout=30)

        return self._llm

    # ── 公共接口 ──────────────────────────────────────────────────

    async def send_message(self, page, message: str, platform: str = "doubao") -> dict:
        """发送消息到 AI 平台.

        策略：browser-harness 优先 → browser-use 备选 → Playwright JS 降级
        """
        start = time.time()

        # 1. 尝试 browser-harness
        if self._check_harness():
            _stats["harness_calls"] += 1
            result = await self._harness_send(page, message, platform)
            elapsed = time.time() - start

            if result.get("ok"):
                _stats["harness_success"] += 1
                self._update_avg_time(elapsed)
                return result

            _stats["harness_fallback"] += 1
            _stats["last_error"] = result.get("error", "")[:100]
            logger.warning(f"browser-harness failed ({elapsed:.1f}s), trying browser-use")

        # 2. 尝试 browser-use
        if self._check_use():
            _stats["use_calls"] += 1
            result = await self._use_send(page, message, platform)
            elapsed = time.time() - start

            if result.get("ok"):
                _stats["use_success"] += 1
                self._update_avg_time(elapsed)
                return result

            _stats["use_fallback"] += 1
            _stats["last_error"] = result.get("error", "")[:100]
            logger.warning(f"browser-use failed ({elapsed:.1f}s), falling back to JS")

        # 3. 降级到 Playwright JS
        return {"ok": False, "method": "fallback", "error": "需要使用 Playwright JS"}

    async def get_response(self, page, platform: str = "doubao", timeout: int = 120) -> str:
        """获取 AI 响应（通过 browser-harness）."""
        if not self._check_harness():
            return ""

        try:
            cdp_url = self._detect_cdp_url(prefer_platform=platform)
            if not cdp_url:
                return ""

            env = os.environ.copy()
            env['BU_CDP_URL'] = cdp_url

            # 生成读取响应的代码
            code = self._get_harness_response_code(platform)

            result = subprocess.run(
                ['browser-harness'],
                input=code,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return ""

        except subprocess.TimeoutExpired:
            return "[超时]"
        except Exception as e:
            logger.error(f"browser-harness get_response failed: {e}")
            return ""

    def _get_harness_response_code(self, platform: str) -> str:
        """生成读取AI响应的 browser-harness 代码."""
        codes = {
            "doubao": '''
page = ensure_real_tab()
wait_for_load()

# 等待响应出现
import time
start = time.time()
prev_text = ""
stable_count = 0

while time.time() - start < 60:
    result = js("""
        const msgs = document.querySelectorAll('[class*="message"], [class*="chat-item"], [class*="response"]');
        let lastText = "";
        for (const msg of msgs) {
            const text = msg.innerText.trim();
            if (text && text.length > 10 && !text.includes("快速") && !text.includes("新对话")) {
                lastText = text;
            }
        }
        return {text: lastText, count: msgs.length};
    """)

    text = result.get("text", "")
    if text and len(text) > 10:
        if text == prev_text:
            stable_count += 1
            if stable_count >= 2:
                print(text)
                break
        else:
            prev_text = text
            stable_count = 0
    time.sleep(1)
else:
    if prev_text:
        print(prev_text)
    else:
        print("")
''',
            "deepseek": '''
page = ensure_real_tab()
wait_for_load()

import time
start = time.time()
prev_text = ""
stable_count = 0

while time.time() - start < 60:
    result = js("""
        const msgs = document.querySelectorAll('.ds-markdown, [class*="message-content"], [class*="assistant"]');
        let lastText = "";
        for (const msg of msgs) {
            const text = msg.innerText.trim();
            if (text && text.length > 10 && !text.includes("内容由 AI")) {
                lastText = text;
            }
        }
        return {text: lastText, count: msgs.length};
    """)

    text = result.get("text", "")
    if text and len(text) > 10:
        if text == prev_text:
            stable_count += 1
            if stable_count >= 2:
                print(text)
                break
        else:
            prev_text = text
            stable_count = 0
    time.sleep(1)
else:
    if prev_text:
        print(prev_text)
    else:
        print("")
''',
            "volcengine": '''
page = ensure_real_tab()
wait_for_load()

import time
start = time.time()
prev_text = ""
stable_count = 0

while time.time() - start < 60:
    result = js("""
        const msgs = document.querySelectorAll('[class*="message"], [class*="response"], [class*="answer"]');
        let lastText = "";
        for (const msg of msgs) {
            const text = msg.innerText.trim();
            if (text && text.length > 10) {
                lastText = text;
            }
        }
        return {text: lastText, count: msgs.length};
    """)

    text = result.get("text", "")
    if text and len(text) > 10:
        if text == prev_text:
            stable_count += 1
            if stable_count >= 2:
                print(text)
                break
        else:
            prev_text = text
            stable_count = 0
    time.sleep(1)
else:
    if prev_text:
        print(prev_text)
    else:
        print("")
''',
        }
        return codes.get(platform, codes["doubao"])

    async def switch_mode(self, page, platform: str) -> dict:
        """切换到最佳模式."""
        if not self._check_harness():
            return {"switched": False, "error": "browser-harness not available"}

        try:
            codes = {
                "deepseek": '''
page = ensure_real_tab()
wait_for_load()
js("""
    const radios = document.querySelectorAll('[role="radio"]');
    for (const r of radios) {
        if (r.innerText.includes('专家') && r.getAttribute('aria-checked') !== 'true') {
            r.click();
            return {switched: true};
        }
    }
    return {switched: false};
""")
print("OK: mode check done")
''',
                "doubao": '''
page = ensure_real_tab()
wait_for_load()
print("OK: doubao mode check done")
''',
                "volcengine": '''
page = ensure_real_tab()
wait_for_load()
print("OK: volcengine mode check done")
''',
            }

            code = codes.get(platform)
            if not code:
                return {"switched": False}

            # 检测 CDP URL（优先找有目标平台页面的端口）
            cdp_url = self._detect_cdp_url(prefer_platform=platform)
            env = os.environ.copy()
            if cdp_url:
                env['BU_CDP_URL'] = cdp_url

            result = subprocess.run(
                ['browser-harness'],
                input=code,
                capture_output=True,
                text=True,
                timeout=15,
                env=env
            )
            return {"switched": result.returncode == 0, "mode": "browser-harness"}

        except Exception as e:
            logger.error(f"browser-harness switch_mode failed: {e}")
            return {"switched": False, "error": str(e)}

    async def check_input_ready(self, page) -> dict:
        """检查输入框是否可用."""
        try:
            result = await page.evaluate(r"""
                () => {
                    const sels = ['textarea', '[contenteditable="true"]', '[role="textbox"]'];
                    for (const s of sels) {
                        const el = document.querySelector(s);
                        if (el && el.offsetParent !== null) return {found: true};
                    }
                    return {found: false};
                }
            """)
            return result
        except Exception as e:
            return {"found": False, "error": str(e)}

    def _update_avg_time(self, new_time: float):
        """更新平均响应时间."""
        current = _stats["avg_response_time"]
        total_calls = _stats["harness_success"] + _stats["use_success"]
        if total_calls > 0:
            _stats["avg_response_time"] = (current * (total_calls - 1) + new_time) / total_calls
        else:
            _stats["avg_response_time"] = new_time

    def invalidate(self):
        """使缓存失效."""
        self._agents.clear()
        self._llm = None
        self._harness_available = None
        self._use_available = None


# 全局实例
_browser_agent = None


def get_browser_agent() -> BrowserAgent:
    """获取全局 BrowserAgent 实例."""
    global _browser_agent
    if _browser_agent is None:
        _browser_agent = BrowserAgent()
    return _browser_agent


def reset_browser_agent():
    """重置全局 BrowserAgent."""
    global _browser_agent
    if _browser_agent:
        _browser_agent.invalidate()
    _browser_agent = None
