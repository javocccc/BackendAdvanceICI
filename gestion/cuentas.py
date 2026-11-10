from rest_framework.permissions import BasePermission
from .models import PerfilUsuario

class EsAdministradorActivo(BasePermission):
    def has_permission(self, request, view):
        perfil = getattr(request.user, "perfil", None)
        return bool(request.user.is_authenticated and request.user.is_active and perfil
                    and perfil.activo and perfil.rol == PerfilUsuario.Rol.ADMINISTRADOR)
