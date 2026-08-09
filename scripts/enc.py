from pyzbar.pyzbar import decode
from PIL import Image

img = Image.open(r"tem2.jpg")
result = decode(img)
for b in result:
    print("解码结果:", b.data.decode("utf-8"))
