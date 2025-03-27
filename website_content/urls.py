from django.urls import path

from .views import FaqCategoryViewSet, FaqViewSet

urlpatterns = [
    path('faqs/', FaqViewSet.as_view(), name='faqs'),
    path('faq-categories/', FaqCategoryViewSet.as_view(), name='faq-categories'),
]
