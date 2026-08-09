"""
百度地图反向地理编码服务
将GPS坐标(WGS84)转换为BD09并获取地址描述
首次使用前需要在 https://lbsyun.baidu.com/ 申请API Key
"""
import requests

BAIDU_AK = "AXKmfevgE6zJ8zMGzJ0KbBxM5VP2RrAZ"


def wgs84_to_bd09_str(lng, lat):
    """WGS84 → BD09 字符串（百度API要求纬度在前）"""
    from app.services.geo_convert import wgs84_to_bd09
    bd_lng, bd_lat = wgs84_to_bd09(lng, lat)
    return f"{bd_lat},{bd_lng}"


def reverse_geocode(lng, lat):
    """
    反向地理编码：坐标 → 地址描述
    返回: address字符串，失败返回None
    """
    if not BAIDU_AK:
        return None

    coords = wgs84_to_bd09_str(float(lng), float(lat))
    url = "https://api.map.baidu.com/reverse_geocoding/v3/"
    params = {
        "ak": BAIDU_AK,
        "output": "json",
        "coordtype": "bd09ll",
        "location": coords,
    }
    try:
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        if data.get("status") == 0:
            return data.get("result", {}).get("formatted_address", "")
    except:
        pass
    return None
