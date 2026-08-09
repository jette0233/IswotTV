"""
（已弃用）管理后台现在使用独立账密登录，配置在 .env 中：
  ADMIN_USERNAME=admin
  ADMIN_PASSWORD=txj20050707

不再依赖 User.is_admin 字段。
访问 /txjadmin/login 用上述账密获取 token。
"""
print("管理后台已改用独立账密登录，请使用 .env 中的 ADMIN_USERNAME/ADMIN_PASSWORD")
