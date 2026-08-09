import os
import requests, sys
sys.stdout.reconfigure(encoding="utf-8")

cookie_str = os.environ["CHAOXING_COOKIE"]

headers = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Cookie": cookie_str,
}

validate_id = "313F8AA64D3789CF5B5CD171E3FFF401"

# passport2 上返回200的路径
urls = [
    f"https://passport2.chaoxing.com/commonCaptcha/get?validateId={validate_id}",
    f"https://passport2.chaoxing.com/slide/getCaptcha",
    f"https://passport2.chaoxing.com/api/captcha/get",
    f"https://passport2.chaoxing.com/captcha/image",
    f"https://passport2.chaoxing.com/commonCaptcha/slide/get",
    f"https://passport2.chaoxing.com/captcha/get?validateId={validate_id}",
    f"https://passport2.chaoxing.com/api/slide/get",
]

for url in urls:
    print(f"\n{'='*60}")
    print(f"GET {url}")
    print(f"{'='*60}")
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('Content-Type', 'N/A')}")
        print(f"Content-Length: {len(r.content)}")
        # 判断是不是图片
        if "image" in r.headers.get("Content-Type", ""):
            # 保存图片
            fname = url.split("/")[-1].split("?")[0] + ".png"
            with open(fname, "wb") as f:
                f.write(r.content)
            print(f"Saved as: {fname}")
        else:
            print(f"Content[:500]: {r.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")
