from django.db import models
from django.contrib.auth.models import User

class Domain(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Topic(models.Model):
    # We use explicit id corresponding to the topic ID in original data.js (1-63)
    id = models.IntegerField(primary_key=True)
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name='topics')
    title = models.CharField(max_length=200)
    objectives = models.JSONField(default=list)  # list of strings
    lesson_content = models.TextField()  # markdown

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.id}. {self.title}"

class Question(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    options = models.JSONField(default=list)  # list of strings (4 options)
    correct_index = models.IntegerField()  # 0 to 3
    explanation = models.TextField()

    def __str__(self):
        return f"Q for Topic {self.topic_id}: {self.question_text[:50]}..."

class UserProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress')
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='user_progress')
    lesson_completed = models.BooleanField(default=False)
    quiz_completed = models.BooleanField(default=False)
    quiz_score = models.IntegerField(default=0)  # highest score achieved (0-100)
    last_studied = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'topic')

    def __str__(self):
        return f"{self.user.username} - Topic {self.topic_id} Progress"

class MockExamResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mock_exams')
    date_taken = models.DateTimeField(auto_now_add=True)
    total_questions = models.IntegerField()
    correct_answers = models.IntegerField()
    percentage = models.IntegerField()

    class Meta:
        ordering = ['-date_taken']

    def __str__(self):
        return f"{self.user.username} - Mock Exam {self.percentage}% ({self.date_taken.date()})"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('admin', 'Admin'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    unlock_all_topics = models.BooleanField(default=False)
    allowed_topics = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"{self.user.username} Profile ({self.role})"

    def has_access_to_topic(self, topic_id):
        if self.role == 'admin':
            return True
        if self.unlock_all_topics:
            return True
        try:
            return int(topic_id) in (self.allowed_topics or [])
        except (ValueError, TypeError):
            return False


from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        role = 'admin' if instance.is_staff or instance.is_superuser else 'student'
        UserProfile.objects.get_or_create(user=instance, role=role)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if not hasattr(instance, 'profile'):
        role = 'admin' if instance.is_staff or instance.is_superuser else 'student'
        UserProfile.objects.create(user=instance, role=role)
    else:
        instance.profile.save()


class AdditionalTopic(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField(help_text="Paragraph content of the additional topic (supports markdown)")
    image1 = models.ImageField(upload_to='additional_topics/', blank=True, null=True)
    image2 = models.ImageField(upload_to='additional_topics/', blank=True, null=True)
    image3 = models.ImageField(upload_to='additional_topics/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return self.title


