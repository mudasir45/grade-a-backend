from django.shortcuts import render
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Faq, FaqCategory
from .serializers import FaqCategorySerializer, FaqSerializer


class FaqCategoryViewSet(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        categories = FaqCategory.objects.all()
        serializer = FaqCategorySerializer(categories, many=True)
        return Response(serializer.data)
    
class FaqViewSet(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        faqs = Faq.objects.all()
        serializer = FaqSerializer(faqs, many=True)
        return Response(serializer.data)






