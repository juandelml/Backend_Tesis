from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from api_artropodos import views, views_auth

urlpatterns = [
    path('admin/', admin.site.urls),

    # Autenticación y Usuarios
    path('api/auth/signup/', views_auth.signup_view, name='auth_signup'),
    path('api/auth/login/', views_auth.login_view, name='auth_login'),
    path('api/auth/perfil/', views_auth.perfil_view, name='auth_perfil'),
    path('api/auth/logout/', views_auth.logout_view, name='auth_logout'),
    path('api/auth/usuarios/', views_auth.listar_usuarios_view, name='auth_usuarios'),
    path('api/auth/usuarios/<int:user_id>/', views_auth.eliminar_usuario_view, name='auth_eliminar_usuario'),

    # Clasificación e Historial
    path('api/clasificar/', views.clasificar_artropodo, name='clasificar_artropodo'),
    path('api/historial/', views.historial_avistamientos, name='historial_avistamientos'),
    path('api/historial/<str:id_avistamiento>/', views.eliminar_avistamiento, name='eliminar_avistamiento'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)