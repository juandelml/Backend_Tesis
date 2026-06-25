from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from api_artropodos import views

urlpatterns = [
    path('admin/', admin.site.urls),
    # Esta es la ruta HTTP que usará Flutter para clasificar
    path('api/clasificar/', views.clasificar_artropodo, name='clasificar_artropodo'),
    # Ruta para obtener el historial de avistamientos
    path('api/historial/', views.historial_avistamientos, name='historial_avistamientos'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)