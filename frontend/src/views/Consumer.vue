<template>
  <div class="page">
    <el-header class="header">
      <span style="font-weight:bold;font-size:16px">消费者</span>
      <span style="margin-left:6px;color:#909399;font-size:13px">自动签到运行中</span>
      <el-button style="margin-left:auto" size="small" @click="$router.push('/courses')">返回</el-button>
    </el-header>

    <div class="content">
      <div class="section-box">
        <div style="font-weight:500;font-size:14px;margin-bottom:8px">任务执行状态</div>
        <div style="color:#999;font-size:13px;padding:10px 0">签到由服务端 Worker 自动执行，本页面只展示结果。</div>
      </div>

      <!-- 日志面板 -->
      <div class="section-box">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <span style="font-weight:500;font-size:14px">运行日志</span>
          <el-button size="small" @click="runLog=[]">清空</el-button>
        </div>
        <div class="log-panel">
          <div v-for="(l,i) in runLog" :key="i" class="log-line">{{ l }}</div>
          <div v-if="runLog.length===0" style="color:#999;font-size:12px">等待签到活动...</div>
        </div>
      </div>

      <!-- 签到记录 -->
      <div class="section-box">
        <div style="font-weight:500;font-size:14px;margin-bottom:8px">签到记录</div>
        <div v-if="signLogs.length===0" style="color:#999;font-size:13px;padding:10px 0">暂无记录</div>
        <div v-for="log in signLogs" :key="log.id" class="item-row" style="font-size:13px">
          <div>
            <div>活动 #{{ log.activity_id }}</div>
            <div style="font-size:11px;color:#999">{{ new Date(log.created_at).toLocaleString() }}</div>
          </div>
          <div style="display:flex;align-items:center;gap:6px">
            <span :style="{color:log.status==='success'?'#67c23a':'#f56c6c',fontWeight:500}">
              {{ statusLabel(log.status) }}
            </span>
            <span style="font-size:11px;color:#999;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ log.message }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { consumer as consumerApi } from '../api/index.js'
import { ElMessage } from 'element-plus'

const signLogs = ref([])
const runLog = ref([])
let pollTimer = null

const addLog = (msg) => { runLog.value.push('[' + new Date().toLocaleTimeString() + '] ' + msg); if (runLog.value.length>100) runLog.value.shift() }
const statusLabel = (status) => ({pending:'等待中',processing:'执行中',retry:'重试中',success:'成功',manual_required:'需人工处理',expired:'已过期',dead:'失败'})[status] || status

const loadLogs = async () => {
  try { const res = await consumerApi.tasks(); if (res.data.data) signLogs.value = res.data.data || [] } catch(e) {}
}

const autoSign = async () => {
  await loadLogs()
}

onMounted(() => {
  ElMessage.info('自动签到已开启')
  loadLogs()
  pollTimer = setInterval(autoSign, 5000)
})

onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<style scoped>
.header { display:flex; align-items:center; padding:0 16px; height:48px; background:#fff; border-bottom:1px solid #eee; font-size:14px; }
.content { padding:12px; max-width:800px; margin:0 auto; }
.section-box { background:#f8f9fa; border-radius:8px; padding:12px; margin-bottom:12px; }
.item-row { display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid #eee; gap:8px; }
.item-row:last-child { border-bottom:none; }
.log-panel { background:#1e1e1e; color:#d4d4d4; padding:8px; border-radius:6px; max-height:250px; overflow-y:auto; font-family:monospace; font-size:11px; line-height:1.5; }
.log-line { border-bottom:1px solid #333; padding:2px 0; }
@media (prefers-color-scheme: dark) { .section-box { background:#f0f0f0; } .log-panel { background:#1e1e1e; } }
@media (max-width:480px) { .content { padding:8px; } }
</style>
