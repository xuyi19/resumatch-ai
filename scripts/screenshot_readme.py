# -*- coding: utf-8 -*-
"""README 界面截图工具：CDP 驱动 Edge headless 对 5173 各页截图。

用法：先启动 Edge headless（--remote-debugging-port=9222），再运行本脚本。
"""
import base64
import json
import time
import urllib.request

import websocket

PAGES = [
    ("dashboard", "http://localhost:5173/#/app/dashboard"),
    ("analyze", "http://localhost:5173/#/app/analyze"),
    ("result", "http://localhost:5173/#/app/result/demo3f9c2a7e8b1d"),
    ("history", "http://localhost:5173/#/app/history"),
    ("jobs", "http://localhost:5173/#/app/jobs"),
    ("resumes", "http://localhost:5173/#/app/resumes"),
    ("interview", "http://localhost:5173/#/app/interview"),
    ("settings", "http://localhost:5173/#/settings"),
    ("home", "http://localhost:5173/#/"),
]
OUT = r"e:\code\resumatch-ai\docs\images"


def cdp(ws, method, **params):
    ws.send(json.dumps({"id": cdp.n, "method": method, "params": params}))
    cdp.n += 1
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == cdp.n - 1:
            return msg
cdp.n = 1


def shot(name, url):
    # 新建 tab（新版 Edge 要求 PUT）。fragment 会在 HTTP 层被截断，
    # 所以 tab 只开裸域，路由由 Runtime.evaluate 注入 location.hash 完成
    req = urllib.request.Request(
        "http://127.0.0.1:9222/json/new?about:blank", method="PUT")
    tab = json.loads(urllib.request.urlopen(req).read())
    ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=30)
    cdp(ws, "Emulation.setDeviceMetricsOverride", width=1440, height=900,
        deviceScaleFactor=1.25, mobile=False)
    cdp(ws, "Page.navigate", url="http://localhost:5173/")
    time.sleep(3)  # 等待 SPA 首屏
    # 首启引导弹层会盖住 Dashboard，截图前先落跳过标记（同源 localStorage）；
    # llm_config 预置合法键值，抹掉「配置 AI 服务」Key 引导层（同 E2E 预置逻辑）
    cdp(ws, "Runtime.evaluate", expression=(
        "localStorage.setItem('onboarding_done','1');"
        "localStorage.setItem('llm_config', JSON.stringify({api_key:'sk-shot-mock'}))"
    ))
    # Key 引导层判定在 App 首挂载时已锁定（needGuide 不会因 setItem 重算），
    # reload 一次让 bootCheck 带着预置 Key 重跑
    cdp(ws, "Page.reload")
    time.sleep(2)
    cdp(ws, "Runtime.evaluate",
        expression=f"location.hash = '{url.split('#')[1]}'")
    time.sleep(3)  # 等待路由切换 + 数据请求
    # Dashboard 内容超视口（漏斗/归因/热力图在下方），整页截取
    full = name == "dashboard"
    r = cdp(ws, "Page.captureScreenshot", format="png",
            captureBeyondViewport=full)
    with open(rf"{OUT}\{name}.png", "wb") as f:
        f.write(base64.b64decode(r["result"]["data"]))
    ws.close()
    urllib.request.urlopen(f"http://127.0.0.1:9222/json/close/{tab['id']}")
    print(f"{name}.png OK")


if __name__ == "__main__":
    for name, url in PAGES:
        try:
            shot(name, url)
        except Exception as e:
            print(f"{name}.png FAIL: {e}")
