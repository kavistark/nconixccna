import os
import json
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Domain, Topic, Question

class Command(BaseCommand):
    help = 'Loads CCNA syllabus and quiz data from data.json'

    def handle(self, *args, **options):
        json_path = os.path.join(settings.BASE_DIR, 'data.json')
        if not os.path.exists(json_path):
            self.stdout.write(self.style.ERROR(f'data.json not found at {json_path}. Run node convert_data.js first.'))
            return

        with open(json_path, 'r', encoding='utf-8') as f:
            ccna_data = json.load(f)

        self.stdout.write(self.style.SUCCESS(f'Found {len(ccna_data)} topics in data.json. Starting import...'))

        for topic_data in ccna_data:
            topic_id = topic_data['id']
            title = topic_data['title']
            category = topic_data['category']
            objectives = topic_data.get('objectives', [])
            lesson_content = topic_data.get('lesson', '')
            quiz_data = topic_data.get('quiz', [])

            # Get or create the Domain
            domain, created = Domain.objects.get_or_create(name=category)
            if created:
                self.stdout.write(f"Created Domain: {category}")

            # Create or update Topic
            topic, created = Topic.objects.update_or_create(
                id=topic_id,
                defaults={
                    'domain': domain,
                    'title': title,
                    'objectives': objectives,
                    'lesson_content': lesson_content
                }
            )
            
            action = "Created" if created else "Updated"
            self.stdout.write(f"{action} Topic {topic_id}: {title}")

            # Clear existing questions for this topic to avoid duplicates
            Question.objects.filter(topic=topic).delete()

            # Create new questions
            for q in quiz_data:
                Question.objects.create(
                    topic=topic,
                    question_text=q['question'],
                    options=q['options'],
                    correct_index=q['correctIndex'],
                    explanation=q['explanation']
                )
            
            self.stdout.write(f"  -> Imported {len(quiz_data)} questions for Topic {topic_id}")

        self.stdout.write(self.style.SUCCESS('Successfully loaded all CCNA data!'))
