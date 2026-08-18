from .models import AdditionalTopic

def additional_topics(request):
    return {
        'additional_topics': AdditionalTopic.objects.all().order_by('created_at')
    }
