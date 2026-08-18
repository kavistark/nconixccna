from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard_view, name='admin_dashboard'),
    path('student/create/', views.admin_create_student_view, name='admin_create_student'),
    path('student/<int:student_id>/edit/', views.admin_edit_student_view, name='admin_edit_student'),
    path('student/<int:student_id>/delete/', views.admin_delete_student_view, name='admin_delete_student'),
    
    path('additional-topics/', views.admin_additional_topics_list_view, name='admin_additional_topics'),
    path('additional-topics/add/', views.admin_additional_topic_add_view, name='admin_additional_topic_add'),
    path('additional-topics/<int:topic_id>/edit/', views.admin_additional_topic_edit_view, name='admin_additional_topic_edit'),
    path('additional-topics/<int:topic_id>/delete/', views.admin_additional_topic_delete_view, name='admin_additional_topic_delete'),
    
    path('stats/', views.admin_stats_view, name='admin_stats'),
    path('board/', views.admin_board_view, name='admin_board'),
]
