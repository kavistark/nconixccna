from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    path('lesson/<int:topic_id>/', views.lesson_view, name='lesson'),
    path('lesson/<int:topic_id>/complete/', views.lesson_complete_view, name='lesson_complete'),
    
    path('quiz/<int:topic_id>/', views.quiz_view, name='quiz'),
    path('quiz/<int:topic_id>/submit/', views.quiz_submit_view, name='quiz_submit'),
    
    path('mock-exam/', views.mock_exam_setup_view, name='mock_exam_setup'),
    path('mock-exam/active/', views.mock_exam_active_view, name='mock_exam_active'),
    path('mock-exam/submit/', views.mock_exam_submit_view, name='mock_exam_submit'),
    
    path('additional-topic/<int:topic_id>/', views.additional_topic_detail_view, name='additional_topic_detail'),
    
    path('tutor/', views.tutor_bot_view, name='tutor_bot'),
    path('tutor/chat/', views.tutor_chat_api, name='tutor_chat_api'),
    
    path('board/send-event/', views.board_send_event_api, name='board_send_event'),
    path('board/history/', views.board_history_api, name='board_history'),
]


