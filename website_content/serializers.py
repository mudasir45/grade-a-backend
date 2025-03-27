from rest_framework import serializers

from .models import Faq, FaqCategory


class FaqSerializer(serializers.ModelSerializer):
    class Meta:
        model = Faq 
        fields = '__all__'

class FaqCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FaqCategory
        fields = '__all__'

