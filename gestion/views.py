from rest_framework import filters, generics, viewsets
from django_filters.rest_framework import DjangoFilterBackend

from .models import Expediente, PerfilUsuario
from .permissions import PermisoExpediente
from .serializers import ExpedienteSerializer, PerfilUsuarioSerializer


class ExpedienteViewSet(viewsets.ModelViewSet):
    serializer_class = ExpedienteSerializer
    permission_classes = [PermisoExpediente]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["colegiatura", "anio_egreso", "semestre_egreso"]
    search_fields = ["nombre", "rut", "profesor_guia"]
    ordering_fields = ["fecha_creacion", "fecha_examen", "nombre", "rut"]

    def get_queryset(self):
        perfil = getattr(self.request.user, "perfil", None)
        if not perfil or not perfil.activo:
            return Expediente.objects.none()
        if perfil.rol == PerfilUsuario.Rol.ESTUDIANTE:
            return Expediente.objects.filter(pk=perfil.expediente_id)
        return Expediente.objects.all()

    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user)


class PerfilActualView(generics.RetrieveAPIView):
    serializer_class = PerfilUsuarioSerializer

    def get_object(self):
        perfil = self.request.user.perfil
        if not perfil.activo:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("La cuenta está desactivada.")
        return perfil
