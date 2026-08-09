import requests, json, re, hashlib, random, time, cv2, numpy as np

CAPTCHA_BASE = 'https://captcha.chaoxing.com/captcha'
CAPTCHA_ID = 'qDG21VMg9qS5Rcok4cfpnHGnpf5LhcAv'

def _uuid():
    hx='0123456789abcdef';v=[random.choice(hx) for _ in range(36)]
    v[14]='4';v[19]=hx[(int(v[19],16)&3)|8]
    for p in[8,13,18,23]:v[p]='-'
    return ''.join(v)
def _md5(d): return hashlib.md5(d.encode()).hexdigest()

s = requests.Session()
s.headers['User-Agent'] = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'

# 1. Get conf
lt = str(int(time.time()*1000))
r = s.get(f'{CAPTCHA_BASE}/get/conf', params={'callback':'cx_captcha_function','captchaId':CAPTCHA_ID,'_':lt}, timeout=15)
sv = str(json.loads(re.sub(r'^cx_captcha_function\(','',r.text).rstrip(')'))['t'])
print(f'[1] service_time={sv}')

# 2. Get images
lt2 = str(int(time.time()*1000))
ck = _md5(sv + _uuid())
tk = _md5(sv + CAPTCHA_ID + 'slide' + ck) + ':' + str(int(sv)+300000)
iv = _md5(CAPTCHA_ID + 'slide' + lt2 + _uuid())
r2 = s.get(f'{CAPTCHA_BASE}/get/verification/image', params={
    'callback':'cx_captcha_function','captchaId':CAPTCHA_ID,'type':'slide',
    'version':'1.1.20','captchaKey':ck,'token':tk,'referer':'https://v8.chaoxing.com/','iv':iv,'_':lt2
}, timeout=15)
j2 = json.loads(re.sub(r'^cx_captcha_function\(','',r2.text).rstrip(')'))
token = j2['token']
shade_url = j2['imageVerificationVo']['shadeImage']
cutout_url = j2['imageVerificationVo']['cutoutImage']
print(f'[2] images OK, token={token[:30]}...')

# 3. Download images
big_bytes = s.get(shade_url, timeout=15).content
small_bytes = s.get(cutout_url, timeout=15).content

# 4. OpenCV to get estimate
big = cv2.imdecode(np.frombuffer(big_bytes, np.uint8), cv2.IMREAD_COLOR)
small = cv2.imdecode(np.frombuffer(small_bytes, np.uint8), cv2.IMREAD_COLOR)
bg_gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
sm_gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
res = cv2.matchTemplate(bg_gray, sm_gray, cv2.TM_CCOEFF_NORMED)
_, mv, _, ml = cv2.minMaxLoc(res)
estimate = int(ml[0])
print(f'[3] OpenCV estimate: x={estimate} conf={mv:.3f}')

# 5. Brute force search around estimate +/- 30
results = {}
search_range = list(range(max(0, estimate-30), min(270, estimate+30)))
print(f'[4] Brute forcing {len(search_range)} x values ({estimate-30} to {estimate+30})')

for x in search_range:
    now = str(int(time.time()*1000))
    params = {
        'callback':'cx_captcha_function','captchaId':CAPTCHA_ID,'type':'slide',
        'token':token,'textClickArr':json.dumps([{'x':int(x)}]),
        'coordinate':'[]','runEnv':'10','version':'1.1.20','t':'a','iv':iv,'_':now
    }
    r3 = s.get(f'{CAPTCHA_BASE}/check/verification/result', params=params, timeout=10)
    data = json.loads(re.sub(r'^cx_captcha_function\(','',r3.text).rstrip(')'))
    rv = data.get('result', False)
    extra = data.get('extraData', '')
    results[x] = (rv, extra)
    if rv:
        print(f'  >>> FOUND x={x}! extra={extra[:80]}')
        break
    if x % 5 == 0:
        print(f'  x={x} result={rv} msg={data.get("msg","")}')

successes = [(x, extra) for x, (rv, extra) in results.items() if rv]
if successes:
    print(f'\nSUCCESS! x={successes[0][0]} extra={successes[0][1]}')
else:
    print(f'\nAll failed. Tried {len(search_range)} values.')
    # Try a wider range
    for x in range(0, 270):
        if x not in results:
            now = str(int(time.time()*1000))
            params = {
                'callback':'cx_captcha_function','captchaId':CAPTCHA_ID,'type':'slide',
                'token':token,'textClickArr':json.dumps([{'x':int(x)}]),
                'coordinate':'[]','runEnv':'10','version':'1.1.20','t':'a','iv':iv,'_':now
            }
            r3 = s.get(f'{CAPTCHA_BASE}/check/verification/result', params=params, timeout=10)
            data = json.loads(re.sub(r'^cx_captcha_function\(','',r3.text).rstrip(')'))
            if data.get('result', False):
                print(f'\n>>> FOUND in wider range: x={x}! extra={data.get("extraData","")[:80]}')
                break
            if x % 20 == 0:
                print(f'  wide x={x} result={data.get("result")} msg={data.get("msg","")}')
