"""
主项目URL配置
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/mcp/', include('mcp_app.urls')),
    path('api/llm/', include('llm_connector.urls')),
]