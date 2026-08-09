import cv2, numpy as np, requests

# Download the live background JPG
UA = {'User-Agent': 'Mozilla/5.0'}
big_url = "https://captcha-b.chaoxing.com/slide/big/1AD3EDF3A95665D8EB9D238C0DE8DF3A.jpg"
jpg = cv2.imdecode(np.frombuffer(requests.get(big_url, headers=UA).content, np.uint8), cv2.IMREAD_COLOR)

# Load the screenshot crop
crop = cv2.imread("G:\\chaoxing\\backend\\captcha_crop.png")

# The jpg is 320x160, the crop has the background at a specific position
# From browser: background starts at crop-x=4 (since page-x=464 and crop-x=460)
# Extract the background area from the screenshot crop
bg_screenshot = crop[4:4+160, 4:4+320]  # left=4, top=4, width=320, height=160

if bg_screenshot.shape[1] != 320 or bg_screenshot.shape[0] != 160:
    print(f"Screenshot bg extraction failed: got {bg_screenshot.shape}")
    bg_screenshot = cv2.resize(crop[:160, :320], (320, 160))

# Convert to same color space
jpg_gray = cv2.cvtColor(jpg, cv2.COLOR_BGR2GRAY).astype(float)
ss_gray = cv2.cvtColor(bg_screenshot, cv2.COLOR_BGR2GRAY).astype(float)

# DIFFERENCE: the overlay/obstacle is what the CSS/Canvas adds to the JPG
diff = ss_gray - jpg_gray

print(f"Diff stats: min={diff.min():.0f} max={diff.max():.0f} mean={diff.mean():.1f}")

# The obstacle should create a POSITIVE difference (darker screenshot at obstacle)
# or a NEGATIVE difference (lighter screenshot at obstacle)
# Find columns with the largest absolute difference

col_abs_diff = np.sum(np.abs(diff), axis=0)
# Smooth
col_abs_smooth = np.convolve(col_abs_diff, np.ones(5)/5, mode='same')
# Find the 56px window with maximum difference
window = 56
diff_profile = np.convolve(col_abs_smooth, np.ones(window)/window, mode='valid')
max_diff_x = int(np.argmax(diff_profile))
min_diff_x = int(np.argmin(diff_profile))
print(f"Max diff window: x={max_diff_x} (most different)")
print(f"Min diff window: x={min_diff_x} (most similar)")

# Look at the actual diff vs x=150-250 region (expected obstacle zone)
print(f"\nDiff values per column (x=150-250):")
for x in range(150, 250, 5):
    val = col_abs_smooth[x]
    bar = '#' * int(val / 100)
    print(f"  x={x:3d}: {val:6.1f} {bar}")

# Save the diff image for inspection
diff_viz = np.abs(diff).astype(np.uint8)
cv2.imwrite("G:\\chaoxing\\backend\\diff_viz.png", diff_viz)
print("\nDiff image saved to G:\\chaoxing\\backend\\diff_viz.png")
