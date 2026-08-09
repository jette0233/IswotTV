import cv2, numpy as np, requests, json

BIG_URL = "https://captcha-b.chaoxing.com/slide/big/1AD3EDF3A95665D8EB9D238C0DE8DF3A.jpg"
SMALL_URL = "https://captcha-b.chaoxing.com/slide/small/1AD3EDF3A95665D8EB9D238C0DE8DF3A.jpg"
UA = {'User-Agent': 'Mozilla/5.0'}

big_bytes = requests.get(BIG_URL, headers=UA).content
small_bytes = requests.get(SMALL_URL, headers=UA).content

big = cv2.imdecode(np.frombuffer(big_bytes, np.uint8), cv2.IMREAD_COLOR)
small = cv2.imdecode(np.frombuffer(small_bytes, np.uint8), cv2.IMREAD_COLOR)

bg = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
sg = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
h, w = bg.shape
print(f"Background: {w}x{h}, Slider: {small.shape[1]}x{small.shape[0]}")

# NEW APPROACH: Instead of template matching, look for the obstacle/hole in the background
# The obstacle is a visual indicator showing where to slide to
# It's usually a dark/light overlay shaped like the slider

# Method 1: Find the position by looking at LOCAL CONTRAST differences
# The obstacle has low contrast (dark overlay), so find 56px windows with unique contrast
# Compute local standard deviation using boxFilter
mean = cv2.boxFilter(bg.astype(float), -1, (5,5))
sq_mean = cv2.boxFilter((bg.astype(float))**2, -1, (5,5))
local_var = sq_mean - mean**2
local_std = np.sqrt(np.maximum(local_var, 0))

# For each 56px column window, compute the average local std
window = 56
result = np.zeros(w - window)
for x in range(w - window):
    region = local_std[:, x:x+window]
    result[x] = np.mean(region)

# The obstacle overlay would make the region HAVE LESS texture (lower std)
min_x = int(np.argmin(result))
print(f"Min texture window: x={min_x} (lower = more likely obstacle)")

# Method 2: Look for vertical edge PAIRS (cutout has 2 vertical edges ~56px apart)
sobelx = cv2.Sobel(bg, cv2.CV_64F, 1, 0, ksize=3)
col_edges = np.sum(np.abs(sobelx), axis=0)
# Find strongest edge pairs
edges = []
for i in range(5, w-5):
    if col_edges[i] > np.mean(col_edges)*1.8 and col_edges[i] > col_edges[i-3] and col_edges[i] > col_edges[i+3]:
        edges.append(i)

print(f"\nVertical edge peaks (>1.8x mean): {edges}")

# Method 3: Try to use the slider directly but as DIFFERENCE matching
# Instead of matching content, compute pixel-by-pixel difference at each position
# The correct position should have MINIMAL difference (since slider content came from there)
# But the obstacle overlay MODIFIES the pixels, so the smallest difference might still be wrong

# Method 4: Try to find a SHADOW (darker strip) that's 56px wide
# The obstacle adds a semi-transparent dark overlay
col_mean = np.mean(bg.astype(float), axis=0)
# Smooth column means
col_smooth = np.convolve(col_mean, np.ones(5)/5, mode='same')
# The obstacle should be darker - find the DARKEST 56px window
darkness = np.convolve(col_smooth, np.ones(window)/window, mode='valid')
darkest = int(np.argmin(darkness))
print(f"\nDarkest window: x={darkest} dark_val={darkness[darkest]:.1f}")

# Method 5: Find where the slider SHAPE (not content) matches
# The slider has a distinctive shape with curved edges
# Use edge detection on the slider and find where similar edge patterns exist
# First, edge-detect the slider to get its shape
small_edge = cv2.Canny(sg, 50, 150)
big_edge = cv2.Canny(bg, 50, 150)
# Match slider shape against background edges
res = cv2.matchTemplate(big_edge, small_edge, cv2.TM_CCOEFF_NORMED)
_, mv, _, ml = cv2.minMaxLoc(res)
print(f"\nCanny shape matching: x={ml[0]} conf={mv:.3f}")

# Also save the images for visual inspection
cv2.imwrite("G:\\chaoxing\\backend\\live_bg.jpg", big)
cv2.imwrite("G:\\chaoxing\\backend\\live_slider.png", small)

# Summary
print(f"\n=== Summary ===")
print(f"Min texture: {min_x}")
print(f"Darkest window: {darkest}")
print(f"Canny match: {ml[0]} (conf={mv:.3f})")
if edges:
    print(f"Edge peaks: {edges}")
