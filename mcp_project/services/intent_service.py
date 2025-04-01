# services/intent_service.py
"""
意图识别服务
"""
import logging
from typing import Dict, Any

logger = logging.getLogger('mcp_app')


class IntentService:
    """识别用户意图的服务"""

    @staticmethod
    def parse_intent(message: str) -> Dict[str, Any]:
        """
        从用户消息中解析意图
        简单实现版本 - 在生产环境中可能需要更复杂的NLU或调用LLM API
        """
        message = message.lower()

        # 基本意图识别
        if any(keyword in message for keyword in ["查看待办", "我的任务", "待办事项", "任务列表"]):
            return {
                "action": "get_tasks",
                "parameters": {}
            }

        if any(keyword in message for keyword in ["更新状态", "完成任务", "修改任务"]):
            # 提取任务ID和状态 (简化版)
            # 实际应用中应使用更复杂的实体提取
            task_id = None
            new_status = None

            # 简单的规则匹配
            if "任务" in message and "改为" in message:
                parts = message.split("任务")
                if len(parts) > 1:
                    id_part = parts[1].split("改为")[0].strip()
                    if id_part.isdigit():
                        task_id = id_part

                status_parts = message.split("改为")
                if len(status_parts) > 1:
                    new_status = status_parts[1].strip()

            return {
                "action": "update_task_status",
                "parameters": {
                    "task_id": task_id,
                    "status": new_status
                }
            }

        # 默认意图
        return {
            "action": "unknown",
            "parameters": {}
        }


# services/backend_service.py
"""
后端API调用服务
"""
import logging
import httpx
from typing import Dict, Any
from django.conf import settings
from ..models import APILog, UserRequest

logger = logging.getLogger('mcp_app')


class BackendService:
    """后端API调用服务"""

    @staticmethod
    async def call_backend_api(
            endpoint: str,
            method: str = "GET",
            headers: Dict = None,
            data: Dict = None,
            user_request: UserRequest = None
    ) -> Dict[str, Any]:
        """调用后端API"""
        if headers is None:
            headers = {}

        url = f"{settings.BACKEND_API_BASE}{endpoint}"

        api_log = APILog(
            request=user_request,
            endpoint=endpoint,
            method=method,
            request_data=data or {}
        )

        async with httpx.AsyncClient() as client:
            try:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers, params=data, timeout=10.0)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=data, timeout=10.0)
                elif method.upper() == "PUT":
                    response = await client.put(url, headers=headers, json=data, timeout=10.0)
                else:
                    raise ValueError(f"不支持的HTTP方法: {method}")

                # 记录响应信息
                api_log.status_code = response.status_code

                response.raise_for_status()
                response_data = response.json()

                api_log.response_data = response_data
                api_log.success = True
                api_log.save()

                return response_data
            except httpx.HTTPStatusError as e:
                logger.error(f"API调用失败 {e.response.status_code}: {e}")

                api_log.status_code = e.response.status_code
                api_log.response_data = {"error": str(e)}
                api_log.success = False
                api_log.save()

                return {"error": str(e), "status_code": e.response.status_code}
            except Exception as e:
                logger.error(f"API调用异常: {e}")

                api_log.status_code = 500
                api_log.response_data = {"error": str(e)}
                api_log.success = False
                api_log.save()

                return {"error": str(e)}


# services/processor_service.py
"""
意图处理服务
"""
import logging
import jwt
from typing import Dict, Any, Optional
from django.conf import settings
from .backend_service import BackendService
from ..models import UserRequest

logger = logging.getLogger('mcp_app')


class ProcessorService:
    """处理用户意图的服务"""

    @staticmethod
    def extract_token_info(token: str) -> Dict[str, Any]:
        """从JWT令牌中提取信息"""
        try:
            # 注意：这里不验证令牌，只是解析它
            decoded = jwt.decode(token, options={"verify_signature": False})
            return decoded
        except Exception as e:
            logger.error(f"解析令牌失败: {e}")
            return {}

    @staticmethod
    async def process_intent(
            intent: Dict[str, Any],
            token: str,
            organ_id: str,
            user_request: Optional[UserRequest] = None
    ) -> Dict[str, Any]:
        """处理已识别的意图"""
        headers = {
            "Authorization": token,
            "Amp-Organ-Id": organ_id,
            "Accept": "application/json"
        }

        action = intent.get("action", "unknown")

        if action == "get_tasks":
            # 查询待办任务
            endpoint = "/api/track-issues/track/issues/workbench/issues"
            params = {"issuesTypeId": "96"}  # 从示例中获取的参数

            result = await BackendService.call_backend_api(
                endpoint, "GET", headers, params, user_request
            )
            return {
                "action": "get_tasks",
                "success": "error" not in result,
                "data": result,
                "message": "成功获取待办任务" if "error" not in result else f"获取任务失败: {result.get('error')}"
            }

        elif action == "update_task_status":
            # 更新任务状态 (需要根据实际API调整)
            task_id = intent.get("parameters", {}).get("task_id")
            new_status = intent.get("parameters", {}).get("status")

            if not task_id or not new_status:
                return {
                    "action": "update_task_status",
                    "success": False,
                    "message": "更新任务需要提供任务ID和新状态"
                }

            # 假设更新状态的API端点
            endpoint = f"/api/track-issues/track/issues/{task_id}/status"
            data = {"status": new_status}

            result = await BackendService.call_backend_api(
                endpoint, "PUT", headers, data, user_request
            )
            return {
                "action": "update_task_status",
                "success": "error" not in result,
                "data": result,
                "message": f"成功将任务 {task_id} 状态更新为 {new_status}"
                if "error" not in result else f"更新任务状态失败: {result.get('error')}"
            }

        else:
            return {
                "action": "unknown",
                "success": False,
                "message": "我不理解您的请求，请尝试查询待办任务或更新任务状态"
            }


# services/response_service.py
"""
响应格式化服务
"""
import logging
from typing import Dict, Any

logger = logging.getLogger('mcp_app')


class ResponseService:
    """格式化响应的服务"""

    @staticmethod
    def format_response(intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """格式化返回给用户的响应"""
        action = intent_result.get("action", "unknown")

        if action == "get_tasks":
            if intent_result.get("success", False):
                tasks_data = intent_result.get("data", {}).get("data", [])

                if not tasks_data:
                    return {
                        "text": "您目前没有待办任务。",
                        "data": {"tasks": []}
                    }

                # 格式化任务列表
                tasks = []
                for task in tasks_data:
                    tasks.append({
                        "id": task.get("id", "未知ID"),
                        "title": task.get("title", "未命名任务"),
                        "status": task.get("status", "未知状态"),
                        "priority": task.get("priority", "普通"),
                        "created_at": task.get("createdAt", "未知时间"),
                        "due_date": task.get("dueDate", "无截止日期")
                    })

                # 创建文本响应
                task_list_text = "以下是您的待办任务:\n\n"
                for i, task in enumerate(tasks, 1):
                    task_list_text += f"{i}. {task['title']} - 状态: {task['status']}"
                    if task['due_date']:
                        task_list_text += f", 截止日期: {task['due_date']}"
                    task_list_text += "\n"

                return {
                    "text": task_list_text,
                    "data": {"tasks": tasks}
                }
            else:
                return {
                    "text": f"获取待办任务失败: {intent_result.get('message', '未知错误')}",
                    "data": None
                }

        elif action == "update_task_status":
            if intent_result.get("success", False):
                return {
                    "text": intent_result.get("message", "任务状态已更新。"),
                    "data": intent_result.get("data")
                }
            else:
                return {
                    "text": f"更新任务状态失败: {intent_result.get('message', '未知错误')}",
                    "data": None
                }

        else:
            return {
                "text": "我不太理解您的请求。您可以尝试查询待办任务或更新任务状态。",
                "data": None
            }