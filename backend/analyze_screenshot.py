import cv2, numpy as np

# Read screenshot
screenshot = cv2.imread("C:\\Users\\16200\\.agent-browser\\tmp\\screenshots\\screenshot-1779410773973.png")
if screenshot is None:
    print("Failed to load screenshot")
    exit()

print(f"Screenshot size: {screenshot.shape}")

# Captcha area location from browser measurements:
# Background (cx_imgBg): left=464, top=222, width=320, height=160
# But this is the image area. Let's crop a bit larger to include the drag handle
# Drag handle (cx_rightBtn): left=465, top=399, width=40, height=40
# Background bottom edge = 222 + 160 = 382
# Drag handle bottom = 399 + 40 = 439

# Crop the captcha area (background + slider track)
x, y, w, h = 460, 218, 330, 230  # slightly larger than background
captcha_img = screenshot[y:y+h, x:x+w]
cv2.imwrite("G:\\chaoxing\\backend\\captcha_crop.png", captcha_img)
print(f"Cropped captcha: {captcha_img.shape}")

# Convert to grayscale
gray = cv2.cvtColor(captcha_img, cv2.COLOR_BGR2GRAY)
h2, w2 = gray.shape

# The obstacle/hole should be visible in the screenshot!
# Look for a dark/shadowed rectangular region

# Method 1: Look for the DARKEST 56px window (shadow = obstacle)
mean_col = np.mean(gray.astype(float), axis=0)
# Smooth
mean_smooth = np.convolve(mean_col, np.ones(5)/5, mode='same')
dark_scores = np.convolve(mean_smooth, np.ones(56)/56, mode='valid')
darkest = int(np.argmin(dark_scores))
print(f"Darkest 56px window: x={darkest} (in crop coords)")

# Method 2: Look for line SEGMENTS in the cropped area
# The obstacle creates visible line features at the cutout boundary
edges = cv2.Canny(gray, 30, 100)
# Find vertical lines
lines = cv2.HoughLinesP(edges, 1, np.pi/180, 30, minLineLength=20, maxLineGap=5)
if lines is not None:
    vert_lines = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if abs(x2 - x1) < 8 and y2 - y1 > 20:
            vert_lines.append((x1 + x2)//2)
    if vert_lines:
        from collections import Counter
        c = Counter(vert_lines)
        print(f"Vertical lines (Hough): {c.most_common(10)}")

# Method 3: Find gradient hotspots (where the obstacle overlay changes brightness abruptly)
sobelx = cv2.Sobel(gray.astype(float), cv2.CV_64F, 1, 0, ksize=3)
col_grad = np.sum(np.abs(sobelx), axis=0)
# Look for an edge pair 50-60px apart
threshold = np.mean(col_grad) + np.std(col_grad)
strong_cols = np.where(col_grad > threshold)[0]
print(f"Strong gradient cols: {len(strong_cols)}")

# Method 4: Try to detect the RECTANGULAR SHADOW by looking at brightness change points
# Scan horizontally from left to right at the slider's y-position (middle of image)
mid_y = 80  # roughly center
row = gray[mid_y, :].astype(float)
# Find points where brightness drops significantly (shadow edge)
diffs = np.abs(np.diff(row))
big_drops = np.where(diffs > 10)[0]
print(f"Brightness drops at y=80: {big_drops[:15]}")

# Method 5: Vertical projection of dark pixels (pixel value < 80 = dark/shadow)
dark_mask = (gray < 80).astype(np.uint8)
dark_proj = np.sum(dark_mask, axis=0)
# Find the 56px window with most dark pixels
dark_win = np.convolve(dark_proj.astype(float), np.ones(56), mode='valid')
darkest_region = int(np.argmax(dark_win))
print(f"Most dark pixels window: x={darkest_region} dark_count={dark_win[darkest_region]:.0f}")

print(f"\nSuggested x values (in crop coords): {darkest}, {darkest_region}")
print(f"To convert to page/screen x: + {x}")
print(f"To convert to background-relative x: same as crop coords (background starts at x=0 in crop)")
