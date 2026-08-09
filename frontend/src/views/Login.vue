<template>
  <div class="login-page" id="login-page">
    <div class="login-card">
      <div class="login-header">
        <img src="/icon.png" class="login-icon" />
        <h1>学习通（残疾关怀版）</h1>
        <p class="slogan">圆梦酒吧舞，您值得拥有</p>
        <p class="version">School of Science, BUCEA 内测版 v1.0</p>
      </div>
      <el-tabs v-model="tab" class="login-tabs">
        <el-tab-pane label="登录" name="login">
          <el-input v-model="form.phone" placeholder="账号" class="input-field" />
          <el-input v-model="form.password" type="password" placeholder="密码" show-password class="input-field" />
          <el-button type="primary" class="btn" @click="handleLogin">登录</el-button>
          <p class="switch-link"><a href="#" @click.prevent="tab='register'">没有账号？注册</a></p>
        </el-tab-pane>
        <el-tab-pane label="注册" name="register">
          <el-input v-model="reg.phone" placeholder="手机号" class="input-field" />
          <el-input v-model="reg.password" type="password" placeholder="密码" show-password class="input-field" />
          <el-input v-model="reg.nickname" placeholder="昵称" class="input-field" />
          <el-button type="primary" class="btn" @click="handleRegister">注册</el-button>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { auth } from '../api/index.js'
import { ElMessage } from 'element-plus'

const router = useRouter()
const tab = ref('login')
const form = reactive({ phone: '', password: '' })
const reg = reactive({ phone: '', password: '', nickname: '' })

const handleLogin = async () => {
  if (!form.phone || !form.password) return ElMessage.warning('请输入账号和密码')
  try {
    const res = await auth.login(form)
    if (res.data.code === 200) {
      localStorage.setItem('token', res.data.data.token)
      localStorage.setItem('uid', res.data.data.uid)
      localStorage.setItem('nickname', res.data.data.nickname)
      ElMessage.success('登录成功')
      router.push('/courses')
    } else { ElMessage.error(res.data.msg) }
  } catch (e) { ElMessage.error('登录失败: ' + (e.response?.data?.msg || e.message)) }
}

onMounted(() => { document.body.classList.add('login-active') })
onUnmounted(() => { document.body.classList.remove('login-active') })

const handleRegister = async () => {
  if (!reg.phone || !reg.password) return ElMessage.warning('请填写完整')
  try {
    const res = await auth.register(reg)
    if (res.data.code === 200) { ElMessage.success('注册成功，请登录'); tab.value = 'login' }
    else ElMessage.error(res.data.msg)
  } catch (e) { ElMessage.error('注册失败') }
}
</script>

<style>
/* 全局：login页禁止body滚动 */
body.login-active { overflow: hidden !important; margin: 0; }
</style>

<style scoped>
.login-page {
  height: 100vh; overflow: hidden;
  display: flex; justify-content: center; align-items: center;
  background: url('/background.jpg') center/cover no-repeat;
}
.login-card {
  width: min(380px, calc(100vw - 32px));
  box-sizing: border-box;
  background: rgba(255,255,255,0.8);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 24px 20px;
}
.login-header { text-align: center; margin-bottom: 6px; }
.login-icon { width: 180px; height: 180px; border-radius: 16px; }
h1 { font-size: 18px; margin: 4px 0 2px; color: #333; }
.slogan { font-size: 13px; color: #666; margin: 0; }
.version { font-size: 11px; color: #999; margin: 2px 0 0; font-style: italic; }
.input-field { margin-bottom: 10px; }
.btn { width: 100%; }
.switch-link { text-align: center; margin-top: 8px; font-size: 13px; }
.switch-link a { color: #409eff; }
:deep(.el-tabs__item) { font-size: 14px; }
:deep(.el-tabs__header) { margin-bottom: 10px; }
/* 暗黑模式兜底 */
@media (prefers-color-scheme: dark) {
  .login-card { background: rgba(255,255,255,0.85); }
  h1, .slogan, .version { color: #333; }
  :deep(.el-input__wrapper) { background: rgba(255,255,255,0.9); }
}
</style>
