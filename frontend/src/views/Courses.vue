<template>
  <div class="page">
    <el-header class="header">
      <span style="font-weight:bold;font-size:16px">学习通（残疾关怀版）</span>
      <span style="margin-left:6px;color:#909399;font-size:12px">{{ nickname }}</span>
      <el-button style="margin-left:auto" size="small" @click="logout">退出</el-button>
    </el-header>

    <div class="nav-tabs">
      <div :class="['nav-item', {active: tab==='courses'}]" @click="tab='courses'">我的课程</div>
      <div :class="['nav-item', {active: tab==='cookie'}]" @click="tab='cookie'">Cookie管理</div>
    </div>

    <div class="content">

      <!-- ====== 课程 Tab ====== -->
      <div v-show="tab==='courses'">
        <!-- 周一到周五按钮 -->
        <div class="day-bar">
          <div v-for="d in days" :key="d.val"
            :class="['day-btn', {active: selectedDay===d.val}]"
            @click="selectedDay=d.val; loadCourses()">
            {{ d.label }}
          </div>
        </div>

        <div style="display:flex;gap:8px;margin:12px 0;flex-wrap:wrap">
          <el-button type="primary" size="small" @click="showCreate=true">+ 创建课程</el-button>
          <el-button size="small" @click="showJoin=true">加入课程</el-button>
        </div>

        <div v-if="loading" style="text-align:center;padding:30px;color:#999">加载中...</div>
        <div v-else-if="courseList.length===0" style="text-align:center;padding:30px;color:#999;font-size:14px">
          该日没有课程<br/>创建或加入一个课程开始使用
        </div>
        <div v-for="c in courseList" :key="c.id" class="course-item">
          <div class="course-info">
            <div class="course-name">{{ c.course_name }}</div>
            <div class="course-id">{{ c.course_id }}</div>
            <div v-if="c.teacher_name" class="course-teacher">{{ c.teacher_name }}</div>
            <div v-if="c.address" class="course-addr">{{ c.address }}</div>
          </div>
          <div class="course-actions">
            <el-button size="small" type="primary" plain @click="goProducer(c)">生产</el-button>
            <el-button size="small" plain @click="goConsumer(c)">消费</el-button>
            <el-button v-if="c.is_creator" size="small" plain @click="editCourse(c)">编辑</el-button>
            <el-button v-if="c.is_creator" size="small" plain type="danger" @click="deleteCourse(c)">删除</el-button>
            <el-button v-if="!c.is_creator" size="small" plain @click="leaveCourse(c)">退出</el-button>
          </div>
        </div>
      </div>

      <!-- ====== Cookie Tab ====== -->
      <div v-show="tab==='cookie'">
        <el-card shadow="never" style="border:none">
          <div style="font-size:16px;font-weight:500;margin-bottom:12px">绑定学习通Cookie</div>

          <el-alert
            v-if="cookieStatus && !cookieExpired"
            type="success" :description="'Cookie有效，最长有效期剩余 ' + cookieRemaining + ' 天'" show-icon
            :closable="false" style="margin-bottom:12px;font-size:13px"
          />
          <el-alert
            v-else-if="cookieExpired"
            type="warning" title="Cookie已过期，请重新绑定" show-icon
            :closable="false" style="margin-bottom:12px"
          />
          <el-alert
            v-else type="info" title="尚未绑定Cookie，不会自动签到" show-icon
            :closable="false" style="margin-bottom:12px"
          />

          <div class="method-box">
            <div class="method-title">方式一：自动登录</div>
            <div class="method-desc">一劳永逸，系统自动维护Cookie状态</div>
            <el-input v-model="cxPhone" placeholder="学习通手机号" size="small" style="margin-bottom:8px" />
            <el-input v-model="cxPassword" type="password" placeholder="学习通密码" show-password size="small" style="margin-bottom:8px" />
            <el-button size="small" type="primary" @click="bindAuto">绑定</el-button>
          </div>

          <div class="method-box">
            <div class="method-title" style="display:flex;align-items:center;gap:6px">
              方式二：手动粘贴Cookie
              <el-tooltip placement="top" width="340" popper-style="padding:12px">
                <template #content>
                  <div style="font-size:12px;line-height:1.6">
                    <p><b>如何获取Cookie</b></p>
                    <p>1. 用电脑浏览器打开 i.chaoxing.com 并登录</p>
                    <p>2. 按 F12 打开开发者工具</p>
                    <p>3. 点「网络」(Network) 选项卡</p>
                    <p>4. 在过滤框输入 cookie.js</p>
                    <p>5. 点那条请求，在右侧找到 Cookie 字段</p>
                    <p>6. 复制整段 Cookie 值粘贴到下方</p>
                    <img src="/ep.png" style="width:100%;margin-top:8px;border-radius:4px" />
                    <p style="margin-top:8px;color:#e6a23c"><b>最长有效期：7天</b></p>
                  </div>
                </template>
                <span style="display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:50%;background:#409eff;color:#fff;font-size:12px;font-weight:bold;cursor:pointer">?</span>
              </el-tooltip>
            </div>
            <div class="method-desc">按 F12 抓 cookie.js 请求头的 Cookie 值</div>
            <el-input v-model="manualCookie" type="textarea" :rows="3" placeholder="粘贴Cookie字符串..." style="margin-bottom:8px;font-size:12px;font-family:monospace" />
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span style="font-size:12px;color:#e6a23c">最长有效期：7天</span>
              <el-button size="small" @click="uploadCookie">上传Cookie</el-button>
            </div>
          </div>
        </el-card>
      </div>
    </div>

    <el-dialog v-model="showCreate" :title="editingCourse ? '编辑课程' : '创建课程'" width="90%" :style="{maxWidth:'420px'}">
      <el-input v-model="newCourse.course_id" placeholder="学习通课程ID" :disabled="!!editingCourse" style="margin-bottom:8px" />
      <el-input v-model="newCourse.course_name" placeholder="课程名称" style="margin-bottom:8px" />
      <el-input v-model="newCourse.teacher_name" placeholder="授课教师（可选）" style="margin-bottom:8px" />
      <el-input v-model="newCourse.address" placeholder="签到地址（定位签到必填）" style="margin-bottom:8px" />
      <div style="display:flex;gap:8px;margin-bottom:8px">
        <el-input v-model="newCourse.default_latitude" placeholder="默认纬度（可选）" size="small" />
        <el-input v-model="newCourse.default_longitude" placeholder="默认经度（可选）" size="small" />
      </div>
      <div style="font-size:13px;color:#666;margin-bottom:8px">上课日</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap">
        <el-checkbox v-for="d in days" :key="d.val" v-model="newCourseDays" :label="d.val" border size="small">
          {{ d.label }}
        </el-checkbox>
      </div>
      <template #footer>
        <el-button @click="showCreate=false; editingCourse=null">取消</el-button>
        <el-button type="primary" @click="editingCourse ? updateCourse() : createCourse()" :disabled="newCourseDays.length===0">
          {{ editingCourse ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showJoin" title="加入课程" width="90%" :style="{maxWidth:'400px'}">
      <el-input v-model="joinCourseId" placeholder="输入课程ID" />
      <template #footer>
        <el-button @click="showJoin=false">取消</el-button>
        <el-button type="primary" @click="joinCourse">加入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { course as courseApi, auth as authApi } from '../api/index.js'
import { ElMessage } from 'element-plus'

const router = useRouter()
const uid = computed(() => localStorage.getItem('uid'))
const nickname = computed(() => localStorage.getItem('nickname'))
const dayNames = { '1':'周一','2':'周二','3':'周三','4':'周四','5':'周五' }
const days = [
  {val:'1',label:'周一'},{val:'2',label:'周二'},{val:'3',label:'周三'},
  {val:'4',label:'周四'},{val:'5',label:'周五'},
]

const tab = ref('courses')
const selectedDay = ref(new Date().getDay().toString() === '0' || new Date().getDay().toString() === '6' ? '1' : new Date().getDay().toString())

// 课程
const loading = ref(false)
const courseList = ref([])
const showCreate = ref(false)
const showJoin = ref(false)
const editingCourse = ref(null)
const newCourse = ref({ course_id: '', course_name: '', teacher_name: '', address: '', default_latitude: '', default_longitude: '' })
const newCourseDays = ref(['1','2','3','4','5'])
const joinCourseId = ref('')

// Cookie
const cookieStatus = ref(null)
const cookieExpired = ref(false)
const cookieRemaining = ref(0)
const cxPhone = ref('')
const cxPassword = ref('')
const manualCookie = ref('')

const loadCourses = async () => {
  loading.value = true
  try {
    const res = await courseApi.list(uid.value, selectedDay.value)
    if (res.data.code===200) courseList.value = res.data.data
  } catch(e) {}
  loading.value = false
}

const loadCookieStatus = async () => {
  try {
    const res = await authApi.cookieStatus()
    if (res.data.code===200) {
      const d = res.data.data
      if (d.has_cookie) { cookieStatus.value = d; cookieExpired.value = d.is_expired; cookieRemaining.value = d.remaining_days }
    }
  } catch(e) {}
}

const createCourse = async () => {
  if (!newCourse.value.course_id) return ElMessage.warning('请输入课程ID')
  try {
    const res = await courseApi.create({
      creator_id: uid.value,
      ...newCourse.value,
      weekdays: newCourseDays.value.join(',')
    })
    if (res.data.code===200) {
      ElMessage.success('创建成功'); showCreate.value=false; editingCourse.value=null
      newCourse.value = { course_id: '', course_name: '', teacher_name: '', address: '', default_latitude: '', default_longitude: '' }
      newCourseDays.value = ['1','2','3','4','5']
      loadCourses()
    } else ElMessage.warning(res.data.msg)
  } catch(e) { ElMessage.error('创建失败') }
}

const joinCourse = async () => {
  if (!joinCourseId.value) return ElMessage.warning('请输入课程ID')
  try {
    const res = await courseApi.join({ user_id: uid.value, course_id: joinCourseId.value })
    if (res.data.code===200) { ElMessage.success('加入成功'); showJoin.value=false; joinCourseId.value=''; loadCourses() }
    else ElMessage.warning(res.data.msg)
  } catch(e) { ElMessage.error('加入失败') }
}

const uploadCookie = async () => {
  if (!manualCookie.value) return ElMessage.warning('请粘贴Cookie')
  try { const res = await authApi.uploadCookie({ cookie: manualCookie.value }); if (res.data.data) { ElMessage.success('Cookie上传成功'); manualCookie.value=''; loadCookieStatus() } } catch(e) { ElMessage.error('上传失败') }
}

const bindAuto = async () => {
  if (!cxPhone.value || !cxPassword.value) return ElMessage.warning('请输入学习通账号和密码')
  try {
    const res = await authApi.refreshCookie({ password: cxPassword.value, phone: cxPhone.value })
    if (res.data.code===200) { ElMessage.success('绑定成功'); cxPhone.value=''; cxPassword.value=''; loadCookieStatus() }
    else ElMessage.error(res.data.msg)
  } catch(e) { ElMessage.error('绑定失败') }
}

const editCourse = (row) => {
  editingCourse.value = row
  newCourse.value = {
    course_id: row.course_id,
    course_name: row.course_name,
    teacher_name: row.teacher_name || '',
    address: row.address || '',
    default_latitude: '',
    default_longitude: '',
  }
  newCourseDays.value = (row.weekdays || '1,2,3,4,5').split(',')
  showCreate.value = true
}

const updateCourse = async () => {
  try {
    const res = await courseApi.update({
      course_id: editingCourse.value.id,
      uid: uid.value,
      course_name: newCourse.value.course_name,
      teacher_name: newCourse.value.teacher_name,
      address: newCourse.value.address,
      weekdays: newCourseDays.value.join(','),
      default_latitude: newCourse.value.default_latitude,
      default_longitude: newCourse.value.default_longitude,
    })
    if (res.data.code === 200) {
      ElMessage.success('课程已更新')
      showCreate.value = false; editingCourse.value = null
      loadCourses()
    } else if (res.data.code === 403) {
      ElMessage.warning(res.data.msg)
    } else {
      ElMessage.warning(res.data.msg || '更新失败')
    }
  } catch(e) { ElMessage.error('更新失败: ' + (e.response?.data?.msg || e.message)) }
}

const deleteCourse = async (row) => {
  if (!confirm('确定删除课程「' + row.course_name + '」？')) return
  try {
    const res = await courseApi.delete({ course_id: row.id, uid: uid.value })
    if (res.data.code === 200) {
      ElMessage.success('已删除')
      loadCourses()
    } else if (res.data.code === 403) {
      ElMessage.warning(res.data.msg)
    } else {
      ElMessage.warning(res.data.msg || '删除失败')
    }
  } catch(e) { ElMessage.error('删除失败: ' + (e.response?.data?.msg || e.message)) }
}

const leaveCourse = async (row) => {
  if (!confirm('确定退出课程「' + row.course_name + '」？')) return
  try {
    const res = await courseApi.leave({ course_id: row.id })
    if (res.data.code === 200) { ElMessage.success('已退出'); loadCourses() }
  } catch(e) { ElMessage.error('退出失败: ' + (e.response?.data?.msg || e.message)) }
}

const goProducer = (row) => { localStorage.setItem('currentCourseName', row.course_name); localStorage.setItem('currentSourceCourseId', row.course_id); router.push('/producer/' + row.id) }
const goConsumer = (row) => { localStorage.setItem('currentCourseName', row.course_name); router.push('/consumer') }
const logout = () => { localStorage.clear(); router.push('/login') }

onMounted(() => { loadCourses(); loadCookieStatus() })
</script>

<style scoped>
.header { display:flex; align-items:center; padding:0 16px; height:48px; background:#fff; border-bottom:1px solid #eee; font-size:14px; }
.nav-tabs { display:flex; background:#fff; border-bottom:1px solid #eee; }
.nav-item { flex:1; text-align:center; padding:10px 0; font-size:14px; color:#666; cursor:pointer; border-bottom:2px solid transparent; }
.nav-item.active { color:#409eff; border-bottom-color:#409eff; font-weight:500; }
.content { padding:12px; max-width:800px; margin:0 auto; }

/* 周一到周五按钮 */
.day-bar { display:flex; gap:6px; }
.day-btn {
  flex:1; text-align:center; padding:10px 4px; border-radius:8px;
  background:#f5f5f5; color:#666; cursor:pointer; font-size:14px; font-weight:500;
  transition:all 0.2s;
}
.day-btn.active { background:#409eff; color:#fff; }
.day-btn:active { opacity:0.7; }

.course-item { display:flex; align-items:center; padding:12px 0; border-bottom:1px solid #f0f0f0; gap:8px; }
.course-info { flex:1; min-width:0; }
.course-name { font-size:15px; font-weight:500; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.course-id { font-size:12px; color:#909399; margin-top:2px; }
.course-teacher { font-size:12px; color:#409eff; margin-top:1px; }
.course-addr { font-size:11px; color:#999; margin-top:1px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.course-actions { display:flex; gap:4px; flex-shrink:0; flex-wrap:wrap; }

.method-box { background:#f8f9fa; border-radius:8px; padding:12px; margin-bottom:12px; }
.method-title { font-size:14px; font-weight:500; margin-bottom:4px; }
.method-desc { font-size:12px; color:#666; margin-bottom:8px; }

/* 暗黑模式防护 */
@media (prefers-color-scheme: dark) {
  .header, .nav-tabs, .day-btn { background: #fff; color: #333; }
  .nav-item { color: #666; }
  .nav-item.active { color: #409eff; }
  .method-box { background: #f8f9fa; }
  .day-btn { background: #f0f0f0; color: #555; }
  .day-btn.active { background: #409eff; color: #fff; }
}
@media (max-width: 480px) {
  .content { padding:8px; }
  .day-btn { font-size:13px; padding:8px 2px; }
}
</style>
