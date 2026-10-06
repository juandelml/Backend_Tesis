import os
import cv2
import torch
import numpy as np
from PIL import Image
import torch.nn as nn
from torchvision import models, transforms
from ultralytics import YOLO
import time
import base64
import uuid

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from .models import HistorialAvistamiento

# ==========================================
# 1. CARGA GLOBAL DE MODELOS (Al iniciar servidor)
# ==========================================
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
print(f"Cargando modelos en: {device}")

# Rutas absolutas a tus modelos
RUTA_YOLO = os.path.join(settings.BASE_DIR, 'api_artropodos', 'modelos', 'YOLOv8s_50.pt')
RUTA_MOBILENET = os.path.join(settings.BASE_DIR, 'api_artropodos', 'modelos', 'mejor_mobilenet_exp2.pth')

# A. Cargar YOLOv8s
modelo_yolo = YOLO(RUTA_YOLO)

# B. Cargar MobileNetV3
clases_artropodos = ['Araneae', 'Coleoptera', 'Diptera', 'Hemiptera', 'Hymenoptera', 'Lepidoptera', 'Odonata']
modelo_mobilenet = models.mobilenet_v3_large(weights=None)
num_ftrs = modelo_mobilenet.classifier[3].in_features
modelo_mobilenet.classifier[3] = nn.Linear(num_ftrs, 7)
modelo_mobilenet.load_state_dict(torch.load(RUTA_MOBILENET, map_location=device, weights_only=True))
modelo_mobilenet = modelo_mobilenet.to(device)
modelo_mobilenet.eval() 

# C. Transformación requerida por MobileNet
transformacion_img = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

# ==========================================
# 2. EL ENDPOINT DE INFERENCIA
# ==========================================
@api_view(['POST'])
def clasificar_artropodo(request):
    if 'imagen' not in request.FILES:
        return Response({"error": "No se detectó el archivo 'imagen' en la petición."}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Iniciamos el cronómetro interno del servidor
        inicio_procesamiento = time.time()
        
        imagen_bytes = request.FILES['imagen'].read()
        np_arr = np.frombuffer(imagen_bytes, np.uint8)
        img_cv2 = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        if img_cv2 is None:
            return Response({"error": "Formato de imagen no soportado."}, status=status.HTTP_400_BAD_REQUEST)

        # --- ETAPA 1: DETECCIÓN ---
        resultados_yolo = modelo_yolo(img_cv2, conf=0.5, verbose=False) 
        
        if len(resultados_yolo[0].boxes) == 0:
            return Response({"exito": False, "mensaje": "No se detectó ningún artrópodo."}, status=status.HTTP_200_OK)

        img_pintada = img_cv2.copy()
        detecciones = []

        # --- ETAPA 2: RECORRER TODAS LAS DETECCIONES Y CLASIFICARLAS ---
        for caja in resultados_yolo[0].boxes.data:
            x1, y1, x2, y2 = map(int, caja[:4])
            
            # Validación simple para no procesar cajas fuera de la imagen
            h_img, w_img = img_cv2.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w_img, x2), min(h_img, y2)

            if x1 >= x2 or y1 >= y2:
                continue

            recorte_cv2 = img_cv2[y1:y2, x1:x2]
            recorte_rgb = cv2.cvtColor(recorte_cv2, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(recorte_rgb)

            # Clasificación
            img_tensor = transformacion_img(img_pil).unsqueeze(0).to(device)
            
            with torch.no_grad():
                outputs = modelo_mobilenet(img_tensor)
                probabilidades = torch.nn.functional.softmax(outputs, dim=1)[0]
                confianza_clase, predd = torch.max(probabilidades, 0)
                clase_final = clases_artropodos[predd.item()]
                confianza_porcentaje = round(confianza_clase.item() * 100, 2)
                
            detecciones.append({
                "clase": clase_final,
                "confianza": f"{confianza_porcentaje}%",
                "caja_delimitadora": { "x1": x1, "y1": y1, "x2": x2, "y2": y2 }
            })

            # --- PINTAR ---
            # Configuraciones de diseño
            color_caja = (0, 255, 0)    # Verde
            color_texto = (0, 0, 0)     # Negro (para que resalte sobre el fondo verde)
            escala_fuente = 0.6         # Letra más pequeña
            grosor_fuente = 1           # Letra más fina
            fuente = cv2.FONT_HERSHEY_SIMPLEX
            
            # 1. Dibujamos la caja verde principal
            cv2.rectangle(img_pintada, (x1, y1), (x2, y2), color_caja, 2)
            
            # 2. Preparamos el texto
            etiqueta = f"{clase_final} {confianza_porcentaje}%"
            
            # 3. Calculamos cuánto mide el texto en píxeles para hacerle su fondo
            (ancho_texto, alto_texto), baseline = cv2.getTextSize(etiqueta, fuente, escala_fuente, grosor_fuente)
            
            # 4. Dibujamos el rectángulo de fondo (Relleno) justo arriba de la caja
            cv2.rectangle(img_pintada, (x1, max(0, y1 - alto_texto - 10)), (x1 + ancho_texto + 10, y1), color_caja, cv2.FILLED)
            
            # 5. Escribimos el texto en negro sobre el fondo verde
            cv2.putText(img_pintada, etiqueta, (x1 + 5, max(15, y1 - 5)), fuente, escala_fuente, color_texto, grosor_fuente)

        # Si tras procesar las cajas no hay detecciones válidas, terminar sin guardar nada
        if len(detecciones) == 0:
            return Response({"exito": False, "mensaje": "No se detectó ningún artrópodo en la imagen."}, status=status.HTTP_200_OK)

        # Convertimos la imagen ya con todas las cajas pintadas a Base64
        _, buffer = cv2.imencode('.jpg', img_pintada)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        # 6. Paramos el cronómetro
        tiempo_total_servidor = round((time.time() - inicio_procesamiento) * 1000, 2)

        # --- ETAPA 3: GUARDAR EN MONGODB ---
        try:
            # 1. Guardar la imagen original de forma local para tener la ruta
            archivo_imagen = request.FILES['imagen']
            fs = FileSystemStorage()
            # Generar un nombre único para evitar sobreescribir imágenes
            nombre_unico = f"{uuid.uuid4().hex}_{archivo_imagen.name}"
            nombre_guardado = fs.save(nombre_unico, archivo_imagen)
            ruta_imagen = fs.url(nombre_guardado)
            
            # 2. Extraer latitud y longitud (si vienen)
            lat = request.POST.get('latitud')
            lon = request.POST.get('longitud')
            
            lat_float = float(lat) if lat else None
            lon_float = float(lon) if lon else None

            # 3. Obtener datos del usuario (autenticado por Token o enviado como fallback)
            usuario_id = None
            usuario_username = "Anónimo"
            usuario_institucion = ""

            if request.user and request.user.is_authenticated:
                usuario_id = str(request.user.id)
                usuario_username = request.user.username
                usuario_institucion = request.user.institucion or ""
            elif request.POST.get('usuario_username'):
                usuario_username = request.POST.get('usuario_username')
                usuario_institucion = request.POST.get('usuario_institucion', '')
                usuario_id = request.POST.get('usuario_id')

            # 4. Crear y guardar el documento en MongoDB usando MongoEngine
            historial = HistorialAvistamiento(
                imagen_ruta=ruta_imagen,
                latitud=lat_float,
                longitud=lon_float,
                detecciones=detecciones,
                usuario_id=usuario_id,
                usuario_username=usuario_username,
                usuario_institucion=usuario_institucion
            )
            historial.save()
        except Exception as mongo_e:
            print(f"Error guardando en MongoDB: {str(mongo_e)}")
            # Dependiendo de tu lógica de negocio, puedes decidir fallar o continuar si MongoDB falla.
            # Aquí continuamos con la respuesta para no afectar al usuario de la app.

        url_absoluta = request.build_absolute_uri(ruta_imagen) if 'ruta_imagen' in locals() and ruta_imagen else None
        id_historial = str(historial.id) if 'historial' in locals() and hasattr(historial, 'id') else None
        fecha_historial = (
            historial.fecha_hora.isoformat()
            if 'historial' in locals() and hasattr(historial, 'fecha_hora') and historial.fecha_hora
            else timezone.now().isoformat()
        )

        return Response({
            "exito": True,
            "tiempo_servidor_ms": tiempo_total_servidor,
            "id": id_historial,
            "imagen_url": url_absoluta,
            "fecha_hora": fecha_historial,
            "latitud": lat_float if 'lat_float' in locals() else None,
            "longitud": lon_float if 'lon_float' in locals() else None,
            "detecciones": detecciones,
            "imagen_pintada": img_base64, # Enviamos la imagen en texto con todas las detecciones
            "usuario": usuario_username if 'usuario_username' in locals() and usuario_username else 'Anónimo',
            "institucion": usuario_institucion if 'usuario_institucion' in locals() and usuario_institucion else '',
            "usuario_id": usuario_id if 'usuario_id' in locals() else None
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": f"Error del servidor: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ==========================================
# 3. ENDPOINT DE HISTORIAL
# ==========================================
@api_view(['GET'])
def historial_avistamientos(request):
    """
    Retorna el historial de todos los avistamientos guardados en MongoDB,
    ordenados del más reciente al más antiguo.
    Permite filtrar con ?solo_mios=true si el usuario está autenticado.
    """
    try:
        solo_mios = request.GET.get('solo_mios', 'false').lower() in ['true', '1']
        
        if solo_mios and request.user and request.user.is_authenticated:
            from mongoengine.queryset.visitor import Q
            user_id = str(request.user.id)
            registros = HistorialAvistamiento.objects(
                Q(usuario_id=user_id) | Q(usuario_username=request.user.username)
            )
        else:
            # Recuperamos todos los registros (mongoengine ya los ordena por '-fecha_hora' según models.py)
            registros = HistorialAvistamiento.objects.all()
        
        datos_historial = []
        for registro in registros:
            # Generamos la URL absoluta de la imagen para que Flutter pueda mostrarla
            url_absoluta = request.build_absolute_uri(registro.imagen_ruta) if registro.imagen_ruta else None
            
            datos_historial.append({
                "id": str(registro.id),
                "imagen_url": url_absoluta,
                "fecha_hora": registro.fecha_hora.isoformat() if registro.fecha_hora else None,
                "latitud": registro.latitud,
                "longitud": registro.longitud,
                "detecciones": registro.detecciones,
                "usuario": getattr(registro, 'usuario_username', 'Anónimo') or 'Anónimo',
                "institucion": getattr(registro, 'usuario_institucion', '') or '',
                "usuario_id": getattr(registro, 'usuario_id', None)
            })
            
        return Response(datos_historial, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({"error": f"Error al obtener historial: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# 4. ENDPOINT PARA ELIMINAR AVISTAMIENTO
# ==========================================
@api_view(['DELETE'])
def eliminar_avistamiento(request, id_avistamiento):
    """
    Elimina un avistamiento de MongoDB.
    Los administradores pueden borrar cualquier avistamiento.
    Los observadores solo pueden borrar sus propios avistamientos.
    """
    try:
        from bson import ObjectId
        try:
            obj_id = ObjectId(id_avistamiento)
        except Exception:
            return Response({"error": "ID de avistamiento inválido."}, status=status.HTTP_400_BAD_REQUEST)

        registro = HistorialAvistamiento.objects(id=obj_id).first()
        if not registro:
            return Response({"error": "Avistamiento no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        # Si el usuario está autenticado, verificamos permisos
        if request.user and request.user.is_authenticated:
            es_admin = getattr(request.user, 'rol', '') == 'admin' or request.user.is_staff or request.user.is_superuser
            es_propietario = getattr(registro, 'usuario_id', None) == str(request.user.id)
            if not (es_admin or es_propietario):
                return Response({"error": "No tienes permiso para eliminar este avistamiento."}, status=status.HTTP_403_FORBIDDEN)

        # Borrar archivo local si existe
        if registro.imagen_ruta:
            ruta_relativa = registro.imagen_ruta.replace(settings.MEDIA_URL, '', 1)
            ruta_archivo = os.path.join(settings.MEDIA_ROOT, ruta_relativa)
            if os.path.exists(ruta_archivo):
                try:
                    os.remove(ruta_archivo)
                except Exception:
                    pass

        registro.delete()
        return Response({"exito": True, "mensaje": "Avistamiento eliminado exitosamente."}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": f"Error al eliminar avistamiento: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

