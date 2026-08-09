import requests
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

cookie_str = os.environ["CHAOXING_COOKIE"]

headers = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Cookie": cookie_str,
    "Referer": "https://mobilelearn.chaoxing.com/",
}

activeId = "1000159576320"
enc = "CAEFA8F9020550F567F306F972B0A5E9"

print("=" * 60)
print("Step 1: 调签到API确认validate返回")
print("=" * 60)

url_sign = f"https://mobilelearn.chaoxing.com/pptSign/stuSignajax?activeId={activeId}&enc={enc}&clientip=&latitude=-1&longitude=-1&appType=15&fid=0&address="
r = requests.get(url_sign, headers=headers, timeout=10)
print(f"状态码: {r.status_code}")
print(f"返回内容: {r.text[:200]}")
print()

# 如果是validate_xxx，提取validate ID
validate_id = None
if "validate" in r.text.lower():
    import re
    match = re.search(r'validate_([A-F0-9]+)', r.text, re.IGNORECASE)
    if match:
        validate_id = match.group(1)
        print(f"提取到validate ID: {validate_id}")
    else:
        print(f"raw validate: {r.text[:100]}")

print()
print("=" * 60)
print("Step 2: 探索验证码相关接口")
print("=" * 60)

# 常见验证码接口路径
captcha_paths = [
    f"/pptSign/validateCode?validate={validate_id}" if validate_id else "",
    f"/commonCaptcha/get?validateId={validate_id}" if validate_id else "",
    f"/pptSign/slideCaptcha/get?validateId={validate_id}" if validate_id else "",
    f"/pptSign/captcha/get?validateId={validate_id}" if validate_id else "",
    "/commonCaptcha/getCaptcha",
    "/captcha/get",
    "/slideCaptcha/get",
    "/commonCaptcha/getCaptcha?type=SLIDE",
    "/commonCaptcha/image",
]

base = "https://mobilelearn.chaoxing.com"
for path in captcha_paths:
    if not path:
        continue
    url = base + path
    try:
        r2 = requests.get(url, headers=headers, timeout=8)
        print(f"\n[{r2.status_code}] {path}")
        print(f"  内容[:200]: {r2.text[:200]}")
    except Exception as e:
        print(f"[ERR] {path}: {e}")

print()
print("=" * 60)
print("Step 3: 尝试用activeId相关的API")
print("=" * 60)

other_paths = [
    f"/v2/apis/sign/getSignDetail?activeId={activeId}",
    f"/v2/apis/sign/getActiveDetail?activeId={activeId}",
    f"/widget/sign/pcStuSignController/getActiveInfo?activeId={activeId}",
]

for path in other_paths:
    url = base + path
    try:
        r2 = requests.get(url, headers=headers, timeout=8)
        print(f"\n[{r2.status_code}] {path}")
        print(f"  内容[:300]: {r2.text[:300]}")
    except Exception as e:
        print(f"[ERR] {path}: {e}")
