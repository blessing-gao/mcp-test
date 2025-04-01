"""
MCP应用序列化器
"""
from rest_framework import serializers

class IntentParameterSerializer(serializers.Serializer):
    """意图参数序列化器"""
    task_id = serializers.CharField(required=False, allow_null=True)
    status = serializers.CharField(required=False, allow_null=True)

class IntentSerializer(serializers.Serializer):
    """意图序列化器"""
    action = serializers.CharField()
    parameters = IntentParameterSerializer(required=False, default={})

class UserMessageSerializer(serializers.Serializer):
    """用户消息序列化器"""
    message = serializers.CharField(required=True)
    user_id = serializers.CharField(required=False, allow_null=True)
    token = serializers.CharField(required=True)
    intent = IntentSerializer(required=False, allow_null=True)

class TaskItemSerializer(serializers.Serializer):
    """任务项序列化器"""
    id = serializers.CharField()
    title = serializers.CharField()
    status = serializers.CharField()
    priority = serializers.CharField(required=False, allow_null=True)
    created_at = serializers.CharField(required=False, allow_null=True)
    due_date = serializers.CharField(required=False, allow_null=True)

class MCPResponseSerializer(serializers.Serializer):
    """MCP响应序列化器"""
    text = serializers.CharField()
    data = serializers.JSONField(required=False, allow_null=True)
