from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse
from django.utils import timezone
from rest_framework import filters, generics, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import Acta, CambioColegiatura, Expediente, PerfilUsuario, RegistroAuditoria
from .permissions import PermisoActa, PermisoExpediente
from .serializers import (
    ActaSerializer, CambioColegiaturaSerializer, ExpedienteSerializer,
    NuevoEstadoColegiaturaSerializer, PerfilUsuarioSerializer, RegistroAuditoriaSerializer,
)
from .serializers import ExpedienteSerializer, PerfilUsuarioSerializer

class ActaViewSet(viewsets.ModelViewSet):
    serializer_class = ActaSerializer
    permission_classes = [PermisoActa]
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ["expediente"]

    def get_queryset(self):
        perfil = getattr(self.request.user, "perfil", None)
        if not perfil or not perfil.activo:
            return Acta.objects.none()
        if perfil.rol == PerfilUsuario.Rol.ESTUDIANTE:
            return Acta.objects.filter(expediente_id=perfil.expediente_id)
        return Acta.objects.all()

    def perform_create(self, serializer):
        acta = serializer.save(cargada_por=self.request.user)
        RegistroAuditoria.objects.create(
            expediente=acta.expediente, usuario=self.request.user, accion="acta", detalles="Acta cargada"
        )

    def perform_update(self, serializer):
        anterior = self.get_object().archivo
        acta = serializer.save()
        if anterior.name != acta.archivo.name:
            anterior.delete(save=False)
        RegistroAuditoria.objects.create(
            expediente=acta.expediente, usuario=self.request.user, accion="acta", detalles="Acta actualizada"
        )

    def perform_destroy(self, instance):
        archivo = instance.archivo
        expediente = instance.expediente
        instance.delete()
        archivo.delete(save=False)
        RegistroAuditoria.objects.create(
            expediente=expediente, usuario=self.request.user, accion="acta", detalles="Acta eliminada"
        )

    @action(detail=True, methods=["get"], url_path="descargar")
    def descargar(self, request, pk=None):
        acta = self.get_object()
        return FileResponse(acta.archivo.open("rb"), as_attachment=True, filename=acta.nombre_original)
    
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
