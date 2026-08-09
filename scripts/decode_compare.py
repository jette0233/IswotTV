from pyzbar.pyzbar import decode
from PIL import Image
import os, sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = os.path.dirname(os.path.abspath(__file__))

images = ["1.jpg", "2.jpg"]
results = {}

for img_name in images:
    img_path = os.path.join(base_dir, img_name)
    if not os.path.exists(img_path):
        print("[X] 未找到: " + img_name)
        continue
    
    img = Image.open(img_path)
    result = decode(img)
    
    if result:
        url = result[0].data.decode("utf-8")
        enc_start = url.find("enc=")
        if enc_start != -1:
            enc_end = url.find("&", enc_start)
            enc = url[enc_start+4:enc_end] if enc_end != -1 else url[enc_start+4:]
            results[img_name] = {"url": url, "enc": enc}
            print("[" + img_name + "]")
            print("  URL: " + url)
            print("  enc: " + enc)
            print()
        else:
            print("[?] " + img_name + " 未找到enc参数")
    else:
        print("[X] " + img_name + " 解码失败")

print("=" * 60)
if "1.jpg" in results and "2.jpg" in results:
    if results["1.jpg"]["enc"] == results["2.jpg"]["enc"]:
        print(">>> 结论: enc 相同! 视觉刷新 != 底层enc刷新")
        print(">>> 同一个enc: " + results["1.jpg"]["enc"])
    else:
        print(">>> 结论: enc 变了!")
        print(">>> 1.jpg enc: " + results["1.jpg"]["enc"])
        print(">>> 2.jpg enc: " + results["2.jpg"]["enc"])
elif len(results) == 1:
    print(">>> 只有一张图能解码，无法对比")
