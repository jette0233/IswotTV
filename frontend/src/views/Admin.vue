<template>
  <div style="min-height:100vh;background:#f5f7fa;font-family:-apple-system,BlinkMacSystemFont,sans-serif">

    <!-- Login -->
    <div v-if="!token" style="display:flex;align-items:center;justify-content:center;min-height:100vh;background:#f0f2f5">
      <div style="background:#fff;border-radius:8px;padding:40px;width:380px;box-shadow:0 2px 12px rgba(0,0,0,0.08)">
        <h1 style="font-size:20px;margin:0 0 24px 0;text-align:center;color:#333">管理后台</h1>
        <el-input v-model="loginUser" placeholder="管理员账号" style="margin-bottom:16px" />
        <el-input v-model="loginPass" type="password" placeholder="管理员密码" style="margin-bottom:16px" @keyup.enter="doLogin" />
        <el-button type="primary" style="width:100%" @click="doLogin">登录</el-button>
        <div v-if="loginError" style="color:#e74c3c;font-size:13px;margin-top:8px;text-align:center">{{ loginError }}</div>
      </div>
    </div>

    <!-- Main -->
    <div v-else style="max-width:1200px;margin:0 auto;padding:20px">
      <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:#fff;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,0.06);margin-bottom:16px">
        <h1 style="font-size:17px;margin:0;color:#333">管理后台</h1>
        <el-button size="small" @click="doLogout">退出</el-button>
      </div>

      <el-card style="margin-bottom:16px">
        <el-menu mode="horizontal" :ellipsis="false" @select="switchTab" :default-active="tab">
          <el-menu-item index="dashboard">概览</el-menu-item>
          <el-menu-item index="courses">课程</el-menu-item>
          <el-menu-item index="users">用户</el-menu-item>
          <el-menu-item index="logs">签到日志</el-menu-item>
        </el-menu>
      </el-card>

      <!-- Dashboard -->
      <div v-if="tab==='dashboard'">
        <el-row :gutter="16">
          <el-col :span="4" v-for="s in stats" :key="s.label">
            <el-card>
              <div style="font-size:26px;font-weight:700;color:#409eff">{{ s.value }}</div>
              <div style="font-size:13px;color:#666;margin-top:4px">{{ s.label }}</div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <!-- Courses -->
      <div v-if="tab==='courses'">
        <el-card>
          <div style="display:flex;gap:8px;margin-bottom:16px;align-items:center">
            <el-input v-model="courseKw" placeholder="搜索课程名" style="width:200px" @keyup.enter="loadCourses" />
            <el-select v-model="courseCf" style="width:120px">
              <el-option label="全部" value="" />
              <el-option label="有验证码" value="1" />
              <el-option label="无验证码" value="0" />
            </el-select>
            <el-button type="primary" @click="loadCourses">搜索</el-button>
            <el-button type="success" @click="showCreateCourse=true" style="margin-left:auto">新增课程</el-button>
          </div>

          <el-dialog v-model="showCreateCourse" title="新增课程" width="420px">
            <el-form label-width="100px">
              <el-form-item label="课程ID">
                <el-input v-model="createForm.course_id" placeholder="学习通课程ID" />
              </el-form-item>
              <el-form-item label="课程名称">
                <el-input v-model="createForm.course_name" />
              </el-form-item>
              <el-form-item label="授课教师">
                <el-input v-model="createForm.teacher_name" placeholder="可选" />
              </el-form-item>
              <el-form-item label="签到地址">
                <el-input v-model="createForm.address" />
              </el-form-item>
              <el-form-item label="上课日">
                <el-checkbox-group v-model="createForm.weekdayList">
                  <el-checkbox label="1">周一</el-checkbox>
                  <el-checkbox label="2">周二</el-checkbox>
                  <el-checkbox label="3">周三</el-checkbox>
                  <el-checkbox label="4">周四</el-checkbox>
                  <el-checkbox label="5">周五</el-checkbox>
                </el-checkbox-group>
              </el-form-item>
              <el-form-item label="纬度">
                <el-input v-model="createForm.lat" placeholder="39.9042" />
              </el-form-item>
              <el-form-item label="经度">
                <el-input v-model="createForm.lng" placeholder="116.4074" />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="showCreateCourse=false">取消</el-button>
              <el-button type="primary" @click="doCreateCourse">创建</el-button>
            </template>
          </el-dialog>

          <!-- 编辑课程弹窗 -->
          <el-dialog v-model="showEditCourse" title="编辑课程" width="420px">
            <el-form label-width="100px">
              <el-form-item label="课程名称">
                <el-input v-model="editForm.course_name" />
              </el-form-item>
              <el-form-item label="授课教师">
                <el-input v-model="editForm.teacher_name" placeholder="可选" />
              </el-form-item>
              <el-form-item label="签到地址">
                <el-input v-model="editForm.address" />
              </el-form-item>
              <el-form-item label="上课日">
                <el-checkbox-group v-model="editForm.weekdayList">
                  <el-checkbox label="1">周一</el-checkbox>
                  <el-checkbox label="2">周二</el-checkbox>
                  <el-checkbox label="3">周三</el-checkbox>
                  <el-checkbox label="4">周四</el-checkbox>
                  <el-checkbox label="5">周五</el-checkbox>
                </el-checkbox-group>
              </el-form-item>
              <el-form-item label="纬度">
                <el-input v-model="editForm.lat" placeholder="39.9042" />
              </el-form-item>
              <el-form-item label="经度">
                <el-input v-model="editForm.lng" placeholder="116.4074" />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="showEditCourse=false">取消</el-button>
              <el-button type="primary" @click="doEditCourse">保存</el-button>
            </template>
          </el-dialog>

          <!-- 课程详情弹窗（成员管理） -->
          <el-dialog v-model="showDetail" title="课程详情" width="650px">
            <div v-if="detailData">
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:16px;font-size:14px">
                <div><b>课程名：</b>{{ detailData.course_name }}</div>
                <div><b>课程ID：</b>{{ detailData.course_id }}</div>
                <div><b>教师：</b>{{ detailData.teacher_name || '-' }}</div>
                <div><b>签到地址：</b>{{ detailData.address || '-' }}</div>
                <div><b>上课日：</b>{{ detailData.weekdays }}</div>
                <div><b>创建者：</b>{{ detailData.creator_nickname }} (ID: {{ detailData.creator_id }})</div>
                <div><b>成员数：</b>{{ detailData.member_count }}</div>
                <div><b>验证码：</b>{{ detailData.has_captcha ? '是' : '否' }}</div>
              </div>

              <div style="font-weight:500;margin-bottom:8px;font-size:14px">成员列表</div>
              <el-table :data="detailData.members" size="small" stripe>
                <el-table-column prop="uid" label="UID" width="60" />
                <el-table-column prop="nickname" label="昵称" width="120" />
                <el-table-column prop="phone" label="手机号" width="130" />
                <el-table-column label="角色" width="70">
                  <template #default="{row}">
                    <el-tag v-if="row.is_creator" size="small" type="warning">创建者</el-tag>
                    <span v-else style="color:#909399">成员</span>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="100">
                  <template #default="{row}">
                    <el-button v-if="!row.is_creator" size="small" type="danger" @click="kickMember(row)">踢出</el-button>
                    <el-button v-else size="small" plain @click="confirmTakeOverCourse()">接管</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-dialog>

          <!-- 超级管理员接管课程确认 -->
          <el-dialog v-model="showChangeCreatorDialog" title="超级管理员接管课程" width="380px">
            <p style="font-size:14px;margin:0 0 12px 0">确认将当前课程创建者直接变更为 <b>超级管理员本人</b>？</p>
            <p style="font-size:13px;color:#909399">接管后，当前创建者会降为普通成员，超级管理员成为新的课程创建者。</p>
            <template #footer>
              <el-button @click="showChangeCreator=null">取消</el-button>
              <el-button type="primary" @click="doChangeCreator">确认转让</el-button>
            </template>
          </el-dialog>

          <el-table :data="courses" size="small" stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="course_name" label="课程名" min-width="160" />
            <el-table-column prop="teacher_name" label="教师" width="100" />
            <el-table-column label="验证码" width="90">
              <template #default="{row}">
                <el-switch :model-value="row.has_captcha" @change="toggleCaptcha(row.id,$event)" />
              </template>
            </el-table-column>
            <el-table-column label="MQ" width="60">
              <template #default="{row}">{{ row.has_active_mq?'是':'否' }}</template>
            </el-table-column>
            <el-table-column prop="member_count" label="成员" width="60" />
            <el-table-column label="创建者" width="120">
              <template #default="{row}">{{ row.creator_nickname || row.creator_id }}</template>
            </el-table-column>
            <el-table-column label="操作" width="180">
              <template #default="{row}">
                <el-button size="small" @click="showCourseDetail(row)">详情</el-button>
                <el-button size="small" @click="editCourse(row)">编辑</el-button>
                <el-button size="small" type="danger" @click="deleteCourse(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div style="display:flex;gap:8px;margin-top:12px;align-items:center;font-size:13px">
            <el-button size="small" :disabled="coursePage<=1" @click="coursePage--;loadCourses()">上一页</el-button>
            <span>第{{ coursePage }}/{{ courseTotalPage }}页 共{{ courseTotal }}条</span>
            <el-button size="small" :disabled="coursePage>=courseTotalPage" @click="coursePage++;loadCourses()">下一页</el-button>
          </div>
        </el-card>
      </div>

      <!-- Users -->
      <div v-if="tab==='users'">
        <el-card>
          <div style="display:flex;gap:8px;margin-bottom:16px">
            <el-input v-model="userKw" placeholder="搜索昵称/手机号" style="width:200px" @keyup.enter="loadUsers" />
            <el-button type="primary" @click="loadUsers">搜索</el-button>
          </div>
          <el-table :data="users" size="small" stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="nickname" label="昵称" width="120" />
            <el-table-column prop="phone" label="手机号" width="130" />
            <el-table-column label="Cookie" width="80">
              <template #default="{row}">
                <el-tag v-if="row.has_cookie" size="small" type="success">有</el-tag>
                <el-tag v-else size="small" type="info">无</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="注册时间" min-width="160" />
            <el-table-column label="操作" width="80">
              <template #default="{row}">
                <el-button size="small" type="danger" @click="deleteUser(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div style="display:flex;gap:8px;margin-top:12px;align-items:center;font-size:13px">
            <el-button size="small" :disabled="userPage<=1" @click="userPage--;loadUsers()">上一页</el-button>
            <span>第{{ userPage }}/{{ userTotalPage }}页 共{{ userTotal }}条</span>
            <el-button size="small" :disabled="userPage>=userTotalPage" @click="userPage++;loadUsers()">下一页</el-button>
          </div>
        </el-card>
      </div>

      <!-- Logs -->
      <div v-if="tab==='logs'">
        <el-card>
          <el-table :data="logs" size="small" stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="user_id" label="用户ID" width="70" />
            <el-table-column prop="course_id" label="课程ID" width="70" />
            <el-table-column label="状态" width="80">
              <template #default="{row}">
                <el-tag :type="row.status==='success'?'success':row.status==='fail'?'danger':'warning'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="message" label="消息" min-width="200" />
            <el-table-column prop="created_at" label="时间" min-width="160" />
          </el-table>
          <div style="display:flex;gap:8px;margin-top:12px;align-items:center;font-size:13px">
            <el-button size="small" :disabled="logPage<=1" @click="logPage--;loadLogs()">上一页</el-button>
            <span>第{{ logPage }}/{{ logTotalPage }}页 共{{ logTotal }}条</span>
            <el-button size="small" :disabled="logPage>=logTotalPage" @click="logPage++;loadLogs()">下一页</el-button>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'

const http = axios.create({baseURL: window.location.origin})

export default {
  data() {
    return {
      token: sessionStorage.getItem('admin_token'),
      loginUser: '', loginPass: '', loginError: '',
      tab: 'dashboard',
      stats: [],
      courses: [], coursePage: 1, courseTotal: 0, courseTotalPage: 1, courseKw: '', courseCf: '',
      showCreateCourse: false, createForm: {course_id:'',course_name:'',teacher_name:'',address:'',weekdayList:['1','2','3','4','5'],lat:'',lng:''},
      showEditCourse: false, editForm: {id:null,course_name:'',teacher_name:'',address:'',weekdayList:['1','2','3','4','5'],lat:'',lng:''},
      showDetail: false, detailData: null, showChangeCreator: false,
      users: [], userPage: 1, userTotal: 0, userTotalPage: 1, userKw: '',
      logs: [], logPage: 1, logTotal: 0, logTotalPage: 1,
    }
  },
  mounted() {
    if (this.token) this.loadDashboard()
  },
  computed: {
    showChangeCreatorDialog: {
      get() {
        return this.showChangeCreator
      },
      set(val) {
        this.showChangeCreator = val
      }
    }
  },
  methods: {
    getToken() { return sessionStorage.getItem('admin_token') },
    adminGet(path) {
      return http.get('/api/txjadmin' + path, {headers: {'Authorization': 'Bearer ' + this.getToken()}}).then(function(r){return r.data})
    },
    adminPost(path, data) {
      return http.post('/api/txjadmin' + path, data, {headers: {'Authorization': 'Bearer ' + this.getToken()}}).then(function(r){return r.data})
    },
    doLogin() {
      var self = this
      http.post('/api/txjadmin/login', {username: this.loginUser, password: this.loginPass}).then(function(r){
        var d = r.data
        if (d.code === 200) {
          self.token = d.data.token
          sessionStorage.setItem('admin_token', self.token)
          self.loadDashboard()
        } else {
          self.loginError = d.msg
        }
      })
    },
    doLogout() {
      sessionStorage.removeItem('admin_token')
      this.token = null
    },
    switchTab(t) {
      this.tab = t
      if (t==='dashboard') this.loadDashboard()
      else if (t==='courses') this.loadCourses()
      else if (t==='users') this.loadUsers()
      else if (t==='logs') this.loadLogs()
    },
    loadDashboard() {
      var self = this
      this.adminGet('/dashboard').then(function(d){
        if (d.code!==200) return
        self.stats = [
          {label:'用户数', value:d.data.total_users},
          {label:'课程数', value:d.data.total_courses},
          {label:'有验证码', value:d.data.active_captcha_courses},
          {label:'总签到记录', value:d.data.total_sign_logs},
          {label:'今日签到', value:d.data.today_sign_logs},
        ]
      })
    },
    loadCourses() {
      var self = this
      this.adminGet('/courses?page='+this.coursePage+'&per_page=20&keyword='+encodeURIComponent(this.courseKw)+'&has_captcha='+this.courseCf).then(function(d){
        if (d.code!==200) return
        self.courses = d.data.courses
        self.courseTotal = d.data.total
        self.courseTotalPage = Math.ceil(d.data.total/20)
      })
    },
    toggleCaptcha(cid, val) {
      var self = this
      this.adminPost('/course/toggle-captcha', {course_id: cid, has_captcha: val}).then(function(d){
        if (d.code===200) self.$message.success(val?'已拦截':'已放行')
        else self.$message.error(d.msg)
      })
    },
    doCreateCourse() {
      var f = this.createForm
      if (!f.course_id) {this.$message.error('请输入课程ID'); return}
      var self = this
      this.adminPost('/course/create', {
        course_id: f.course_id,
        course_name: f.course_name || undefined,
        teacher_name: f.teacher_name || undefined,
        address: f.address || undefined,
        weekdays: f.weekdayList.length ? f.weekdayList.join(',') : '1,2,3,4,5',
        default_latitude: f.lat || undefined,
        default_longitude: f.lng || undefined,
      }).then(function(d){
        if (d.code===200) {self.$message.success('创建成功'); self.showCreateCourse=false; self.loadCourses()}
        else self.$message.error(d.msg)
      })
    },
    editCourse(row) {
      var self = this
      this.adminGet('/course/detail?course_id='+row.id).then(function(d){
        if (d.code!==200) {self.$message.error('获取课程信息失败'); return}
        var c = d.data
        self.editForm = {
          id: c.id, course_name: c.course_name || '',
          teacher_name: c.teacher_name || '',
          address: c.address || '', weekdayList: (c.weekdays||'1,2,3,4,5').split(','),
          lat: c.default_latitude || '', lng: c.default_longitude || '',
        }
        self.showEditCourse = true
      })
    },
    doEditCourse() {
      var f = this.editForm
      var self = this
      this.adminPost('/course/update', {
        course_id: f.id, course_name: f.course_name,
        teacher_name: f.teacher_name || undefined,
        address: f.address,
        weekdays: f.weekdayList.join(','),
        default_latitude: f.lat || undefined, default_longitude: f.lng || undefined,
      }).then(function(d){
        if (d.code===200) {self.$message.success('已更新'); self.showEditCourse=false; self.loadCourses()}
        else self.$message.error(d.msg)
      })
    },
    deleteCourse(row) {
      if (!confirm('确定删除课程「'+row.course_name+'」？\n相关成员和签到记录将被一并删除')) return
      var self = this
      this.adminPost('/course/delete', {course_id: row.id}).then(function(d){
        if (d.code===200) {self.$message.success('已删除'); self.loadCourses()}
        else self.$message.error(d.msg)
      })
    },
    deleteUser(row) {
      if (!confirm('确定删除用户「'+row.nickname+'」？\n相关课程成员和签到记录将被一并删除')) return
      var self = this
      this.adminPost('/user/delete', {uid: row.id}).then(function(d){
        if (d.code===200) {self.$message.success('已删除'); self.loadUsers()}
        else self.$message.error(d.msg)
      })
    },
    loadUsers() {
      var self = this
      this.adminGet('/users?page='+this.userPage+'&per_page=20&keyword='+encodeURIComponent(this.userKw)).then(function(d){
        if (d.code!==200) return
        self.users = d.data.users
        self.userTotal = d.data.total
        self.userTotalPage = Math.ceil(d.data.total/20)
      })
    },
    loadLogs() {
      var self = this
      this.adminGet('/sign-logs?page='+this.logPage+'&per_page=20').then(function(d){
        if (d.code!==200) return
        self.logs = d.data.logs
        self.logTotal = d.data.total
        self.logTotalPage = Math.ceil(d.data.total/20)
      })
    },
    showCourseDetail(row) {
      var self = this
      this.adminGet('/course/detail?course_id='+row.id).then(function(d){
        if (d.code!==200) {self.$message.error('获取课程详情失败'); return}
        self.detailData = d.data
        self.showDetail = true
      })
    },
    kickMember(member) {
      if (!confirm('确定将「'+member.nickname+'」踢出课程？')) return
      var self = this
      this.adminPost('/course/kick-member', {course_id: this.detailData.id, uid: member.uid}).then(function(d){
        if (d.code===200) {
          self.$message.success('已踢出')
          // 刷新详情
          self.showCourseDetail({id: self.detailData.id})
        } else {
          self.$message.error(d.msg)
        }
      })
    },
    confirmTakeOverCourse() {
      this.showChangeCreator = true
    },
    doChangeCreator() {
      var self = this
      this.adminPost('/course/change-creator', {course_id: this.detailData.id}).then(function(d){
        if (d.code===200) {
          self.$message.success('课程已由超级管理员接管')
          self.showChangeCreator = false
          self.showCourseDetail({id: self.detailData.id})
          self.loadCourses()
        } else {
          self.$message.error(d.msg)
        }
      }).catch(function(e){
        self.$message.error('接管失败: ' + (e.response?.data?.msg || e.response?.status || e.message))
      })
    },
  }
}
</script>
