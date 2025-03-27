from django.contrib import admin

from .models import Faq, FaqCategory

# i wanted to register them professionally

class FaqCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')
    list_filter = ('name', 'description')
    list_per_page = 10

admin.site.register(FaqCategory, FaqCategoryAdmin)

class FaqAdmin(admin.ModelAdmin):
    list_display = ('question', 'answer', 'category')
    search_fields = ('question', 'answer', 'category')
    list_filter = ('question', 'answer', 'category')
    list_per_page = 10

admin.site.register(Faq, FaqAdmin)



