from django.shortcuts import render

# Create your views here.
# 1. 首先，在app/views.py中添加MinIO相关视图

from django.http import JsonResponse
from minio import Minio
from minio.error import S3Error
import json

# MinIO配置
MINIO_ENDPOINT = 'www.shenben.club:9000'
MINIO_ACCESS_KEY = 'test'
MINIO_SECRET_KEY = '123456'
MINIO_SECURE = False  # 如果使用HTTPS，设为True


def get_minio_client():
    """获取MinIO客户端连接"""
    return Minio(
        endpoint=MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )


def list_buckets(request):
    """获取所有bucket列表"""
    try:
        # 创建MinIO客户端
        minio_client = get_minio_client()

        # 获取所有bucket
        buckets = minio_client.list_buckets()

        # 将bucket信息转换为JSON友好的格式
        buckets_data = [
            {
                'name': bucket.name,
                'creation_date': bucket.creation_date.isoformat()
            }
            for bucket in buckets
        ]

        return JsonResponse({
            'status': 'success',
            'data': buckets_data
        })

    except S3Error as e:
        return JsonResponse({
            'status': 'error',
            'message': f'S3 Error: {str(e)}'
        }, status=500)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


def list_objects(request, bucket_name):
    """获取指定bucket下的对象列表"""
    try:
        # 创建MinIO客户端
        minio_client = get_minio_client()

        # 检查bucket是否存在
        if not minio_client.bucket_exists(bucket_name):
            return JsonResponse({
                'status': 'error',
                'message': f'Bucket {bucket_name} does not exist'
            }, status=404)

        # 获取bucket中的对象
        objects = minio_client.list_objects(bucket_name, recursive=True)

        # 将对象信息转换为JSON友好的格式
        objects_data = [
            {
                'name': obj.object_name,
                'size': obj.size,
                'last_modified': obj.last_modified.isoformat() if obj.last_modified else None,
                'etag': obj.etag,
                'content_type': obj.content_type
            }
            for obj in objects
        ]

        return JsonResponse({
            'status': 'success',
            'bucket': bucket_name,
            'data': objects_data
        })

    except S3Error as e:
        return JsonResponse({
            'status': 'error',
            'message': f'S3 Error: {str(e)}'
        }, status=500)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


# 添加一个健康检查接口
def health_check(request):
    """MinIO服务健康检查"""
    try:
        minio_client = get_minio_client()
        # 尝试列出buckets来检查连接
        minio_client.list_buckets()
        return JsonResponse({'status': 'healthy'})
    except Exception as e:
        return JsonResponse({'status': 'unhealthy', 'error': str(e)}, status=500)