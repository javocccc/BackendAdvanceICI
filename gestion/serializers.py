from rest_framework import serializers

from .models import Expediente, PerfilUsuario
from .rut import normalizar_rut


class PerfilUsuarioSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="usuario.email", read_only=True)
    expediente_id = serializers.IntegerField(source="expediente.id", read_only=True)

    class Meta:
        model = PerfilUsuario
        fields = ["id", "email", "nombre", "rol", "activo", "expediente_id"]


class ExpedienteSerializer(serializers.ModelSerializer):
    estudiante = PerfilUsuarioSerializer(source="perfil_estudiante", read_only=True)
    creado_por = serializers.CharField(source="creado_por.username", read_only=True)

    class Meta:
        model = Expediente
        fields = [
            "id", "nombre", "rut", "anio_egreso", "semestre_egreso", "fecha_examen",
            "nota_examen", "profesor_guia", "informante_1", "informante_2",
            "informante_adicional", "colegiatura", "fecha_colegiatura",
            "estudiante", "creado_por", "fecha_creacion", "fecha_actualizacion",
        ]
        read_only_fields = ["colegiatura", "fecha_colegiatura"]

    def validate_rut(self, valor):
        return normalizar_rut(valor)

    def validate(self, attrs):
        # La comisión de examen no puede repetir a un docente en dos puestos.
        campos = ("profesor_guia", "informante_1", "informante_2", "informante_adicional")
        nombres = [attrs.get(campo, getattr(self.instance, campo, "")) for campo in campos]
        presentes = [nombre.strip().casefold() for nombre in nombres if nombre.strip()]
        if len(presentes) != len(set(presentes)):
            raise serializers.ValidationError("Un docente aparece más de una vez en la comisión.")
        return attrs
