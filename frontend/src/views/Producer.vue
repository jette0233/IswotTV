<template>
  <div class="page">
    <el-header class="header">
      <span style="font-weight:bold;font-size:16px">生产者</span>
      <span style="margin-left:6px;color:#909399;font-size:13px">{{ courseName }}</span>
      <el-button style="margin-left:auto" size="small" @click="$router.push('/courses')">返回</el-button>
    </el-header>

    <div class="content">
      <!-- 状态 -->
      <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
        <div class="stat-box">
          <span style="color:#999;font-size:12px">生产者</span>
          <span :style="{color:isProducer?'#67c23a':'#909399',fontWeight:500}">
            {{ isProducer ? '当选' : '等待' }}
          </span>
        </div>
        <div class="stat-box">
          <span style="color:#999;font-size:12px">摄像头</span>
          <span :style="{color:cameraActive?'#67c23a':'#f56c6c',fontWeight:500}">
            {{ cameraActive ? '运行中' : '未启动' }}
          </span>
        </div>
        <div class="stat-box" style="flex:1">
          <span style="color:#999;font-size:12px">最新enc</span>
          <span style="font-family:monospace;font-size:11px;color:#666;word-break:break-all">{{ lastEnc || '等待中' }}</span>
        </div>
      </div>

      <!-- 摄像头 -->
      <div class="section-box">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <span style="font-weight:500;font-size:14px">摄像头</span>
          <el-button v-if="!cameraActive" size="small" type="primary" @click="startCamera">启动</el-button>
          <el-button v-else size="small" @click="stopCamera">停止</el-button>
        </div>
        <div v-if="cameraError" class="warn-box">{{ cameraError }}</div>
        <video v-show="cameraActive" ref="videoRef" autoplay playsinline class="video" />
      </div>

      <!-- 日志面板 -->
      <div class="section-box">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <span style="font-weight:500;font-size:14px">日志</span>
          <el-button size="small" @click="log=[]">清空</el-button>
        </div>
        <div class="log-panel">
          <div v-for="(l,i) in log" :key="i" class="log-line">{{ l }}</div>
          <div v-if="log.length===0" style="color:#999;font-size:12px">启动摄像头后日志将显示在此处</div>
        </div>
      </div>

      <div style="display:flex;gap:8px;margin-top:8px">
        <el-button v-if="isProducer && cameraActive" size="small" @click="forceClaim">重新竞选</el-button>
        <el-button v-if="!isProducer && cameraActive" size="small" @click="forceClaim">竞选生产者</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { producer as producerApi } from '../api/index.js'
import { ElMessage } from 'element-plus'

const route = useRoute()
const courseId = computed(() => route.params.courseId)
const uid = computed(() => localStorage.getItem('uid'))
const courseName = ref('')

const isProducer = ref(false)
const cameraActive = ref(false)
const cameraError = ref('')
const lastEnc = ref('')
const log = ref([])
const gpsLat = ref(null)
const gpsLng = ref(null)
const videoRef = ref(null)
let mediaStream = null
let captureTimer = null
let heartbeatTimer = null

const addLog = (msg) => { log.value.push('[' + new Date().toLocaleTimeString() + '] ' + msg); if (log.value.length>100) log.value.shift() }

const claimProducer = async () => {
  try {
    const res = await producerApi.claim({ course_id: courseId.value, user_id: uid.value })
    if (res.data.code===200) {
      isProducer.value = res.data.data?.is_producer || false
      addLog(isProducer.value ? '竞选成功，你是生产者' : '竞选失败，已有其他生产者')
    }
  } catch(e) { addLog('竞选请求失败: ' + e.message) }
}

const sendHeartbeat = async () => {
  if (!isProducer.value) {
    // 不是生产者，自动重试竞选
    await claimProducer()
    return
  }
  try { await producerApi.heartbeat({ course_id: courseId.value, user_id: uid.value }) }
  catch(e) { isProducer.value = false; addLog('心跳丢失，重新竞选...') }
}

const captureAndDecode = async () => {
  if (!videoRef.value || !cameraActive.value) return
  const video = videoRef.value
  if (video.readyState < 2) return
  // 固定640x480，jsQR在这个分辨率下解码效果最好
  const cw = 640, ch = 480
  const canvas = document.createElement('canvas')
  canvas.width = cw; canvas.height = ch
  const ctx = canvas.getContext('2d')
  ctx.drawImage(video, 0, 0, cw, ch)
  try {
    const imageData = ctx.getImageData(0, 0, cw, ch)
    const jsQR = (await import('jsqr')).default
    const code = jsQR(imageData.data, imageData.width, imageData.height)
    if (code) {
      const url = code.data
      addLog('完整URL: ' + url)
      const parts = url.split(/[?&]/)
      let enc = null, activeId = null
      for (const p of parts) {
        const [k, v] = p.split('=')
        if (k === 'enc') enc = v
        else if (k === 'id') activeId = v
      }
      if (enc && activeId) {
        lastEnc.value = enc.substring(0,20) + '...'
        addLog('enc: ' + enc.substring(0,16) + '  activeId: ' + activeId)
        if (isProducer.value) {
          await producerApi.pushEnc({
            course_id: courseId.value,
            user_id: uid.value,
            enc,
            active_id: activeId,
            latitude: gpsLat.value,
            longitude: gpsLng.value,
          })
          addLog('enc已推送' + (gpsLat.value ? ' (含GPS)' : ''))
        } else { addLog('未当选，跳过推送') }
      } else {
        addLog('未提取到enc/activeId, URL长度=' + url.length)
      }
    } else { addLog('未检测到二维码，调整手机位置') }
  } catch(e) { addLog('解码异常: ' + e.message) }
}

const captureGPS = () => {
  if (!navigator.geolocation) { addLog('浏览器不支持GPS定位'); return }
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      gpsLat.value = pos.coords.latitude
      gpsLng.value = pos.coords.longitude
      addLog('GPS: ' + gpsLat.value.toFixed(6) + ', ' + gpsLng.value.toFixed(6))
    },
    (err) => { addLog('GPS定位失败: ' + err.message) },
    { enableHighAccuracy: true, timeout: 10000 }
  )
}

const startCamera = async () => {
  cameraError.value = ''
  captureGPS()
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } }
    })
    if (videoRef.value) videoRef.value.srcObject = mediaStream
    cameraActive.value = true
    addLog('摄像头已启动')
    await claimProducer()
    // 每5秒检查一次，没当选就重试竞选
    if (!isProducer.value) {
      addLog('首次竞选失败，持续重试...')
    }
    captureTimer = setInterval(captureAndDecode, 3000)
    heartbeatTimer = setInterval(sendHeartbeat, 5000)
  } catch(e) {
    if (e.name==='NotAllowedError') cameraError.value = '摄像头权限被拒绝'
    else if (e.name==='NotFoundError') cameraError.value = '未检测到摄像头'
    else cameraError.value = '摄像头启动失败: ' + e.message
    addLog('摄像头启动失败: ' + e.message)
  }
}

const stopCamera = () => {
  if (mediaStream) { mediaStream.getTracks().forEach(t=>t.stop()); mediaStream=null }
  cameraActive.value = false; isProducer.value = false
  if (captureTimer) clearInterval(captureTimer); if (heartbeatTimer) clearInterval(heartbeatTimer)
  addLog('摄像头已停止')
}

const forceClaim = async () => { await claimProducer() }

onMounted(() => { courseName.value = localStorage.getItem('currentCourseName') || '' })
onUnmounted(() => { stopCamera() })
</script>

<style scoped>
.header { display:flex; align-items:center; padding:0 16px; height:48px; background:#fff; border-bottom:1px solid #eee; font-size:14px; }
.content { padding:12px; max-width:800px; margin:0 auto; }
.stat-box { display:flex; flex-direction:column; background:#f8f9fa; border-radius:8px; padding:8px 12px; min-width:70px; }
.section-box { background:#f8f9fa; border-radius:8px; padding:12px; margin-bottom:12px; }
.video { width:100%; max-width:640px; border-radius:8px; background:#000; display:block; }
.warn-box { background:#fdf0ef; color:#f56c6c; padding:8px 12px; border-radius:6px; font-size:13px; margin-bottom:8px; }
.log-panel { background:#1e1e1e; color:#d4d4d4; padding:8px; border-radius:6px; max-height:200px; overflow-y:auto; font-family:monospace; font-size:11px; line-height:1.5; }
.log-line { border-bottom:1px solid #333; padding:2px 0; }
@media (prefers-color-scheme: dark) {
  .stat-box, .section-box { background:#f0f0f0; }
  .log-panel { background:#1e1e1e; }
}
@media (max-width:480px) { .content { padding:8px; } }
</style>
