"""
定位签到专用模块
使用 /pptSign 接口而不是 stuSignajax
"""
import requests


def sign_location(cookie, name, active_id, address, latitude, longitude, fid):
    """
    定位签到
    参数:
        cookie: 学习通Cookie字符串
        name: 学生姓名（学习通里的真实姓名）
        active_id: 签到活动ID
        address: 地址描述
        latitude: 纬度
        longitude: 经度
        fid: 学校ID（从Cookie或配置获取）
    """
    # 从Cookie中提取uid和fid
    uid = ""
    import re
    uid_match = re.search(r'_uid=(\d+)', cookie)
    if uid_match:
        uid = uid_match.group(1)

    params = {
        "name": name,
        "address": address,
        "activeId": active_id,
        "uid": uid,
        "clientip": "",
        "latitude": str(latitude),
        "longitude": str(longitude),
        "fid": str(fid) if fid else "0",
        "appType": "15",
        "ifTiJiao": "1",
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Cookie": cookie,
        "Referer": "https://mobilelearn.chaoxing.com/",
    }

    try:
        resp = requests.get(
            "https://mobilelearn.chaoxing.com/pptSign",
            params=params,
            headers=headers,
            timeout=10,
        )
        text = resp.text.strip()

        if "success" in text.lower():
            return text, "success", "定位签到成功"
        elif "签到过了" in text or "已签到" in text:
            return text, "success", "已签到"
        elif "errorLocation1" in text:
            return text, "fail", "位置不匹配(errorLocation1)"
        elif "validate" in text.lower():
            return text, "fail", f"需要滑块验证: {text[:50]}"
        elif "请登录" in text:
            return text, "fail", "Cookie已失效"
        else:
            return text, "fail", f"签到失败: {text[:100]}"
    except Exception as e:
        return str(e), "fail", f"网络错误: {str(e)}"
