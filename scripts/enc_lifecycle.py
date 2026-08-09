from pyzbar.pyzbar import decode
from PIL import Image
import os, sys

sys.stdout.reconfigure(encoding='utf-8')

base_dir = os.path.dirname(os.path.abspath(__file__))
images = ["00.jpg", "10.jpg", "20.jpg", "30.jpg"]
results = {}

print("=" * 70)
print("enc 生命周期测试 (10s更新间隔)")
print("=" * 70)

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
        aid_start = url.find("id=")
        c_start = url.find("&c=")
        
        aid = url[aid_start+3:url.find("&", aid_start)] if aid_start != -1 else "N/A"
        c_val = url[c_start+3:url.find("&", c_start+3)] if c_start != -1 else "N/A"
        enc = url[enc_start+4:url.find("&", enc_start)] if enc_start != -1 else "N/A"
        
        results[img_name] = {"enc": enc, "activeId": aid, "c": c_val}
    else:
        results[img_name] = {"enc": "DECODE_FAIL", "activeId": "?", "c": "?"}

# 打印表格
print()
print(f"{'时刻':<8} {'enc':<36} {'activeId':<18} {'c':<10}")
print("-" * 72)
for i, img_name in enumerate(images):
    r = results[img_name]
    time_label = f"T+{i*10}s"
    enc_display = r["enc"][:32]
    print(f"{time_label:<8} {enc_display:<36} {r['activeId']:<18} {r['c']:<10}")

print()
print("=" * 70)

# 分析enc变化模式
encs = [results[img]["enc"] for img in images if results[img]["enc"] != "DECODE_FAIL"]
unique_encs = list(set(encs))

if len(unique_encs) == 1:
    print(">>> enc 全程没变!")
elif len(encs) == len(unique_encs):
    print(">>> 每个10s都生成一个全新的enc，无复用")
else:
    print(">>> enc 变化模式: " + " -> ".join(encs))
    for i in range(1, len(encs)):
        status = "变化" if encs[i] != encs[i-1] else "相同"
        print(f"    T+{i*10}s: {status}")

print()
# 检查activeId是否一致
aids = [results[img]["activeId"] for img in images if results[img]["activeId"] != "N/A"]
if len(set(aids)) == 1:
    print(">>> activeId (签到活动ID) 始终保持不变: " + aids[0])
else:
    print(">>> activeId 也变了! " + str(aids))
