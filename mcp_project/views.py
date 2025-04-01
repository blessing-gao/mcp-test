# views.py
"""
大模型连接器视图
"""
import logging
import json
from typing import Dict, Any, List
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
import httpx

logger = logging.getLogger('llm_connector')


class LLMMessage:
    """大模型消息类"""

    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def to_dict(self):
        return {
            "role": self.role,
            "content": self.content
        }


class UserQueryView(APIView):
    """处理用户查询的视图"""
    permission_classes = [AllowAny]  # 生产环境中应使用适当的权限

    async def post(self, request, *args, **kwargs):
        """处理POST请求"""
        try:
            # 验证请求数据
            query = request.data.get('query')
            user_id = request.data.get('user_id')
            token = request.data.get('token')

            if not query or not token:
                return Response(
                    {"error": "必须提供查询内容和认证令牌"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 调用LLM API进行意图理解
            llm_response = await self.call_llm_api(query)

            if "error" in llm_response:
                return Response(
                    {"text": f"抱歉，我无法处理您的请求。错误: {llm_response['error']}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # 处理LLM响应，提取动作
            processed_response = await self.process_llm_response(llm_response)

            # 如果需要执行具体操作，调用MCP API
            if processed_response.get("action_needed", False):
                action_type = processed_response.get("action_type")
                action_data = processed_response.get("action_data", {})

                # 调用MCP执行操作
                mcp_response = await self.call_mcp_api(
                    query,
                    user_id,
                    token,
                    action_type,
                    action_data
                )

                if "error" in mcp_response:
                    return Response(
                        {"text": f"抱歉，执行操作时出错: {mcp_response['error']}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

                # 返回MCP处理结果
                return Response({
                    "text": mcp_response.get("text", "操作已完成"),
                    "data": mcp_response.get("data")
                })

            # 如果不需要执行操作，直接返回处理后的LLM响应
            return Response({
                "text": processed_response.get("text", "我理解了您的请求")
            })

        except Exception as e:
            logger.exception(f"处理用户查询时出错: {e}")
            return Response(
                {"text": "抱歉，处理您的请求时出现了技术问题。"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    async def call_llm_api(self, query: str) -> Dict[str, Any]:
        """调用大模型API获取响应"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.LLM_API_KEY}"
        }

        # 构建LLM请求
        request_data = {
            "model": settings.LLM_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": """
                    你是一个任务管理助手，可以帮助用户查询和管理他们的待办任务。
                    如果用户请求查看任务，回复'ACTION:GET_TASKS'。
                    如果用户请求更新任务状态，回复'ACTION:UPDATE_TASK'，并尽可能提取任务ID和新状态。
                    """
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            "temperature": 0.3  # 使用较低的温度以获得更确定性的响应
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.LLM_API_URL,
                    headers=headers,
                    json=request_data,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"调用LLM API失败 {e.response.status_code}: {e}")
            return {"error": f"HTTP错误: {e.response.status_code}"}
        except Exception as e:
            logger.error(f"调用LLM API失败: {e}")
            return {"error": str(e)}

    async def process_llm_response(self, llm_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理LLM的响应，提取操作指令

        这里我们解析大模型的输出，检查是否包含ACTION标记
        """
        try:
            content = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "")

            if "ACTION:GET_TASKS" in content:
                return {
                    "text": "正在查询您的待办任务...",
                    "action_needed": True,
                    "action_type": "get_tasks",
                    "action_data": {}
                }

            elif "ACTION:UPDATE_TASK" in content:
                # 尝试从响应中提取任务ID和状态
                # 这是一个简化的示例，实际实现可能需要更复杂的解析
                task_id = None
                new_status = None

                if "任务ID:" in content:
                    id_part = content.split("任务ID:")[1].split("\n")[0].strip()
                    if id_part.isdigit():
                        task_id = id_part

                if "新状态:" in content:
                    new_status = content.split("新状态:")[1].split("\n")[0].strip()

                return {
                    "text": "正在更新任务状态...",
                    "action_needed": True,
                    "action_type": "update_task_status",
                    "action_data": {
                        "task_id": task_id,
                        "status": new_status
                    }
                }

            # 如果没有检测到操作指令，直接返回内容
            return {
                "text": content,
                "action_needed": False
            }

        except Exception as e:
            logger.error(f"处理LLM响应时出错: {e}")
            return {
                "text": "抱歉，处理您的请求时出现了问题。",
                "action_needed": False
            }

    async def call_mcp_api(self, message: str, user_id: str, token: str, action_type: str = None,
                           action_data: Dict = None) -> Dict[str, Any]:
        """调用MCP API执行操作"""
        headers = {
            "Content-Type": "application/json"
        }

        data = {
            "message": message,
            "user_id": user_id,
            "token": token
        }

        # 如果有具体操作，添加到请求中
        if action_type:
            data["intent"] = {
                "action": action_type,
                "parameters": action_data or {}
            }

        try:
            # MCP API地址
            mcp_api_url = f"{settings.MCP_API_URL}/process/"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    mcp_api_url,
                    headers=headers,
                    json=data,
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"调用MCP API失败: {e}")
            return {"error": str(e)}


class HealthCheckView(APIView):
    """健康检查视图"""
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        """处理GET请求"""
        return Response({"status": "ok"})


# urls.py
"""
大模型连接器URL配置
"""
from django.urls import path
from .views import UserQueryView, HealthCheckView

urlpatterns = [
    path('query/', UserQueryView.as_view(), name='user_query'),
    path('health/', HealthCheckView.as_view(), name='health_check'),
]