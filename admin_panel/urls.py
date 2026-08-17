from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard_view, name='admin_dashboard'),
    path('student/create/', views.admin_create_student_view, name='admin_create_student'),
    path('student/<int:student_id>/edit/', views.admin_edit_student_view, name='admin_edit_student'),
    path('student/<int:student_id>/delete/', views.admin_delete_student_view, name='admin_delete_student'),
    
    path('stats/', views.admin_stats_view, name='admin_stats'),
    path('board/', views.admin_board_view, name='admin_board'),
]
