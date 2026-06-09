import requests
import json
import time
import base64

url = 'http://127.0.0.1:8000/api/clasificar/'
ruta_imagen = '/Users/juande/Documents/Tesis Cimat/fotosPrueba/foto_prueba_google.jpg'
ruta_guardado = '/Users/juande/Documents/Tesis Cimat/resultadosPrueba/foto_procesada_google.jpg'
111
print(f"Enviando imagen a {url}...")

# Iniciamos el cronómetro del "Celular"
inicio_peticion = time.time()

try:
    with open(ruta_imagen, 'rb') as archivo_foto:
        archivos = {'imagen': archivo_foto}
        respuesta = requests.post(url, files=archivos)
    
    # Paramos el cronómetro al recibir la respuesta
    tiempo_peticion = round(time.time() - inicio_peticion, 3)
    datos = respuesta.json()
    
    print("\n=== MÉTRICAS DE RENDIMIENTO ===")
    print(f"Tiempo de ida y vuelta (Latencia total): {tiempo_peticion} segundos")
    if "tiempo_servidor_segundos" in datos:
        print(f"Tiempo neto de inferencia IA: {datos['tiempo_servidor_segundos']} segundos")
        
    print("\n=== RESPUESTA DEL SERVIDOR ===")
    
    # Si viene la imagen pintada, la decodificamos y la guardamos
    if "imagen_pintada" in datos:
        img_data = base64.b64decode(datos["imagen_pintada"])
        with open(ruta_guardado, "wb") as f:
            f.write(img_data)
        print(f"📸 ¡Imagen procesada guardada exitosamente en: {ruta_guardado}!")
        
        # Borramos el base64 gigante para que no inunde la consola al imprimir
        del datos["imagen_pintada"]

    print(json.dumps(datos, indent=4, ensure_ascii=False))

except Exception as e:
    print(f"Ocurrió un error: {e}")