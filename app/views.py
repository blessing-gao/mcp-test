# app/views.py
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from minio import Minio
from minio.error import S3Error
import json
import io
import os
from datetime import timedelta

# MinIO配置
MINIO_ENDPOINT = 'shenben.club:9000'
MINIO_ACCESS_KEY = 'test'
MINIO_SECRET_KEY = 'Ab123456'
MINIO_SECURE = False  # 如果使用HTTPS，设为True


def get_minio_client():
    """获取MinIO客户端连接"""
    return Minio(
        endpoint=MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
        http_client = None  # 让MinIO自动创建HTTP客户端
    )


def health_check(request):
    """MinIO服务健康检查"""
    try:
        minio_client = get_minio_client()
        # 尝试列出buckets来检查连接
        minio_client.list_buckets()
        return JsonResponse({'状态': '正常', 'message': 'MinIO服务连接正常'})
    except Exception as e:
        return JsonResponse({'状态': '异常', 'message': f'连接错误: {str(e)}'}, status=500)


def list_buckets(request):
    """获取所有存储桶列表"""
    try:
        # 创建MinIO客户端
        minio_client = get_minio_client()

        # 获取所有bucket
        buckets = minio_client.list_buckets()

        # 将bucket信息转换为JSON友好的格式
        buckets_data = [
            {
                '名称': bucket.name,
                '创建时间': bucket.creation_date.isoformat()
            }
            for bucket in buckets
        ]

        return JsonResponse({
            '状态': '成功',
            '存储桶列表': buckets_data
        })

    except S3Error as e:
        return JsonResponse({
            '状态': '错误',
            '消息': f'S3错误: {str(e)}'
        }, status=500)

    except Exception as e:
        return JsonResponse({
            '状态': '错误',
            '消息': f'系统错误: {str(e)}'
        }, status=500)


def list_objects(request, bucket_name):
    """获取指定存储桶下的对象列表"""
    try:
        # 获取前缀参数（可选，用于目录导航）
        prefix = request.GET.get('prefix', '')

        # 创建MinIO客户端
        minio_client = get_minio_client()

        # 检查bucket是否存在
        if not minio_client.bucket_exists(bucket_name):
            return JsonResponse({
                '状态': '错误',
                '消息': f'存储桶 {bucket_name} 不存在'
            }, status=404)

        # 获取bucket中的对象
        objects = minio_client.list_objects(bucket_name, prefix=prefix, recursive=False)

        # 将对象信息转换为JSON友好的格式
        files_data = []
        folders_data = set()

        for obj in objects:
            # 处理文件夹逻辑
            if '/' in obj.object_name[len(prefix):]:
                # 这是一个子目录中的文件
                folder_name = obj.object_name[len(prefix):].split('/')[0] + '/'
                folders_data.add(folder_name)
            else:
                # 这是一个文件
                files_data.append({
                    '名称': obj.object_name,
                    '大小(字节)': obj.size,
                    '修改时间': obj.last_modified.isoformat() if obj.last_modified else None,
                    '类型': obj.content_type or '未知'
                })

        # 转换文件夹集合为列表
        folders_list = [{'名称': folder, '类型': '文件夹'} for folder in folders_data]

        return JsonResponse({
            '状态': '成功',
            '存储桶': bucket_name,
            '当前目录': prefix,
            '文件夹': folders_list,
            '文件': files_data
        })

    except S3Error as e:
        return JsonResponse({
            '状态': '错误',
            '消息': f'S3错误: {str(e)}'
        }, status=500)

    except Exception as e:
        return JsonResponse({
            '状态': '错误',
            '消息': f'系统错误: {str(e)}'
        }, status=500)


@csrf_exempt
def create_bucket(request):
    """创建新的存储桶"""
    if request.method != 'POST':
        return JsonResponse({'状态': '错误', '消息': '只支持POST请求'}, status=405)

    try:
        data = json.loads(request.body)
        bucket_name = data.get('bucket_name')

        if not bucket_name:
            return JsonResponse({'状态': '错误', '消息': '必须提供存储桶名称'}, status=400)

        # 创建MinIO客户端
        minio_client = get_minio_client()

        # 检查bucket是否已存在
        if minio_client.bucket_exists(bucket_name):
            return JsonResponse({
                '状态': '错误',
                '消息': f'存储桶 {bucket_name} 已存在'
            }, status=409)

        # 创建bucket
        minio_client.make_bucket(bucket_name)

        return JsonResponse({
            '状态': '成功',
            '消息': f'存储桶 {bucket_name} 创建成功'
        })

    except S3Error as e:
        return JsonResponse({
            '状态': '错误',
            '消息': f'S3错误: {str(e)}'
        }, status=500)

    except Exception as e:
        return JsonResponse({
            '状态': '错误',
            '消息': f'系统错误: {str(e)}'
        }, status=500)


@csrf_exempt
def upload_file(request, bucket_name):
    """上传文件到指定存储桶"""
    if request.method != 'POST':
        return JsonResponse({'状态': '错误', '消息': '只支持POST请求'}, status=405)

    try:
        # 检查是否有文件上传
        if 'file' not in request.FILES:
            return JsonResponse({'状态': '错误', '消息': '没有提供文件'}, status=400)

        uploaded_file = request.FILES['file']
        # 获取可选的对象名称参数，如果未提供则使用上传的文件名
        object_name = request.POST.get('object_name', uploaded_file.name)
        # 获取可选的前缀（子目录）
        prefix = request.POST.get('prefix', '')
        if prefix and not prefix.endswith('/'):
            prefix += '/'

        full_object_name = prefix + object_name

        # 创建MinIO客户端
        minio_client = get_minio_client()

        # 检查bucket是否存在
        if not minio_client.bucket_exists(bucket_name):
            return JsonResponse({
                '状态': '错误',
                '消息': f'存储桶 {bucket_name} 不存在'
            }, status=404)

        # 上传文件
        file_data = uploaded_file.read()
        file_size = len(file_data)
        content_type = uploaded_file.content_type or 'application/octet-stream'

        # 使用put_object上传
        minio_client.put_object(
            bucket_name,
            full_object_name,
            io.BytesIO(file_data),
            file_size,
            content_type=content_type
        )

        return JsonResponse({
            '状态': '成功',
            '消息': f'文件已上传',
            '存储桶': bucket_name,
            '文件路径': full_object_name,
            '文件大小': file_size,
            '文件类型': content_type
        })

    except S3Error as e:
        return JsonResponse({
            '状态': '错误',
            '消息': f'S3错误: {str(e)}'
        }, status=500)

    except Exception as e:
        return JsonResponse({
            '状态': '错误',
            '消息': f'系统错误: {str(e)}'
        }, status=500)


def download_file(request, bucket_name, object_name):
    """下载指定存储桶中的文件"""
    try:
        # 创建MinIO客户端
        minio_client = get_minio_client()

        # 检查bucket是否存在
        if not minio_client.bucket_exists(bucket_name):
            return JsonResponse({
                '状态': '错误',
                '消息': f'存储桶 {bucket_name} 不存在'
            }, status=404)

        # 尝试获取对象的统计信息，如果不存在会抛出异常
        try:
            stat = minio_client.stat_object(bucket_name, object_name)
        except S3Error as e:
            if e.code == 'NoSuchKey':
                return JsonResponse({
                    '状态': '错误',
                    '消息': f'文件 {object_name} 不存在'
                }, status=404)
            raise

        # 获取对象数据
        response = minio_client.get_object(bucket_name, object_name)

        # 设置响应头
        http_response = HttpResponse(
            response.read(),
            content_type=stat.content_type
        )

        # 设置内容处理方式，提供文件名
        filename = os.path.basename(object_name)
        http_response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return http_response

    except S3Error as e:
        return JsonResponse({
            '状态': '错误',
            '消息': f'S3错误: {str(e)}'
        }, status=500)

    except Exception as e:
        return JsonResponse({
            '状态': '错误',
            '消息': f'系统错误: {str(e)}'
        }, status=500)


@csrf_exempt
def delete_file(request, bucket_name, object_name):
    """删除指定存储桶中的文件"""
    if request.method != 'DELETE':
        return JsonResponse({'状态': '错误', '消息': '只支持DELETE请求'}, status=405)

    try:
        # 创建MinIO客户端
        minio_client = get_minio_client()

        # 检查bucket是否存在
        if not minio_client.bucket_exists(bucket_name):
            return JsonResponse({
                '状态': '错误',
                '消息': f'存储桶 {bucket_name} 不存在'
            }, status=404)

        # 删除对象
        minio_client.remove_object(bucket_name, object_name)

        return JsonResponse({
            '状态': '成功',
            '消息': f'文件 {object_name} 已从存储桶 {bucket_name} 中删除'
        })

    except S3Error as e:
        return JsonResponse({
            '状态': '错误',
            '消息': f'S3错误: {str(e)}'
        }, status=500)

    except Exception as e:
        return JsonResponse({
            '状态': '错误',
            '消息': f'系统错误: {str(e)}'
        }, status=500)


def get_file_url(request, bucket_name, object_name):
    """获取文件的临时访问URL"""
    try:
        # 获取过期时间参数（默认7天）
        expires = int(request.GET.get('expires', 7 * 24 * 60 * 60))

        # 创建MinIO客户端
        minio_client = get_minio_client()

        # 检查bucket是否存在
        if not minio_client.bucket_exists(bucket_name):
            return JsonResponse({
                '状态': '错误',
                '消息': f'存储桶 {bucket_name} 不存在'
            }, status=404)

        # 尝试获取对象的统计信息，如果不存在会抛出异常
        try:
            minio_client.stat_object(bucket_name, object_name)
        except S3Error as e:
            if e.code == 'NoSuchKey':
                return JsonResponse({
                    '状态': '错误',
                    '消息': f'文件 {object_name} 不存在'
                }, status=404)
            raise

        # 生成临时URL
        url = minio_client.presigned_get_object(
            bucket_name,
            object_name,
            expires=timedelta(seconds=expires)
        )

        return JsonResponse({
            '状态': '成功',
            '存储桶': bucket_name,
            '文件': object_name,
            '链接': url,
            '过期时间(秒)': expires
        })

    except S3Error as e:
        return JsonResponse({
            '状态': '错误',
            '消息': f'S3错误: {str(e)}'
        }, status=500)

    except Exception as e:
        return JsonResponse({
            '状态': '错误',
            '消息': f'系统错误: {str(e)}'
        }, status=500)