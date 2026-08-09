"""
滑块验证码服务 - 自建 OpenCV Canny 方案
当签到接口返回 validate_xxx 时，走 captcha.chaoxing.com 完整流程获取 validate token

流程：
1. get/conf → 获取服务器时间戳 service_time
2. 用 service_time 生成 captchaKey/token，用本地时间生成 iv
3. get/verification/image → 获取滑块图片 URL + next_token
4. OpenCV Canny + matchTemplate → 计算滑动距离
5. check/verification/result → 提交距离 → 拿到 validate token (extraData)
6. 带 validate 重试签到

关键发现：
- captchaKey 和 token 用服务器时间，iv 用本地时间
- ddddocr slide_match 在学习通滑块上识别率极低（~0%）
- OpenCV Canny + TM_CCOEFF_NORMED 识别率高（一次通过）
- extraData 返回的是 JSON 字符串，需解析出 validate 字段
"""

import re
import json
import hashlib
import random
import time
import requests

import cv2
import numpy as np

# ─── 常量 ───
CAPTCHA_BASE = "https://captcha.chaoxing.com/captcha"
CAPTCHA_ID = "qDG21VMg9qS5Rcok4cfpnHGnpf5LhcAv"
CAPTCHA_TYPE = "slide"

# ─── UUID 生成（与学习通 JS 端一致） ───

def _uuid():
    """生成与学习通 JS 端相同格式的 UUID（无大写，特定位置固定值）"""
    hex_chars = "0123456789abcdef"
    vA = [random.choice(hex_chars) for _ in range(36)]
    vA[14] = "4"
    try:
        num = int(vA[19], 16)
    except ValueError:
        num = 0
    vA[19] = hex_chars[(num & 3) | 8]
    for pos in [8, 13, 18, 23]:
        vA[pos] = "-"
    return "".join(vA)


def _md5(data):
    return hashlib.md5(data.encode("utf-8")).hexdigest()


# ─── OpenCV 滑块距离计算 ───


def _calc_distance_opencv(small_bytes, big_bytes):
    """
    使用 OpenCV matchTemplate 计算滑块缺口 x 坐标。
    流程：
    1. 将滑块裁剪到非透明区域（去掉透明背景噪声）
    2. 限定背景图 y 轴 ROI（滑块的 y 坐标固定，只在此区域搜索，避免干扰阴影）
    3. 多策略匹配：灰度 → 模糊 → Canny → CCORR
    返回 x 坐标（像素），全部失败返回 None
    """
    try:
        nparr_big = np.frombuffer(big_bytes, np.uint8)
        nparr_small = np.frombuffer(small_bytes, np.uint8)
        big_img = cv2.imdecode(nparr_big, cv2.IMREAD_COLOR)
        small_img = cv2.imdecode(nparr_small, cv2.IMREAD_UNCHANGED)

        if big_img is None or small_img is None:
            print("[CaptchaSolver] 图片解码失败")
            return None

        # ── 转灰度 ──
        big_gray = cv2.cvtColor(big_img, cv2.COLOR_BGR2GRAY)
        if len(small_img.shape) == 3 and small_img.shape[2] == 4:
            small_gray = cv2.cvtColor(small_img, cv2.COLOR_BGRA2GRAY)
        else:
            small_gray = cv2.cvtColor(small_img, cv2.COLOR_BGR2GRAY)

        # ── 裁剪滑块到非透明区域 ──
        crop_x, crop_y, crop_w, crop_h = 0, 0, small_gray.shape[1], small_gray.shape[0]
        small_cropped = small_gray
        if len(small_img.shape) == 3 and small_img.shape[2] == 4:
            alpha = small_img[:, :, 3]
            nz = cv2.findNonZero(alpha)
            if nz is not None:
                sx, sy, sw, sh = cv2.boundingRect(nz)
                if sw > 10 and sh > 10:
                    crop_x, crop_y, crop_w, crop_h = sx, sy, sw, sh
                    small_cropped = small_gray[sy:sy+sh, sx:sx+sw]

        # ── 限定背景 ROI（以滑块 y 为中心 ±40px，排除干扰阴影） ──
        slider_center_y = crop_y + crop_h // 2
        roi_y_start = max(0, slider_center_y - 40)
        roi_y_end = min(big_gray.shape[0], slider_center_y + 40)
        big_roi = big_gray[roi_y_start:roi_y_end, :]

        if small_cropped.shape[0] < big_roi.shape[0] and small_cropped.shape[1] < big_roi.shape[1]:

            # ── 策略1: 灰度图 TM_CCOEFF_NORMED ──
            res = cv2.matchTemplate(big_roi, small_cropped, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val > 0.50:
                print(f"[CaptchaSolver] 灰度匹配 x={max_loc[0]} conf={max_val:.3f}")
                return max_loc[0]

            # ── 策略2: 高斯模糊 ──
            big_blur = cv2.GaussianBlur(big_roi, (5, 5), 0)
            small_blur = cv2.GaussianBlur(small_cropped, (5, 5), 0)
            res2 = cv2.matchTemplate(big_blur, small_blur, cv2.TM_CCOEFF_NORMED)
            _, max_val2, _, max_loc2 = cv2.minMaxLoc(res2)
            if max_val2 > 0.45:
                print(f"[CaptchaSolver] 模糊匹配 x={max_loc2[0]} conf={max_val2:.3f}")
                return max_loc2[0]

            # ── 策略3: Canny ──
            big_canny = cv2.Canny(big_blur, 50, 150)
            small_canny = cv2.Canny(small_blur, 50, 150)
            res3 = cv2.matchTemplate(big_canny, small_canny, cv2.TM_CCOEFF_NORMED)
            _, max_val3, _, max_loc3 = cv2.minMaxLoc(res3)
            if max_val3 > 0.35:
                print(f"[CaptchaSolver] Canny匹配 x={max_loc3[0]} conf={max_val3:.3f}")
                return max_loc3[0]

            # ── 策略4: TM_CCORR_NORMED 兜底 ──
            res4 = cv2.matchTemplate(big_roi, small_cropped, cv2.TM_CCORR_NORMED)
            _, max_val4, _, max_loc4 = cv2.minMaxLoc(res4)
            print(f"[CaptchaSolver] 最终匹配 x={max_loc4[0]} conf={max_val4:.3f}")
            return max_loc4[0]
        else:
            print(f"[CaptchaSolver] 裁剪后尺寸异常, 回退原图匹配")
            res4 = cv2.matchTemplate(big_gray, small_gray, cv2.TM_CCORR_NORMED)
            _, max_val4, _, max_loc4 = cv2.minMaxLoc(res4)
            print(f"[CaptchaSolver] 回退匹配 x={max_loc4[0]} conf={max_val4:.3f}")
            return max_loc4[0]

    except Exception as e:
        print(f"[CaptchaSolver] OpenCV 计算距离失败: {e}")
        return None


# ─── 步骤 1: 获取服务器时间 ───

def _get_service_time(cookie=""):
    """从 get/conf 获取服务器时间戳"""
    local_time = str(int(time.time() * 1000))
    params = {
        "callback": "cx_captcha_function",
        "captchaId": CAPTCHA_ID,
        "_": local_time,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    }
    if cookie:
        headers["Cookie"] = cookie

    try:
        resp = requests.get(f"{CAPTCHA_BASE}/get/conf", params=params, headers=headers, timeout=15)
        text = resp.text
        json_str = re.sub(r'^cx_captcha_function\(', '', text).rstrip(')')
        data = json.loads(json_str)
        service_time = data.get("t", "")
        print(f"[CaptchaSolver] get/conf 成功, server_time={service_time}")
        return str(service_time)
    except Exception as e:
        print(f"[CaptchaSolver] get/conf 失败: {e}")
        return None


# ─── 步骤 2: 获取滑块图片 ───

def _get_images(cookie, service_time):
    """用服务器时间生成加密参数，获取滑块图片 URL + next_token"""
    local_time = str(int(time.time() * 1000))

    captcha_key = _md5(service_time + _uuid())
    token = _md5(service_time + CAPTCHA_ID + CAPTCHA_TYPE + captcha_key) + ":" + str(int(service_time) + 300000)
    iv = _md5(CAPTCHA_ID + CAPTCHA_TYPE + local_time + _uuid())

    params = {
        "callback": "cx_captcha_function",
        "captchaId": CAPTCHA_ID,
        "type": CAPTCHA_TYPE,
        "version": "1.1.20",
        "captchaKey": captcha_key,
        "token": token,
        "referer": "https://v8.chaoxing.com/",
        "iv": iv,
        "_": local_time,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    }
    if cookie:
        headers["Cookie"] = cookie

    try:
        resp = requests.get(f"{CAPTCHA_BASE}/get/verification/image", params=params, headers=headers, timeout=15)
        text = resp.text
        json_str = re.sub(r'^cx_captcha_function\(', '', text).rstrip(')')

        if '"10030"' in json_str:
            print(f"[CaptchaSolver] image 接口返回验证错误: {json_str[:100]}")
            return None, None, None, None

        data = json.loads(json_str)
        next_token = data.get("token", "")
        img_vo = data.get("imageVerificationVo", {})
        shade_url = img_vo.get("shadeImage", "")
        cutout_url = img_vo.get("cutoutImage", "")

        if not next_token or not shade_url or not cutout_url:
            print(f"[CaptchaSolver] image 解析失败: keys={list(data.keys())}")
            return None, None, None, None

        print(f"[CaptchaSolver] 获取图片成功")
        return next_token, shade_url, cutout_url, iv

    except Exception as e:
        print(f"[CaptchaSolver] get/image 失败: {e}")
        return None, None, None, None


# ─── 生成类人滑动轨迹 ───

def _generate_track(distance):
    """
    生成类人滑动轨迹，包含多个 (x, y, t) 点。
    模拟：加速 → 匀速 → 减速 → 微调
    """
    import random
    track = []
    current = 0
    t = 0
    # 先快速移动大半段距离
    mid = int(distance * random.uniform(0.6, 0.8))
    while current < mid:
        step = random.randint(3, 8)
        current = min(current + step, mid)
        t += random.randint(8, 20)
        track.append({"x": current, "y": random.randint(-2, 2), "t": t})
    # 减速逼近
    while current < distance - 2:
        step = random.randint(1, 3)
        current = min(current + step, distance)
        t += random.randint(15, 30)
        track.append({"x": current, "y": random.randint(-1, 1), "t": t})
    # 最后微调
    if current != distance:
        track.append({"x": distance, "y": 0, "t": t + random.randint(10, 30)})
    return track


# ─── 步骤 4: 提交验证结果 ───

def _check_result(cookie, next_token, iv, distance):
    """提交滑块验证结果，成功返回 validate token"""
    local_time = str(int(time.time() * 1000))
    # 生成类人轨迹
    track = _generate_track(distance)
    params = {
        "callback": "cx_captcha_function",
        "captchaId": CAPTCHA_ID,
        "type": CAPTCHA_TYPE,
        "token": next_token,
        "textClickArr": json.dumps(track),
        "coordinate": "[]",
        "runEnv": "10",
        "version": "1.1.20",
        "t": "a",
        "iv": iv,
        "_": local_time,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    }
    if cookie:
        headers["Cookie"] = cookie

    try:
        resp = requests.get(f"{CAPTCHA_BASE}/check/verification/result", params=params, headers=headers, timeout=15)
        text = resp.text
        json_str = re.sub(r'^cx_captcha_function\(', '', text).rstrip(')')

        data = json.loads(json_str)
        result_val = data.get("result", False)
        extra_data_str = data.get("extraData", "")

        if result_val and extra_data_str:
            # extraData 是 JSON 字符串，里面包含 validate 字段
            try:
                extra_data = json.loads(extra_data_str)
                validate_token = extra_data.get("validate", "")
            except (json.JSONDecodeError, TypeError):
                # 可能直接就是 validate token
                validate_token = extra_data_str

            if validate_token:
                print(f"[CaptchaSolver] 验证通过! validate={validate_token[:40]}...")
                return validate_token
            else:
                print(f"[CaptchaSolver] 验证通过但无 validate: {extra_data_str[:200]}")
                return None
        else:
            print(f"[CaptchaSolver] 验证失败: {json_str[:200]}")
            return None

    except Exception as e:
        print(f"[CaptchaSolver] check/result 失败: {e}")
        return None


# ─── 主入口: 完整滑块验证流程 ───

def solve_validate(cookie="", max_retries=3):
    """
    执行完整滑块验证码流程，返回 validate token。
    最多重试 max_retries 次。

    参数:
        cookie: 学习通 Cookie 字符串（可选）
        max_retries: 最大重试次数

    返回:
        validate token 字符串，失败返回 None
    """
    img_headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    }

    for attempt in range(1, max_retries + 1):
        print(f"[CaptchaSolver] 第 {attempt}/{max_retries} 次尝试...")

        # 步骤 1: 获取服务器时间
        service_time = _get_service_time(cookie)
        if not service_time:
            continue

        # 步骤 2: 获取图片
        next_token, shade_url, cutout_url, iv = _get_images(cookie, service_time)
        if not next_token:
            continue

        # 步骤 3: 计算距离
        big_bytes = requests.get(shade_url, headers=img_headers, timeout=15).content
        small_bytes = requests.get(cutout_url, headers=img_headers, timeout=15).content
        distance = _calc_distance_opencv(small_bytes, big_bytes)
        if distance is None:
            continue

        # 步骤 4: 提交验证
        validate_token = _check_result(cookie, next_token, iv, distance)
        if validate_token:
            return validate_token

        # 失败，短暂等待后重试
        time.sleep(0.5)

    print(f"[CaptchaSolver] {max_retries} 次尝试均失败")
    return None


def sign_with_captcha(sign_func, cookie, enc, active_id, latitude="-1", longitude="-1", address=""):
    """
    （已弃用验证码求解）直接尝试签到，检测到滑块验证时返回原始结果。
    """
    result_text, status, message = sign_func(cookie, enc, active_id, latitude, longitude, None, address)
    if "validate" in result_text.lower() and "success" not in result_text.lower():
        return result_text, "fail", f"需要滑块验证: {result_text[:50]}"
    return result_text, status, message
