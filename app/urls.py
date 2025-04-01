# app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # MinIO API接口
    path('minio/health/', views.health_check, name='minio_health'),
    path('minio/buckets/', views.list_buckets, name='list_buckets'),
    path('minio/buckets/<str:bucket_name>/objects/', views.list_objects, name='list_objects'),
]