import os
import requests, sys
sys.stdout.reconfigure(encoding='utf-8')

cookie_str = os.environ["CHAOXING_COOKIE"]

headers = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Cookie": cookie_str,
}

validate_id = "313F8AA64D3789CF5B5CD171E3FFF401"

# 尝试不同domain + 不同path的组合
domains = [
    "https://mobilelearn.chaoxing.com",
    "https://mooc1.chaoxing.com",
    "https://mooc2.chaoxing.com",
    "https://passport2.chaoxing.com",
    "https://i.chaoxing.com",
]

paths = [
    f"/commonCaptcha/get?validateId={validate_id}",
    "/slide/getCaptcha",
    "/api/captcha/get",
    "/captcha/image",
    "/commonCaptcha/slide/get",
    f"/captcha/get?validateId={validate_id}",
    "/api/slide/get",
]

found = False
for domain in domains:
    for path in paths:
        url = domain + path
        try:
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code != 500:
                found = True
                print(f"[{r.status_code}] {url}")
                print(f"  内容: {r.text[:200]}")
                print()
        except:
            pass

if not found:
    print("所有路径都返回500，验证码系统不在这些标准路径下")
    print()
    print("验证码是学习通App内原生实现的，接口路径可能在App内部硬编码")
    print("需要抓包App流量才能获取")
