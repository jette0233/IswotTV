"""
完整验证码求解链路：
1. agent-browser 打开登录页 → 填表 → 触发验证码
2. 从 DOM 获取验证码图片 URLs
3. 截图 + 下载 JPG → diff 分析找缺口位置
4. JS 注入设置滑块位置并触发验证
5. 提取 validate token
"""
import subprocess, json, time, re, requests, cv2, numpy as np

UA = {'User-Agent': 'Mozilla/5.0'}
BASE_URL = "https://v8.chaoxing.com"

def ab(cmd):
    """执行 agent-browser 命令"""
    full_cmd = f'agent-browser {cmd}'
    r = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=30)
    out = r.stdout.strip()
    # 尝试从 CLIXML 中提取有效输出 (去除 XML 标签)
    if out.startswith('#< CLIXML'):
        # 提取 eval 返回的字符串 (用引号包裹的)
        m = re.search(r'"([^"]*)"', out)
        return m.group(1) if m else out
    return out

# Step 1: Open login page and trigger captcha
print("[1] Opening login page...")
ab(f'open "{BASE_URL}"')
ab('wait --load networkidle')
ab('type "input[placeholder*=\'手机号\']" "15801337883"')
ab('type "input[placeholder*=\'密码\']" "txj20050707"')
ab('click "#login"')
ab('wait --load networkidle')
time.sleep(2)

# Step 2: Get image URLs
print("[2] Getting captcha image URLs...")
img_src = ab('eval "document.querySelector(\'.cx_imgBtn img\').src"')
bg_style = ab('eval "document.querySelector(\'.cx_imgBg\').style.backgroundImage"')
print(f"  img_src={img_src}")
print(f"  bg_style={bg_style[:60]}...")

small_url = img_src.strip('"')
big_match = re.search(r'"(https://[^"]+)"', bg_style)
if not big_match:
    # Try alternative parsing
    big_match = re.search(r'url\(["\']?([^"\'\)]+)["\']?\)', bg_style)
big_url = big_match.group(1) if big_match else ""

print(f"  Big: {big_url}")
print(f"  Small: {small_url}")

# Step 3: Download images and screenshot
print("[3] Analyzing captcha...")
big_bytes = requests.get(big_url, headers=UA).content
small_bytes = requests.get(small_url, headers=UA).content

# Take screenshot
ab('screenshot')
time.sleep(1)

# Find screenshot file
import glob
screenshots = glob.glob("C:\\Users\\16200\\.agent-browser\\tmp\\screenshots\\*.png")
if not screenshots:
    print("No screenshot found!")
    exit()
screenshot_path = max(screenshots, key=os.path.getmtime)

# Step 4: Diff analysis on screenshot vs JPG
screenshot = cv2.imread(screenshot_path)
if screenshot is None:
    print("Failed to load screenshot")
    exit()

# Background position from DOM
bg_left, bg_top = 464, 222
bg_w, bg_h = 320, 160

# Crop screenshot to background area (with some margin)
crop = screenshot[bg_top-4:bg_top+bg_h+4, bg_left-4:bg_left+bg_w+4]
ss_bg = cv2.resize(crop, (320, 160))

# Download JPG
jpg = cv2.imdecode(np.frombuffer(big_bytes, np.uint8), cv2.IMREAD_COLOR)

# Compute diff
ss_gray = cv2.cvtColor(ss_bg, cv2.COLOR_BGR2GRAY).astype(float)
jpg_gray = cv2.cvtColor(jpg, cv2.COLOR_BGR2GRAY).astype(float)
diff = np.abs(ss_gray - jpg_gray)
col_diff = np.sum(diff, axis=0)
col_smooth = np.convolve(col_diff, np.ones(5)/5, mode='same')

# Find the 56px window with max difference (obstacle overlay)
profile = np.convolve(col_smooth, np.ones(56)/56, mode='valid')
obstacle_x = int(np.argmax(profile))

# Also try the raw column difference method
raw_peak = int(np.argmax(col_smooth))

print(f"  Obstacle position (diff window): x={obstacle_x}")
print(f"  Peak column difference: x={raw_peak}")

# Use both values
candidates = [obstacle_x, raw_peak]

# Step 5: Set slider position via JavaScript and trigger submit
print("[4] Setting slider position and triggering verification...")
for x in candidates:
    if 0 < x < 264:
        # Move slider and trigger captcha
        js = f"""
        var slider = document.querySelector('.cx_imgBtn');
        var handle = document.querySelector('.cx_rightBtn');
        slider.style.left = '{x}px';
        handle.style.left = '{x-1}px';
        slider.style.transition = 'none';
        handle.style.transition = 'none';
        """
        ab(f'eval "{js}"')
        time.sleep(0.5)
        
        # Check if captcha passed
        prompt = ab('eval "document.getElementById(\'prompt\').innerText"')
        print(f"  x={x}: prompt='{prompt}'")
        
        # If prompt changed, captcha might have passed
        if '成功' in prompt or '验证通过' in prompt or 'success' in prompt.lower():
            print(f"  >>> CAPTCHA PASSED at x={x}!")
            break

# Step 6: Get validate token
print("[5] Trying to extract validate token...")
validata = ab('eval "document.getElementById(\'validata\').value"')
print(f"  validata={validata}")

# Close browser
ab('close')
print("Done!")
