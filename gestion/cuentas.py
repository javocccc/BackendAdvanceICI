from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission
from .models import PerfilUsuario
from .serializers import CuentaSerializer

class EsAdministradorActivo(BasePermission):
    def has_permission(self, request, view):
        perfil = getattr(request.user, "perfil", None)
        return bool(request.user.is_authenticated and request.user.is_active and perfil
                    and perfil.activo and perfil.rol == PerfilUsuario.Rol.ADMINISTRADOR)

class CuentaViewSet(viewsets.ModelViewSet):
    queryset = PerfilUsuario.objects.select_related("usuario", "expediente").all().order_by("nombre", "id")
    serializer_class = CuentaSerializer
    permission_classes = [EsAdministradorActivo]
    filterset_fields = ["rol", "activo"]
    search_fields = ["nombre", "usuario__email"]

    def perform_update(self, serializer):
        perfil = self.get_object()
        if perfil.usuario_id == self.request.user.id:
            rol = serializer.validated_data.get("rol", perfil.rol)
            activo = serializer.validated_data.get("activo", perfil.activo)
            if rol != PerfilUsuario.Rol.ADMINISTRADOR or not activo:
                raise ValidationError("No puede quitarse su propio acceso de Administrador.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.usuario_id == self.request.user.id:
            raise ValidationError("No puede eliminar su propia cuenta.")
        instance.usuario.delete()
