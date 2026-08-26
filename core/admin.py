from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Domain, Topic, Question, AdditionalTopic, UserProfile, MockExamResult, UserProgress

@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'topic', 'lesson_completed', 'quiz_completed', 'quiz_score', 'last_studied')
    list_filter = ('lesson_completed', 'quiz_completed', 'topic__domain', 'last_studied')
    search_fields = ('user__username', 'topic__title')


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'domain')
    list_filter = ('domain',)
    search_fields = ('title', 'lesson_content')

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('topic', 'question_text', 'correct_index')
    list_filter = ('topic',)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'unlock_all_topics')
    list_filter = ('role',)

@admin.register(MockExamResult)
class MockExamResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'date_taken', 'percentage', 'correct_answers')
    list_filter = ('date_taken',)

@admin.register(AdditionalTopic)
class AdditionalTopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at')
    search_fields = ('title', 'content')
    readonly_fields = ('created_at',)
        