# app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # 健康检查接口
    path('minio/健康检查/', views.health_check, name='health_check'),
    path('minio/health/', views.health_check, name='health_check_en'),

    # 存储桶操作
    path('minio/存储桶/列表/', views.list_buckets, name='list_buckets'),
    path('minio/buckets/', views.list_buckets, name='list_buckets_en'),
    path('minio/存储桶/创建/', views.create_bucket, name='create_bucket'),
    path('minio/buckets/create/', views.create_bucket, name='create_bucket_en'),

    # 文件操作
    path('minio/存储桶/<str:bucket_name>/文件/', views.list_objects, name='list_objects'),
    path('minio/buckets/<str:bucket_name>/objects/', views.list_objects, name='list_objects_en'),
    path('minio/存储桶/<str:bucket_name>/上传/', views.upload_file, name='upload_file'),
    path('minio/buckets/<str:bucket_name>/upload/', views.upload_file, name='upload_file_en'),
    path('minio/存储桶/<str:bucket_name>/下载/<path:object_name>', views.download_file, name='download_file'),
    path('minio/buckets/<str:bucket_name>/download/<path:object_name>', views.download_file, name='download_file_en'),
    path('minio/存储桶/<str:bucket_name>/删除/<path:object_name>', views.delete_file, name='delete_file'),
    path('minio/buckets/<str:bucket_name>/delete/<path:object_name>', views.delete_file, name='delete_file_en'),
    path('minio/存储桶/<str:bucket_name>/链接/<path:object_name>', views.get_file_url, name='get_file_url'),
    path('minio/buckets/<str:bucket_name>/url/<path:object_name>', views.get_file_url, name='get_file_url_en'),
]