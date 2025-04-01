# mcp_app/__init__.py
"""
MCP App
"""

# mcp_app/apps.py
from django.apps import AppConfig

class McpAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mcp_app'

# mcp_app/models.py
"""
MCP应用数据模型
"""
from django.db import models
from django.utils import timezone

class UserRequest(models.Model):
    """用户请求记录模型"""
    user_id = models.CharField(max_length=255, verbose_name="用户ID")
    message = models.TextField(verbose_name="用户消息")
    intent = models.CharField(max_length=100, verbose_name="识别的意图")
    parameters = models.JSONField(default=dict, verbose_name="意图参数")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="创建时间")

    class Meta:
        verbose_name = "用户请求"
        verbose_name_plural = "用户请求"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user_id} - {self.intent} - {self.created_at}"

class APILog(models.Model):
    """API调用日志模型"""
    request = models.ForeignKey(UserRequest, on_delete=models.CASCADE, related_name="api_logs", verbose_name="关联请求")
    endpoint = models.CharField(max_length=255, verbose_name="API端点")
    method = models.CharField(max_length=10, verbose_name="HTTP方法")
    request_data = models.JSONField(default=dict, verbose_name="请求数据")
    response_data = models.JSONField(default=dict, verbose_name="响应数据")
    status_code = models.IntegerField(default=0, verbose_name="状态码")
    success = models.BooleanField(default=False, verbose_name="是否成功")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="创建时间")

    class Meta:
        verbose_name = "API调用日志"
        verbose_name_plural = "API调用日志"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.endpoint} - {self.status_code} - {self.created_at}"

# mcp_app/admin.py
from django.contrib import admin
from .models import UserRequest, APILog

@admin.register(UserRequest)
class UserRequestAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'intent', 'created_at')
    search_fields = ('user_id', 'intent', 'message')
    list_filter = ('intent', 'created_at')
    date_hierarchy = 'created_at'

@admin.register(APILog)
class APILogAdmin(admin.ModelAdmin):
    list_display = ('endpoint', 'method', 'status_code', 'success', 'created_at')
    list_filter = ('success', 'method', 'status_code', 'created_at')
    search_fields = ('endpoint',)
    date_hierarchy = 'created_at'

# mcp_app/views.py
"""
MCP应用视图
"""
import logging
import json
from typing import Dict, Any
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .models import UserRequest
from .serializers import UserMessageSerializer, MCPResponseSerializer
from mcp_project.services.intent_service import IntentService
from mcp_project.services.processor_service import ProcessorService
from mcp_project.services.response_service import ResponseService

logger = logging.getLogger('mcp_app')


class ProcessMessageView(APIView):
    """处理用户消息的视图"""
    permission_classes = [AllowAny]  # 生产环境中应使用适当的权限

    async def post(self, request, *args, **kwargs):
        """处理POST请求"""
        try:
            # 验证请求数据
            serializer = UserMessageSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {"error": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 从请求中获取数据
            message = serializer.validated_data.get('message')
            token = serializer.validated_data.get('token')
            user_id = serializer.validated_data.get('user_id', 'anonymous')
            intent_data = serializer.validated_data.get('intent')

            # 创建用户请求记录
            if intent_data:
                user_request = UserRequest.objects.create(
                    user_id=user_id,
                    message=message,
                    intent=intent_data.get('action', 'unknown'),
                    parameters=intent_data.get('parameters', {})
                )
            else:
                # 如果请求中没有指定意图，使用意图识别服务解析
                intent = IntentService.parse_intent(message)
                user_request = UserRequest.objects.create(
                    user_id=user_id,
                    message=message,
                    intent=intent.get('action', 'unknown'),
                    parameters=intent.get('parameters', {})
                )

            # 提取JWT令牌信息
            token_info = ProcessorService.extract_token_info(token)
            # 获取企业ID，没有则使用默认值
            organ_id = token_info.get('organ_id', settings.DEFAULT_ORGAN_ID)

            # 使用意图处理服务处理请求
            if intent_data:
                # 如果请求中指定了意图，直接处理
                intent_result = await ProcessorService.process_intent(
                    intent_data, token, organ_id, user_request
                )
            else:
                # 使用解析的意图
                intent_result = await ProcessorService.process_intent(
                    intent, token, organ_id, user_request
                )

            # 格式化响应
            response_data = ResponseService.format_response(intent_result)

            # 验证响应格式
            response_serializer = MCPResponseSerializer(data=response_data)
            if not response_serializer.is_valid():
                logger.error(f"响应格式验证失败: {response_serializer.errors}")
                return Response(
                    {"error": "内部服务器错误：响应格式无效"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            return Response(response_data)

        except Exception as e:
            logger.exception(f"处理消息时出错: {e}")
            return Response(
                {"text": "抱歉，处理您的请求时出现了技术问题。"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HealthCheckView(APIView):
    """健康检查视图"""
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        """处理GET请求"""
        return Response({"status": "ok"})

# mcp_app/urls.py
"""
MCP应用URL配置
"""
from django.urls import path
from .views import ProcessMessageView, HealthCheckView

urlpatterns = [
    path('process/', ProcessMessageView.as_view(), name='process_message'),
    path('health/', HealthCheckView.as_view(), name='health_check'),
]