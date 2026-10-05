import re
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from .models import Usuario

EMAIL_REGEX = r'^[\w\.-]+@[\w\.-]+\.\w+$'

def serializar_usuario(usuario):
    return {
        "id": usuario.id,
        "email": usuario.email,
        "username": usuario.username,
        "nombre": usuario.first_name,
        "apellidos": usuario.last_name,
        "institucion": usuario.institucion or "",
        "rol": usuario.rol,
        "fecha_registro": usuario.fecha_registro.isoformat() if usuario.fecha_registro else None,
        "is_staff": usuario.is_staff,
    }

@api_view(['POST'])
@permission_classes([AllowAny])
def signup_view(request):
    """
    Registro de nuevos usuarios:
    - Nombre, Apellidos, Username, Email, Password obligatorios.
    - Institución opcional.
    - Rol: por defecto 'observador', o 'admin'.
    - Fecha de registro: automática del sistema.
    """
    data = request.data
    email = data.get('email', '').strip().lower()
    username = data.get('username', '').strip()
    nombre = data.get('nombre', data.get('first_name', '')).strip()
    apellidos = data.get('apellidos', data.get('last_name', '')).strip()
    password = data.get('password', '')
    institucion = data.get('institucion', '').strip()
    rol = data.get('rol', 'observador').strip().lower()

    # Validaciones de campos obligatorios
    if not email:
        return Response({"error": "El correo electrónico es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
    if not re.match(EMAIL_REGEX, email):
        return Response({"error": "El formato del correo electrónico no es válido."}, status=status.HTTP_400_BAD_REQUEST)
    if not username:
        return Response({"error": "El nombre de usuario es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
    if not nombre:
        return Response({"error": "El nombre es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
    if not apellidos:
        return Response({"error": "Los apellidos son obligatorios."}, status=status.HTTP_400_BAD_REQUEST)
    if not password or len(password) < 6:
        return Response({"error": "La contraseña debe tener al menos 6 caracteres."}, status=status.HTTP_400_BAD_REQUEST)

    # Validar rol
    if rol not in ['observador', 'admin']:
        rol = 'observador'

    # Validar unicidad
    if Usuario.objects.filter(email__iexact=email).exists():
        return Response({"error": "Ya existe una cuenta registrada con este correo electrónico."}, status=status.HTTP_400_BAD_REQUEST)

    if Usuario.objects.filter(username__iexact=username).exists():
        return Response({"error": "El nombre de usuario ya está en uso. Por favor elige otro."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        usuario = Usuario.objects.create_user(
            email=email,
            username=username,
            first_name=nombre,
            last_name=apellidos,
            password=password,
            institucion=institucion,
            rol=rol
        )

        token, _ = Token.objects.get_or_create(user=usuario)

        return Response({
            "exito": True,
            "mensaje": "Usuario registrado exitosamente.",
            "token": token.key,
            "usuario": serializar_usuario(usuario)
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({"error": f"Error al registrar usuario: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Inicio de sesión únicamente con correo electrónico y contraseña.
    """
    data = request.data
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return Response({"error": "Debes ingresar tu correo y contraseña."}, status=status.HTTP_400_BAD_REQUEST)

    usuario = Usuario.objects.filter(email__iexact=email).first()

    if not usuario or not usuario.check_password(password):
        return Response({"error": "Correo electrónico o contraseña incorrectos."}, status=status.HTTP_400_BAD_REQUEST)

    if not usuario.is_active:
        return Response({"error": "Esta cuenta ha sido desactivada. Contacta al administrador."}, status=status.HTTP_403_FORBIDDEN)

    token, _ = Token.objects.get_or_create(user=usuario)

    return Response({
        "exito": True,
        "mensaje": "Inicio de sesión exitoso.",
        "token": token.key,
        "usuario": serializar_usuario(usuario)
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def perfil_view(request):
    """
    Obtiene los datos del usuario autenticado actual.
    """
    return Response({
        "exito": True,
        "usuario": serializar_usuario(request.user)
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    Cierra la sesión eliminando el token de autenticación.
    """
    try:
        request.user.auth_token.delete()
    except Exception:
        pass
    return Response({"exito": True, "mensaje": "Sesión cerrada correctamente."}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_usuarios_view(request):
    """
    Permite a los administradores listar todos los usuarios registrados.
    """
    if request.user.rol != 'admin' and not request.user.is_staff:
        return Response({"error": "No tienes permisos de administrador para realizar esta acción."}, status=status.HTTP_403_FORBIDDEN)

    usuarios = Usuario.objects.all().order_by('-fecha_registro')
    return Response({
        "exito": True,
        "usuarios": [serializar_usuario(u) for u in usuarios]
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def eliminar_usuario_view(request, user_id):
    """
    Permite a un administrador eliminar a un usuario.
    """
    if request.user.rol != 'admin' and not request.user.is_staff:
        return Response({"error": "No tienes permisos de administrador para eliminar usuarios."}, status=status.HTTP_403_FORBIDDEN)

    try:
        usuario_a_borrar = Usuario.objects.get(id=user_id)
        if usuario_a_borrar.id == request.user.id:
            return Response({"error": "No puedes eliminar tu propia cuenta de administrador."}, status=status.HTTP_400_BAD_REQUEST)

        usuario_a_borrar.delete()
        return Response({"exito": True, "mensaje": "Usuario eliminado correctamente."}, status=status.HTTP_200_OK)
    except Usuario.DoesNotExist:
        return Response({"error": "Usuario no encontrado."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": f"Error al eliminar usuario: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
