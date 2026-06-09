from mongoengine import Document, StringField, DateTimeField, FloatField, ListField, DictField
from django.utils import timezone

class HistorialAvistamiento(Document):
    imagen_ruta = StringField(required=True)
    fecha_hora = DateTimeField(default=timezone.now)
    latitud = FloatField(null=True)
    longitud = FloatField(null=True)
    detecciones = ListField(DictField())

    meta = {
        'collection': 'historial_avistamientos',
        'ordering': ['-fecha_hora']
    }

