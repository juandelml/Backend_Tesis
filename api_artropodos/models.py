from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
from mongoengine import Document, StringField, DateTimeField, FloatField, ListField, DictField

class UsuarioManager(BaseUserManager):
    def create_user(self, email, username, first_name, last_name, password=None, **extra_fields):
        if not email:
            raise ValueError('El correo electrónico es obligatorio')
        if not username:
            raise ValueError('El nombre de usuario es obligatorio')
        email = self.normalize_email(email)
        user = self.model(
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            **extra_fields
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, first_name, last_name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('rol', 'admin')
        return self.create_user(email, username, first_name, last_name, password, **extra_fields)

class Usuario(AbstractUser):
    ROLES = (
        ('observador', 'Observador'),
        ('admin', 'Administrador'),
    )

    email = models.EmailField(unique=True, verbose_name="Correo electrónico")
    username = models.CharField(max_length=50, unique=True, verbose_name="Nombre de usuario")
    first_name = models.CharField(max_length=100, verbose_name="Nombre")
    last_name = models.CharField(max_length=100, verbose_name="Apellidos")
    institucion = models.CharField(max_length=150, blank=True, default="", verbose_name="Institución")
    rol = models.CharField(max_length=20, choices=ROLES, default='observador', verbose_name="Rol")
    fecha_registro = models.DateTimeField(default=timezone.now, verbose_name="Fecha de registro")

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    objects = UsuarioManager()

    def save(self, *args, **kwargs):
        if self.rol == 'admin':
            self.is_staff = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.email}) - {self.rol}"


class HistorialAvistamiento(Document):
    imagen_ruta = StringField(required=True)
    fecha_hora = DateTimeField(default=timezone.now)
    latitud = FloatField(null=True)
    longitud = FloatField(null=True)
    detecciones = ListField(DictField())
    # Metadatos del usuario que realizó la captura
    usuario_id = StringField(null=True)
    usuario_username = StringField(default='Anónimo')
    usuario_institucion = StringField(null=True)

    meta = {
        'collection': 'historial_avistamientos',
        'ordering': ['-fecha_hora']
    }


