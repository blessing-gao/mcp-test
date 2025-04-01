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