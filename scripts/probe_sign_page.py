import os
import requests, re, sys

sys.stdout.reconfigure(encoding='utf-8')

cookie_str = os.environ["CHAOXING_COOKIE"]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": cookie_str,
}

activeId = "1000159576320"
# 用最新一张截图里的enc
enc = "CAEFA8F9020550F567F306F972B0A5E9"

# 访问签到页面
url = f"https://mobilelearn.chaoxing.com/widget/sign/e?id={activeId}&enc={enc}&c=466760&DB_STRATEGY=PRIMARY_KEY&STRATEGY_PARA=id"
print(f"访问: {url}")
r = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
print(f"状态码: {r.status_code}")
print(f"最终URL: {r.url}")
print(f"内容长度: {len(r.text)}")
print()
print("--- 页面内容前2000字 ---")
print(r.text[:2000])

# 搜索验证码相关关键词
keywords = ["captcha", "geetest", "slide", "滑块", "验证", "validate", "gt", "challenge"]
print()
print("--- 搜索验证码相关关键词 ---")
for kw in keywords:
    if kw in r.text.lower():
        # 找上下文
        idx = r.text.lower().find(kw)
        start = max(0, idx - 50)
        end = min(len(r.text), idx + 100)
        print(f"\n找到 '{kw}' 在位置 {idx}:")
        print(f"  ...{r.text[start:end]}...")
